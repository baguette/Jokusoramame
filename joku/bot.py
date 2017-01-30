"""
Main bot class.
"""
import asyncio
import os
import sys
import traceback
from collections import OrderedDict
import time
import random

import discord
import itertools
import logbook
import logging

from discord import Message
from discord.ext import commands
from discord.ext.commands import Bot, CommandInvokeError, CheckFailure, MissingRequiredArgument, CommandOnCooldown
from discord.gateway import DiscordWebSocket, ReconnectWebSocket, ResumeWebSocket
from discord.state import ConnectionState
from logbook.compat import redirect_logging
from logbook import StreamHandler

from joku.rdblog import RdbLogAdapter
from joku.utils import paginate_large_message
from rethinkdb import ReqlDriverError

from joku.redis import RedisAdapter
from joku.rethink import RethinkAdapter

from joku import manager

try:
    import yaml
except ImportError:
    import ruamel.yaml as yaml

redirect_logging()

StreamHandler(sys.stderr).push_application()


class Jokusoramame(Bot):
    def __init__(self, config: dict, *args, **kwargs):
        """
        Creates a new instance of the bot.

        :param config: The config to create this with.

        :param manager: The bot manager to use.
        :param state: The type of state to use. This can either be the vanilla ConnectionState, or a modified subclass.
        """

        # Get the shard ID.
        shard_id = kwargs.get("shard_id", 0)

        self.manager = kwargs.get("manager")  # type: manager.SingleLoopManager

        self.config = config

        # Logging stuff
        self.logger = logbook.Logger("Jokusoramame:Shard-{}".format(shard_id))
        self.logger.level = logbook.INFO

        logging.root.setLevel(logging.INFO)

        # Call init.
        super().__init__(command_prefix=self.get_command_prefix, *args, **kwargs)

        # Override ConnectionState.
        self.connection = kwargs.get("state", ConnectionState) \
            (dispatch=self.dispatch, chunker=self._chunker,
             syncer=self._syncer, http=self.http, loop=self.loop)

        self.app_id = ""
        self.owner_id = ""

        self.startup_time = time.time()

        self.rethinkdb = RethinkAdapter(self)
        self.rdblog = RdbLogAdapter(self)

        self.redis = RedisAdapter(self)

        # Re-assign commands and extensions.
        self.commands = OrderedDict()
        self.extensions = OrderedDict()
        self.cogs = OrderedDict()

        self._rotator_task = None  # type: asyncio.Task
        self._avatar_rotator = None  # type: asyncio.Task

        # Our own task.
        # We can use this to kill ourselves by running `self.own_task.cancel()`.
        self.own_task = None  # type: asyncio.Task

    # Utility functions.
    def get_member(self, id: str):
        """
        Gets a member from all members.
        """
        return discord.utils.get(self.get_all_members(), id=id)

    @staticmethod
    async def get_command_prefix(self: 'Jokusoramame', message: discord.Message):
        if self.config.get("developer_mode", False):
            # Use `jd!` prefix.
            return "jd!"

        if message.guild.id == 110373943822540800:
            # Don't conflict in dbots
            return ["j" + s for s in "?^&$}#~:"]
        return ["j" + s for s in "!?^&$}#~:"]

    async def rotate_game_text(self):
        for i in itertools.cycle(self.config.get("game_rotation", [])):
            await self.change_presence(
                game=discord.Game(name=i), status=discord.Status.online
            )
            await asyncio.sleep(15)

    async def on_command_error(self, exception, context: 'Context'):
        """
        Handles command errors.
        """
        if isinstance(exception, CommandInvokeError):
            # Regular error.
            await context.channel.send("\U0001f6ab This kills the bot (An error has happened "
                                       "and has been logged.)")
            lines = traceback.format_exception(type(exception),
                                               exception.__cause__, exception.__cause__.__traceback__)
            self.logger.error(''.join(lines))

            # Log to the error channel.
            error_channel_id = str(self.config.get("log_channels", {}).get("error_channel", ""))
            error_channel = self.manager.get_channel(error_channel_id)

            if not error_channel:
                self.logger.error("Could not find error channel!")
            else:
                fmt = "Server: {}\nChannel: {}\nCommand: {}\n\n{}".format(context.message.server.name,
                                                                          context.message.channel.name,
                                                                          context.invoked_with,
                                                                          ''.join(lines))
                await context.channel.send(fmt, use_codeblocks=True)
            return

        # Switch based on isinstance.
        if isinstance(exception, CheckFailure):
            channel = context.message.channel
            await context.channel.send("\U0001f6ab Check failed: {}".format(' '.join(exception.args)))

        elif isinstance(exception, MissingRequiredArgument):
            await context.channel.send("\U0001f6ab Error: {}".format(' '.join(exception.args)))

        elif isinstance(exception, CommandOnCooldown):
            await context.channel.send("\U0001f6ab Command is on cooldown. Retry after {} "
                                       "seconds.".format(round(exception.retry_after, 1)))

    async def on_ready(self):
        self.logger.info("Loaded Jokusoramame, logged in as {}#{}.".format(self.user.name, self.user.discriminator))
        self.logger.info("Guilds: {}".format(len(self.guilds)))
        self.logger.info("Users: {}".format(self.manager.unique_member_count))

        app_info = await self.application_info()
        self.app_id = app_info.id
        self.owner_id = app_info.owner.id

        self.logger.info("I am owned by {}#{} ({}).".format(app_info.owner.name, app_info.owner.discriminator,
                                                            self.owner_id))
        self.logger.info("Invite link: {}".format(discord.utils.oauth_url(self.app_id)))

        try:
            await self.rethinkdb.connect(**self.config.get("rethinkdb", {}))
            data = self.config.get("rethinkdb", {}).copy()
            data["db"] = "joku_logs"
            await self.rdblog.connect(**data)
        except ReqlDriverError:
            self.logger.error("Unable to connect to RethinkDB!")
            traceback.print_exc()
            await self.logout()
            return

        try:
            await self.redis.connect(**self.config.get("redis", {}))
        except ConnectionRefusedError:
            self.logger.error("Unable to connect to Redis!")
            traceback.print_exc()
            await self.logout()
            return

        for cog in self.config.get("autoload", []):
            try:
                self.load_extension(cog)
            except Exception as e:
                self.logger.error("Failed to load cog {}!".format(cog))
                self.logger.exception()
            else:
                self.logger.info("Loaded cog {}.".format(cog))

        self.logger.info("Loaded {} cogs.".format(len(self.cogs)))
        self.logger.info("Running with {} commands.".format(len(self.commands)))

        for name, cog in self.cogs.items():
            if hasattr(cog, "ready"):
                self.loop.create_task(cog.ready())

        if self._rotator_task is not None:
            self._rotator_task.cancel()
            try:
                self._rotator_task.result()
            except Exception:
                self.logger.exception()

        self._rotator_task = self.loop.create_task(self.rotate_game_text())

        new_time = time.time() - self.startup_time

        self.logger.info("Bot ready in {} seconds.".format(new_time))

    async def on_message(self, message: Message):
        self.logger.info("Recieved message: {message.content} "
                         "from {message.author.display_name} ({message.author.name}){bot}"
                         .format(message=message, bot=" [BOT]" if message.author.bot else ""))
        self.logger.info(" On channel: #{message.channel.name}".format(message=message))

        if message.guild is not None:
            self.logger.info(" On server: {} ({})".format(message.guild.name, message.guild.id))

        # Check if an ignore rule exists for that channel.
        if self.rethinkdb.connection is None:
            return

        if await self.rethinkdb.is_channel_ignored(message.channel, type_="commands"):
            return

        await super().on_message(message)

    async def on_message_edit(self, before: discord.Message, message: discord.Message):
        if before.content == message.content:
            pass

        await self.on_message(message)

    def run(self):
        token = self.config["bot_token"]
        super().run(token)

    async def login(self, *args, **kwargs):
        token = self.config["bot_token"]
        return await super().login(token)

    async def connect(self):
        self.ws = await DiscordWebSocket.from_client(self)

        while not self.is_closed:
            try:
                await self.ws.poll_event()
            except (ReconnectWebSocket, ResumeWebSocket) as e:
                resume = type(e) is ResumeWebSocket
                self.logger.info('Got ' + type(e).__name__)
                self.ws = await DiscordWebSocket.from_client(self, resume=resume)
            except discord.ConnectionClosed as e:
                await self.close()
                try:
                    await self.rethinkdb.connection.close()
                except Exception:
                    pass

                try:
                    await self.rdblog.connection.close()
                except Exception:
                    pass
                if e.code != 1000:
                    raise

    def die(self):
        """
        Kills all tasks the bot is running.
        """
        self.loop.stop()
        all_tasks = asyncio.gather(*asyncio.Task.all_tasks(), loop=self.loop)
        all_tasks.cancel()

        # Get rid of the exceptions.
        all_tasks.exception()


class Context(commands.Context):
    def __init__(self, *args, **kwargs):
        self._bot = None
        super().__init__(*args, **kwargs)

    @property
    def bot(self) -> Jokusoramame:
        return self._bot

    @bot.setter
    def bot(self, i):
        self._bot = i

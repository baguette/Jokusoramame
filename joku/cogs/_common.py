import random
from collections import OrderedDict

import aiohttp

from joku.core.bot import Jokusoramame


class _CogMeta(type):
    def __prepare__(*args, **kwargs):
        # Use an OrderedDict for the class body.
        return OrderedDict()


class Cog(metaclass=_CogMeta):
    def __init__(self, bot: Jokusoramame):
        self._bot = bot

        self.logger = self.bot.logger

        # A cog-local session that can be used.
        self.session = aiohttp.ClientSession()

        # A RNG that can be used by each cog.
        self.rng = random.SystemRandom()

    def __unload(self):
        self.session.close()

    @property
    def bot(self) -> 'Jokusoramame':
        """
        :return: The bot instance associated with this cog.
        """
        return self._bot

    @classmethod
    def setup(cls, bot: Jokusoramame):
        bot.add_cog(cls(bot))

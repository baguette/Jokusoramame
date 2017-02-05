from sqlalchemy import Column, BigInteger, Integer, DateTime, func, String, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """
    A user object in the database.
    """
    __tablename__ = "user"

    #: The ID of the user.
    #: This is their snowflake ID.
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=False,
                unique=True)

    #: The XP points of the user.
    xp = Column(Integer, nullable=False, default=0)

    #: The level of the user.
    #: This is automatically calculated.
    level = Column(Integer, nullable=False, default=1)

    #: The money of the user.
    money = Column(Integer, nullable=False, default=200)

    #: The last modified time of the user.
    last_modified = Column(DateTime(), server_default=func.now())

    #: The inventory for this user.
    inventory = relationship("UserInventoryItem")

    def __repr__(self):
        return "<User id={} xp={} money={}>".format(self.id, self.xp, self.money)

    __str__ = __repr__


class UserInventoryItem(Base):
    """
    Represents an item in a user's inventory.
    """
    __tablename__ = "user_inv_item"

    #: The ID for this inventory item.
    id = Column(Integer, primary_key=True, autoincrement=True)

    #: The user ID for this inventory item.
    user_id = Column(BigInteger, ForeignKey('user.id'))

    #: The item ID for this inventory item.
    #: Used internally.
    item_id = Column(Integer, autoincrement=False, nullable=False)

    #: The count for this inventory item.
    count = Column(Integer, autoincrement=False, nullable=False)


class Guild(Base):
    """
    A guild object in the database.
    """
    __tablename__ = "guild"

    #: The ID of the guild.
    id = Column(BigInteger, primary_key=True, nullable=False, autoincrement=False,
                unique=True)

    #: A relationship to the rolestates.
    rolestates = relationship("RoleState", backref="guild")

    #: A relationship to the settings.
    settings = relationship("Setting", backref="guild")

    #: A relationship to the event settings.
    event_settings = relationship("EventSetting", backref="guild")

    #: A relationship to the tags.
    tags = relationship("Tag", backref="guild")

    #: An array of roleme role IDs this guild can have.
    roleme_roles = Column(ARRAY(BigInteger), nullable=True, default=[])


class Tag(Base):
    """
    Represents a tag in the database.
    """
    __tablename__ = "tag"

    #: The ID of the tag.
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False,
                unique=True)

    #: The guild ID of this tag.
    guild_id = Column(BigInteger, ForeignKey("guild.id"))

    #: The user ID of this tag.
    user_id = Column(BigInteger, ForeignKey("user.id"))
    user = relationship("User", backref="tags")

    #: The name of the tag.
    name = Column(String, nullable=False, unique=False, index=True)

    #: Is this tag global?
    global_ = Column(Boolean, default=False, nullable=False)

    #: The tag content.
    content = Column(String, unique=False, nullable=False)

    #: The last modified date for this tag.
    last_modified = Column(DateTime, default=func.now())


class UserColour(Base):
    """
    Stores the colour state for a user.
    """
    __tablename__ = "user_colour"

    #: The ID of this colour mapping.
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)

    #: The user ID that is represented by this colour.
    user_id = Column(BigInteger, ForeignKey("user.id"), nullable=False)
    user = relationship("User", backref="colours")

    #: The guild ID that is represented by this colour.
    guild_id = Column(BigInteger, ForeignKey("guild.id"), nullable=False)
    guild = relationship("Guild", backref="colours")

    #: The role ID that this usercolour uses.
    role_id = Column(BigInteger, nullable=False, unique=True)


class RoleState(Base):
    """
    Represents the role state of a user.
    """
    __tablename__ = "rolestate"

    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)

    #: The user this rolestate is for.
    user_id = Column(BigInteger, ForeignKey('user.id'))
    user = relationship('User')

    #: The guild ID this rolestate is for.
    guild_id = Column(BigInteger, ForeignKey("guild.id"), nullable=False)

    #: The array of role IDs this rolestate contains.
    roles = Column(ARRAY(BigInteger), nullable=True)

    #: The nickname for this rolestate.
    nick = Column(String, nullable=True)

    def __repr__(self):
        return "<RoleState user_id={} guild_id={} nick='{}' roles={}>".format(self.user_id, self.guild_id,
                                                                              self.nick, self.roles)

    __str__ = __repr__


class Setting(Base):
    """
    A setting object in the database.
    """
    __tablename__ = "setting"

    #: The ID of the setting.
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)

    #: The name of the setting.
    name = Column(String, nullable=False, unique=False)

    #: The value of the setting.
    value = Column(JSONB, nullable=False)

    #: The guild ID this setting is in.
    guild_id = Column(BigInteger, ForeignKey("guild.id"), unique=False, nullable=False)


class EventSetting(Base):
    """
    Represents a special setting for event listeners.
    """
    __tablename__ = "event_setting"

    #: The ID of this event setting.
    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)

    #: The guild ID of this event setting.
    guild_id = Column(BigInteger, ForeignKey("guild.id"))

    #: Is this setting enabled?
    enabled = Column(Boolean, nullable=False, default=False)

    #: The event this setting is for.
    event = Column(String)

    #: The message that this setting contains.
    message = Column(String, unique=False, nullable=True)

    #: The event channel that this setting is for.
    channel_id = Column(BigInteger, unique=False, nullable=False)

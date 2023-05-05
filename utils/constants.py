import os
import enum

EMBED_COLOURS = [
    # blues (deep -> light)
    0x00001B,
    0x001034,
    0x00294D,
    0x194266,
    0x325B7F,
    # yellows (deep -> light)
    0xAA7300,
    0xC38C08,
    0xDCA521,
    0xF5BE3A,
    0xFFD753,
]

TOKEN = os.getenv("DISCORD_TOKEN")

SCRAP_METAL = "<:ScrapMetal:1102208993407021086>"
COPPER = "<:Copper:1102223921778016309>"
CURRENCY_EMOJIS = {"scrap_metal": SCRAP_METAL, "copper": COPPER}
COPPER_SCRAP_RATE = 500_000

DEVS_SERVER_ID = 919223073054539858
CHANGELOG_CHANNEL_ID = 1020660847321808930


class Enum(enum.Enum):
    """An enum that supports searching values and converting itself to a `dict`."""

    @classmethod
    def try_value(cls, value):
        try:
            return cls(value)
        except:
            return value

    @classmethod
    def to_dict(cls):
        """Returns a `dict` containing each attribute, with its name as the key and value as value."""
        return {i.name: i.value for i in cls}


class IntEnum(Enum):
    """An enum that supports comparing and hashing as an int."""

    def __int__(self):
        return self.value


class InventoryType(IntEnum):
    backpack = 0
    chest = 1
    vault = 2


class ItemType(IntEnum):
    tool = 0
    collectable = 1
    power_up = 2
    sellable = 3
    bundle = 4


class ItemRarity(IntEnum):
    common = 0
    uncommon = 1
    rare = 2
    epic = 3
    legendary = 4
    godly = 5


MAZE_DIRECTIONS = ["⬆️", "⬅️", "⬇️", "➡️"]

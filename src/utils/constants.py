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


class EmbedColour:
    """A list of preset colours to be used in embeds"""

    INFO = BLUE = 0x7FB2F0  # light blue
    SUCCESS = GREEN = 0x88E08C  # light green
    FAIL = RED = 0xFF8F8F  # light red
    WARNING = YELLOW = 0xFFC87D  # light orange
    DEFAULT = GREY = 0x282B30  # light grey


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
        except ValueError:
            return value

    @classmethod
    def to_dict(cls):
        """Returns a `dict` containing each attribute, with its name as the key and value as value. The name will be automatically converted to lowercase."""
        return {i.name.lower(): i.value for i in cls}


class IntEnum(Enum):
    """An enum that supports comparing and hashing as an int."""

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return self.name.lower()


class InventoryType(IntEnum):
    BACKPACK = 0
    CHEST = 1
    VAULT = 2


class ItemType(IntEnum):
    FOOD = 1
    RESOURCE = 2
    COLLECTIBLE = 3
    BATTLEGEAR = 4
    DECOR = 5
    BUNDLE = 6
    ANIMAL = 7


class ItemRarity(IntEnum):
    COMMON = 0
    UNCOMMON = 1
    RARE = 2
    EPIC = 3
    LEGENDARY = 4
    GODLY = 5


MAZE_DIRECTIONS = ["⬆️", "⬅️", "⬇️", "➡️"]

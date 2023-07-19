import os
import enum


TOKEN = os.getenv("DISCORD_TOKEN")

SCRAP_METAL = "<:ScrapMetal:1102208993407021086>"
COPPER = "<:Copper:1102223921778016309>"
CURRENCY_EMOJIS = {"scrap_metal": SCRAP_METAL, "copper": COPPER}
COPPER_SCRAP_RATE = 500_000

DEVS_SERVER_ID = 919223073054539858
LOG_CHANNEL_ID = 988046548309016586

ITEM_OTHER_ATTR = {"food_value_min": int, "food_value_max": int, "battlegear_type": str, "armour_protection": int}


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


class IntEnum(Enum, enum.IntEnum):
    """An enum that supports comparing and hashing as an int."""

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return self.name.lower()


class EmbedColour(IntEnum):
    """A list of preset colours to be used in embeds"""

    INFO = 0x3498DB  # light blue
    SUCCESS = 0x88E08C  # light green
    FAIL = 0xFF8F8F  # light red
    WARNING = 0xFFC87D  # light orange
    DEFAULT = 0x282B30  # light grey


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

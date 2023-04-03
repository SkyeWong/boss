import os

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

DEVS_SERVER_ID = 919223073054539858
CHANGELOG_CHANNEL_ID = 1020660847321808930

INV_TYPES = {"backpack": 0, "chest": 1, "vault": 2}  # TODO: use `enum.Enum` for this.
ITEM_TYPES = {
    "tool": 0,
    "collectable": 1,
    "power-up": 2,
    "sellable": 3,
    "bundle": 4,
}  # TODO: use `enum.Enum` for this.
RARITIES = {  # TODO: use `enum.Enum` for this.
    "common": 0,
    "uncommon": 1,
    "rare": 2,
    "epic": 3,
    "legendary": 4,
    "godly": 5,
}
CROP_TYPES = [
    [
        "Carrots",
        [
            "<:carrot_1:1018835890019254292>",
            "<:carrot_2:1018835891806027776>",
            "<:carrot_3:1018835893672493076>",
        ],
    ],
    [
        "Wheats",
        [
            "<:wheat_1:1021073899997380619>",
            "<:wheat_2:1021073901914165349>",
            "<:wheat_3:1021073905030529084>",
        ],
    ],
    ["Potatos", ["🟠", "🟧", "🥔"]],
    [
        "Cabbages",
        [
            "<:cabbage_1:1018850735439482890>",
            "<:cabbage_2:1018850737037516800>",
            "<:cabbage_3:1018850738748788746>",
        ],
    ],
]

MAZE_DIRECTIONS = ["⬆️", "⬅️", "⬇️", "➡️"]

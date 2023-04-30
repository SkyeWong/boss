# nextcord
from nextcord.ext import commands
from nextcord import Embed, Interaction
from nextcord.ui import View, Button
import nextcord

# constants
from utils import constants

# inbuilt modules
import math
import random


def roundup(number, round_to):
    return number if number % round_to == 0 else number + round_to - number % round_to


def rounddown(number, round_to):
    return number if number % round_to == 0 else number - number % round_to


def delete_field(embed: Embed, field_name: str):
    for i in range(len(embed.fields)):
        field = embed.fields[i]
        if field.name == field_name:
            embed.remove_field(i)
    return embed


def check_if_it_is_skye(interaction: Interaction):
    return interaction.user.id == 806334528230129695

def check_if_not_dev_guild(*args, **kwargs):
    return args[1].guild.id != constants.DEVS_SERVER_ID

def text_to_num(text: str):
    text = text.lower()
    text = text.split()
    gold = 0
    for i in text:
        d = {
            "k": 1000,  # thousands
            "m": 1000000,  # millions
            "b": 1000000000,  # billions
        }
        i = i.lower()
        if not isinstance(i, str):
            # Non-strings are bad are missing data in poster's submission
            raise TextToNumException(
                f"text_to_num() must be passed str, not {i.__class__.__qualname__}"
            )
        elif i.isnumeric():
            gold += int(i)
        elif i[-1] in d:
            # separate out the K, M, or B
            num, magnitude = i[:-1], i[-1]
            try:
                # if this succeeds, you have your (first) float
                num = float(num)
            except ValueError:
                raise TextToNumException(
                    f"text_to_num() received a non-number prefix before {magnitude}"
                )
            gold += num * d[magnitude]
        else:
            raise TextToNumException(f"text_to_num() is passed an incorrect magnitude.")
    return math.floor(gold)


def sec_to_txt(seconds):
    units = {"d": 3600 * 24, "h": 3600, "m": 60, "s": 1}

    time_txt = ""

    for unit, seconds_of_unit in units.items():
        time_txt += f"{seconds // seconds_of_unit}{unit} "
        seconds %= seconds_of_unit

    return time_txt


def get_mapping(interaction: Interaction, bot: commands.Bot):
    mapping = {}

    for cog_name, cog in bot.cogs.items():
        commands = []
        for application_cmd in cog.application_commands:
            cmd_in_guild = False
            if isinstance(application_cmd, nextcord.SlashApplicationCommand):
                if (
                    application_cmd.is_global
                    or interaction.guild_id in application_cmd.guild_ids
                ):
                    cmd_in_guild = True
                if cmd_in_guild:
                    commands.append(application_cmd)
        if len(commands) != 0:
            mapping[cog_name] = (cog, commands)
    return mapping


def get_error_message():
    embed = Embed()
    embed.title = "An error occurred. Try again in a few seconds."
    embed.description = ">>> If this continues to happen, please report it in our [server](https://discord.gg/SPtMSrCTAS 'BOSS Server')."
    embed.colour = random.choice(constants.EMBED_COLOURS)
    view = View()
    button = Button(label="Join server", url="https://discord.gg/tsTRMqEMFH")
    view.add_item(button)
    return embed, view


def get_item_embed(item, owned_quantity: dict[str, int] | int = None):
    embed = Embed()
    embed.colour = random.choice(constants.EMBED_COLOURS)
    embed.title = item["name"]

    description = ""
    for i in item["description"].splitlines():
        description += f"> _{i}_\n"

    embed.description = description

    if not owned_quantity:  # `owned_quantity` is 0/ empty dict
        embed.description += f"\nYou own **0**"

    elif isinstance(owned_quantity, int):
        embed.description += f"\nYou own **{owned_quantity}**"

    elif (
        isinstance(owned_quantity, dict) and owned_quantity
    ):  # make sure the dict is not empty
        embed.description += f" \nYou own"
        for inv_type, quantity in owned_quantity.items():
            embed.description += f"\n` - ` **{quantity}** in your {inv_type}"

    prices = {
        "buy": item["buy_price"],
        "sell": item["sell_price"],
        "trade": item["trade_price"],
    }

    prices_txt = ""
    for k, price in prices.items():
        if not price or price == 0:
            prices_txt += f"`{k.capitalize()}`: Unknown\n"
        else:
            prices_txt += f"`{k.capitalize()}`: ◎ {int(price):,}\n"
    embed.add_field(name="Prices", value=prices_txt, inline=False)
    
    item_rarity = [i.name for i in constants.ItemRarity if i.value == item["rarity"]][0]
    embed.add_field(
        name="Rarity",
        value=item_rarity.replace("_", " ").capitalize(),
        inline=True,
    )

    item_type = [i.name for i in constants.ItemType if i.value == item["type"]][0]
    embed.add_field(
        name="Type",
        value=item_type.replace("_", " ").capitalize(),
        inline=True,
    )
    embed.set_thumbnail(url=f"https://cdn.discordapp.com/emojis/{item['emoji_id']}.png")
    return embed


def format_with_link(text: str):
    """Formats a text with its markdown link form: \[text](link)"""
    return f"[`{text}`](https://boss-bot.onrender.com/)"


class TextEmbed(Embed):
    
    """A `nextcord.Embed` with the description set as `text`."""
    
    def __init__(self, text: str):
        super().__init__(description=text)


class BossException(Exception):
    """Boss raises this exception when it is misused, or a user-input is incorrect."""

    def __init__(self, text=None, *args: object) -> None:
        super().__init__(*args)
        self.text = text


class CommandNotFound(BossException):
    pass


class MoveItemException(BossException):
    pass


class TextToNumException(BossException):
    pass


class CommandCheckException(BossException):
    """
    Boss raises this exception as an internal error (will be caught) that is found in the command_check function.
    This happens due to unusual activities that the user has been doing.
    """

    pass


class DatabaseReconnect(CommandCheckException):
    pass


class NewPlayer(CommandCheckException):
    pass


class DisabledCommand(CommandCheckException):
    pass


class PlayerNotExist(BossException):
    pass


class ComponentLabelTooLong(BossException):
    pass

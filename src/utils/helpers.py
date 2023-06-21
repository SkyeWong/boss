# nextcord
from nextcord.ext import commands
from nextcord import Embed, Interaction, BaseApplicationCommand, CallbackWrapper
from nextcord.ui import View, Button
import nextcord

# constants
from utils import constants
from utils.constants import SCRAP_METAL, COPPER, EmbedColour
from utils.postgres_db import Database

# inbuilt modules
import math
import random
from datetime import datetime
from typing import Literal, Optional, Union


def roundup(number: int, round_to: int) -> int:
    return number if number % round_to == 0 else number + round_to - number % round_to


def rounddown(number: int, round_to: int) -> int:
    return number if number % round_to == 0 else number - number % round_to


def check_if_not_dev_guild(*args, **kwargs) -> bool:
    return args[1].guild.id != constants.DEVS_SERVER_ID


def get_formatted_time() -> str:
    """Returns the current time in the format "DD <month> YY HH:MM"."""
    return datetime.now().strftime("%d %B %Y %H:%M")


def text_to_num(text: str) -> int:
    """Converts a text representation of a number into the actual number. Note that the decimals will be dropped.

    Args:
        text (str): The text to convert

    Raises:
        TextToNumException: a invalid number is passed.

    Returns:
        res: The converted number.
    """
    # lower the strings and remove commas and whitespace
    text = text.lower()
    text = text.replace(" ", "")
    text = text.replace(",", "")
    d = {
        "k": 1_000,  # thousands
        "m": 1_000_000,  # millions
        "b": 1_000_000_000,  # billions
        "t": 1_000_000_000_000,  # trillions
    }

    text = text.split()
    res = 0
    for i in text:
        i = i.lower()
        if not isinstance(i, str):
            # Non-strings are bad are missing data in poster's submission
            raise TextToNumException(f"text_to_num() must be passed str, not {i.__class__.__qualname__}")
        elif i.isnumeric():
            res += int(i)
        elif i[-1] in d:
            # separate out the K, M, or B
            num, magnitude = i[:-1], i[-1]
            try:
                # if this succeeds, you have your (first) float
                num = float(num)
            except ValueError:
                raise TextToNumException(f"text_to_num() received a non-number prefix before {magnitude}")
            res += num * d[magnitude]
        else:
            raise TextToNumException(f"text_to_num() is passed an incorrect magnitude.")
    return math.floor(res)


def sec_to_txt(seconds: int) -> str:
    """
    Converts a duration in seconds to a human-readable string.

    Args:
        `seconds`: A non-negative integer representing the duration in seconds.

    Returns:
        A string representing the duration in a human-readable format.
        The format is "Xd Yh Zm Ts", where X, Y, Z, and T are non-negative integers
        representing the number of days, hours, minutes, and seconds respectively.
        The units are abbreviated as follows: "d" for days, "h" for hours,
        "m" for minutes, and "s" for seconds.
    """
    units = {"d": 3600 * 24, "h": 3600, "m": 60, "s": 1}

    time_txt = ""

    for unit, seconds_of_unit in units.items():
        time_txt += f"{seconds // seconds_of_unit}{unit} "
        seconds %= seconds_of_unit

    return time_txt


def command_info(
    long_help: Optional[str] = None,
    notes: Optional[list[str]] = None,
    examples: Optional[dict[str, str]] = None,
    **kwargs,
):
    """Adds additional information to a command, which can be displayed in /help."""

    class AddCommandInfo(CallbackWrapper):
        def modify(self, app_cmd: BaseApplicationCommand) -> None:
            app_cmd.long_help = long_help
            app_cmd.notes = notes
            app_cmd.examples = examples
            for k, v in kwargs.items():
                setattr(app_cmd, k, v)

    def wrapper(func):
        return AddCommandInfo(func)

    return wrapper


def work_in_progress(dev_guild_only: bool = True):
    """Marks a command as work in progress, so it would display a message when used.

    Args:
        dev_guild_only (bool, optional): make the command available only in the dev server. Defaults to True.
    """

    class WorkInProgressCommand(CallbackWrapper):
        def modify(self, app_cmd: BaseApplicationCommand) -> None:
            app_cmd.original_callback = self.callback

            async def callback(*args, **kwargs):
                if args[1].guild_id == constants.DEVS_SERVER_ID and dev_guild_only:
                    await app_cmd.original_callback(*args, **kwargs)
                else:
                    await args[1].send(embed=TextEmbed("This command is work in progress. Check back later maybe?"))

            app_cmd.callback = callback

    def wrapper(func):
        return WorkInProgressCommand(func)

    return wrapper


def get_mapping(interaction: Interaction, bot: commands.Bot = None) -> dict:
    """
    Returns a dictionary mapping each cog in the bot to its associated application commands.

    Args:
        `interaction`: A `nextcord.Interaction` object representing the user interaction.
        `bot`: A `commands.Bot` object representing the Discord bot, which defaults to `interaction.client`.

    Returns:
        A `dict` mapping each cog in the bot to a tuple containing the cog object
        and a list of application commands associated with that cog.

        >>> {
        ...     cog_name: (cog, cog_commands)
        ... }

        The application commands are filtered based on whether they are global or
        specific to the server where the interaction occurred.
    """
    mapping = {}
    cmd_in_server = lambda cmd: cmd.is_global or interaction.guild_id in cmd.guild_ids
    if bot is None:
        bot = interaction.client
    for cog_name, cog in bot.cogs.items():
        commands = []
        for cmd in cog.application_commands:
            if isinstance(cmd, nextcord.BaseApplicationCommand):
                if cmd_in_server(cmd):
                    commands.append(cmd)
            elif isinstance(cmd, nextcord.SlashApplicationSubcommand):
                if cmd_in_server(cmd.parent_cmd):
                    commands.append(cmd)
        if len(commands) != 0:
            mapping[cog_name] = (cog, commands)
    return mapping


def get_error_message():
    embed = Embed()
    embed.title = "An error occurred. Try again in a few seconds."
    embed.description = ">>> If this continues to happen, please report it in our [server](https://discord.gg/SPtMSrCTAS 'BOSS Server')."
    embed.colour = constants.EmbedColour.FAIL
    view = View()
    button = Button(label="Join server", url="https://discord.gg/tsTRMqEMFH")
    view.add_item(button)
    return embed, view


def get_item_embed(item, owned_quantity: dict[str, int] | int = None):
    embed = Embed()
    embed.colour = constants.EmbedColour.INFO
    embed.title = item["name"]

    description = ""
    for i in item["description"].splitlines():
        description += f"> _{i}_\n"

    embed.description = description

    if not owned_quantity:  # `owned_quantity` is 0/ empty dict
        embed.description += f"\nYou own **0**"

    elif isinstance(owned_quantity, int):
        embed.description += f"\nYou own **{owned_quantity}**"

    elif isinstance(owned_quantity, dict) and owned_quantity:  # make sure the dict is not empty
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
            prices_txt += f"`{k.capitalize()}`: {SCRAP_METAL} {int(price):,}\n"
    embed.add_field(name="Prices", value=prices_txt, inline=False)

    item_rarity = constants.ItemRarity(item["rarity"])
    item_type = constants.ItemType(item["type"])
    embed.set_thumbnail(url=f"https://cdn.discordapp.com/emojis/{item['emoji_id']}.png")
    embed.set_footer(text=f"{item_rarity} {item_type}".replace("_", " ").title())
    return embed


def format_with_link(text: str):
    """Formats a text with its markdown link form: \[text](link)"""
    return f"[`{text}`](https://boss-bot.onrender.com/)"


class TextEmbed(Embed):
    """A `nextcord.Embed` with the description set as `text`."""

    def __init__(self, text: str, colour: int = EmbedColour.DEFAULT):
        super().__init__(description=text, colour=colour)


class BossItem:
    def __init__(
        self,
        item_id: int,
        quantity: Optional[int] = 1,
        name: Optional[str] = None,
        emoji: Optional[str] = None,
    ) -> None:
        self.item_id = item_id
        self.quantity = quantity
        self._name = name
        self._emoji = emoji

    async def get_name(self, db: Database):
        """Retrieves the name of the item from the database, if not already cached."""
        if self._name is None:
            self._name, self._emoji = await db.fetchrow(
                """
                SELECT name, CONCAT('<:', emoji_name, ':', emoji_id, '>') AS emoji
                FROM utility.items
                WHERE item_id = $1
                """,
                self.item_id,
            )
        return self._name

    async def get_emoji(self, db: Database):
        """Retrieves the emoji representation of the item from the database, if not already cached."""
        if self._emoji is None:
            self._name, self._emoji = await db.fetchrow(
                """
                SELECT name, CONCAT('<:', emoji_name, ':', emoji_id, '>') AS emoji
                FROM utility.items
                WHERE item_id = $1
                """,
                self.item_id,
            )
        return self._emoji

    def __eq__(self, other):
        """Check if the `item_id`s of 2 BossItem instances are the same, or the `item_id` is equal to a `int`."""
        if isinstance(other, BossItem):
            return self.item_id == other.item_id
        if isinstance(other, int):
            return self.item_id == other
        raise NotImplementedError

    def __mul__(self, other):
        """
        Multiply the quantity of this `BossItem` by a scalar value.

        Args:
            other (int or float): The scalar value to multiply the quantity by.

        Raises:
            NotImplementedError: If the `other` argument is not an instance of
                either the int or float classes.

        Returns:
            BossItem: A new BossItem instance with a quantity equal to the current quantity multiplied by the scalar value.
        """
        if not isinstance(other, (int, float)):
            raise NotImplementedError(f"`other` must be type int or float, not {other.__class__}")
        return self.__class__(self.item_id, round(self.quantity * other), self._name, self._emoji)

    def __repr__(self):
        return f"BossItem(item_id={self.item_id}, quantity={self.quantity}, name={self._name!r}, emoji={self._emoji!r})"


class BossPrice:
    def __init__(
        self,
        price: Union[int, str],
        currency_type: Literal["scrap_metal", "copper"] = "scrap_metal",
    ) -> None:
        if currency_type not in ("scrap_metal", "copper"):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")
        self.currency_type = currency_type

        if isinstance(price, str):
            self.price = text_to_num(price)
        else:
            self.price = price

    @classmethod
    def from_range(
        cls,
        min_price: Union[int, str],
        max_price: Union[int, str],
        currency_type: Literal["scrap_metal", "copper"] = "scrap_metal",
    ) -> "BossPrice":
        """Creates a new BossPrice instance with a random price value within a range.

        Args:
            min_price (int or str): The minimum price value, either as an integer or a string.
            max_price (int or str): The maximum price value, either as an integer or a string.
            type (str, optional): The type of currency, either "scrap_metal" or "copper". Defaults to "scrap_metal".

        Raises:
            ValueError: If the `type` argument is not "scrap_metal" or "copper".
            ValueError: If the maximum price is smaller than the minimum price

        Returns:
            BossPrice: A new BossPrice instance with a price value randomly chosen within the specified range.
        """
        if currency_type not in ("scrap_metal", "copper"):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")

        if isinstance(min_price, str):
            min_price = text_to_num(min_price)
        if isinstance(max_price, str):
            max_price = text_to_num(max_price)

        if max_price < min_price:
            raise ValueError("The max price should be larger than min price.")

        return cls(random.randint(min_price, max_price), currency_type)

    @classmethod
    def from_unit_price(
        cls,
        unit_price: int,
        quantity: int,
        rand_factor: float,
        currency_type: Literal["scrap_metal", "copper"] = "scrap_metal",
    ) -> "BossPrice":
        """
        Create a new BossPrice instance based on a unit price, quantity, and random factor.

        Args:
            unit_price (int): The unit price of the item.
            quantity (int): The quantity of items being traded.
            rand_factor (float): A random factor between 0.8 and 1.2 to adjust the price.

        Returns:
            BossPrice: A new BossPrice instance with a price range based on the unit price,
            quantity, and random factor.
        """
        if currency_type not in ("scrap_metal", "copper"):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")
        rand_price = round(rand_factor * quantity * unit_price)
        price_min = round(rand_price * 0.8)
        price_max = round(rand_price * 1.2)
        return cls.from_range(price_min, price_max, currency_type)

    def __mul__(self, other):
        """Multiplies the price of this BossPrice by a scalar value.

        Args:
            other (int or float): The scalar value to multiply the price by.

        Returns:
            BossPrice: A new BossPrice instance with a price value equal to the current price multiplied by the scalar value.
        """
        return self.__class__(self.price * other, self.currency_type)

    def __repr__(self):
        return f"BossPrice(price={self.price}, type='{self.currency_type}')"


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


class NegativeBalance(BossException):
    pass


class NegativeInvQuantity(BossException):
    pass


class BossWarning(Warning):
    def __init__(self, text=None, *args: object) -> None:
        super().__init__(*args)
        self.text = text
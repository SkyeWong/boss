# nextcord
from nextcord.ext import commands
from nextcord import Embed, Interaction, BaseApplicationCommand, CallbackWrapper
from nextcord.ui import View, Button
import nextcord

# constants
from utils import constants
from utils.constants import SCRAP_METAL, EmbedColour
from utils.postgres_db import Database

# inbuilt modules
import math
import random
import json
from datetime import datetime
from typing import Literal, Optional, Union, Self


def check_if_not_dev_guild(*args, **_) -> bool:
    return args[1].guild is not None and args[1].guild.id != constants.DEVS_SERVER_ID


def get_formatted_time() -> str:
    """Returns the current time in the format "DD <month> YY HH:MM"."""
    return datetime.now().strftime("%d %B %Y %H:%M")


def text_to_num(text: str) -> int:
    """Converts a text representation of a number into the actual number. Note that the decimals will be dropped.

    Args:
        text (str): The text to convert

    Raises:
        ValueError: a invalid number is passed.

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
            raise ValueError(f"text_to_num() must be passed str, not {i.__class__.__qualname__}")
        elif i.isnumeric():
            res += int(i)
        elif i[-1] in d:
            # separate out the K, M, or B
            num, magnitude = i[:-1], i[-1]
            try:
                # if this succeeds, you have your (first) float
                num = float(num)
            except ValueError:
                raise ValueError(f"text_to_num() received a non-number prefix before {magnitude}")
            res += num * d[magnitude]
        else:
            raise ValueError("text_to_num() is passed an incorrect magnitude.")
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
    notes: Optional[list[str] | str] = None,
    examples: Optional[dict[str, str]] = None,
    **kwargs,
):
    """Adds additional information to a command, which can be displayed in /help."""

    class AddCommandInfo(CallbackWrapper):
        def modify(self, app_cmd: BaseApplicationCommand) -> None:
            app_cmd.long_help = long_help
            app_cmd.notes = [notes] if isinstance(notes, str) else notes
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
                interaction: BossInteraction = args[1]
                if interaction.guild_id == constants.DEVS_SERVER_ID and dev_guild_only:
                    await app_cmd.original_callback(*args, **kwargs)
                else:
                    await interaction.send_text(
                        "The developement of this command is in progress.\nYou can't use it now, but keep checking for updates!"
                    )

            app_cmd.callback = callback

    def wrapper(func):
        return WorkInProgressCommand(func)

    return wrapper


def get_error_message():
    embed = BossEmbed(
        title="An error occurred. Try again in a few seconds.",
        description="If this continues to happen, please report it in our [server](https://discord.gg/EshzsTUtHe 'BOSS Server').",
        colour=EmbedColour.FAIL,
    )
    view = View()
    button = Button(label="Join server", url="https://discord.gg/EshzsTUtHe")
    view.add_item(button)
    return embed, view


def get_item_embed(item, owned_quantity: dict[str, int] | int = None):
    embed = BossEmbed(title=item["name"], colour=EmbedColour.INFO)

    description = ""
    for i in item["description"].splitlines():
        description += f"> _{i}_\n"

    embed.description = description

    if not owned_quantity:  # `owned_quantity` is 0/ empty dict
        embed.description += "\nYou own **0**"

    elif isinstance(owned_quantity, int):
        embed.description += f"\nYou own **{owned_quantity}**"

    elif isinstance(owned_quantity, dict) and owned_quantity:  # make sure the dict is not empty
        embed.description += " \nYou own"
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

    info = ""
    other_attr = json.loads(item["other_attributes"])
    if (food_min := other_attr.get("food_value_min")) and (
        food_max := other_attr.get("food_value_max")
    ):
        info += f"\n- </use:1107319705070477462>: restore {food_min} - {food_max} points of hunger"
    if armour_prot := other_attr.get("armour_protection"):
        info += f"\n- Provides {armour_prot} points of protection."
    if weapon_dmg := other_attr.get("weapon_damage"):
        info += f"\n- Deals {weapon_dmg} points of damage on each hit."
    if additional_info := item.get("additional_info"):
        info += f"\n- {additional_info}"

    if info:
        embed.add_field(
            name="Additional info",
            value=info,
            inline=False,
        )

    item_rarity = constants.ItemRarity(item["rarity"])
    item_type = constants.ItemType(item["type"])
    embed.set_thumbnail(url=f"https://cdn.discordapp.com/emojis/{item['emoji_id']}.png")
    embed.set_footer(text=f"{item_rarity} {item_type}".replace("_", " ").title())
    return embed


def format_with_link(text: str):
    """Formats a text with its markdown link form: \[text](link)"""
    return f"[`{text}`](https://boss-bot.onrender.com/)"


PB_EMOJIS = {
    "PB1E": "<:PB1E:1130331732571328624>",
    "PB1R": "<:PB1R:1130329877162229793>",
    "PB1F": "<:PB1F:1130329874482073610>",
    "PB2E": "<:PB2E:1130329878814785628>",
    "PB2R": "<:PB2R:1130329883671801876>",
    "PB2F": "<:PB2F:1130329882073772092>",
    "PB3E": "<:PB3E:1130329887115321435>",
    "PB3F": "<:PB3F:1130451473143189504>",
}


def create_pb(percentage: int):
    """Creates a progress bar with the width of 5 and with `filled` emojis set to the filled variants."""
    filled = round(percentage / 20)

    if filled < 0:
        filled = 0
    if filled > 5:
        filled = 5

    pb = ""
    # if even 1 block needs to be filled set the first block to filled, otherwise leave it empty
    pb += PB_EMOJIS["PB1F"] if filled > 0 else PB_EMOJIS["PB1E"]
    # if filled is 5, then the last one will be filled, so we need to fill 3 blocks (5 minus the first and last "rounded" blocks)
    # otherwise we fill (filled - 1) blocks since the first one is filled by the above line
    pb += PB_EMOJIS["PB2F"] * (3 if filled == 5 else filled - 1)
    # if filled is 0, similar to the above line, we leave 3 blocks as empty
    # otherwise we leave the remaining blocks out of 3 empty (5 minus the first and last "rounded" blocks)
    pb += PB_EMOJIS["PB2E"] * (3 if filled == 0 else 3 - (filled - 1))
    # lastly fill in the last block with reasons similar to the first block
    pb += PB_EMOJIS["PB3F"] if filled == 5 else PB_EMOJIS["PB3E"]
    if filled < 5:
        # check if filled is not 5 because if the last one is filled then we don't need to replace
        # replace the last "filled" block with the "half-filled" one to make it rounded
        pb = PB_EMOJIS["PB2R"].join(pb.rsplit(PB_EMOJIS["PB2F"], 1))
    if filled == 1:
        # if only 1 block is filled, then replace the first block with its half-filled variant
        pb = pb.replace(PB_EMOJIS["PB1F"], PB_EMOJIS["PB1R"], 1)
    return pb


def find_command(
    client: Union[commands.Bot, nextcord.Client], command_name: str
) -> Union[nextcord.SlashApplicationCommand, nextcord.SlashApplicationSubcommand]:
    """Finds the slash command (searches for subcommands too) with the name `command_name`. This presumes that command exist and has no typos."""
    cmds = client.get_all_application_commands()
    slash_cmd: nextcord.SlashApplicationCommand = next(
        cmd for cmd in cmds if cmd.name == command_name.split()[0]
    )
    split_index = 1
    # find the macro command in the children of the base command, if it doesnt match the full command name
    while slash_cmd.qualified_name != command_name:
        slash_cmd = slash_cmd.children[command_name.split()[split_index]]
        split_index += 1
    return slash_cmd


class BossEmbed(Embed):
    def __init__(
        self,
        interaction: Optional[Interaction] = None,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        colour: Optional[Union[int, nextcord.Colour, EmbedColour]] = EmbedColour.DEFAULT,
        timestamp: Optional[datetime] = None,
        with_url: Optional[bool] = False,
        show_macro_msg: Optional[bool] = True,
    ) -> None:
        self.interaction = interaction
        self.show_macro_msg = show_macro_msg
        super().__init__(
            colour=colour,
            title=title,
            url="https://boss-bot.onrender.com/" if with_url else None,
            description=description,
            timestamp=timestamp,
        )
        if (
            self.show_macro_msg
            and interaction
            and interaction.client.running_macro_views.get(interaction.user.id)
        ):
            # check whether the user is running a macro
            super().set_footer(text=f"{self.interaction.user.name} is running a /macro")

    def set_footer(self, *, text: Optional[str] = None, icon_url: Optional[str] = None) -> Self:
        if (
            self.show_macro_msg
            and self.interaction
            and self.interaction.client.running_macro_views.get(self.interaction.user.id)
        ):
            # check whether the user is running a macro
            msg = f"{self.interaction.user.name} is running a /macro"
            if "\n" in text:
                text = f"{text}\n{msg}"
            else:
                text = f"{text} | {msg}"
        return super().set_footer(text=text, icon_url=icon_url)


class TextEmbed(BossEmbed):
    """A `nextcord.Embed` with the description set as `text`."""

    def __init__(
        self,
        text: Optional[str] = None,
        colour: Union[int, nextcord.Colour, EmbedColour] = EmbedColour.DEFAULT,
        interaction: Optional[Interaction] = None,
    ):
        super().__init__(interaction, description=text, colour=colour)


class BossInteraction(Interaction):
    def Embed(
        self,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        colour: Optional[Union[int, nextcord.Colour, EmbedColour]] = EmbedColour.DEFAULT,
        timestamp: Optional[datetime] = None,
        with_url: Optional[bool] = True,
        show_macro_msg: Optional[bool] = True,
    ) -> BossEmbed:
        return BossEmbed(
            self,
            title=title,
            description=description,
            colour=colour,
            timestamp=timestamp,
            with_url=with_url,
            show_macro_msg=show_macro_msg,
        )

    def TextEmbed(
        self,
        text: str,
        colour: Union[int, EmbedColour] = EmbedColour.DEFAULT,
        show_macro_msg: bool = True,
    ) -> TextEmbed:
        if show_macro_msg:
            return TextEmbed(text, colour, self)
        else:
            return TextEmbed(text, colour)

    async def send_text(
        self,
        text: str,
        colour: Union[int, EmbedColour] = EmbedColour.DEFAULT,
        show_macro_msg: bool = True,
        **kwargs,
    ) -> Union[nextcord.PartialInteractionMessage, nextcord.WebhookMessage]:
        return await self.send(embed=self.TextEmbed(text, colour, show_macro_msg), **kwargs)


class BossItem:
    def __init__(
        self,
        id: int,
        quantity: Optional[int] = 1,
        name: Optional[str] = None,
        emoji: Optional[str] = None,
    ) -> None:
        self.id = id
        self.quantity = quantity
        self._name = name
        self._emoji = emoji

    async def get_name(self, db: Database):
        """Retrieves the name of the item from the database, if not already cached."""
        if self._name is None:
            self._name, self._emoji = await db.fetchrow(
                """
                SELECT name, CONCAT('<:_:', emoji_id, '>') AS emoji
                FROM utility.items
                WHERE item_id = $1
                """,
                self.id,
            )
        return self._name

    async def get_emoji(self, db: Database):
        """Retrieves the emoji representation of the item from the database, if not already cached."""
        if self._emoji is None:
            self._name, self._emoji = await db.fetchrow(
                """
                SELECT name, CONCAT('<:_:', emoji_id, '>') AS emoji
                FROM utility.items
                WHERE item_id = $1
                """,
                self.id,
            )
        return self._emoji

    def __eq__(self, other):
        """Check if the `item_id`s of 2 BossItem instances are the same, or the `item_id` is equal to a `int`."""
        if isinstance(other, BossItem):
            return self.id == other.id
        if isinstance(other, int):
            return self.id == other
        return NotImplemented

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
            return NotImplemented
        return self.__class__(self.id, round(self.quantity * other), self._name, self._emoji)

    def __repr__(self):
        return f"BossItem(item_id={self.id}, quantity={self.quantity}, name={self._name!r}, emoji={self._emoji!r})"


class BossCurrency:
    def __init__(
        self,
        value: Union[int, str],
        currency_type: Literal["scrap_metal", "copper"] = "scrap_metal",
    ) -> None:
        if currency_type not in ("scrap_metal", "copper"):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")
        self.currency_type = currency_type

        if isinstance(value, str):
            self.price = text_to_num(value)
            # this is assumed to be enter by devs and therefore no error-catching is performed
        else:
            self.price = value

    @classmethod
    def from_range(
        cls,
        min_value: Union[int, str],
        max_value: Union[int, str],
        currency_type: Literal["scrap_metal", "copper"] = "scrap_metal",
    ) -> "BossCurrency":
        """Creates a new BossCurrency instance with a random price value within a range.

        Args:
            min_price (int or str): The minimum price value, either as an integer or a string.
            max_price (int or str): The maximum price value, either as an integer or a string.
            type (str, optional): The type of currency, either "scrap_metal" or "copper". Defaults to "scrap_metal".

        Raises:
            ValueError: If the `type` argument is not "scrap_metal" or "copper".
            ValueError: If the maximum price is smaller than the minimum price

        Returns:
            BossCurrency: A new BossCurrency instance with a price value randomly chosen within the specified range.
        """
        if currency_type not in ("scrap_metal", "copper"):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")

        if isinstance(min_value, str):
            min_value = text_to_num(min_value)
        if isinstance(max_value, str):
            max_value = text_to_num(max_value)

        if max_value < min_value:
            raise ValueError("The max price should be larger than min price.")

        return cls(random.randint(min_value, max_value), currency_type)

    @classmethod
    def from_unit_value(
        cls,
        unit_value: int,
        quantity: int,
        rand_factor: float,
        currency_type: Literal["scrap_metal", "copper"] = "scrap_metal",
    ) -> "BossCurrency":
        """
        Create a new BossCurrency instance based on a unit price, quantity, and random factor.

        Args:
            unit_price (int): The unit price of the item.
            quantity (int): The quantity of items being traded.
            rand_factor (float): A random factor between 0.8 and 1.2 to adjust the price.

        Returns:
            BossCurrency: A new BossCurrency instance with a price range based on the unit price,
            quantity, and random factor.
        """
        if currency_type not in ("scrap_metal", "copper"):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")
        rand_price = round(rand_factor * quantity * unit_value)
        price_min = round(rand_price * 0.8)
        price_max = round(rand_price * 1.2)
        return cls.from_range(price_min, price_max, currency_type)

    def __mul__(self, other):
        """Multiplies the price of this BossCurrency by a scalar value.

        Args:
            other (int or float): The scalar value to multiply the price by.

        Returns:
            BossCurrency: A new BossCurrency instance with a price value equal to the current price multiplied by the scalar value.
        """
        return self.__class__(self.price * other, self.currency_type)

    def __repr__(self):
        return f"BossCurrency(price={self.price}, type='{self.currency_type}')"

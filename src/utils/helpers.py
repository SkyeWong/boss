# nextcord
from nextcord.ext import commands
from nextcord.utils import MISSING
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
from typing import Literal, Optional, Union, List


def roundup(number: int, round_to: int) -> int:
    return number if number % round_to == 0 else number + round_to - number % round_to


def rounddown(number: int, round_to: int) -> int:
    return number if number % round_to == 0 else number - number % round_to


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
                if args[1].guild_id == constants.DEVS_SERVER_ID and dev_guild_only:
                    await app_cmd.original_callback(*args, **kwargs)
                else:
                    await args[1].send(
                        embed=TextEmbed(
                            "The developement of this command is in progress.\nYou can't use it now, but keep checking for updates!"
                        )
                    )

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
    embed.description = (
        "If this continues to happen, please report it in our [server](https://discord.gg/SPtMSrCTAS 'BOSS Server')."
    )
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

    info = ""
    if (food_min := item.get("food_value_min")) and (food_max := item.get("food_value_max")):
        info += f"\n- </use:1107319705070477462>: restore {food_min} - {food_max} points of hunger"
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
    # lighter colours
    "PB1E": "<:PB1E:1121318451500290088>",
    "PB1HF": "<:PB1HF:1121322335060901928>",
    "PB1F": "<:PB1F:1121318454285320324>",
    "PB2E": "<:PB2E:1121318455996592148>",
    "PB2HF": "<:PB2HF:1125688174249791509>",
    "PB2F": "<:PB2F:1121318441845018634>",
    "PB3E": "<:PB3E:1121318446257406023>",
    "PB3F": "<:PB3F:1121318449352822788>",
}


def create_pb(percentage: int):
    """Creates a progress bar with the width of 5 and with `filled` emojis set to the filled variants."""
    filled = round(percentage / 10) * 10  # round off to the nearest 10
    filled = round(filled / 20)

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
        pb = PB_EMOJIS["PB2HF"].join(pb.rsplit(PB_EMOJIS["PB2F"], 1))
    if filled == 1:
        # if only 1 block is filled, then replace the first block with its half-filled variant
        pb = pb.replace(PB_EMOJIS["PB1F"], PB_EMOJIS["PB1HF"], 1)
    return pb


class TextEmbed(Embed):
    """A `nextcord.Embed` with the description set as `text`."""

    def __init__(self, text: str, colour: int = EmbedColour.DEFAULT):
        super().__init__(description=text, colour=colour)


async def send(
    interaction: Interaction,
    content: Optional[str] = None,
    *,
    embed: Embed = MISSING,
    embeds: List[Embed] = MISSING,
    file: nextcord.File = MISSING,
    files: List[nextcord.File] = MISSING,
    view: View = MISSING,
    tts: bool = False,
    delete_after: Optional[float] = None,
    allowed_mentions: nextcord.AllowedMentions = MISSING,
    flags: Optional[nextcord.MessageFlags] = None,
    ephemeral: Optional[bool] = None,
    suppress_embeds: Optional[bool] = None,
):
    """
    Sends a message with the given `interaction`, and modifies embed if the user is running a macro.
    Only use this in grinding commands, since it fetches values from the database every time it is run.
    """
    running_macro_id = await interaction.client.db.fetchval(
        "SELECT running_macro_id FROM players.players WHERE player_id = $1", interaction.user.id
    )
    if running_macro_id and embed:  # check whether the user is running a macro
        footer = f"{interaction.user.name} is running a /macro"
        if embed.footer.text:
            footer += f" | {embed.footer.text}"
        embed.set_footer(text=footer)

    return await interaction.send(
        content=content,
        embed=embed,
        embeds=embeds,
        file=file,
        files=files,
        view=view,
        tts=tts,
        ephemeral=ephemeral,
        delete_after=delete_after,
        allowed_mentions=allowed_mentions,
        flags=flags,
        suppress_embeds=suppress_embeds,
    )


def find_command(
    client: Union[commands.Bot, nextcord.Client], command_name: str
) -> Union[nextcord.SlashApplicationCommand, nextcord.SlashApplicationSubcommand]:
    """Finds the slash command (searches for subcommands too) with the name `command_name`. This presumes that command exist and has no typos."""
    cmds = client.get_all_application_commands()
    slash_cmd: nextcord.SlashApplicationCommand = next(cmd for cmd in cmds if cmd.name == command_name.split()[0])
    split_index = 1
    # find the macro command in the children of the base command, if it doesnt match the full command name
    while slash_cmd.qualified_name != command_name:
        slash_cmd = slash_cmd.children[command_name.split()[split_index]]
        split_index += 1
    return slash_cmd


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
                SELECT name, CONCAT('<:', emoji_name, ':', emoji_id, '>') AS emoji
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
                SELECT name, CONCAT('<:', emoji_name, ':', emoji_id, '>') AS emoji
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

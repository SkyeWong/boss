# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import (
    Embed,
    SlashOption,
    ButtonStyle,
    SlashApplicationCommand as SlashCmd,
    SlashApplicationSubcommand as SlashSubcmd,
    CallbackWrapper,
    BaseApplicationCommand,
    CallbackWrapper,
    BaseApplicationCommand,
)
from nextcord.ui import View, Button

# database
from utils.postgres_db import Database

# my modules and constants
from utils import constants, helpers
from utils.player import Player
from utils.constants import EmbedColour
from utils.helpers import BossInteraction, command_info

# views and modals
from .views import EditItemView, ConfirmItemDelete, EmojiView

# default modules
import json
from typing import Union


class DevOnly(commands.Cog, name="Developer Dashboard"):
    """Toolkit for developers to assist moderate the bot"""

    COG_EMOJI = "⚙️"

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def require_user_id(variable_name: str, default_to_author: bool = False):
        """Checks if `variable_name` (the option that requires a user id) is valid before running the command,
        and convert it into a `Player` object before running the command again."""

        class RequireUserIdCmd(CallbackWrapper):
            def modify(self, app_cmd: BaseApplicationCommand) -> None:
                original_callback = self.callback

                async def callback(*args, **kwargs):
                    interaction: BossInteraction = args[1]
                    user_id = kwargs[variable_name]

                    if default_to_author and user_id is None:
                        user = interaction.user
                    else:
                        user_id = int(user_id)
                        try:
                            user = await interaction.client.fetch_user(user_id)
                        except (nextcord.NotFound, nextcord.HTTPException):
                            await interaction.send_text("The user id is invalid"),
                            return

                    player = Player(interaction.client.db, user)
                    if not await player.is_present():
                        await interaction.send_text("The user doesn't play BOSS!"),
                        return

                    kwargs[variable_name] = player
                    await original_callback(*args, **kwargs)

                app_cmd.callback = callback

        def wrapper(func):
            return RequireUserIdCmd(func)

        return wrapper

    def cog_application_command_check(self, interaction: BossInteraction) -> bool:
        if interaction.guild_id:
            return interaction.guild_id == constants.DEVS_SERVER_ID
        else:
            return False

    GET_ITEM_SQL = """
        SELECT i.* 
        FROM utility.items AS i
        INNER JOIN utility.SearchItem($1) AS s
        ON i.item_id = s.item_id
    """

    async def choose_item_autocomplete(self, interaction: BossInteraction, data: str):
        db: Database = self.bot.db
        items = await db.fetch(self.GET_ITEM_SQL, data)
        await interaction.response.send_autocomplete([i["name"] for i in items][:25])

    @nextcord.slash_command(name="modify", guild_ids=[constants.DEVS_SERVER_ID])
    async def modify(self, interaction: BossInteraction):
        """Modify users and items info."""
        pass

    @modify.subcommand(name="user")
    async def modify_user(self, interaction: BossInteraction):
        """Edit a user's profile."""
        pass

    @modify_user.subcommand(name="currency", description="Modify or set a user's scrap metal and coppers")
    @require_user_id("player", default_to_author=True)
    async def modify_currency(
        self,
        interaction: BossInteraction,
        currency_type: str = SlashOption(name="currency-type", choices=["scrap_metal", "copper"]),
        amount: str = SlashOption(name="amount"),
        player: str = SlashOption(name="user-id", required=False),
        set_or_modify: str = SlashOption(
            name="set-or-modify",
            description="Changes the user's scrap metal by a certain value or sets it to the value. DEFAULT: MODIFY",
            choices=["set", "modify"],
            required=False,
            default="modify",
        ),
    ):
        assert isinstance(player, Player)  # should be converted by `require_user_id()`
        try:
            amount = helpers.text_to_num(amount)
        except ValueError:
            await interaction.send_text("The amount is invalid")
            return
        if not await player.is_present():
            await interaction.send_text("The user doesn't play BOSS")
            return

        if set_or_modify == "set":
            new_scrap = await player.set_currency(currency_type, amount)
            msg = f"{interaction.user.mention} set `{player.user.name}`'s {currency_type} to **`{new_scrap:,}`**"
        else:
            new_scrap = await player.modify_currency(currency_type, amount)
            msg = f"{interaction.user.mention} set `{player.user.name}`'s {currency_type} to **`{new_scrap:,}`**, modified by {amount:,}"

        embed = interaction.TextEmbed(msg, show_macro_msg=False)
        await interaction.send(embed=embed)
        await interaction.guild.get_channel(constants.LOG_CHANNEL_ID).send(embed=embed)

    @modify_user.subcommand(name="experience", description="Set a user's experience")
    @require_user_id("player", default_to_author=True)
    async def modify_experience(
        self,
        interaction: BossInteraction,
        experience: int = SlashOption(description="Level * 100 + experience", required=True),
        player: str = SlashOption(name="user-id", required=False),
    ):
        assert isinstance(player, Player)  # should be converted by `require_user_id()`
        db: Database = self.bot.db
        await db.fetchval(
            """
            UPDATE players.players
            SET experience = $1
            WHERE player_id = $2
            """,
            experience,
            player.user.id,
        )
        embed = interaction.TextEmbed(
            f"{interaction.user.mention} set `{player.user.name}`'s experience to `{experience}`!",
            show_macro_msg=False,
        )
        await interaction.send(embed=embed)
        await interaction.guild.get_channel(constants.LOG_CHANNEL_ID).send(embed=embed)

    @modify_user.subcommand(name="hunger", description="Set a user's hunger")
    @require_user_id("player", default_to_author=True)
    async def modify_hunger(
        self,
        interaction: BossInteraction,
        hunger: int = SlashOption(
            description="Hunger to set to. min - 0, max - 100", required=True, min_value=0, max_value=100
        ),
        player: str = SlashOption(name="user-id", required=False),
    ):
        assert isinstance(player, Player)  # should be converted by `require_user_id()`
        db: Database = self.bot.db
        await db.fetchval(
            """
            UPDATE players.players
            SET hunger = $1
            WHERE player_id = $2
            """,
            hunger,
            player.user.id,
        )
        embed = interaction.TextEmbed(
            f"{interaction.user.mention} set `{player.user.name}`'s hunger to `{hunger}`!",
            show_macro_msg=False,
        )
        await interaction.send(embed=embed)
        await interaction.guild.get_channel(constants.LOG_CHANNEL_ID).send(embed=embed)

    @modify_user.subcommand(name="health", description="Set a user's health")
    @require_user_id("player", default_to_author=True)
    async def modify_health(
        self,
        interaction: BossInteraction,
        health: int = SlashOption(
            description="Health to set to. min - 0, max - 100", required=True, min_value=0, max_value=100
        ),
        player: str = SlashOption(name="user-id", required=False),
    ):
        assert isinstance(player, Player)  # should be converted by `require_user_id()`
        db: Database = self.bot.db
        await db.fetchval(
            """
            UPDATE players.players
            SET health = $1
            WHERE player_id = $2
            """,
            health,
            player.user.id,
        )
        embed = interaction.TextEmbed(
            f"{interaction.user.mention} set `{player.user.name}`'s health to `{health}`!",
            show_macro_msg=False,
        )
        await interaction.send(embed=embed)
        channel = await self.bot.fetch_channel(988046548309016586)  # log channel
        await channel.send(embed=embed)

    @modify_user.subcommand(name="inventory")
    @require_user_id("player", default_to_author=True)
    async def modify_inventory(
        self,
        interaction: BossInteraction,
        inv_type: int = SlashOption(
            name="inventory-type",
            description="The type of inventory to edit",
            required=True,
            choices=constants.InventoryType.to_dict(),
        ),
        item_name: str = SlashOption(
            name="item",
            description="The item to add/delete",
            required=True,
            autocomplete_callback=choose_item_autocomplete,
        ),
        player: str = SlashOption(
            name="user-id",
            description="The id of the user whose inventory you want to edit, defaults to you",
            required=False,
        ),
        quantity: int = SlashOption(
            description="How many items to add or delete? defaults to 1",
            required=False,
            default=1,
        ),
    ):
        """Edit a user's inventory."""
        # INVENTORY TYPES
        #   0 --> backpack (when die lose all stuff, only 32 slots)
        #   1 --> chest (when players attack base and lose some stuff, infinite slots)
        #   2 --> vault (will never be lost, only 5 slots)
        assert isinstance(player, Player)  # should be converted by `require_user_id()`
        db: Database = self.bot.db
        item = await db.fetchrow(self.GET_ITEM_SQL, item_name)
        if item is None:
            await interaction.send_text("The item does not exist.")
            return

        try:
            async with db.pool.acquire() as conn:
                async with conn.transaction():
                    # moves item to to_place
                    quantities = await conn.fetchrow(
                        """
                            INSERT INTO players.inventory As inv (player_id, inv_type, item_id, quantity)
                            VALUES ($1, $2, $3, $4)
                            ON CONFLICT(player_id, inv_type, item_id) DO UPDATE
                                SET quantity = inv.quantity + excluded.quantity
                            RETURNING 
                                quantity As new, 
                                COALESCE(
                                    (SELECT quantity As old_quantity FROM players.inventory WHERE player_id=$1 AND inv_type=$2 AND item_id=$3), 
                                    0
                                ) As old 
                            """,
                        player.user.id,
                        inv_type,
                        item["item_id"],
                        quantity,
                    )
                    if quantities["new"] < 0:
                        raise MoveItemException("Not enough items to remove!")
                    if quantities["new"] == quantities["old"]:  # a new item is added
                        inventory = await conn.fetchrow(
                            """
                                SELECT inv_type, COUNT(*) AS items
                                FROM players.inventory
                                WHERE player_id = $1
                                GROUP BY inv_type
                                """,
                            player.user.id,
                        )

                        for i in inventory:
                            # transaction has not been committed, items are not updated
                            if i == inv_type == 0 and len(i["items"]) >= 32:
                                raise MoveItemException("Backpacks only have 32 slots!")
                            if i == inv_type == 2 and len(i["items"]) >= 5:
                                raise MoveItemException("Vaults only have 5 slots!")

        except MoveItemException as e:
            await interaction.send_text(e.text)
            return

        embed = interaction.Embed(
            title=f"{interaction.user.name} **UPDATED** `{player.user.name}'s {constants.InventoryType(inv_type)}`",
            show_macro_msg=False,
        )
        embed.add_field(name="Item", value=item["name"], inline=False)
        embed.add_field(
            name="Quantites",
            value=f"```diff\n- {quantities['old']}\n+ {quantities['new']}\n```",
            inline=False,
        )
        embed.set_thumbnail(url=f"https://cdn.discordapp.com/emojis/{item['emoji_id']}.png")
        await interaction.send(embed=embed)
        await interaction.guild.get_channel(constants.LOG_CHANNEL_ID).send(embed=embed)

    @modify.subcommand(name="item")
    async def modify_item(self, interaction: BossInteraction):
        """Add, edit, or delete an item."""
        pass

    @modify_item.subcommand(name="add", description="Add a new item into the game")
    async def add_item(
        self,
        interaction: BossInteraction,
        name: str = SlashOption(required=True, min_length=2),
        description: str = SlashOption(required=True, min_length=2),
        emoji_id: str = SlashOption(required=True),
        rarity: int = SlashOption(
            choices=constants.ItemRarity.to_dict(),
            required=False,
            default=0,
        ),
        item_type: int = SlashOption(choices=constants.ItemType.to_dict(), required=False, default=1),
        buy_price: str = SlashOption(required=False, default="0", description="0 --> unable to be bought"),
        sell_price: str = SlashOption(required=False, default="0", description="0 --> unable to be sold"),
        trade_price: str = SlashOption(required=False, default="0", description="0 --> unknown value"),
        other_attributes: str = SlashOption(required=False, default="", description="in JSON format"),
    ):
        errors = []
        prices = {"buy": buy_price, "sell": sell_price, "trade": trade_price}
        for k, price in prices.items():
            # if value in one of these convert them from "2k" to 2000
            try:
                prices[k] = helpers.text_to_num(price)
            except ValueError:
                errors.append(
                    f"The {k} price is not a valid number. Tip: use `2k` for _2,000_, `5m 4k` for _5,004,000_"
                )
        # change emoji id to int
        if not emoji_id.isnumeric():
            errors.append("The emoji id is invalid")
        else:
            emoji_id = int(emoji_id)

        # load the other attributes json text into dict
        if other_attributes:
            try:
                _ = json.loads(other_attributes)
            except json.JSONDecodeError:
                errors.append("The format of `other attributes` are invalid.")
            if not isinstance(_, dict):
                errors.append("`Other attributes should be in a dictionary format.")
            elif any(i for i in _.keys() if i not in constants.ITEM_OTHER_ATTR):
                # `any()` should be more efficient than `all()` since if only 1 match is required
                errors.append(f"Only these keys are available for the other attributes: `{constants.ITEM_OTHER_ATTR}`.")
        else:
            other_attributes = None

        # if an error occured send a message and return the function
        if len(errors) > 0:
            embed = Embed()
            embed.set_author(name="The following error(s) occured:")
            embed.description = ">>> "
            for index, error in enumerate(errors):
                embed.description += f"{index + 1}. {error}\n"
            await interaction.send(embed=embed, ephemeral=True)
            return

        db: Database = self.bot.db
        res = await db.fetchrow(
            """
            SELECT name
            FROM utility.items
            WHERE name = $1
            """,
            name,
        )
        if res:
            await interaction.send_text("An item with the same name exists. Rename the item.")
            return

        try:
            item = await db.fetchrow(
                """
                INSERT INTO utility.items (name, description, emoji_id, buy_price, sell_price, trade_price, rarity, type, other_attributes)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING *
                """,
                name,
                description,
                emoji_id,
                prices["buy"],
                prices["sell"],
                prices["trade"],
                rarity,
                item_type,
                other_attributes,
            )
        except Exception as e:
            # only devs will be able to run this command, so it is safe to show the complete error message to them
            await interaction.send_text(f"{e.__class__.__name__}: {e}", EmbedColour.WARNING)
            return

        embed = helpers.get_item_embed(item)

        view = View()

        async def send_edit_item(interaction: BossInteraction):
            client: nextcord.Client = interaction.client
            cmds = client.get_all_application_commands()
            modify_cmd: nextcord.SlashApplicationCommand = [cmd for cmd in cmds if cmd.name == "modify"][0]
            edit_item_cmd = modify_cmd.children["item"].children["edit"]
            await edit_item_cmd.invoke_callback(interaction, itemname=item["name"])

        edit_btn = Button(label="Edit", style=ButtonStyle.blurple)
        edit_btn.callback = send_edit_item
        view.add_item(edit_btn)

        await interaction.send(embed=embed, view=view)
        await interaction.guild.get_channel(constants.LOG_CHANNEL_ID).send(
            f"A new item is added by {interaction.user.mention}: ", embed=embed
        )

    @modify_item.subcommand(
        name="edit",
        description="Edit an item's name, description, trade price etc",
    )
    async def edit_item(
        self,
        interaction: BossInteraction,
        itemname: str = SlashOption(
            name="item",
            description="The item to edit",
            autocomplete_callback=choose_item_autocomplete,
        ),
    ):
        db: Database = self.bot.db
        item = await db.fetchrow(self.GET_ITEM_SQL, itemname)
        if not item:
            await interaction.send_text("The item is not found!", EmbedColour.WARNING)
        else:
            item = dict(item)
            item.pop("sml", None)
            view = EditItemView(interaction, item)
            embed = view.get_item_embed()
            await interaction.send(embed=embed, view=view)

    @modify_item.subcommand(name="delete", description="Delete an existing item")
    async def delete_item(
        self,
        interaction: BossInteraction,
        item: str = SlashOption(
            description="The item to delete",
            autocomplete_callback=choose_item_autocomplete,
        ),
    ):
        db: Database = self.bot.db
        item = await db.fetchrow(self.GET_ITEM_SQL, item)
        if not item:
            await interaction.send_text("The item is not found!")
        else:
            view = ConfirmItemDelete(interaction, item)
            await interaction.send(embed=view.embed, view=view)

    async def choose_base_commands_autocomplete(self, interaction: BossInteraction, data: str):
        client: nextcord.Client = interaction.client
        cmds = [cmd.qualified_name for cmd in client.get_all_application_commands()]
        cmds.sort()
        if not data:
            # return full list
            await interaction.response.send_autocomplete(cmds[:25])
        else:
            # send a list of nearest matches from the list of item
            near_cmds = [cmd for cmd in cmds if data.lower() in cmd.lower()]
            await interaction.response.send_autocomplete(near_cmds[:25])

    @nextcord.slash_command(name="get-command-id", guild_ids=[constants.DEVS_SERVER_ID])
    async def get_command_id(
        self,
        interaction: BossInteraction,
        command_name: str = SlashOption(
            name="command",
            description="The command to get the ID of",
            autocomplete_callback=choose_base_commands_autocomplete,
        ),
    ):
        """Get the application ID of a slash command."""
        client: nextcord.Client = interaction.client
        cmds = client.get_all_application_commands()
        command = [cmd for cmd in cmds if cmd.qualified_name == command_name and isinstance(cmd, SlashCmd)]
        if not command:
            await interaction.send_text("The command is not found")
            return
        command = command[0]

        command_id = list(command.command_ids.values())[0]
        embed = interaction.Embed(title=command.get_mention(interaction.guild), description=f"> ID: `{command_id}`\n")

        if not command.children:
            embed.description += f"> Mention syntax: <\/{command.qualified_name}:{command_id}>"
        else:
            subcmds = self.get_all_subcommands(command)
            mentions = [
                f"{subcmd.get_mention(interaction.guild)}: \{subcmd.get_mention(interaction.guild)}"
                for subcmd in subcmds
            ]
            embed.description += "\n".join(mentions)

        guilds_str = ""
        if guild_ids := command.guild_ids:
            for guild_id in guild_ids:
                guild = await self.bot.fetch_guild(guild_id)
                guilds_str += f"{guild.name} `({guild_id})`\n"
        else:
            guilds_str = f"**Global**"
        embed.add_field(name="Servers", value=guilds_str)
        await interaction.send(embed=embed)

    def get_all_subcommands(self, cmd: Union[SlashCmd, SlashSubcmd]) -> list[SlashCmd, SlashSubcmd]:
        """Get all subcommand names of a command."""
        cmd_names = []
        for subcmd in cmd.children.values():
            if subcmd.children:
                cmd_names.extend(self.get_all_subcommands(subcmd))
            else:
                cmd_names.append(subcmd)
        return cmd_names

    @nextcord.slash_command(name="reload-villagers", guild_ids=[constants.DEVS_SERVER_ID])
    async def reload_villagers(self, interaction: BossInteraction):
        """Reload the villagers used in /trade."""
        cog = self.bot.get_cog("Resource Repository")
        await cog.update_villagers()
        await interaction.send_text("Reloaded villagers.")

    async def emoji_autocomplete_callback(self, interaction: BossInteraction, data: str):
        """Returns a list of autocompleted choices of emojis of a server's emoji."""
        emojis = [emoji for guild in self.bot.guilds for emoji in guild.emojis]

        if not data:
            # return full list
            await interaction.response.send_autocomplete(sorted([emoji.name for emoji in emojis])[:25])
            return
        # send a list of nearest matches from the list of item
        near_emojis = sorted([emoji.name for emoji in emojis if data.lower() in emoji.name.lower()])
        await interaction.response.send_autocomplete(near_emojis[:25])

    @nextcord.slash_command(
        name="emoji", description="Search for emojis in the server!", guild_ids=[constants.DEVS_SERVER_ID]
    )
    @command_info(
        examples={
            "emoji": "Displays the full list of the server's emoji",
            "emoji emoji:<query>": "Search for emojis whose names match the query",
        },
    )
    async def emoji(
        self,
        interaction: BossInteraction,
        emoji_name: str = SlashOption(
            name="emoji",
            description="Emoji to search for, its id or name. If left empty, all emojis in this server will be shown.",
            required=False,
            autocomplete_callback=emoji_autocomplete_callback,
        ),
    ):
        bot_emojis = [emoji for guild in self.bot.guilds for emoji in guild.emojis]
        if not emoji_name:  # send full list
            view = EmojiView(interaction, sorted(bot_emojis, key=lambda emoji: emoji.name))
            embed = view._get_embed()
            view.disable_buttons()

            await interaction.send(
                f"There are `{len(bot_emojis)}` emojis.",
                embed=embed,
                view=view,
            )
            return

        if len(emoji_name) < 2:
            await interaction.send_text("The search term must be longer than 2 characters.")
            return

        emoji_name = emoji_name.lower()
        # perform a search on emojis
        emojis_found = [
            emoji for emoji in bot_emojis if emoji_name in emoji.name.lower() or emoji_name == str(emoji.id)
        ]

        emojis_found.sort(key=lambda emoji: emoji.name)

        if emojis_found:
            view = EmojiView(interaction, emojis_found)
            embed = view._get_embed()
            view.disable_buttons()

            await interaction.send(
                f"There are `{len(emojis_found)}` results for `{emoji_name}`.",
                embed=embed,
                view=view,
            )
        else:
            await interaction.send_text(f"No emojis are found for `{emoji_name}`.")


class MoveItemException(Exception):
    def __init__(self, text) -> None:
        self.text = text


def setup(bot: commands.Bot):
    bot.add_cog(DevOnly(bot))

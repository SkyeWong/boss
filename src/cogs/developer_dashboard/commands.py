# default modules
from typing import Union

# database
import asyncpg

# nextcord
import nextcord
from nextcord import ButtonStyle
from nextcord import SlashApplicationCommand as SlashCmd
from nextcord import SlashApplicationSubcommand as SlashSubcmd
from nextcord import SlashOption
from nextcord.ext import commands
from nextcord.ui import Button

from cogs.developer_dashboard.views import ConfirmItemDelete, EditItemView, EmojiView, check_input

# my modules and constants
from utils import constants, helpers
from utils.constants import EmbedColour
from utils.helpers import BossInteraction, command_info
from utils.player import Player
from utils.postgres_db import Database
from utils.template_views import BaseView


class DeveloperDashboard(commands.Cog, name="Developer Dashboard"):
    """Toolkit for developers to assist moderate the bot"""

    COG_EMOJI = "⚙️"

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_application_command_check(self, interaction: nextcord.Interaction) -> bool:
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

    @modify.subcommand(name="user")
    async def modify_user(self, interaction: BossInteraction):
        """Edit a user's profile."""

    @modify_user.subcommand(name="currency", description="Modify or set a user's scrap metal and coppers")
    async def modify_currency(
        self,
        interaction: BossInteraction,
        currency_type: str = SlashOption(name="currency-type", choices=["scrap_metal", "copper"]),
        amount_str: str = SlashOption(name="amount"),
        user: Union[nextcord.User, nextcord.Member, None] = SlashOption(required=False),
        set_or_modify: str = SlashOption(
            name="set-or-modify",
            description="Changes the user's scrap metal by a certain value or sets it to the value. DEFAULT: MODIFY",
            choices=["set", "modify"],
            required=False,
            default="modify",
        ),
    ):
        if not user:
            user = interaction.user
        try:
            amount = helpers.text_to_num(amount_str)
        except ValueError:
            await interaction.send_text("The amount is invalid")
            return
        player = Player(interaction.client.db, user)
        if not await player.is_present():
            await interaction.send_text("The user doesn't play BOSS")
            return

        if set_or_modify == "set":
            new_scrap = await player.set_currency(currency_type, amount)
            msg = f"{interaction.user.mention} set `{user.name}`'s {currency_type} to **`{new_scrap:,}`**"
        else:
            new_scrap = await player.modify_currency(currency_type, amount)
            msg = (
                f"{interaction.user.mention} set `{user.name}`'s {currency_type} to"
                f" **`{new_scrap:,}`**, modified by {amount:,}"
            )

        embed = interaction.text_embed(msg, show_macro_msg=False)
        await interaction.send(embed=embed)
        await interaction.guild.get_channel(constants.LOG_CHANNEL_ID).send(embed=embed)

    @modify_user.subcommand(name="experience", description="Set a user's experience")
    async def modify_experience(
        self,
        interaction: BossInteraction,
        experience: int = SlashOption(description="Level * 100 + experience", required=True),
        player: nextcord.User = SlashOption(required=False),
    ):
        if not player:
            player = interaction.user
        db: Database = self.bot.db
        await db.fetchval(
            """
            UPDATE players.players
            SET experience = $1
            WHERE player_id = $2
            """,
            experience,
            player.id,
        )
        embed = interaction.text_embed(
            f"{interaction.user.mention} set `{player.name}`'s experience to `{experience}`!",
            show_macro_msg=False,
        )
        await interaction.send(embed=embed)
        await interaction.guild.get_channel(constants.LOG_CHANNEL_ID).send(embed=embed)

    @modify_user.subcommand(name="hunger", description="Set a user's hunger")
    async def modify_hunger(
        self,
        interaction: BossInteraction,
        hunger: int = SlashOption(description="Hunger to set to.", required=True, min_value=0, max_value=100),
        player: nextcord.User = SlashOption(required=False),
    ):
        if not player:
            player = interaction.user
        db: Database = self.bot.db
        await db.fetchval(
            """
            UPDATE players.players
            SET hunger = $1
            WHERE player_id = $2
            """,
            hunger,
            player.id,
        )
        embed = interaction.text_embed(
            f"{interaction.user.mention} set `{player.name}`'s hunger to `{hunger}`!",
            show_macro_msg=False,
        )
        await interaction.send(embed=embed)
        await interaction.guild.get_channel(constants.LOG_CHANNEL_ID).send(embed=embed)

    @modify_user.subcommand(name="health", description="Set a user's health")
    async def modify_health(
        self,
        interaction: BossInteraction,
        health: int = SlashOption(description="Health to set to", required=True, min_value=0, max_value=100),
        player: nextcord.User = SlashOption(required=False),
    ):
        if not player:
            player = interaction.user
        db: Database = self.bot.db
        await db.fetchval(
            """
            UPDATE players.players
            SET health = $1
            WHERE player_id = $2
            """,
            health,
            player.id,
        )
        embed = interaction.text_embed(
            f"{interaction.user.mention} set `{player.name}`'s health to `{health}`!",
            show_macro_msg=False,
        )
        await interaction.send(embed=embed)
        channel = await self.bot.fetch_channel(988046548309016586)  # log channel
        await channel.send(embed=embed)

    @modify_user.subcommand(name="inventory")
    async def modify_inventory(
        self,
        interaction: BossInteraction,
        inv_type: int = SlashOption(
            name="inventory-type",
            description="The type of inventory to edit",
            required=True,
            choices=constants.InventoryType,
        ),
        item_name: str = SlashOption(
            name="item",
            description="The item to add/delete",
            required=True,
            autocomplete_callback=choose_item_autocomplete,
        ),
        player: nextcord.User = SlashOption(
            description="The user whose inventory you want to edit, defaults to you", required=False
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
        if not player:
            player = interaction.user
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
                        INSERT INTO players.inventory As inv 
                            (player_id, inv_type, item_id, quantity)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT(player_id, inv_type, item_id) DO UPDATE
                            SET quantity = inv.quantity + excluded.quantity
                        RETURNING 
                            quantity As new, 
                            COALESCE(
                                (SELECT quantity As old_quantity 
                                FROM players.inventory 
                                WHERE player_id=$1 AND inv_type=$2 AND item_id=$3), 
                                0
                            ) As old 
                        """,
                        player.id,
                        inv_type,
                        item["item_id"],
                        quantity,
                    )
                    if quantities["new"] < 0:
                        raise MoveItemException("Not enough items to remove!")
                    if quantities["new"] == quantities["old"]:  # a new item is added
                        inventory = await conn.fetch(
                            """
                                SELECT inv_type, COALESCE(COUNT(*), 0) AS items
                                FROM players.inventory
                                WHERE player_id = $1
                                GROUP BY inv_type
                                ORDER BY inv_type
                                """,
                            player.id,
                        )
                        # transaction has not been committed, items are not updated
                        backpack = constants.InventoryType.BACKPACK.value
                        if inv_type == backpack and inventory[backpack]["items"] >= 32:
                            raise MoveItemException("Backpacks only have 32 slots!")
                        vault = constants.InventoryType.VAULT.value
                        if inv_type == vault and inventory[vault]["items"] >= 5:
                            raise MoveItemException("Vaults only have 5 slots!")

        except MoveItemException as exc:
            await interaction.send_text(exc.text)
            return

        embed = interaction.embed(
            title=f"{interaction.user.name} **UPDATED** `{player.name}'s {constants.InventoryType(inv_type)}`",
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

    @modify_item.subcommand(name="add", description="Add a new item into the game")
    async def add_item(
        self,
        interaction: BossInteraction,
        name: str = SlashOption(required=True, min_length=2),
        description: str = SlashOption(required=True, min_length=2),
        emoji_id: str = SlashOption(required=True),
        rarity: str = SlashOption(choices=[i.name for i in constants.ItemRarity], required=False, default=0),
        item_type: str = SlashOption(choices=[i.name for i in constants.ItemType], required=False, default=1),
        buy_price: str = SlashOption(required=False, default="0", description="0 --> unable to be bought"),
        sell_price: str = SlashOption(required=False, default="0", description="0 --> unable to be sold"),
        trade_price: str = SlashOption(required=False, default="0", description="0 --> unknown value"),
        other_attributes: str = SlashOption(required=False, default="", description="in JSON format"),
    ):
        errors = []
        values = {}
        for column, user_input in {
            "name": name,
            "description": description,
            "emoji_id": emoji_id,
            "rarity": rarity,
            "type": item_type,
            "buy_price": buy_price,
            "sell_price": sell_price,
            "trade_price": trade_price,
            "other_attributes": other_attributes,
        }.items():
            try:
                if (value := check_input(column, user_input)) is not None:
                    values[column] = value
            except ValueError as exc:
                errors.append(exc.args[0])

        # if it is an invalid value send a message and leave the function
        if errors:
            embed = interaction.embed(description="")
            embed.set_author(name="The following error(s) occured:")
            for index, error in enumerate(errors):
                embed.description += f"{index + 1}. {error}\n"
            await interaction.send(embed=embed, ephemeral=True)
            return

        db: Database = self.bot.db
        if await db.fetchrow("SELECT name FROM utility.items WHERE name = $1", name):
            await interaction.send_text("An item with the same name exists. Rename the item.")
            return

        try:
            sql = (
                "INSERT INTO utility.items ("
                + ", ".join(values.keys())
                + ") VALUES ("
                + ", ".join(f"${i + 1}" for i, column in enumerate(values))
                + ") RETURNING *"
            )  # add each column into the query
            item = await db.fetchrow(sql, *values.values())
        except asyncpg.PostgresError as exc:
            # only devs will be able to run this command,
            # so it is safe to show the complete error message to them
            await interaction.send_text(f"{exc.__class__.__name__}: {exc}", EmbedColour.WARNING)
            return

        embed = helpers.get_item_embed(item)
        view = BaseView(interaction)

        async def send_edit_item(btn_inter: BossInteraction):
            # invoke_callback will be added with `nextcord.slash_command` decorator
            # pylint: disable=no-member
            await self.edit_item.invoke_callback(btn_inter, itemname=item["name"])
            # pylint: enable=no-member

        edit_btn = Button(label="Edit", style=ButtonStyle.blurple)
        edit_btn.callback = send_edit_item
        view.add_item(edit_btn)

        async def send_delete_item(btn_inter: BossInteraction):
            # invoke_callback will be added with `nextcord.slash_command` decorator
            # pylint: disable=no-member
            await self.delete_item.invoke_callback(btn_inter, item=item["name"])
            # pylint: enable=no-member

        delete_btn = Button(label="Delete", style=ButtonStyle.blurple)
        delete_btn.callback = send_delete_item
        view.add_item(delete_btn)

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
        embed = interaction.embed(title=command.get_mention(interaction.guild), description=f"> ID: `{command_id}`\n")

        if not command.children:
            embed.description += f"> Mention syntax: \\{command.get_mention(interaction.guild)}"
        else:
            subcmds = self.get_all_subcommands(command)
            mentions = [
                f"{subcmd.get_mention(interaction.guild)}: \\{subcmd.get_mention(interaction.guild)}"
                for subcmd in subcmds
            ]
            embed.description += "\n".join(mentions)

        guilds_str = ""
        if guild_ids := command.guild_ids:
            for guild_id in guild_ids:
                guild = await self.bot.fetch_guild(guild_id)
                guilds_str += f"{guild.name} `({guild_id})`\n"
        else:
            guilds_str = "**Global**"
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
        name="emoji",
        description="Search for emojis in the server!",
        guild_ids=[constants.DEVS_SERVER_ID],
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
            await EmojiView.send(interaction, sorted(bot_emojis, key=lambda emoji: emoji.name))
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

        if not emojis_found:
            await interaction.send_text(f"No emojis are found for `{emoji_name}`.")
            return

        await EmojiView.send(
            interaction,
            emojis_found,
            f"There are `{len(emojis_found)}` results for `{emoji_name}`.",
        )


class MoveItemException(Exception):
    def __init__(self, text) -> None:
        self.text = text


def setup(bot: commands.Bot):
    bot.add_cog(DeveloperDashboard(bot))

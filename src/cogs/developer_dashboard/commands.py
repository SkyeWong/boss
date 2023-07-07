# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import (
    Embed,
    Interaction,
    SlashOption,
    ButtonStyle,
    SlashApplicationCommand as SlashCmd,
    SlashApplicationSubcommand as SlashSubcmd,
)
from nextcord.ui import View, Button

# database
from utils.postgres_db import Database

import parsedatetime as pdt

# my modules and constants
from utils import constants, helpers
from utils.player import Player
from utils.constants import EmbedColour
from utils.helpers import MoveItemException, TextEmbed, command_info

# views and modals
from .views import EditItemView, ConfirmItemDelete, EmojiView

# default modules
from datetime import datetime
import random
import json
from typing import Union


class DevOnly(commands.Cog, name="Developer Dashboard"):
    """Toolkit for developers to assist moderate the bot"""

    COG_EMOJI = "⚙️"

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_application_command_check(self, interaction: Interaction) -> bool:
        if interaction.guild_id:
            return interaction.guild_id == constants.DEVS_SERVER_ID
        else:
            return False

    @nextcord.slash_command(
        name="avatar",
        description="Shows avatar of a user.",
        guild_ids=[constants.DEVS_SERVER_ID],
    )
    async def avatar(
        self,
        interaction: Interaction,
        user: nextcord.Member = SlashOption(
            name="user",
            description="The user whom you wants to have avatar shown. Defaults to... YOU!",
            required=False,
            default=None,
            verify=True,
        ),
    ):
        if user == None:
            user = interaction.user
        embed = Embed()
        embed.set_author(name=user.name)
        embed.description = f"<{user.display_avatar.url}>"
        embed.set_image(user.display_avatar.url)
        await interaction.send(embed=embed)

    GET_ITEM_SQL = """
        SELECT i.* 
        FROM utility.items AS i
        INNER JOIN utility.SearchItem($1) AS s
        ON i.item_id = s.item_id
    """

    async def choose_item_autocomplete(self, interaction: Interaction, data: str):
        db: Database = self.bot.db
        items = await db.fetch(self.GET_ITEM_SQL, data)
        await interaction.response.send_autocomplete([i["name"] for i in items][:25])

    @nextcord.slash_command(name="modify", guild_ids=[constants.DEVS_SERVER_ID])
    async def modify(self, interaction: Interaction):
        """Modify users and items info."""
        pass

    @modify.subcommand(name="user")
    async def modify_user(self, interaction: Interaction):
        """Edit a user's profile."""
        pass

    @modify_user.subcommand(name="scrap-metal", description="Modify or set a user's scrap metal")
    async def modify_scrap(
        self,
        interaction: Interaction,
        scrap_metal: str = SlashOption(name="scrap-metal", required=True),
        user_id: str = SlashOption(name="user-id", required=False, default=None),
        set_or_modify: int = SlashOption(
            name="set-or-modify",
            description="Changes the user's scrap metal by a certain value or sets it to the value. DEFAULT: MODIFY",
            choices={"set": 0, "modify": 1},
            required=False,
            default=1,
        ),
    ):
        if user_id is None:
            user_id = interaction.user.id
        else:
            user_id = int(user_id)
        try:
            user = await self.bot.fetch_user(user_id)
        except (nextcord.NotFound, nextcord.HTTPException):
            await interaction.send(
                embed=TextEmbed("The user id is invalid"),
            )
            return

        player = Player(self.bot.db, user)
        try:
            scrap_metal = helpers.text_to_num(scrap_metal)
        except helpers.TextToNumException as e:
            await interaction.send(
                embed=Embed(
                    title="Can't set the `scrap metal` to that, try again",
                    description=f"Error:\n{e.args[0]}",
                ),
            )
        else:
            if not await player.is_present():
                await interaction.send(
                    embed=TextEmbed(description="The user doesn't play BOSS! what a boomer."),
                )
                return

            if set_or_modify == 0:
                new_scrap = await player.set_scrap(scrap_metal)
                embed = TextEmbed(f"{interaction.user.mention} set `{user.name}`'s scrap metal to **`{new_scrap:,}`**")
            else:
                new_scrap = await player.modify_scrap(scrap_metal)
                embed = TextEmbed(
                    f"{interaction.user.mention} set `{user.name}`'s scrap metal to **`{new_scrap:,}`**, modified by {scrap_metal:,}"
                )

            await interaction.send(embed=embed)
            channel = await self.bot.fetch_channel(988046548309016586)
            await channel.send(embed=embed)

    @modify_user.subcommand(name="copper", description="Modify or set a user's copper")
    async def modify_copper(
        self,
        interaction: Interaction,
        copper: str = SlashOption(),
        user_id: str = SlashOption(name="user-id", required=False),
        set_or_modify: int = SlashOption(
            name="set-or-modify",
            description="Changes the user's copper by a certain value or sets it to the value. DEFAULT: MODIFY",
            choices={"set": 0, "modify": 1},
            required=False,
            default=1,
        ),
    ):
        if user_id is None:
            user_id = interaction.user.id
        else:
            user_id = int(user_id)
        try:
            user = await self.bot.fetch_user(user_id)
        except (nextcord.NotFound, nextcord.HTTPException):
            await interaction.send(
                embed=TextEmbed("The user id is invalid"),
            )
            return

        player = Player(self.bot.db, user)
        try:
            copper = helpers.text_to_num(copper)
        except helpers.TextToNumException as e:
            await interaction.send(
                embed=Embed(
                    title="Can't set the `copper` to that, try again",
                    description=f"Error:\n{e.args[0]}",
                ),
            )
        else:
            if not await player.is_present():
                await interaction.send(
                    embed=TextEmbed(description="The user doesn't play BOSS! what a boomer."),
                )
                return

            if set_or_modify == 0:
                new_copper = await player.set_copper(copper)
                embed = TextEmbed(f"{interaction.user.mention} set `{user.name}`'s copper to **`{new_copper:,}`**")
            else:
                new_copper = await player.modify_copper(copper)
                embed = TextEmbed(
                    f"{interaction.user.mention} set `{user.name}`'s copper to **`{new_copper:,}`**, modified by {copper:,}"
                )

            await interaction.send(embed=embed)
            channel = await self.bot.fetch_channel(988046548309016586)
            await channel.send(embed=embed)

    @modify_user.subcommand(name="experience", description="Set a user's experience")
    async def modify_experience(
        self,
        interaction: Interaction,
        experience: int = SlashOption(description="Level * 100 + experience", required=True),
        user_id: str = SlashOption(name="user-id", required=False, default=None),
    ):
        if user_id is None:
            user_id = interaction.user.id
        else:
            user_id = int(user_id)

        try:
            user = await self.bot.fetch_user(user_id)
        except (nextcord.NotFound, nextcord.HTTPException):
            await interaction.send(
                embed=TextEmbed("The user id is invalid"),
            )
            return

        player = Player(self.bot.db, user)
        if not await player.is_present():
            await interaction.send(
                embed=TextEmbed("The user doesn't play BOSS! what a boomer."),
            )
            return
        db: Database = self.bot.db
        await db.fetchval(
            """
            UPDATE players.players
            SET experience = $1
            WHERE player_id = $2
            """,
            experience,
            user_id,
        )
        embed = TextEmbed(f"{interaction.user.mention} set `{user.name}`'s experience to `{experience}`!")
        await interaction.send(embed=embed)

        channel = await self.bot.fetch_channel(988046548309016586)
        await channel.send(embed=embed)

    @modify_user.subcommand(name="hunger", description="Set a user's hunger")
    async def modify_hunger(
        self,
        interaction: Interaction,
        hunger: int = SlashOption(
            description="Hunger to set to. min - 0, max - 100", required=True, min_value=0, max_value=100
        ),
        user_id: str = SlashOption(name="user-id", required=False, default=None),
    ):
        if user_id is None:
            user_id = interaction.user.id
        else:
            user_id = int(user_id)

        try:
            user = await self.bot.fetch_user(user_id)
        except (nextcord.NotFound, nextcord.HTTPException):
            await interaction.send(
                embed=TextEmbed("The user id is invalid"),
            )
            return

        player = Player(self.bot.db, user)
        if not await player.is_present():
            await interaction.send(
                embed=TextEmbed("The user doesn't play BOSS!"),
            )
            return
        db: Database = self.bot.db
        await db.fetchval(
            """
            UPDATE players.players
            SET hunger = $1
            WHERE player_id = $2
            """,
            hunger,
            user_id,
        )
        embed = TextEmbed(f"{interaction.user.mention} set `{user.name}`'s hunger to `{hunger}`!")
        await interaction.send(embed=embed)

        channel = await self.bot.fetch_channel(988046548309016586)
        await channel.send(embed=embed)

    @modify_user.subcommand(name="health", description="Set a user's health")
    async def modify_health(
        self,
        interaction: Interaction,
        health: int = SlashOption(
            description="Health to set to. min - 0, max - 100", required=True, min_value=0, max_value=100
        ),
        user_id: str = SlashOption(name="user-id", required=False, default=None),
    ):
        if user_id is None:
            user_id = interaction.user.id
        else:
            user_id = int(user_id)

        try:
            user = await self.bot.fetch_user(user_id)
        except (nextcord.NotFound, nextcord.HTTPException):
            await interaction.send(
                embed=TextEmbed("The user id is invalid"),
            )
            return

        player = Player(self.bot.db, user)
        if not await player.is_present():
            await interaction.send(
                embed=TextEmbed("The user doesn't play BOSS!"),
            )
            return
        db: Database = self.bot.db
        await db.fetchval(
            """
            UPDATE players.players
            SET health = $1
            WHERE player_id = $2
            """,
            health,
            user_id,
        )
        embed = TextEmbed(f"{interaction.user.mention} set `{user.name}`'s health to `{health}`!")
        await interaction.send(embed=embed)

        channel = await self.bot.fetch_channel(988046548309016586)
        await channel.send(embed=embed)

    @modify_user.subcommand(name="inventory")
    async def modify_inventory(
        self,
        interaction: Interaction,
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
        player_id: str = SlashOption(
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
        #   1 --> chest (when players attack base and lose lose some stuff, infinite slots)
        #   2 --> vault (will never be lost, only 5 slots)
        if player_id == None:
            player_id = interaction.user.id
        try:
            player_id = int(player_id)
            player: nextcord.User = await interaction.client.fetch_user(player_id)
        except (nextcord.NotFound, nextcord.HTTPException, ValueError):
            await interaction.send(
                embed=TextEmbed("The user id is invalid"),
            )
            return
        db: Database = self.bot.db
        item = await db.fetchrow(self.GET_ITEM_SQL, item_name)
        if item is None:
            await interaction.send(embed=TextEmbed("The item is not found"), ephemeral=True)
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
                        player_id,
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
                            player_id,
                        )

                        for i in inventory:
                            # transaction has not been committed, items are not updated
                            if i == inv_type == 0 and len(i["items"]) >= 32:
                                raise MoveItemException("Backpacks only have 32 slots!")
                            if i == inv_type == 2 and len(i["items"]) >= 5:
                                raise MoveItemException("Vaults only have 5 slots!")

        except MoveItemException as e:
            await interaction.send(embed=TextEmbed(e.text), ephemeral=True)
            return

        inv_type_str = [i.name for i in constants.InventoryType if i.value == inv_type][0]
        embed = Embed(title=f"{interaction.user.name} **UPDATED** `{player.name}'s {inv_type_str}`")
        embed.add_field(name="Item", value=item["name"], inline=False)
        embed.add_field(
            name="Quantites",
            inline=False,
            value="```diff\n" f"- {quantities['old']}\n+ {quantities['new']}\n" "```",
        )
        embed.set_thumbnail(url=f"https://cdn.discordapp.com/emojis/{item['emoji_id']}.png")
        await interaction.send(embed=embed)
        await interaction.guild.get_channel(988046548309016586).send(embed=embed)

    @modify.subcommand(name="item")
    async def modify_item(self, interaction: Interaction):
        """Add, edit, or delete an item."""
        pass

    @modify_item.subcommand(name="add", description="Add a new item into the game")
    async def add_item(
        self,
        interaction: Interaction,
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
            except helpers.TextToNumException:
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
                other_attributes = json.loads(other_attributes)
            except json.JSONDecodeError:
                errors.append("The format of `other attributes` are invalid.")
            if not isinstance(other_attributes, dict):
                errors.append("`Other attributes should be in a dictionary format.")
        else:
            other_attributes = {}

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
            await interaction.send(
                embed=TextEmbed("An item with the same name exists. Rename the item."),
            )
            return

        try:
            sql = (
                "INSERT INTO utility.items (name, description, emoji_id, buy_price, sell_price, trade_price, rarity, type"
                + (", " if other_attributes else "")
                + ", ".join(other_attributes.keys())
                + ") "
                + "VALUES ($1, $2, $3, $4, $5, $6, $7, $8"
                + (", " if other_attributes else "")
                + ", ".join([f"${i + 10}" for i, column in enumerate(other_attributes)])
                + ") "
                + "RETURNING *"
            )
            item = await db.fetchrow(
                sql,
                name,
                description,
                emoji_id,
                prices["buy"],
                prices["sell"],
                prices["trade"],
                rarity,
                item_type,
                *other_attributes.values(),
            )
        except Exception as e:
            await interaction.send(embed=TextEmbed(f"{e.__class__.__name__}: {e}", EmbedColour.WARNING))
            return

        embed = helpers.get_item_embed(item)

        view = View()

        async def send_edit_item(interaction: Interaction):
            client: nextcord.Client = interaction.client
            cmds = client.get_all_application_commands()
            modify_cmd: nextcord.SlashApplicationCommand = [cmd for cmd in cmds if cmd.name == "modify"][0]
            edit_item_cmd = modify_cmd.children["item"].children["edit"]
            await edit_item_cmd.invoke_callback(interaction, itemname=item["name"])

        edit_btn = Button(label="Edit", style=ButtonStyle.blurple)
        edit_btn.callback = send_edit_item
        view.add_item(edit_btn)

        await interaction.send(embed=embed, view=view)
        await interaction.guild.get_channel(988046548309016586).send(
            f"A new item is added by {interaction.user.mention}: ", embed=embed
        )

    @modify_item.subcommand(
        name="edit",
        description="Edit an item's name, description, trade price etc",
    )
    async def edit_item(
        self,
        interaction: Interaction,
        itemname: str = SlashOption(
            name="item",
            description="The item to edit",
            autocomplete_callback=choose_item_autocomplete,
        ),
    ):
        db: Database = self.bot.db
        item = await db.fetchrow(self.GET_ITEM_SQL, itemname)
        if not item:
            await interaction.send(embed=TextEmbed("The item is not found!", EmbedColour.WARNING))
        else:
            item = dict(item)
            item.pop("sml", None)
            view = EditItemView(interaction, item)
            embed = view.get_item_embed()
            await interaction.send(embed=embed, view=view)

    @modify_item.subcommand(name="delete", description="Delete an existing item")
    async def delete_item(
        self,
        interaction: Interaction,
        item: str = SlashOption(
            description="The item to delete",
            autocomplete_callback=choose_item_autocomplete,
        ),
    ):
        db: Database = self.bot.db
        item = await db.fetchrow(self.GET_ITEM_SQL, item)
        if not item:
            await interaction.send("The item is not found!", ephemeral=True)
        else:
            view = ConfirmItemDelete(interaction, item)
            await interaction.send(embed=view.embed, view=view)

    async def choose_base_commands_autocomplete(self, interaction: Interaction, data: str):
        client: nextcord.Client = interaction.client
        cmds = client.get_all_application_commands()
        cmds = [cmd.qualified_name for cmd in cmds]
        cmds.sort()
        if not data:
            # return full list
            await interaction.response.send_autocomplete([cmd for cmd in cmds[:25]])
        else:
            # send a list of nearest matches from the list of item
            near_cmds = [cmd for cmd in cmds if data.lower() in cmd.lower()]
            await interaction.response.send_autocomplete(near_cmds[:25])

    @nextcord.slash_command(name="get-command-id", guild_ids=[constants.DEVS_SERVER_ID])
    async def get_command_id(
        self,
        interaction: Interaction,
        command_name: str = SlashOption(
            name="command",
            description="The command to get the ID of",
            default=None,
            required=True,
            autocomplete_callback=choose_base_commands_autocomplete,
        ),
    ):
        """Get the application ID of a slash command."""
        client: nextcord.Client = interaction.client
        cmds = client.get_all_application_commands()
        # only save slash commands and subcommands, not message/ user commands
        cmds = [
            cmd
            for cmd in cmds
            if isinstance(cmd, nextcord.SlashApplicationCommand) or isinstance(cmd, nextcord.SlashApplicationSubcommand)
        ]
        command = [cmd for cmd in cmds if cmd.qualified_name == command_name]
        if not command:
            await interaction.send("The command is not found", ephemeral=True)
            return
        command = command[0]

        command_id = list(command.command_ids.values())[0]

        embed = Embed()
        embed.colour = random.choice(constants.EMBED_COLOURS)
        # if command has no subcommand, mention it
        # else, only display the name
        embed.title = f"</{command.qualified_name}:{command_id}>"

        embed.description = (
            f"> ID: `{command_id}`\n> Mention syntax: <\/{command.qualified_name}:{command_id}>"
            if not command.children
            else ""
        )  # only show base command mention syntax if it has no subcommands

        subcmd_names = [i.qualified_name for i in self.get_all_subcommands(command)]
        if subcmd_names:
            embed.add_field(
                name="Subcommands",
                value="\n".join(
                    [f"</{subcmd_name}:{command_id}>: <\/{subcmd_name}:{command_id}>" for subcmd_name in subcmd_names]
                ),
                inline=False,
            )

        guilds_str = ""
        for guild_id in command.command_ids.keys():
            if not guild_id:
                guilds_str = f"**Global**"
                break
            else:
                guild = await self.bot.fetch_guild(guild_id)
                guilds_str += f"{guild.name} `({guild_id})`\n"
        embed.add_field(name="Servers", value=guilds_str, inline=False)

        embed.set_footer(
            text="Mention a slash command with </𝘤𝘰𝘮𝘮𝘢𝘯𝘥-𝘯𝘢𝘮𝘦:𝘤𝘰𝘮𝘮𝘢𝘯𝘥-𝘪𝘥> | Replace the `command-name` with the subcommand **full name** to mention it"
        )
        await interaction.send(embed=embed)

    @nextcord.slash_command(
        name="raise-error",
        description="Raise an error",
        guild_ids=[constants.DEVS_SERVER_ID],
    )
    async def raise_error(self, interaction: Interaction):
        raise helpers.BossException

    def search_subcommand(self, cmd: nextcord.SlashApplicationCommand, cmd_name):
        cmd_found = False
        subcommands = cmd.children.values()
        if len(subcommands) > 0:
            for x in subcommands:
                if x.qualified_name in cmd_name:
                    if cmd_name == x.qualified_name:
                        cmd_found = True
                        cmd = x
                        break
                    if len(x.children) > 0:
                        return self.search_subcommand(x, cmd_name)
        return cmd_found, cmd

    def get_all_subcommands(self, cmd: Union[SlashCmd, SlashSubcmd]) -> list[SlashCmd, SlashSubcmd]:
        """Get all subcommand names of a command."""
        cmd_names = []
        for subcmd in cmd.children.values():
            if subcmd.children:
                cmd_names.extend(self.get_all_subcommands(subcmd))
            else:
                cmd_names.append(subcmd)
        return cmd_names

    async def choose_command_autocomplete(self, interaction: Interaction, data: str) -> list[str]:
        """
        Return every command and subcommand in the bot.
        Returns command that match `data` if it is provided.
        """
        client: nextcord.Client = interaction.client
        cmds = [i for i in client.get_all_application_commands() if isinstance(i, SlashCmd)]

        cmd_names = []
        for cmd in cmds:
            if cmd.is_global or interaction.guild_id in cmd.guild_ids:
                cmd_names.append(cmd.qualified_name)
                if cmd.children:
                    cmd_names.extend([i.qualified_name for i in self.get_all_subcommands(cmd)])

        cmd_names.sort()
        if not data:
            # return full list
            await interaction.response.send_autocomplete(cmd_names[:25])
        else:
            # send a list of nearest matches from the list of item
            near_items = [cmd for cmd in cmd_names if data.lower() in cmd.lower()]
            await interaction.response.send_autocomplete(near_items[:25])

    def parse_command(self, interaction: Interaction, cmd_name: str):
        client: nextcord.Client = interaction.client
        all_cmds = [i for i in client.get_all_application_commands() if isinstance(i, SlashCmd)]

        cmd_list = cmd_name.split()
        for item in cmd_list:
            cmd = next((i for i in all_cmds if i.name == item), None)
            if cmd is None:
                raise helpers.CommandNotFound()
            if isinstance(cmd, SlashCmd):
                base_cmd = cmd
            all_cmds = cmd.children.values()

        if cmd.qualified_name != cmd_name:
            raise helpers.CommandNotFound()

        if not base_cmd.is_global and interaction.guild_id not in base_cmd.guild_ids:
            raise helpers.CommandNotFound()

        return cmd

    @nextcord.slash_command(name="disable-global", guild_ids=[constants.DEVS_SERVER_ID])
    async def disable_global(
        self,
        interaction: Interaction,
        command: str = SlashOption(
            description="The command to disable",
            required=True,
            autocomplete_callback=choose_command_autocomplete,
        ),
        duration_str: str = SlashOption(
            name="duration",
            description="Duration to disable the command for. Defaults to forever.",
            default=None,
        ),
        reason: str = SlashOption(
            description="Reason to disable the command.",
            choices=(
                "security concerns",
                "maintainance",
                "gameplay disruption",
                "other",
            ),
            default=None,
        ),
        extra_info: str = SlashOption(
            name="extra-info",
            description="Extra information that you would like the player to know.",
            default=None,
        ),
    ):
        """Disable a command globally"""
        try:
            cmd = self.parse_command(interaction, command)
        except helpers.CommandNotFound:
            await interaction.send(
                embed=TextEmbed(
                    "The command is not found! Use </help:964753444164501505> for a list of available commands.",
                    EmbedColour.WARNING,
                )
            )
            return

        until = None
        if duration_str:
            cal = pdt.Calendar()
            result = cal.parse(duration_str)

            until = datetime(*result[0][:6])

        db: Database = self.bot.db

        embed = Embed(title="Successfully disabled the command!")
        embed.description = f"{helpers.format_with_link('Command')} - "

        if cmd.children:
            await db.executemany(
                """
                INSERT INTO utility.disabled_commands (command_name, until, reason, extra_info)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT(command_name) DO UPDATE
                    SET until = excluded.until,
                        reason = excluded.reason,
                        extra_info = excluded.extra_info
                """,
                [(subcommand.qualified_name, until, reason, extra_info) for subcommand in list(cmd.children.values())],
            )

            embed.description += ", ".join(
                [
                    f"</{subcommand.qualified_name}:{list(subcommand.command_ids.values())[0]}>"
                    for subcommand in list(cmd.children.values())
                ]
            )

        else:
            await db.execute(
                """
                INSERT INTO utility.disabled_commands (command_name, until, reason, extra_info)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT(command_name) DO UPDATE
                    SET until = excluded.until,
                        reason = excluded.reason,
                        extra_info = excluded.extra_info
                """,
                cmd.qualified_name,
                until,
                reason,
                extra_info,
            )
            embed.description += f"</{cmd.qualified_name}:{list(cmd.command_ids.values())[0]}>"

        if until:
            until_ts = int(until.timestamp())
            embed.description += f"\n{helpers.format_with_link('Until')} - <t:{until_ts}:F> • <t:{until_ts}:R>"
        else:
            embed.description += f"\n{helpers.format_with_link('Until')} - forever"

        embed.description += (
            f"\n{helpers.format_with_link('Reason')} - {reason}"
            f"\n{helpers.format_with_link('Extra info')} - {extra_info}"
        )

        await interaction.send(embed=embed)

    @nextcord.slash_command(name="enable-global", guild_ids=[constants.DEVS_SERVER_ID])
    async def enable_global(
        self,
        interaction: Interaction,
        command: str = SlashOption(
            description="The command to enable",
            required=True,
            autocomplete_callback=choose_command_autocomplete,
        ),
    ):
        """Enable a command globally"""
        try:
            cmd = self.parse_command(interaction, command)
        except helpers.CommandNotFound:
            await interaction.send(
                embed=TextEmbed(
                    "The command is not found! Use </help:964753444164501505> for a list of available commands.",
                    EmbedColour.WARNING,
                )
            )
            return
        db: Database = self.bot.db
        embed = Embed(title="Successfully enabled the command!")
        embed.description = f"{helpers.format_with_link('Command')} - "

        if cmd.children:
            await db.executemany(
                """
                DELETE FROM utility.disabled_commands 
                WHERE command_name = $1
                """,
                [(subcommand.qualified_name,) for subcommand in list(cmd.children.values())],
            )

            embed.description += ", ".join(
                [
                    f"</{subcommand.qualified_name}:{list(subcommand.command_ids.values())[0]}>"
                    for subcommand in list(cmd.children.values())
                ]
            )

        else:
            await db.execute(
                """
                DELETE FROM utility.disabled_commands 
                WHERE command_name = $1
                """,
                cmd.qualified_name,
            )
            embed.description += f"</{cmd.qualified_name}:{list(cmd.command_ids.values())[0]}>"
        await interaction.send(embed=embed)

    @nextcord.slash_command(name="reload-villagers", guild_ids=[constants.DEVS_SERVER_ID])
    async def reload_villagers(self, interaction: Interaction):
        """Reload the villagers used in /trade."""
        cog = self.bot.get_cog("Resource Repository")
        await cog.update_villagers.__call__()
        await interaction.send(embed=TextEmbed("Reloaded villagers."))

    async def emoji_autocomplete_callback(self, interaction: Interaction, data: str):
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
        interaction: Interaction,
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
            await interaction.send(embed=TextEmbed("The search term must be longer than 2 characters."))
        else:  # perform a search on emojis
            emojis_found = [
                emoji for emoji in bot_emojis if emoji_name.lower() in emoji.name.lower() or emoji_name == str(emoji.id)
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
                await interaction.send(embed=TextEmbed(f"No emojis are found for `{emoji_name}`."))


def setup(bot: commands.Bot):
    bot.add_cog(DevOnly(bot))

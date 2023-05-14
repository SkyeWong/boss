# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Embed, Interaction, SlashOption, ButtonStyle
from nextcord.ui import View, Button

# database
from utils.postgres_db import Database

import parsedatetime as pdt

# my modules and constants
from utils.player import Player
from utils import constants, helpers
from utils.helpers import MoveItemException, TextEmbed

# views and modals
from views.dev_views import (
    EditItemView,
    ConfirmItemDelete,
    ConfirmChangelogSend,
    ConfirmChangelogDelete,
    ConfirmChangelogEdit,
)

# default modules
from datetime import datetime
import random
from collections import defaultdict


class DevOnly(commands.Cog, name="Developer Dashboard"):
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

    async def choose_item_autocomplete(self, interaction: Interaction, data: str):
        sql = """
            SELECT name
            FROM utility.items
            ORDER BY name
        """
        db: Database = self.bot.db
        result = await db.fetch(sql)
        items = [i[0] for i in result]
        if not data:
            # return full list
            await interaction.response.send_autocomplete(items[:25])
            return
        else:
            # send a list of nearest matches from the list of item
            near_items = [item for item in items if data.lower() in item.lower()][:25]
            await interaction.response.send_autocomplete(near_items)

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
                embed=Embed(description="Either an internal error occured or you entered an incorrect user_id."),
                ephemeral=True,
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
                ephemeral=True,
            )
        else:
            if not await player.is_present():
                await interaction.send(
                    embed=TextEmbed(description="The user doesn't play BOSS! what a boomer."),
                    ephemeral=True,
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
                embed=Embed(description="Either an internal error occured or you entered an incorrect user_id."),
                ephemeral=True,
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
                ephemeral=True,
            )
        else:
            if not await player.is_present():
                await interaction.send(
                    embed=TextEmbed(description="The user doesn't play BOSS! what a boomer."),
                    ephemeral=True,
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
                embed=Embed(description="Either an internal error occured or you entered an incorrect user_id."),
                ephemeral=True,
            )
            return

        player = Player(self.bot.db, user)
        if not await player.is_present():
            await interaction.send(
                embed=Embed(description="The user doesn't play BOSS! what a boomer."),
                ephemeral=True,
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
            player = await interaction.client.fetch_user(player_id)
        except (nextcord.NotFound, nextcord.HTTPException, ValueError):
            await interaction.send(
                embed=Embed(description="Either an internal error occured or you entered an incorrect user_id."),
                ephemeral=True,
            )
            return
        db: Database = self.bot.db
        item = await db.fetchrow(
            """
            SELECT item_id, name, emoji_id
            FROM utility.items
            WHERE name ILIKE $1 or emoji_name ILIKE $1
            LIMIT 1
            """,
            f"%{item_name}%",
        )
        if item is None:
            await interaction.send(embed=Embed(description="The item is not found"), ephemeral=True)
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

                    inv_items = await db.fetch(
                        """
                        SELECT inv_type, item_id
                        FROM players.inventory
                        WHERE player_id = $1
                        """,
                        player_id,
                    )

                    num_of_items_in_inv = defaultdict(set)
                    for inv_item in inv_items:
                        num_of_items_in_inv[inv_item["inv_type"]].add(item["item_id"])

                    for i, items in num_of_items_in_inv.items():
                        # transaction has not been committed, items are not updated
                        if i == inv_type == 0 and len(items) >= 32 and item["item_id"] not in items:
                            raise MoveItemException("Backpacks only have 32 slots!")
                        if i == inv_type == 2 and len(items) >= 5 and item["item_id"] not in items:
                            raise MoveItemException("Vaults only have 5 slots!")

        except MoveItemException as e:
            await interaction.send(embed=TextEmbed(e.text), ephemeral=True)
            return

        inv_type_str = [i.name for i in constants.InventoryType if i.value == inv_type][0]
        embed = Embed(
            title=f"{interaction.user.name} **UPDATED** `{player.name}#{player.discriminator}'s {inv_type_str}`"
        )
        embed.add_field(name="Item", value=item["name"], inline=False)
        embed.add_field(
            name="Quantites",
            inline=False,
            value="```diff\n" f"- {quantities['old']}\n" f"+ {quantities['new']}\n" "```",
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
        emoji_name: str = SlashOption(required=True),
        emoji_id: str = SlashOption(required=True),
        rarity: int = SlashOption(
            choices=constants.ItemRarity.to_dict(),
            required=False,
            default=0,
        ),
        item_type: int = SlashOption(choices=constants.ItemType.to_dict(), required=False, default=0),
        buy_price: str = SlashOption(required=False, default="0", description="0 --> unable to be bought"),
        sell_price: str = SlashOption(required=False, default="0", description="0 --> unable to be sold"),
        trade_price: str = SlashOption(required=False, default="0", description="0 --> unknown value"),
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
        # if an error occured send a message and return the function
        if len(errors) > 0:
            embed = Embed()
            embed.set_author(name="The following error(s) occured:\n>>> ")
            embed.description = ""
            for index, error in enumerate(errors):
                embed.description += f"{index + 1}. {error}\n"
            await interaction.send(embed=embed, ephemeral=True)
            return

        db: Database = self.bot.db
        res = await db.fetch(
            """
            SELECT name
            FROM utility.items
            WHERE LOWER(name) ILIKE $1 OR LOWER(emoji_name) ILIKE $1
            """,
            f"%{name.lower()}%",
        )
        if len(res) > 0:
            await interaction.send(
                embed=Embed(description="An item with the same name exists. Rename the item."),
                ephemeral=True,
            )
            return

        try:
            item = await db.fetchrow(
                """
                INSERT INTO utility.items (name, description, emoji_name, emoji_id, buy_price, sell_price, trade_price, rarity, type)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING *
                """,
                name,
                description,
                emoji_name,
                emoji_id,
                prices["buy"],
                prices["sell"],
                prices["trade"],
                rarity,
                item_type,
            )
        except Exception as e:
            await interaction.send(
                "either you entered an invalid value or an internal error occured.",
                ephemeral=True,
            )
            raise e

        embed = helpers.get_item_embed(item)

        view = View()

        async def send_edit_item(interaction: Interaction):
            client: nextcord.Client = interaction.client
            cmds = client.get_all_application_commands()
            modify_cmd: nextcord.SlashApplicationCommand = [cmd for cmd in cmds if cmd.name == "modify"][0]
            edit_item_cmd = modify_cmd.children["item"].children["edit"]
            await edit_item_cmd.invoke_callback(interaction, item=item["name"])

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
        inherit_hooks=True,
    )
    async def edit_item(
        self,
        interaction: Interaction,
        item: str = SlashOption(
            description="The item to edit",
            autocomplete_callback=choose_item_autocomplete,
        ),
    ):
        db: Database = self.bot.db
        item = await db.fetchrow(
            """
            SELECT item_id, name, description, emoji_name, emoji_id, buy_price, sell_price, trade_price, rarity, type
            FROM utility.items
            WHERE name ILIKE $1 or emoji_name ILIKE $1
            ORDER BY name ASC
            """,
            f"%{item}%",
        )
        if not item:
            await interaction.send("The item is not found!", ephemeral=True)
        else:
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
        item = await db.fetchrow(
            """
            SELECT item_id, name, description, emoji_name, emoji_id, buy_price, sell_price, trade_price, rarity, type
            FROM utility.items
            WHERE name ILIKE $1 or emoji_name ILIKE $1
            ORDER BY name ASC
            """,
            f"%{item}%",
        )
        if not item:
            await interaction.send("The item is not found!", ephemeral=True)
        else:
            view = ConfirmItemDelete(interaction, item)
            await interaction.send(embed=view.embed, view=view)

    @nextcord.slash_command(name="changelog", guild_ids=[constants.DEVS_SERVER_ID])
    async def changelog(self, interaction: Interaction):
        """Send a new message, edit, or delete one in the BOSS changelog channel."""
        pass

    @changelog.subcommand(
        name="send",
        description="Notify users about a new change in the changelog.",
        inherit_hooks=True,
    )
    async def send_changelog(
        self,
        interaction: Interaction,
        content: str = SlashOption(
            description="The changes of the latest update",
            required=True,
            max_length=4096,
        ),
        title: str = SlashOption(description="Title of the changelog", required=False, max_length=256),
        image: nextcord.Attachment = SlashOption(
            description="Image of the changelog • will disappear after a few days",
            required=False,
        ),
        image_link: str = SlashOption(
            description="LINK of the changelog image • ignored if an image is uploaded • doesn't disappear",
            required=False,
        ),
        ping_role_id: str = SlashOption(
            name="ping-role-id",
            description="The id of the role to ping. Defaults to @Bot Changelog Ping. Type 'none' to NOT ping a role.",
            required=False,
        ),
        content_message_id: str = SlashOption(
            name="content-message-id",
            description="This passes the content of a message into the embed. This unsets the `content` parameter.",
            required=False,
        ),
    ):
        boss_server = await self.bot.fetch_guild(827537903634612235)
        if not ping_role_id:
            ping_role = boss_server.get_role(1020661085243719700)
        else:
            if ping_role_id.lower() == "none":
                ping_role = None
            else:
                try:
                    ping_role = boss_server.get_role(int(ping_role_id))
                except ValueError:
                    await interaction.send("Invalid role id! Try again.", ephemeral=True)
                    return
                if not ping_role:  # ping_role == None, the role isn't found
                    await interaction.send("The role does not exist! Try again.", ephemeral=True)
                    return
        if content_message_id:
            try:
                if not content_message_id.isnumeric():
                    await interaction.send("Invalid message id", ephemeral=True)
                    return
                message = await interaction.channel.fetch_message(int(content_message_id))
                content = message.content
                if not content:
                    await interaction.send("The message is empty/ only consists of embeds.", ephemeral=True)
            except (nextcord.NotFound, nextcord.Forbidden, nextcord.HTTPException) as e:
                if isinstance(e, nextcord.NotFound):
                    await interaction.send(
                        f"The message is not found, or it is not in this channel: {interaction.channel.mention}",
                        ephemeral=True,
                    )
                elif isinstance(e, nextcord.Forbidden):
                    await interaction.send(
                        "I do not have the correct permissions to get the message!",
                        ephemeral=True,
                    )
                elif isinstance(e, nextcord.HTTPException):
                    embed, view = helpers.get_error_message()
                    await interaction.send(embed=embed, view=view, ephemeral=True)
                return
        log_embed = Embed()
        log_embed.description = content
        log_embed.colour = random.choice(constants.EMBED_COLOURS)
        log_embed.set_footer(text="Bot Changelog")
        if title:
            log_embed.title = title
        if image:
            log_embed.set_image(url=image.url)
        elif image_link:
            log_embed.set_image(image_link)
        view = ConfirmChangelogSend(interaction, log_embed, ping_role if ping_role else None)
        await interaction.send(embed=view.embed, view=view)

    @changelog.subcommand(name="delete", description="Deletes a changelog message")
    async def delete_changelog(
        self,
        interaction: Interaction,
        message_id: str = SlashOption(
            name="message-id",
            description="The id of the message to delete",
            required=True,
        ),
    ):
        boss_server = await self.bot.fetch_guild(827537903634612235)
        try:
            changelog_channel = await boss_server.fetch_channel(1020660847321808930)
            if not message_id.isnumeric():
                await interaction.send("Invalid message id", ephemeral=True)
                return
            message = await changelog_channel.fetch_message(int(message_id))
            if message.author != self.bot.user:
                await interaction.send("I did not send this message!", ephemeral=True)
                return
            embed = message.embeds[0]
            if not embed.footer or embed.footer.text != "Bot Changelog":
                await interaction.send("This is not a bot changelog message.", ephemeral=True)
                return
        except (nextcord.NotFound, nextcord.Forbidden, nextcord.HTTPException) as e:
            if isinstance(e, nextcord.NotFound):
                await interaction.send("The message is not found!", ephemeral=True)
            elif isinstance(e, nextcord.Forbidden):
                await interaction.send(
                    "I do not have the correct permissions to get the message!",
                    ephemeral=True,
                )
            elif isinstance(e, nextcord.HTTPException):
                embed, view = helpers.get_error_message()
                await interaction.send(embed=embed, view=view, ephemeral=True)
            return
        view = ConfirmChangelogDelete(interaction, message)
        await interaction.send(embed=view.embed, view=view)

    @changelog.subcommand(
        name="edit",
        description="Edit an existing message in the changelog",
        inherit_hooks=True,
    )
    async def edit_changelog(
        self,
        interaction: Interaction,
        message_id: str = SlashOption(
            name="message-id",
            description="The id of the message to edit",
            required=True,
        ),
    ):
        client: nextcord.Client = interaction.client
        boss_server = await client.fetch_guild(827537903634612235)
        try:
            changelog_channel = await boss_server.fetch_channel(1020660847321808930)
            if not message_id.isnumeric():
                await interaction.send("Invalid message id", ephemeral=True)
                return
            message = await changelog_channel.fetch_message(int(message_id))
            if message.author != client.user:
                await interaction.send("I did not send this message!", ephemeral=True)
                return
            if not message.embeds:
                await interaction.send("This message doesn't have an embed", ephemeral=True)
                return
            embed = message.embeds[0]
            if not embed.footer or embed.footer.text != "Bot Changelog":
                await interaction.send("This is not a bot changelog message.", ephemeral=True)
                return
        except (nextcord.NotFound, nextcord.Forbidden, nextcord.HTTPException) as e:
            if isinstance(e, nextcord.NotFound):
                await interaction.send("The message is not found!", ephemeral=True)
            elif isinstance(e, nextcord.Forbidden):
                await interaction.send(
                    "I do not have the correct permissions to get the message!",
                    ephemeral=True,
                )
            elif isinstance(e, nextcord.HTTPException):
                embed, view = helpers.get_error_message()
                await interaction.send(embed=embed, view=view, ephemeral=True)
            return
        view = ConfirmChangelogEdit(interaction, message, embed)
        await interaction.send(embed=view.embed, view=view)

    def get_all_subcmd_names(
        self,
        cmd: nextcord.SlashApplicationCommand | nextcord.SlashApplicationSubcommand,
    ):
        cmd_names = []
        for subcmd in cmd.children.values():
            if subcmd.children:
                return self.get_all_subcmd_names(subcmd)
            else:
                cmd_names.append(subcmd.qualified_name)
        return cmd_names

    async def choose_base_commands_autocomplete(self, interaction: Interaction, data: str):
        client: nextcord.Client = interaction.client
        cmds = client.get_all_application_commands()
        cmds = [
            cmd.qualified_name
            for cmd in cmds
            if isinstance(cmd, nextcord.SlashApplicationCommand) or isinstance(cmd, nextcord.SlashApplicationSubcommand)
        ]
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
            f"> ID: `{command_id}`\n" f"> Mention syntax: <\/{command.qualified_name}:{command_id}>"
            if not command.children
            else ""
        )  # only show base command mention syntax if it has no subcommands

        subcmd_names = self.get_all_subcmd_names(interaction.guild_id, command)
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
        raise ZeroDivisionError

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

    def get_all_subcmd_names(self, guild_id: int, cmd):
        cmd_names = []
        for subcmd in cmd.children.values():
            base_cmd = cmd
            while not isinstance(base_cmd, nextcord.SlashApplicationCommand):
                base_cmd = base_cmd.parent_cmd
            cmd_in_guild = False
            if base_cmd.is_global:
                cmd_in_guild = True
            elif guild_id in base_cmd.guild_ids:
                cmd_in_guild = True
            if cmd_in_guild == True:
                cmd_names.append(subcmd.qualified_name)
            if len(subcmd.children) > 0:
                cmd_names.extend(self.get_all_subcmd_names(guild_id, subcmd))
        return cmd_names

    async def choose_all_commands_autocomplete(self, interaction: Interaction, data: str):
        base_cmds = interaction.client.get_all_application_commands()
        cmd_names = []
        for base_cmd in base_cmds:
            cmd_in_guild = False
            if base_cmd.is_global:
                cmd_in_guild = True
            elif interaction.guild_id in base_cmd.guild_ids:
                cmd_in_guild = True
            if cmd_in_guild == True:
                cmd_names.append(base_cmd.name)
            if hasattr(base_cmd, "children") and len(base_cmd.children) > 0:
                cmd_names.extend(self.get_all_subcmd_names(interaction.guild_id, base_cmd))
        cmd_names.sort()
        if not data:
            # return full list
            await interaction.response.send_autocomplete(cmd_names[:25])
        else:
            # send a list of nearest matches from the list of item
            near_items = [cmd for cmd in cmd_names if data.lower() in cmd.lower()]
            await interaction.response.send_autocomplete(near_items[:25])

    @nextcord.slash_command(name="disable-global", guild_ids=[constants.DEVS_SERVER_ID])
    async def disable_global(
        self,
        interaction: Interaction,
        command: str = SlashOption(
            description="The command to disable",
            required=True,
            autocomplete_callback=choose_all_commands_autocomplete,
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
        mapping = helpers.get_mapping(interaction, self.bot)

        command = command.strip()
        cmd_found = False
        for cog, commands in mapping.values():
            for i in commands:
                cmd_in_guild = False
                if i.is_global:
                    cmd_in_guild = True
                elif interaction.guild_id in i.guild_ids:
                    cmd_in_guild = True
                if cmd_in_guild:
                    if i.name == command:
                        cmd_found = True
                        cmd = i
                        break
                    else:
                        if hasattr(i, "children") and len(i.children) > 0:
                            cmd_found, cmd = self.search_subcommand(i, command)
                            if cmd_found:
                                break
            if cmd_found:
                break

        if cmd_found:
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
                    [
                        (subcommand.qualified_name, until, reason, extra_info)
                        for subcommand in list(cmd.children.values())
                    ],
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
        else:
            await interaction.send(embed=Embed("The command is not found!"))

    @nextcord.slash_command(name="enable-global", guild_ids=[constants.DEVS_SERVER_ID])
    async def enable_global(
        self,
        interaction: Interaction,
        command: str = SlashOption(
            description="The command to enable",
            required=True,
            autocomplete_callback=choose_all_commands_autocomplete,
        ),
    ):
        """Enable a command globally"""
        mapping = helpers.get_mapping(interaction, self.bot)

        command = command.strip()
        cmd_found = False
        for cog, commands in mapping.values():
            for i in commands:
                cmd_in_guild = False
                if i.is_global:
                    cmd_in_guild = True
                elif interaction.guild_id in i.guild_ids:
                    cmd_in_guild = True
                if cmd_in_guild:
                    if i.name == command:
                        cmd_found = True
                        cmd = i
                        break
                    else:
                        if hasattr(i, "children") and len(i.children) > 0:
                            cmd_found, cmd = self.search_subcommand(i, command)
                            if cmd_found:
                                break
            if cmd_found:
                break

        if cmd_found:
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
        else:
            await interaction.send(embed=Embed("The command is not found!"))

    @nextcord.slash_command(name="reload-villagers", guild_ids=[constants.DEVS_SERVER_ID])
    async def reload_villagers(self, interaction: Interaction):
        """Reload the villagers used in /trade."""
        cog = self.bot.get_cog("Resource Repository")
        await cog.update_villagers.__call__()
        await interaction.send(embed=TextEmbed("Reloaded villagers."))


def setup(bot: commands.Bot):
    bot.add_cog(DevOnly(bot))

# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Embed, Interaction, ButtonStyle, SelectOption
from nextcord.ui import View, Modal, Button, button, Select, select, TextInput

# default modules
import random

# database
from utils.postgres_db import Database
from asyncpg import Record

# my modules and constants
from utils.player import Player
from utils import functions, constants

from views.template_views import BaseView, ConfirmView


def _get_item_embed(item: Record):
    embed = Embed()
    embed.colour = random.choice(constants.EMBED_COLOURS)
    embed.title = item["name"]
    embed.description = f">>> _{item['description']}_"

    prices = {
        "buy": item["buy_price"],
        "sell": item["sell_price"],
        "trade": item["trade_price"],
    }

    prices_txt = ""
    for k, price in prices.items():
        if not price or price == 0:
            prices_txt += f"**{k.upper()}** - Unknown\n"
        else:
            prices_txt += f"**{k.upper()}** - ◎ {int(price):,}\n"
    embed.add_field(name="Prices", value=prices_txt, inline=False)

    # **rarity**
    # 0 - common
    # 1 - uncommon
    # 2 - rare
    # 3 - epic
    # 4 - legendary
    # 5 - godly
    rarity = ["common", "uncommon", "rare", "epic", "legendary", "godly"]
    embed.add_field(name="Rarity", value=rarity[item["rarity"]], inline=True)

    # **type**
    # 0 - tool
    # 1 - collectable
    # 2 - power-up
    # 3 - sellable
    # 4 - bundle
    types = ["tool", "collectable", "power-up", "sellable", "bundle"]
    embed.add_field(name="Type", value=types[item["type"]], inline=True)

    embed.add_field(
        name="Emoji",
        value=f"\<:{item['emoji_name']}:{item['emoji_id']}>",
        inline=False,
    )
    embed.add_field(name="ID (cannot be edited)", value=item["item_id"], inline=False)
    embed.set_thumbnail(url=f"https://cdn.discordapp.com/emojis/{item['emoji_id']}.png")
    return embed


class EditItemView(BaseView):
    def __init__(self, slash_interaction: Interaction, item: Record):
        super().__init__(interaction=slash_interaction, timeout=180)
        self.item = item

    def get_item_embed(self):
        return _get_item_embed(self.item)

    @button(label="Edit Names", style=ButtonStyle.blurple)
    async def edit_name(self, button: Button, interaction: Interaction):
        model = EditItemModal(self.interaction, self.item)
        await model.popuplate_inputs(
            include=("name", "description", "emoji_name", "emoji_id")
        )
        await interaction.response.send_modal(model)

    @button(label="Edit Prices")
    async def edit_price(self, button: Button, interaction: Interaction):
        model = EditItemModal(self.interaction, self.item)
        await model.popuplate_inputs(include=("buy_price", "sell_price", "trade_price"))
        await interaction.response.send_modal(model)

    @button(label="Edit Rarities and Types")
    async def edit_rarities_types(self, button: Button, interaction: Interaction):
        model = EditItemModal(self.interaction, self.item)
        await model.popuplate_inputs(include=("rarity", "type"))
        await interaction.response.send_modal(model)


class EditItemModal(Modal):
    def __init__(self, slash_interaction: Interaction, item: Record):
        self.slash_interaction = slash_interaction
        self.item = item

        super().__init__(
            title=f"Editing {self.item['name']}",
        )
        self.inputs = {}

    async def popuplate_inputs(
        self, *, include: tuple[str] = None, exclude: tuple[str] = None
    ):
        """Populate the modal's list of input, and include/exclude any columns that have been provided."""
        # typecast the tuples
        if include is None:
            include = tuple()
        if exclude is None:
            exclude = tuple()

        db: Database = self.slash_interaction.client.db
        # fetch the list of columns in `utility.items` table.
        res = await db.fetch(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'utility' AND table_name = 'items' AND column_name <> 'item_id';
        """
        )
        for column in res:
            column_name = column[0]
            # check if the column is included, and not excluded
            if (
                not include or column_name in include
            ) and column_name not in exclude:  # if no `include` list is provided, ignore that it is not included
                if column_name == "rarity":
                    value = [
                        i.name
                        for i in constants.ItemRarity
                        if i.value == self.item[column_name]
                    ][0]
                elif column_name == "type":
                    value = [
                        i.name
                        for i in constants.ItemType
                        if i.value == self.item[column_name]
                    ][0]
                else:
                    value = self.item[column_name]
                value = str(value)

                input = TextInput(
                    label=column_name,
                    # if the column is description set the style to `paragraph`
                    style=nextcord.TextInputStyle.paragraph
                    if column_name == "description"
                    else nextcord.TextInputStyle.short,
                    default_value=value,
                )

                # add the input to list of children of `nextcord.ui.Modal`
                self.inputs[column_name] = input
                self.add_item(input)

    async def callback(self, interaction: Interaction):
        errors = []
        values = {}

        for column, input in self.inputs.items():
            inputted_value: str = input.value

            # if value in one of these convert them from "2k" to 2000
            if column in ("buy_price", "sell_price", "trade_price"):
                try:
                    values[column] = functions.text_to_num(inputted_value)
                except functions.TextToNumException:
                    errors.append(
                        f"The `{column}` is not a valid number. Tip: use `2k` for _2,000_, `5m 4k` for _5,004,000_"
                    )

            if column in ("name", "description"):
                values[column] = inputted_value

            if column == "emoji_name":
                if len(inputted_value) > 30:
                    errors.append(
                        "The emoji's name must not be more than 30 characters in length."
                    )
                else:
                    values[column] = inputted_value

            if column == "emoji_id":
                if not inputted_value.isnumeric():
                    errors.append("The emoji's id is invalid")
                else:
                    values[column] = int(inputted_value)

            if column == "rarity":
                inputted_value = inputted_value.lower().strip()
                if inputted_value.isnumeric():
                    try:
                        values[column] = constants.ItemRarity(inputted_value).value
                    except:
                        errors.append(
                            "use numbers 0-5 respectively representing `common`, `uncommon`, `rare`, `epic`, `legendary`, `epic` only"
                        )
                else:
                    try:
                        values[column] = constants.ItemRarity[inputted_value].value
                    except KeyError:
                        errors.append(
                            "The rarity must be one of these: `common`, `uncommon`, `rare`, `epic`, `legendary`, `epic`"
                        )

            if column == "type":
                inputted_value = inputted_value.lower().strip()
                if inputted_value.isnumeric():
                    try:
                        values[column] = constants.ItemRarity(inputted_value).value
                    except:
                        errors.append(
                            "use numbers 0-4 respectively representing the types: `tool`, `collectable`, `power-up`, `sellable`, `bundle` only"
                        )
                else:
                    try:
                        values[column] = constants.ItemType[inputted_value].value
                    except KeyError:
                        errors.append(
                            "The type must be one of these: `tool`, `collectable`, `power-up`, `sellable`, `bundle`"
                        )

        # if it is an invalid value send a message and return the function
        if len(errors) > 0:
            embed = Embed()
            embed.set_author(name="The following error(s) occured:")
            embed.description = ""
            for index, error in enumerate(errors):
                embed.description += f"{index + 1}. {error}\n"
            await interaction.send(embed=embed, ephemeral=True)
            return

        inputted_values = [(column, value) for column, value in values.items()]
        changed_values = {
            column: value
            for column, value in inputted_values
            if value != self.item[column]
        }

        if not changed_values:
            await interaction.send(
                embed=Embed(description="You didn't change anything, did you."),
                ephemeral=True,
            )
            return

        try:
            db: Database = self.slash_interaction.client.db
            sql = (
                "UPDATE utility.items "
                "SET "
                f"{', '.join([f'{column} = ${i + 2}' for i, column in enumerate(changed_values)])} "
                "WHERE item_id = $1 "
                "RETURNING *"
            )  # basically add each changed column into the query
            new_item = await db.fetchrow(
                sql, self.item["item_id"], *changed_values.values()
            )

        except Exception as e:
            await interaction.send(
                "either you entered an invalid value or an internal error occured.",
                ephemeral=True,
            )
            raise e

        view = EditItemView(interaction, new_item)
        embed = view.get_item_embed()
        await interaction.edit(embed=embed, view=view)

        embed = Embed(
            title=f"**{interaction.user.name}** edited the following values of `{self.item['name']}`"
        )

        for column, changed_value in changed_values.items():
            old = str(self.item[column]).replace("\n", " ")
            new = str(changed_value).replace("\n", " ")
            embed.add_field(
                name=f"\n**`{column}`**",
                value=f"```diff\n" f"- {old}\n" f"+ {new}\n" f"```",
                inline=False,
            )

        await interaction.guild.get_channel(988046548309016586).send(embed=embed)


class ConfirmItemDelete(ConfirmView):
    def __init__(self, slash_interaction: Interaction, item: Record):
        self.item = item
        embed = _get_item_embed(item)
        embed.title = f"Delete `{item['name']}`?"

        super().__init__(
            slash_interaction=slash_interaction,
            confirm_func=self.delete_item,
            embed=embed,
            confirmed_title="Item deleted!",
        )

    async def delete_item(self, button: Button, interaction: Interaction):
        db: Database = interaction.client.db
        item_name = await db.fetchval(
            """
            DELETE FROM utility.items 
            WHERE item_id = $1
            RETURNING name
            """,
            self.item["item_id"],
        )
        await interaction.guild.get_channel(988046548309016586).send(
            f"{self.interaction.user.mention} deleted the item `{item_name}`"
        )


class ConfirmChangelogSend(ConfirmView):
    """Asks the user to confirm sending the message to changelog, then sends it (or not)."""

    def __init__(
        self,
        slash_interaction: Interaction,
        embed: Embed,
        ping_role: nextcord.Role = None,
    ):
        self.ping_role = ping_role
        self.changelog_embed = embed
        self.msg: nextcord.Message = None

        embed = Embed(
            title="Pending Confirmation",
            description="Send the message to <#1020660847321808930>?",
        )
        if self.ping_role:
            embed.add_field(
                name="Role to ping",
                value=f"{self.ping_role.name} ({self.ping_role.id})",
            )
        else:
            embed.add_field(name="Role to ping", value="No roles will be pinged")

        super().__init__(
            slash_interaction=slash_interaction,
            confirm_func=self.send_changelog,
            embed=embed,
        )

    async def send_edit_changelog(self, interaction: Interaction):
        client: nextcord.Client = interaction.client
        cmds = client.get_all_application_commands()
        changelog_cmd: nextcord.SlashApplicationCommand = [
            cmd for cmd in cmds if cmd.name == "changelog"
        ][0]
        edit_changelog_cmd = changelog_cmd.children["edit"]
        await edit_changelog_cmd.invoke_callback(
            interaction, message_id=str(self.msg.id)
        )

    async def send_delete_changelog(self, interaction: Interaction):
        client: nextcord.Client = interaction.client
        cmds = client.get_all_application_commands()
        changelog_cmd: nextcord.SlashApplicationCommand = [
            cmd for cmd in cmds if cmd.name == "changelog"
        ][0]
        delete_changelog_cmd = changelog_cmd.children["delete"]
        await delete_changelog_cmd.invoke_callback(
            interaction, message_id=str(self.msg.id)
        )

    async def send_changelog(
        self, button: Button, interaction: Interaction
    ):  # the confirm button will perform this action
        client: nextcord.Client = interaction.client
        changelog_channel = await client.fetch_channel(constants.CHANGELOG_CHANNEL_ID)
        # if content is set, it must not be empty (i.e. "")
        # therefore we use if_else
        if self.ping_role:
            self.msg = await changelog_channel.send(
                self.ping_role.mention, embed=self.changelog_embed
            )
        else:
            self.msg = await changelog_channel.send(embed=self.changelog_embed)

        view = View(timeout=None)
        jump_btn = Button(label="Jump", url=self.msg.jump_url)
        view.add_item(jump_btn)
        if client:
            edit_btn = Button(label="Edit", style=ButtonStyle.blurple)
            edit_btn.callback = self.send_edit_changelog
            view.add_item(edit_btn)
            delete_btn = Button(label="Delete", style=ButtonStyle.red)
            delete_btn.callback = self.send_delete_changelog
            view.add_item(delete_btn)
        await interaction.send(
            f"Sent message, the ID is `{self.msg.id}`", view=view, ephemeral=True
        )

    @button(label="View", row=1, style=ButtonStyle.grey)
    async def view_new_embed(self, button: Button, interaction: Interaction):
        await interaction.send(
            "The message looks like this:", embed=self.changelog_embed, ephemeral=True
        )


class ConfirmChangelogDelete(ConfirmView):
    """Asks the user to confirm deleting the message to changelog, then deletes it (or not)."""

    def __init__(self, slash_interaction: Interaction, message: nextcord.Message):
        embed = Embed(title="Pending Confirmation", description="Delete the message?")
        if message.edited_at:
            embed.add_field(
                name="Last edited at",
                value=f"<t:{int(message.edited_at.timestamp())}:f>",
            )
        else:
            embed.add_field(
                name="Sent at", value=f"<t:{int(message.created_at.timestamp())}:f>"
            )

        super().__init__(
            slash_interaction=slash_interaction,
            confirm_func=self.delete_changelog,
            embed=embed,
        )
        self.message = message
        self.changelog_embed = message.embeds[0]
        jump_btn = Button(label="Jump", url=message.jump_url)
        self.add_item(jump_btn)

    async def delete_changelog(
        self, button: Button, interaction: Interaction
    ):  # the confirm button will perform this action
        await self.message.delete()

    @button(label="View Message", row=1, style=ButtonStyle.grey)
    async def view_msg(self, button: Button, interaction: Interaction):
        await interaction.send(
            "The message looks like this:", embed=self.changelog_embed, ephemeral=True
        )


class ConfirmChangelogEdit(ConfirmView):
    """Asks the user to confirm sending the message to changelog, then sends it (or not).
    Also allows users to change the embed content.
    """

    def __init__(
        self,
        slash_interaction: Interaction,
        message: nextcord.Message,
        new_embed: Embed,
    ):
        self.message = message
        self.old_embed = message.embeds[0]
        self.new_embed = new_embed

        embed = Embed(title="Editing message...")
        if self.message.edited_at:
            embed.add_field(
                name="Last edited at",
                value=f"<t:{int(self.message.edited_at.timestamp())}:f>",
            )
        else:
            embed.add_field(
                name="Sent at",
                value=f"<t:{int(self.message.created_at.timestamp())}:f>",
            )

        embed.add_field(name="ID", value=f"`{self.message.id}`")

        super().__init__(
            slash_interaction=slash_interaction,
            confirm_func=self.edit_changelog,
            embed=embed,
        )

        jump_btn = Button(label="Jump", url=message.jump_url, row=1)
        self.add_item(jump_btn)

    async def send_edit_changelog(self, interaction: Interaction):
        client: nextcord.Client = interaction.client
        cmds = client.get_all_application_commands()
        changelog_cmd: nextcord.SlashApplicationCommand = [
            cmd for cmd in cmds if cmd.name == "changelog"
        ][0]
        edit_changelog_cmd = changelog_cmd.children["edit"]
        await edit_changelog_cmd.invoke_callback(
            interaction, message_id=str(self.message.id)
        )

    async def edit_changelog(
        self, button: Button, interaction: Interaction
    ):  # the confirm button will perform this action
        await self.message.edit(embed=self.new_embed)

        view = View(timeout=None)
        jump_btn = Button(label="Jump", url=self.message.jump_url)
        view.add_item(jump_btn)

        edit_btn = Button(label="Edit again...", style=ButtonStyle.blurple)
        edit_btn.callback = self.send_edit_changelog
        view.add_item(edit_btn)

        await interaction.send(
            "The message has successfully been edited!", view=view, ephemeral=True
        )

    @button(label="Edit", row=1, style=ButtonStyle.blurple)
    async def edit_embed(self, button: Button, interaction: Interaction):
        title = self.new_embed.title
        description = self.new_embed.description
        image_url = self.new_embed.image.url
        modal = EditChangelogModal(
            self.interaction, self.message, title, description, image_url
        )
        await interaction.response.send_modal(modal)

    @button(label="Old", row=1, style=ButtonStyle.grey)
    async def view_old_embed(self, button: Button, interaction: Interaction):
        await interaction.send(
            "The original message looks like this:",
            embed=self.old_embed,
            ephemeral=True,
        )

    @button(label="New", row=1, style=ButtonStyle.grey)
    async def view_new_embed(self, button: Button, interaction: Interaction):
        await interaction.send(
            "The edited message looks like this:", embed=self.new_embed, ephemeral=True
        )


class EditChangelogModal(Modal):
    """Asks the user for the title and description, then sends it to a View and confirm."""

    def __init__(
        self,
        slash_interaction: Interaction,
        message: nextcord.Message,
        embed_title: str = None,
        embed_content: str = None,
        embed_image: str = None,
    ):
        self.slash_interaction = slash_interaction
        self.message = message
        embed = message.embeds[0]

        super().__init__(title=f"Editing Changelog Message", timeout=None)

        self.embed_title = TextInput(
            label="Title",
            style=nextcord.TextInputStyle.short,
            required=False,
            default_value=embed.title if not embed_title else embed_title,
            max_length=256,
        )
        self.add_item(self.embed_title)

        self.embed_content = TextInput(
            label="Content",
            style=nextcord.TextInputStyle.paragraph,
            required=True,
            default_value=embed.description if not embed_content else embed_content,
            max_length=4000,
        )
        self.add_item(self.embed_content)

        self.embed_image = TextInput(
            label="Image",
            style=nextcord.TextInputStyle.short,
            required=False,
            default_value=embed.image.url if not embed_image else embed_image,
        )

        self.add_item(self.embed_image)

    async def callback(self, interaction: Interaction):
        await interaction.response.defer()
        title = self.embed_title.value
        content = self.embed_content.value
        image = self.embed_image.value
        new_embed = Embed()
        new_embed.description = content
        new_embed.colour = random.choice(constants.EMBED_COLOURS)
        new_embed.set_footer(text="Bot Changelog")
        if title:
            new_embed.title = title
        if image:
            new_embed.set_image(url=image)

        view = ConfirmChangelogEdit(self.slash_interaction, self.message, new_embed)
        confirm_embed = view.embed
        await self.slash_interaction.edit_original_message(
            embed=confirm_embed, view=view
        )

# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle, SelectOption
from nextcord.ui import Modal, Button, button, Select, select, TextInput

# database
from utils.postgres_db import Database
from asyncpg import Record

# my modules and constants
from utils import constants, helpers
from utils.constants import EmbedColour
from utils.helpers import TextEmbed

from utils.template_views import BaseView, ConfirmView

# default modules
import math
import json
from typing import Optional


def _get_item_embed(item: Record):
    embed = helpers.get_item_embed(item)

    embed.add_field(
        name="Emoji",
        value=f"` <:_:{item['emoji_id']}> `",
        inline=False,
    )
    embed.add_field(name="ID (cannot be edited)", value=item["item_id"], inline=False)
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
        await model.popuplate_inputs(include=("name", "description", "emoji_id"))
        await interaction.response.send_modal(model)

    @button(label="Edit Prices")
    async def edit_price(self, button: Button, interaction: Interaction):
        model = EditItemModal(self.interaction, self.item)
        await model.popuplate_inputs(include=("buy_price", "sell_price", "trade_price"))
        await interaction.response.send_modal(model)

    @button(label="Edit Other Attributes")
    async def edit_rarities_types(self, button: Button, interaction: Interaction):
        model = EditItemModal(self.interaction, self.item)
        await model.popuplate_inputs(include=("rarity", "type", "other_attributes"))
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
        self,
        *,
        include: Optional[tuple] = None,
        exclude: Optional[tuple] = None,
    ):
        """Populate the modal's list of input, and include/exclude any columns that have been provided."""
        # typecast the tuples
        if include is None:
            include = tuple()
        if exclude is None:
            exclude = tuple()

        for field, value in self.item.items():
            # check if the column is included, and not excluded
            if (
                not include or field in include
            ) and field not in exclude:  # if no `include` list is provided, ignore that it is not included
                if field == "rarity":
                    value = constants.ItemRarity(value)
                elif field == "type":
                    value = constants.ItemType(value)
                value = str(value)

                text_input = TextInput(
                    label=field,
                    # if the column is description set the style to `paragraph`
                    style=nextcord.TextInputStyle.paragraph
                    if field in ("description", "other_attributes")
                    else nextcord.TextInputStyle.short,
                    default_value=value,
                )

                # add the input to list of children of `nextcord.ui.Modal`
                self.inputs[field] = text_input
                self.add_item(text_input)

    async def callback(self, interaction: Interaction):
        errors = []
        values = {}

        for column, input in self.inputs.items():
            inputted_value: str = input.value

            # if value in one of these convert them from "2k" to 2000
            if column in ("buy_price", "sell_price", "trade_price"):
                try:
                    values[column] = helpers.text_to_num(inputted_value)
                except ValueError:
                    errors.append(
                        f"The `{column}` is not a valid number. Tip: use `2k` for _2,000_, `5m 4k` for _5,004,000_"
                    )

            if column in ("name", "description"):
                values[column] = inputted_value

            if column == "emoji_id":
                if not inputted_value.isnumeric():
                    errors.append("The emoji's id is invalid")
                else:
                    values[column] = int(inputted_value)

            if column == "rarity":
                inputted_value = inputted_value.strip().upper()
                if inputted_value.isnumeric():
                    try:
                        values[column] = constants.ItemRarity(inputted_value).value
                    except ValueError:
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
                inputted_value = inputted_value.strip().upper()
                if inputted_value.isnumeric():
                    try:
                        values[column] = constants.ItemRarity(inputted_value).value
                    except ValueError:
                        errors.append(
                            "use the following numbers to represent the item types:\n"
                            + "\n".join([f"> {int(i)} - {str(i)}" for i in constants.ItemType])
                        )
                else:
                    try:
                        values[column] = constants.ItemType[inputted_value].value
                    except KeyError:
                        errors.append(
                            "The type must be one of these:\n" + ", ".join([str(i) for i in constants.ItemType])
                        )

            values["other_attributes"] = {}
            if column == "other_attributes" and inputted_value != "":
                # we simply verify that the json is valid, we will not store the loaded json object.
                try:
                    _ = json.loads(inputted_value)
                except json.JSONDecodeError:
                    errors.append("The format of other attributes are invalid")
                else:
                    if not isinstance(_, dict):
                        errors.append("The other attributes should be in a dictionary format.")
                    else:
                        values["other_attributes"] = inputted_value

        # if it is an invalid value send a message and return the function
        if len(errors) > 0:
            embed = Embed()
            embed.set_author(name="The following error(s) occured:")
            embed.description = ""
            for index, error in enumerate(errors):
                embed.description += f"{index + 1}. {error}\n"
            await interaction.send(embed=embed, ephemeral=True)
            return

        changed_values = {column: value for column, value in values.items() if value != self.item[column]}

        if not changed_values:
            await interaction.send(
                embed=TextEmbed("No values are updated!"),
                ephemeral=True,
            )
            return

        try:
            db: Database = self.slash_interaction.client.db
            sql = (
                "UPDATE utility.items"
                + " SET "
                + ", ".join([f"{column} = ${i + 2}" for i, column in enumerate(changed_values)])
                + " WHERE item_id = $1 "
                + " RETURNING *"
            )  # basically add each changed column into the query
            new_item = await db.fetchrow(sql, self.item["item_id"], *changed_values.values())

        except Exception as e:
            # since only devs use this command, we can send them the whole error message
            await interaction.send(embed=TextEmbed(f"{e.__class__.__name__}: {e}", EmbedColour.WARNING), ephemeral=True)
            return

        view = EditItemView(interaction, new_item)
        embed = view.get_item_embed()
        await interaction.edit(embed=embed, view=view)

        embed = Embed(title=f"**{interaction.user.name}** edited the following values of `{self.item['name']}`")

        for column, changed_value in changed_values.items():
            old = str(self.item[column]).replace("\n", " ")
            new = str(changed_value).replace("\n", " ")
            embed.add_field(
                name=f"\n**`{column}`**",
                value=f"```diff\n- {old}\n+ {new}\n```",
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


class EmojiView(BaseView):
    def __init__(self, interaction: Interaction, emojis: list[nextcord.Emoji]):
        super().__init__(interaction=interaction, timeout=300)
        self.emojis = emojis

        self._page = 0
        self.update_select_options()

        self.emoji_index = 0

    @classmethod
    async def send(cls, interaction: Interaction, emojis: list[nextcord.Emoji]):
        view = cls(interaction, emojis)
        embed = view._get_embed()
        view.disable_buttons()

        await interaction.send(f"There are `{len(emojis)}` emojis.", embed=embed, view=view)

    async def update(self, interaction: Interaction):
        self.disable_buttons()
        embed = self._get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @property
    def displayed_emojis(self):
        return self.emojis[25 * self._page : 25 * (self._page + 1)]

    @property
    def page(self):
        return self._page

    @page.setter
    def page(self, new_page):
        self._page = new_page
        self.update_select_options()
        return self._page

    def update_select_options(self):
        emoji_select = [i for i in self.children if i.custom_id == "emoji_select"][0]
        emoji_select.options = [
            SelectOption(label=emoji.name, value=index, emoji=emoji)
            for index, emoji in enumerate(self.displayed_emojis)
        ]

    def _get_embed(self):
        embed = Embed()
        embed.set_author(
            name="Emoji Searcher:",
            icon_url=self.interaction.client.user.display_avatar.url,
        )

        emojis = self.displayed_emojis
        page = self.emoji_index

        emoji: nextcord.Emoji = emojis[page]

        embed.colour = EmbedColour.DEFAULT
        embed.set_footer(
            text=f"Page {page + 1}/{len(emojis)} • List {self.page + 1}/{math.ceil(len(self.emojis) / 25)}"
        )  # + 1 because self.page uses zero-indexing
        embed.set_thumbnail(url=emoji.url)

        embed.title = f"`{page + 1}` - click for emoji"
        embed.url = emoji.url
        embed.description = str(emoji)

        embed.add_field(
            name=f"\:{emoji.name}:",
            value=f">>> ➼ `Name` - \:{emoji.name}:"
            f"\n➼ `Guild` - {emoji.guild.name}"
            f"\n➼ `ID`    - {emoji.id}"
            f"\n➼ `Url`   - {emoji.url}"
            f"\n➼ `Mention syntax` - ` {str(emoji)} `",
        )
        return embed

    def disable_buttons(self):
        back_btn = [i for i in self.children if i.custom_id == "back"][0]
        first_btn = [i for i in self.children if i.custom_id == "first"][0]
        if self.emoji_index == 0:
            back_btn.disabled = True
            first_btn.disabled = True
        else:
            back_btn.disabled = False
            first_btn.disabled = False

        next_btn = [i for i in self.children if i.custom_id == "next"][0]
        last_btn = [i for i in self.children if i.custom_id == "last"][0]
        if self.emoji_index == len(self.displayed_emojis) - 1:
            next_btn.disabled = True
            last_btn.disabled = True
        else:
            next_btn.disabled = False
            last_btn.disabled = False

        less_btn = [i for i in self.children if i.custom_id == "less"][0]
        if self.page == 0:
            less_btn.disabled = True
        else:
            less_btn.disabled = False

        more_btn = [i for i in self.children if i.custom_id == "more"][0]
        if self.page == math.ceil(len(self.emojis) / 25) - 1:
            more_btn.disabled = True
        else:
            more_btn.disabled = False

    @select(placeholder="Choose an emoji...", custom_id="emoji_select")
    async def choose_video(self, select: Select, interaction: Interaction):
        self.emoji_index = int(select.values[0])  # the value is set to the index of the emoji
        await self.update(interaction)

    @button(emoji="⏮️", style=ButtonStyle.blurple, custom_id="first", disabled=True)
    async def first(self, button: Button, interaction: Interaction):
        self.emoji_index = 0
        await self.update(interaction)

    @button(emoji="◀️", style=ButtonStyle.blurple, disabled=True, custom_id="back")
    async def back(self, button: Button, interaction: Interaction):
        self.emoji_index -= 1
        await self.update(interaction)

    @button(emoji="▶️", style=ButtonStyle.blurple, custom_id="next")
    async def next(self, button: Button, interaction: Interaction):
        self.emoji_index += 1
        await self.update(interaction)

    @button(emoji="⏭️", style=ButtonStyle.blurple, custom_id="last")
    async def last(self, button: Button, interaction: Interaction):
        self.emoji_index = len(self.displayed_emojis) - 1
        await self.update(interaction)

    @button(label="Previous list", style=ButtonStyle.gray, custom_id="less", row=2)
    async def less(self, button: Button, interaction: Interaction):
        self.page -= 1
        self.emoji_index = 0  # reset the page because its a new page
        await self.update(interaction)

    @button(label="Next list", style=ButtonStyle.gray, custom_id="more", row=2)
    async def more(self, button: Button, interaction: Interaction):
        self.page += 1
        self.emoji_index = 0  # reset the page because its a new page
        await self.update(interaction)

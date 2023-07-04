# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle, SelectOption
from nextcord.ui import Button, button, Select, select

# database
import asyncpg
from utils.postgres_db import Database

# my modules and constants
from utils.template_views import BaseView
from utils.player import Player
from utils import constants, helpers
from utils.helpers import TextEmbed
from utils.constants import EmbedColour

# default modules
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import pytz
import re
from collections import Counter
from datetime import datetime, timedelta
import math
from string import ascii_uppercase


async def _get_farm_embed_and_img(
    player: Player,
    farm,
    farm_width,
    farm_height,
    *,
    embed: Embed = None,
    label_crops: bool = False,
    selected_crops: list[int] = None,
):
    """
    ### Usage
    Returns a `dict` containing the following key-value pairs:
        `embed`: embed_of_farm
        `file`: farm_image

    ### Parameters
    `player`: `Player`
    `farm`: value obtained from the database (`players.farm.farm`)
    `farm_width`: value obtained from the database (`players.farm.width`)
    `embed`: `Embed` containing default titles, fields, etc. The description will be cleared.
    `selected_crops`: list of indices of crops that will be highlighted with a red rectangle
    """
    if selected_crops is None:
        selected_crops = []
    if embed is None:
        embed = Embed()
        embed.set_author(name=f"{player.user.name}'s Farm")
    embed.colour = constants.EmbedColour.DEFAULT

    db: Database = player.db
    crop_types = await db.fetch(
        """
        SELECT crop_type_id, name, growth_period
        FROM utility.crop_types
        """
    )

    TILE_SIZE = 128  # width, height of tiles

    embed.description = ""
    farm_img = Image.new("RGBA", (farm_width * TILE_SIZE, farm_height * TILE_SIZE))

    x = y = 0  # top-left corner of crop image to be pasted in

    now = datetime.now(tz=pytz.UTC)

    for index, crop in enumerate(farm):
        if crop:
            # find the relevant crop type
            crop_type = [crop_type for crop_type in crop_types if crop_type["crop_type_id"] == crop["type"]][0]

            planted_at: datetime = crop["planted_at"]
            ready_at: datetime = planted_at + crop_type["growth_period"]

            # check if the crop has finished growing
            if now < ready_at:  # crop has not finished growing
                # unready crops have 2 stages (0 and 1)
                # this will choose 1 of them based on how long they have been growing
                growth_stage = (now - planted_at) / crop_type["growth_period"] * 2
                growth_stage = math.floor(growth_stage)

            else:  # crop has finished growing
                growth_stage = 2

            # paste the crop image into the farm image
            tile_img = Image.open(f"resources/crops/{crop_type['name']}_{growth_stage}.png")

        else:
            # tile is empty, paste farm_empty image
            tile_img = Image.open("resources/crops/farm_empty.png")

        # add a red rectangle into the image if the index is in the list of selected_crops
        if index in selected_crops:
            crop_draw = ImageDraw.Draw(tile_img)
            # the image here is image of crop/empty tile, not `farm_img`
            crop_draw.rectangle(
                [
                    (10, 10),
                    (TILE_SIZE - 10, TILE_SIZE - 10),
                ],  # top-left and bottom-right coords for the rectangle
                outline="#58091F",
                width=10,
            )

        # add a small label in bottom right corner of crop if `label_crops` is True
        if label_crops:
            crop_draw = ImageDraw.Draw(tile_img)
            label = f"{ascii_uppercase[index // farm_width]}" f"{index % farm_width + 1}"  # example label: A1

            font = ImageFont.truetype("resources/font/font.ttf", 24)
            txt_width, txt_height = font.getsize(label)

            # draw a background rectangle
            crop_draw.rounded_rectangle(
                (
                    (TILE_SIZE - 5 - txt_width - 5, TILE_SIZE - 5 - txt_height - 5),
                    (TILE_SIZE - 5, TILE_SIZE - 5),
                ),  # top-left and bottom-right coords for the rectangle, create a rectangle with 5px padding around the text
                fill="#1e130e",
                radius=5,
            )

            # draw the label
            # same as the rectangle, the image here is image of crop/empty tile, not `farm_img`
            # text will be white by default
            crop_draw.text(
                (TILE_SIZE - 5 - txt_width - 2, TILE_SIZE - 5 - txt_height - 5),
                text=label,
                font=font,
            )

        farm_img.paste(tile_img, (x, y))

        x += TILE_SIZE
        # change to a new row. x % 3 should be modified to show number of columns in farm, not hard-coded
        if x / TILE_SIZE == farm_width:
            x = 0
            y += TILE_SIZE

    output = BytesIO()
    farm_img.save(output, format="PNG")
    output.seek(0)

    file = nextcord.File(output, "farm.png")
    embed.set_image("attachment://farm.png")

    return dict(embed=embed, file=file)


class FarmView(BaseView):

    """
    The main page of the `/farm` command.

    Inherited from `BaseView` (subclass of `nextcord.View`)
    """

    def __init__(self, interaction: Interaction, player: Player):
        super().__init__(interaction, timeout=180)
        self.player = player

        self.farm = None
        self.farm_width = None
        self.farm_height = None

        self.is_set_up = False

        self.msg: nextcord.PartialInteractionMessage | nextcord.WebhookMessage = None

    async def set_up(self):
        """
        Setups the view.

        Will be run automatically if message is sent by `FarmView.send_message()`.

        Otherwise, it needs to be run manually.
        """
        self.is_set_up = True
        res = await self.player.get_farm()

        if res is None:
            self.farm = self.farm_width = self.farm_height = None
        else:
            self.farm, self.farm_width, self.farm_height = res

    async def get_msg(self, embed: Embed = None, **kwargs):
        if not embed:
            embed = Embed()
        embed.set_author(name=f"{self.player.user.name}'s Farm")

        msg = await _get_farm_embed_and_img(
            self.player,
            self.farm,
            self.farm_width,
            self.farm_height,
            embed=embed,
            **kwargs,
        )
        msg.update(view=self)
        return msg

    async def send_message(self, interaction: Interaction, with_view: bool = True):
        # Check if the player exists
        if not await self.player.is_present():
            await interaction.send(
                embed=TextEmbed("The user hasn't started playing BOSS yet! Maybe invite them over?"),
                ephemeral=True,
            )
            return

        await self.set_up()

        # Check if the player has started his farm
        if not self.farm:
            await interaction.send(embed=TextEmbed("The user hasn't started his/her farm yet!"))
            return

        # All checks succeeded, send the message with the view
        msg = await self.get_msg()
        if not with_view:
            msg.update(view=nextcord.utils.MISSING)

        self.msg = await interaction.send(**msg)

    @button(label="Plant", style=ButtonStyle.blurple)
    async def plant(self, button: Button, interaction: Interaction):
        """Turn to a new page, `PlantView`, which allows users to plant the crops."""
        view = PlantView(self.interaction, self.player, self.farm, self.farm_width, self.farm_height)
        await view.update_components()
        await interaction.response.edit_message(**await view.get_msg())

    @button(label="Harvest", style=ButtonStyle.blurple)
    async def harvest(self, button: Button, interaction: Interaction):
        """Turn to a new page, `HarvestView`, which allows users to harvest the crops."""
        view = HarvestView(self.interaction, self.player, self.farm, self.farm_width, self.farm_height)
        await view.update_components()
        await interaction.response.edit_message(**await view.get_msg())

    @button(label="Progress")
    async def progress(self, button: Button, interaction: Interaction):
        crop_types = await self.player.db.fetch(
            """
            SELECT crop_type_id AS id, name, growth_period, CONCAT('<:', grown_emoji_name, ':', grown_emoji_id, '>') AS emoji
            FROM utility.crop_types
            """
        )

        embed = Embed()
        now = datetime.now(tz=pytz.UTC)

        max_tile_length = len(str(self.farm_width * self.farm_height))

        ready_msg = ""
        unready_msg = ""

        for index, crop in enumerate(self.farm):
            if crop:
                # find the relevant crop type
                crop_type = [crop_type for crop_type in crop_types if crop_type["id"] == crop["type"]][0]

                planted_at: datetime = crop["planted_at"]
                ready_at: datetime = planted_at + crop_type["growth_period"]

                # update the embed description to show the crop's progress (i.e. when it will be ready)
                if now < ready_at:
                    # crop has not fully grown
                    unready_msg += f"` {index + 1: >{max_tile_length}} ` {crop_type['emoji']} **{crop_type['name'].capitalize()}** ready <t:{int(ready_at.timestamp())}:R>\n"
                else:
                    # crop has fully grown
                    ready_msg += f"_` {index + 1: >{max_tile_length}} `_ {crop_type['emoji']} **{crop_type['name'].capitalize()}** ready to harvest!\n"

        if not (ready_msg or unready_msg):
            embed.description = "No crops are planted!"

        if ready_msg:
            embed.add_field(name="Crops ready to harvest", value=ready_msg)
        if unready_msg:
            embed.add_field(name="Crops not ready yet", value=unready_msg)

        await interaction.send(embed=embed, ephemeral=True)

    async def upgrade_farm(self, new_width, new_height):
        pass

    @button(label="Upgrade")
    async def upgrade_farm_btn(self, button: Button, interaction: Interaction):
        """Increase the user's farm size."""
        # TODO: make upgrade requirements

        if self.farm_width * self.farm_height == 12:
            await interaction.send(embed=TextEmbed("Max size reached!"), ephemeral=True)
            return

        # Should result in farm sizes which are either
        #   1. square
        #   2. a rectangle where the height is larger than width by 1
        # Eg. (2, 2) --> (2, 3) --> (3, 3)

        if self.farm_width < self.farm_height:
            self.farm_width += 1
        else:
            self.farm_height += 1

        await interaction.client.db.execute(
            """
            UPDATE players.farm
            SET farm = $1, width = $2, height = $3
            WHERE player_id = $4
            """,
            [None] * (self.farm_width * self.farm_height),
            self.farm_width,
            self.farm_height,
            interaction.user.id,
        )

        # Refreshes the view
        view = FarmView(interaction, self.player)
        await view.set_up()

        await interaction.response.edit_message(**await view.get_msg())

        await interaction.send(
            embed=TextEmbed(f"Farm size is now increased to `{view.farm_width}x{view.farm_height}`!"),
            ephemeral=True,
        )

    @button(emoji="🔄")
    async def refresh_view(self, button: Button, interaction: Interaction):
        """Refresh the page."""
        view = FarmView(interaction, self.player)
        await view.set_up()

        await interaction.response.edit_message(
            **await self.get_msg(),
        )

    async def interaction_check(self, interaction: Interaction) -> bool:
        if not self.is_set_up:  # halt the interaction if `FarmView` is not set up
            embed, view = helpers.get_error_message()
            await interaction.send(embed=embed, view=view, ephemeral=True)
            return False

        return await super().interaction_check(interaction)


class PlantView(BaseView):

    """The **plant** page of the `/farm` command. Allows players to plant their crops."""

    def __init__(self, interaction: Interaction, player: Player, farm, farm_width, farm_height):
        super().__init__(interaction, timeout=180)

        self.player = player  # only the user itself should be able to access `PlantView`
        self.farm = farm
        self.farm_width = farm_width
        self.farm_height = farm_height

        self.crops_to_plant = None
        self.type_to_plant = None

    async def update_components(self):
        """Update the view's select options and buttons. Should be run before sending the message."""
        # update the crops_select select options and select_all button
        crops_select = [i for i in self.children if i.custom_id == "crops_select"][0]
        select_all_btn = [i for i in self.children if i.custom_id == "select_all"][0]

        crops_select.options = []

        for index, crop in enumerate(self.farm):
            if crop is None:  # check if the tile is empty
                label = (
                    f"{ascii_uppercase[index // self.farm_width]}" f"{index % self.farm_width + 1}"
                )  # example label: A1
                crops_select.options.append(
                    SelectOption(
                        label=label,
                        value=index,
                        default=index in self.crops_to_plant if self.crops_to_plant else False,
                    )
                )

        # if there are no empty tiles, show "select all (0)"
        # if user has selected no tiles, show "select all(number of available tiles)"
        # if user has selected at least 1 tiles, show "deselect all"
        if self.crops_to_plant:
            select_all_btn.disabled = False
            select_all_btn.label = "Deselect all"
        elif crops_select.options:
            select_all_btn.disabled = False
            select_all_btn.label = f"Select all empty tiles ({len(crops_select.options)})"
        else:
            select_all_btn.disabled = True
            select_all_btn.label = f"Select all empty tiles (0)"

        if not crops_select.options:  # there are no empty tiles, so we disable the select menus
            crops_select.placeholder = "No empty tiles"
            crops_select.options = [
                SelectOption(label="1")
            ]  # dummy select options, if `options` list is empty an error will be raised.
            crops_select.max_values = 1
            crops_select.disabled = True
        else:
            crops_select.max_values = len(crops_select.options)
            crops_select.disabled = False

        # update the type_select select options
        type_select = [i for i in self.children if i.custom_id == "type_select"][0]
        type_select.options = []

        crop_types = await self.player.db.fetch(
            """
            SELECT crop_type_id AS id, name, growth_period, grown_emoji_name AS emoji_name, grown_emoji_id AS emoji_id
            FROM utility.crop_types
            """
        )

        for crop_type in crop_types:
            type_select.options.append(
                SelectOption(
                    label=f"{crop_type['name'].capitalize()} ({crop_type['growth_period']})",
                    value=crop_type["id"],
                    emoji=f"<:{crop_type['emoji_name']}:{crop_type['emoji_id']}>",
                    default=crop_type["id"] == self.type_to_plant,
                )
            )

        # update whether plant button is disabled
        if self.crops_to_plant and self.type_to_plant:
            plant_btn = [i for i in self.children if i.custom_id == "plant_btn"][0]
            plant_btn.disabled = False

    async def get_msg(self, embed: Embed = None, **kwargs):
        if not embed:
            embed = Embed()
        embed.set_author(name=f"{self.interaction.user.name}'s Farm • Planting")
        embed.set_footer(text="Choose BOTH the tiles and types of crops to plant.")

        msg = await _get_farm_embed_and_img(
            self.player,
            self.farm,
            self.farm_width,
            self.farm_height,
            embed=embed,
            label_crops=True,
            **kwargs,
        )
        msg.update(view=self)
        return msg

    async def on_timeout(self) -> None:
        """Return to the main page."""
        view = FarmView(self.interaction, self.player)
        await view.set_up()

        msg = await view.get_msg()
        for item in msg["view"].children:
            item.disabled = True  # disable the items of the view
        await self.interaction.edit_original_message(**msg)

    @select(placeholder="Choose the tiles...", custom_id="crops_select", min_values=1)
    async def choose_tiles(self, select: Select, interaction: Interaction):
        self.crops_to_plant = [int(value) for value in select.values]

        await self.update_components()

        # make the select menu "sticky"
        for option in select.options:
            option.default = False
            if str(option.value) in select.values:
                option.default = True

        await interaction.response.edit_message(**await self.get_msg(selected_crops=self.crops_to_plant))

    @select(
        placeholder="Choose the crops to plant...",
        custom_id="type_select",
        min_values=1,
        max_values=1,
    )
    async def choose_crop_type(self, select: Select, interaction: Interaction):
        self.type_to_plant = int(select.values[0])

        embed = Embed()

        await self.update_components()

        # make the select menu "sticky"
        for option in select.options:
            option.default = False
            if str(option.value) in select.values:
                option.default = True
                embed.add_field(name="Planting", value=f"{option.emoji} **{option.label}**")

        await interaction.response.edit_message(**await self.get_msg(embed, selected_crops=self.crops_to_plant))

    @button(
        label="Select all empty tiles",
        style=ButtonStyle.blurple,
        custom_id="select_all",
    )
    async def choose_all_empty_tiles(self, button: Button, interaction: Interaction):
        if self.crops_to_plant:  # deselect all
            self.crops_to_plant = []
        else:  # select all
            empty_tiles = [i for i, crop in enumerate(self.farm) if crop is None]

            if not empty_tiles:
                await interaction.send(
                    embed=TextEmbed(
                        "There are no empty tiles! Harvest crops that are unready to remove them.", EmbedColour.WARNING
                    ),
                    ephemeral=True,
                )
                return

            self.crops_to_plant = empty_tiles

        await self.update_components()

        await interaction.response.edit_message(**await self.get_msg(selected_crops=self.crops_to_plant))

    @button(label="Go Back", row=3)
    async def return_to_main_view(self, button: Button, interaction: Interaction):
        """Return the the main `FarmView` page."""
        view = FarmView(interaction, self.player)
        await view.set_up()

        await interaction.response.edit_message(**await view.get_msg())

    @button(
        label="Plant",
        style=ButtonStyle.green,
        custom_id="plant_btn",
        row=3,
        disabled=True,
    )
    async def plant_crops(self, button: Button, interaction: Interaction):
        """Plant the crops and update the database."""
        # If this button is not disabled,
        # then both `self.crops_to_plant` and `self.type_to_plant` should be filled by values.
        # Therefore, we need not check whether they are not `None`.

        self.farm, self.farm_width, self.farm_height = await self.player.get_farm()

        planted_crops = 0

        # alter `self.farm` to "plant" the crops
        for index, crop in enumerate(self.farm):
            if index in self.crops_to_plant:
                if crop is None:
                    self.farm[index] = {
                        "type": self.type_to_plant,
                        "planted_at": datetime.now(tz=pytz.UTC),
                    }
                    planted_crops += 1
                else:  # the tile is actually filled, the user must have used 2 views at the same time
                    await interaction.send(
                        embed=TextEmbed("You can only plant crops in empty tiles!"),
                        ephemeral=True,
                    )
                    return

        farm_for_query = []
        for crop in self.farm:
            if isinstance(crop, (dict, asyncpg.Record)):
                # farm is list[asyncpg.Record], to make it valid for database query we need to change it to tuple
                farm_for_query.append(tuple(crop.values()))
            else:
                farm_for_query.append(crop)

        # update the database
        await self.player.db.execute(
            """
            UPDATE players.farm
            SET farm = $1
            WHERE player_id = $2
            """,
            farm_for_query,
            interaction.user.id,
        )

        # return to the main page
        view = FarmView(interaction, self.player)
        await view.set_up()

        await interaction.response.edit_message(**await view.get_msg())

        # find the name and emoji of the crop type
        # the default option is the one the user chose, so here we fetch that and get its label and emoji
        type_select = [i for i in self.children if i.custom_id == "type_select"][0]
        type_name, type_emoji = [
            (option.label, option.emoji) for option in type_select.options if option.default == True
        ][0]
        # `type_name` will now be "Carrot (0:30:00)"
        type_name = re.sub(r" \(.+\)", "", type_name)
        # `type_name` will now be "Carrot"
        await interaction.send(
            embed=TextEmbed(f"Planted {planted_crops} **{type_name}** {type_emoji}!"),
            ephemeral=True,
        )


class HarvestView(BaseView):

    """
    The **harvest** page of the `/farm` command.

    Allows players to harvest their ready crops, or remove their crops which are not grown.
    """

    def __init__(self, interaction: Interaction, player: Player, farm, farm_width, farm_height):
        super().__init__(interaction, timeout=180)

        self.player = player  # only the user itself should be able to access `HarvestView`
        self.farm = farm
        self.farm_width = farm_width
        self.farm_height = farm_height

        self.crops_to_harvest = None

    async def update_components(self):
        """Update the view's select options and buttons. Should be run before sending the message."""
        crops_select = [i for i in self.children if i.custom_id == "crops_select"][0]
        crops_select.options = []

        for index, crop in enumerate(self.farm):
            if crop is not None:
                label = (
                    f"{ascii_uppercase[index // self.farm_width]}" f"{index % self.farm_width + 1}"
                )  # example label: A1
                crops_select.options.append(
                    SelectOption(
                        label=label,
                        value=index,
                        default=index in self.crops_to_harvest if self.crops_to_harvest else False,
                    )
                )

        if not crops_select.options:  # if every tile is empty, we disable the select menus
            crops_select.placeholder = "No planted tiles"
            crops_select.options = [
                SelectOption(label="1")
            ]  # dummy select options, if `options` list is empty an error will be raised.
            crops_select.max_values = 1

            crops_select.disabled = True
        else:
            crops_select.max_values = len(crops_select.options)

            crops_select.disabled = False

        ready_tiles = []

        crop_types = await self.player.db.fetch(
            """
            SELECT crop_type_id AS id, name, growth_period
            FROM utility.crop_types
            """
        )

        now = datetime.now(tz=pytz.UTC)

        for index, crop in enumerate(self.farm):
            if crop is not None:
                # find the relevant crop type
                crop_type = [crop_type for crop_type in crop_types if crop_type["id"] == crop["type"]][0]

                # check if it has passed the `ready_at` time, which means the crop is ready to be harvested.
                ready_at: datetime = crop["planted_at"] + crop_type["growth_period"]

                if now > ready_at:
                    ready_tiles.append(index)

        select_all_btn = [i for i in self.children if i.custom_id == "select_all_ready"][0]

        if not ready_tiles:  # if there are no full grown tiles, we disable the select_all btn
            select_all_btn.disabled = True
            select_all_btn.label = f"Select all ready tiles (0)"
        else:
            select_all_btn.disabled = False

            if self.crops_to_harvest:
                select_all_btn.label = "Deselect all"
            else:
                select_all_btn.label = f"Select all ready tiles ({len(ready_tiles)})"

        # update whether harvest button is disabled
        if self.crops_to_harvest:
            harvest_btn = [i for i in self.children if i.custom_id == "harvest_btn"][0]
            harvest_btn.disabled = False

    async def get_msg(self, embed: Embed = None, **kwargs):
        if not embed:
            embed = Embed()
        embed.set_author(name=f"{self.interaction.user.name}'s Farm • Harvesting")
        embed.set_footer(text="Harvest fully grown crops and remove those which are not ready yet!")

        msg = await _get_farm_embed_and_img(
            self.player,
            self.farm,
            self.farm_width,
            self.farm_height,
            embed=embed,
            label_crops=True,
            **kwargs,
        )
        msg.update(view=self)
        return msg

    async def on_timeout(self) -> None:
        """Return to the main page."""
        view = FarmView(self.interaction, self.player)
        await view.set_up()

        msg = await view.get_msg()
        for item in msg["view"].children:
            item.disabled = True  # disable the items of the view

        await self.interaction.edit_original_message(**msg)

    @select(placeholder="Choose the tiles...", custom_id="crops_select", min_values=1)
    async def choose_tiles(self, select: Select, interaction: Interaction):
        self.crops_to_harvest = [int(value) for value in select.values]

        await self.update_components()

        await interaction.response.edit_message(**await self.get_msg(selected_crops=self.crops_to_harvest))

    @button(
        label="Select all ready tiles",
        style=ButtonStyle.blurple,
        custom_id="select_all_ready",
    )
    async def choose_all_ready_tiles(self, button: Button, interaction: Interaction):
        if self.crops_to_harvest:  # deselect all
            self.crops_to_harvest = []
        else:  # select all
            ready_tiles = []

            crop_types = await self.player.db.fetch(
                """
                SELECT crop_type_id AS id, name, growth_period
                FROM utility.crop_types
                """
            )

            now = datetime.now(tz=pytz.UTC)

            for index, crop in enumerate(self.farm):
                if crop is not None:
                    # find the relevant crop type
                    crop_type = [crop_type for crop_type in crop_types if crop_type["id"] == crop["type"]][0]

                    # check if it has passed the `ready_at` time, which means the crop is ready to be harvested.
                    ready_at: datetime = crop["planted_at"] + crop_type["growth_period"]

                    if now > ready_at:
                        ready_tiles.append(index)

            if not ready_tiles:
                await interaction.send(
                    embed=TextEmbed("There are no fully grown crops!"),
                    ephemeral=True,
                )
                return

            self.crops_to_harvest = ready_tiles

        await self.update_components()

        await interaction.response.edit_message(**await self.get_msg(selected_crops=self.crops_to_harvest))

    @button(label="Go Back", row=3)
    async def return_to_main_view(self, button: Button, interaction: Interaction):
        """Return the the main `FarmView` page."""
        view = FarmView(interaction, self.player)
        await view.set_up()

        await interaction.response.edit_message(**await view.get_msg())

    @button(
        label="Harvest",
        style=ButtonStyle.green,
        custom_id="harvest_btn",
        row=3,
        disabled=True,
    )
    async def harvest_crops(self, button: Button, interaction: Interaction):
        """Harvest the crops and update the database."""
        # If this button is not disabled,
        # then both `self.crops_to_harvest` should be filled by values.
        # Therefore, we need not check whether it is not `None`.

        self.farm, self.farm_width, self.farm_height = await self.player.get_farm()

        crop_types = await self.player.db.fetch(
            """
            SELECT crop_type_id AS id, name, growth_period, CONCAT('<:', grown_emoji_name, ':', grown_emoji_id, '>') AS emoji, grown_item_id AS item
            FROM utility.crop_types
            """
        )

        now = datetime.now(tz=pytz.UTC)

        crops_select = [i for i in self.children if i.custom_id == "crops_select"][0]
        crops_select.options = []

        altered_crops = {"harvested": Counter(), "removed": Counter()}

        for index, crop in enumerate(self.farm):
            if index in self.crops_to_harvest and crop is not None:
                # find the relevant crop type
                crop_type = [crop_type for crop_type in crop_types if crop_type["id"] == crop["type"]][0]

                # harvest the crop and make the tile empty
                self.farm[index] = None

                # check if it has passed the `ready_at` time, which means the crop is ready to be harvested.
                ready_at: datetime = crop["planted_at"] + crop_type["growth_period"]

                if now > ready_at:
                    altered_crops["harvested"].update({crop_type["id"]: 1})
                else:
                    altered_crops["removed"].update({crop_type["id"]: 1})

        farm_for_query = []
        for crop in self.farm:
            if isinstance(crop, (dict, asyncpg.Record)):
                # farm is list[asyncpg.Record], to make it valid for database query we need to change it to tuple
                farm_for_query.append(tuple(crop.values()))
            else:
                farm_for_query.append(crop)

        # update the database
        await self.player.db.execute(
            """
            UPDATE players.farm
            SET farm = $1
            WHERE player_id = $2
            """,
            farm_for_query,
            interaction.user.id,
        )
        for crop_type_id, count in altered_crops["harvested"].items():
            crop_type = [i for i in crop_types if i["id"] == crop_type_id][0]
            await self.player.add_item(crop_type["item"], quantity=count)

        # return to the main page
        view = FarmView(interaction, self.player)
        await view.set_up()

        await interaction.response.edit_message(**await view.get_msg())

        embed = Embed()

        for name, crops in altered_crops.items():
            msg = ""
            for crop_type_id, count in crops.items():
                crop_type = [i for i in crop_types if i["id"] == crop_type_id][0]
                msg += f"\n` {count}x ` {crop_type['emoji']} **{crop_type['name'].title()}**"

            embed.add_field(name=name.capitalize(), value=msg if msg else "Nothing", inline=False)

        await interaction.send(embed=embed, ephemeral=True)


class InventoryView(BaseView):
    def __init__(self, interaction: Interaction, user: nextcord.User, inv_type: constants.ItemType, page: int = 1):
        super().__init__(interaction, timeout=60)
        self.user = user
        self.inv_type = inv_type.value
        self.page = page
        self.items_per_page = 6

        self.items = []
        self.item_types = []

        self.message: nextcord.Message = None

    def _get_types_options(self) -> list[SelectOption]:
        """Gets a list of SelectOption objects for the item categories. Should be run *after* get_inv_embed() is run

        Returns:
            A list of SelectOption objects.
        """

        # Create a list of SelectOption objects for the categories.
        options = []
        # Add an option for every category
        for i in constants.ItemType:
            if next((j for j in self.inv if j["type"] == i.value), None):
                options.append(SelectOption(label=i.name.capitalize(), value=str(i.value), default=False))

        # Sort the options by label.
        options.sort(key=lambda x: x.label)

        options.insert(0, SelectOption(label="All", default=True))  # Add an "All" option to select every category

        return options

    @classmethod
    async def send(cls, interaction: Interaction, user: nextcord.User, inv_type: constants.ItemType, page: int = 1):
        """Respond to the interaction by sending a message."""
        view = cls(interaction, user, inv_type, page)
        await view.get_inv_content()
        embed = await view.get_inv_embed()

        types_select_menu = [i for i in view.children if i.custom_id == "type_select"][0]
        # set the options of the cog select menu
        options = view._get_types_options()
        types_select_menu.options = options
        types_select_menu.max_values = len(options)
        # Set the old selected values to ["All"].
        view.old_selected_values = ["All"]

        view.disable_buttons()
        view.message = await interaction.send(embed=embed, view=view)

    async def get_inv_content(self):
        db: Database = self.interaction.client.db
        self.inv = await db.fetch(
            """
            SELECT i.name, CONCAT('<:', i.emoji_name, ':', i.emoji_id, '>') AS emoji, i.rarity, i.type, inv.quantity
                FROM players.inventory AS inv
                INNER JOIN utility.items AS i
                ON inv.item_id = i.item_id
            WHERE inv.player_id = $1 AND inv.inv_type = $2
            ORDER BY 
                (CASE WHEN (SELECT inv_worth_sort FROM players.settings WHERE player_id = $1) is True THEN i.trade_price END) DESC NULLS LAST, 
                i.name ASC
            """,
            self.user.id,
            self.inv_type,
        )
        if self.page * self.items_per_page > len(self.inv):
            self.page = math.ceil(len(self.inv) / self.items_per_page) or 1
        return self.inv

    async def get_inv_embed(self):
        user = self.user

        inv_type = str(constants.InventoryType(self.inv_type))

        embed = Embed(description="")
        embed.set_author(
            name=f"{user.name}'s {inv_type}",
            icon_url=user.display_avatar.url,
        )
        embed.colour = constants.EmbedColour.DEFAULT
        storage_emojis_url = [
            "https://i.imgur.com/AsS2mHU.png",  # backpack
            "https://i.imgur.com/UU7ixCv.png",  # chest
            "https://i.imgur.com/9bQT9Vt.png",  # vault
        ]
        embed.set_thumbnail(url=storage_emojis_url[self.inv_type])

        if self.item_types:  # if a filter is set, apply it, otherwise show the whole list
            self.items = [i for i in self.inv if i["type"] in self.item_types]
        else:
            self.items = self.inv

        if len(self.items) == 0:
            embed.description = "Empty"
            return embed

        compact = await self.interaction.client.db.fetchval(
            "SELECT compact_mode FROM players.settings WHERE player_id = $1", self.interaction.user.id
        )

        for item in self.items[self.get_page_start_index() : self.get_page_end_index() + 1]:
            item_type = [i.name for i in constants.ItemType if i.value == item["type"]][0]
            item_rarity = [i.name for i in constants.ItemRarity if i.value == item["rarity"]][0]
            embed.description += f"{item['emoji']} **{item['name']}** ─ {item['quantity']}\n"
            if not compact:
                embed.description += f"➸ `{item_rarity} {item_type}`\n\n".replace("_", " ").title()
        total_items = sum(i["quantity"] for i in self.items)
        embed.set_footer(
            text=f"Page {self.page}/{math.ceil(len(self.items) / self.items_per_page)} • {len(self.items)} unique items • total {total_items} items"
        )
        return embed

    def get_page_start_index(self):
        """
        Returns the start index of the current page of commands.
        For example, if `self.page` is 2 and `self.cmd_per_page` is 6, then the start index will be 6.
        """
        return (self.page - 1) * self.items_per_page

    def get_page_end_index(self):
        """
        Returns the end index of the current page of commands.

        For example, if `self.page` is 2 and `self.cmd_per_page` is 6, then the end index will be 11.
        """
        index = self.get_page_start_index() + self.items_per_page - 1
        return index if index < len(self.items) else len(self.items) - 1

    def disable_buttons(self):
        """
        Updates the state of the buttons to disable the previous, current, and next buttons if they are not applicable.
        Should be run *after* get_inv_embed() is run.

        - For example, if the first page is being shown, then the previous and back buttons will be disabled.
        - If the last page is being shown, then the next and last buttons will be disabled.
        """
        back_btn = [i for i in self.children if i.custom_id == "back"][0]
        first_btn = [i for i in self.children if i.custom_id == "first"][0]
        if self.page == 1:
            back_btn.disabled = True
            first_btn.disabled = True
        else:
            back_btn.disabled = False
            first_btn.disabled = False
        next_btn = [i for i in self.children if i.custom_id == "next"][0]
        last_btn = [i for i in self.children if i.custom_id == "last"][0]
        if self.get_page_end_index() == len(self.items) - 1:
            next_btn.disabled = True
            last_btn.disabled = True
        else:
            next_btn.disabled = False
            last_btn.disabled = False

    @select(
        placeholder="Choose a category...",
        options=[],
        min_values=1,
        max_values=1,
        custom_id="type_select",
    )
    async def select_type(self, select: Select, interaction: Interaction):
        """
        Updates the commands displayed in the embed based on the selected cog.

        The selected cog is passed to the `get_embed()` method and the new embed is then displayed.
        """
        await interaction.response.defer()
        selected_values = select.values
        if "All" in [i for i in selected_values if i not in self.old_selected_values]:
            selected_values = ["All"]
        elif "All" in [i for i in self.old_selected_values if i in selected_values]:
            selected_values.remove("All")

        if "All" in selected_values:
            self.item_types = []
        else:
            self.item_types = [int(i) for i in selected_values]

        self.page = 1

        embed = await self.get_inv_embed()
        self.disable_buttons()
        # disable the buttons, and make the select menu "sticky"
        for option in select.options:
            option.default = False
            if option.value in selected_values:
                option.default = True
        await self.message.edit(embed=embed, view=self)
        self.old_selected_values = selected_values

    @button(emoji="⏮️", style=nextcord.ButtonStyle.blurple, custom_id="first", disabled=True)
    async def first(self, button: Button, interaction: Interaction):
        await interaction.response.defer()
        self.page = 1
        self.disable_buttons()
        embed = await self.get_inv_embed()
        await self.message.edit(embed=embed, view=self)

    @button(emoji="◀️", style=nextcord.ButtonStyle.blurple, custom_id="back", disabled=True)
    async def back(self, button: Button, interaction: Interaction):
        await interaction.response.defer()
        self.page -= 1
        self.disable_buttons()
        embed = await self.get_inv_embed()
        await self.message.edit(embed=embed, view=self)

    @button(emoji="🔄", style=nextcord.ButtonStyle.blurple, custom_id="refresh_msg")
    async def refresh_msg(self, button: Button, interaction: Interaction):
        await interaction.response.defer()

        await self.get_inv_content()
        embed = await self.get_inv_embed()
        self.disable_buttons()
        await self.message.edit(embed=embed, view=self)

    @button(emoji="▶️", style=nextcord.ButtonStyle.blurple, custom_id="next")
    async def next(self, button: Button, interaction: Interaction):
        await interaction.response.defer()
        self.page += 1
        self.disable_buttons()
        embed = await self.get_inv_embed()
        await self.message.edit(embed=embed, view=self)

    @button(emoji="⏭️", style=nextcord.ButtonStyle.blurple, custom_id="last")
    async def last(self, button: Button, interaction: Interaction):
        await interaction.response.defer()
        self.page = math.ceil(len(self.items) / self.items_per_page)
        self.disable_buttons()
        embed = await self.get_inv_embed()
        await self.message.edit(embed=embed, view=self)

# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle, SelectOption
from nextcord.ui import Button, button, Select, select

# database
import asyncpg
from utils.postgres_db import Database

# my modules and constants
from views.template_views import BaseView
from utils.player import Player
from utils import constants, functions

# default modules
from io import BytesIO
from PIL import Image, ImageDraw
import pytz

from collections import Counter
from datetime import datetime
import math


async def _get_farm_msg(
    player: Player,
    farm,
    farm_width,
    *,
    embed: Embed = None,
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

    db: Database = player.db
    crop_types = await db.fetch(
        """
        SELECT crop_type_id, name, growth_period
        FROM utility.crop_types
        """
    )

    embed.description = ""
    farm_img = Image.new(
        "RGBA", (farm_width * 128,) * 2
    )  # crop_size is 128*128px. tuple multiplied by 2 because width and length are the same

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
                [(0, 0), (128, 128)], # top-left and bottom-right coords for the rectangle
                outline="#58091F",
                width=10,
            )
    
        farm_img.paste(tile_img, (x, y))

        x += 128

        # change to a new row. x % 3 should be modified to show number of columns in farm, not hard-coded
        if x / 128 % 3 == 0:
            x = 0
            y += 128

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
            self.farm = self.farm_width = None
        else:
            self.farm, self.farm_width = res

    async def send_message(self, interaction: Interaction, with_view: bool = True):
        # Check if the player exists
        if not await self.player.is_present():
            await interaction.send(
                embed=functions.format_with_embed("The user hasn't started playing BOSS yet! Maybe invite them over?"),
                ephemeral=True,
            )
            return

        await self.set_up()

        # Check if the player has started his farm
        if not self.farm:
            await interaction.send(embed=functions.format_with_embed("The user hasn't started his/her farm yet!"))
            return

        # All checks succeeded, send the message with the view
        self.msg = await interaction.send(
            **await _get_farm_msg(  # returns a dict with {embed: `embed`, file: `farm_image`}
                self.player, self.farm, self.farm_width
            ),
            view=self if with_view else nextcord.utils.MISSING,
        )

    @button(label="Plant", style=ButtonStyle.blurple)
    async def plant(self, button: Button, interaction: Interaction):
        """Turn to a new page, `PlantView`, which allows users to plant the crops."""
        view = PlantView(interaction, self.player, self.farm, self.farm_width)
        await view.update_select_options()
        await interaction.response.edit_message(**await view.get_msg(), view=view)

    @button(label="Harvest", style=ButtonStyle.blurple)
    async def harvest(self, button: Button, interaction: Interaction):
        """Turn to a new page, `HarvestView`, which allows users to harvest the crops."""
        view = HarvestView(interaction, self.player, self.farm, self.farm_width)
        view.update_select_options()
        await interaction.response.edit_message(**await view.get_msg(), view=view)

    @button(label="Progress")
    async def progress(self, button: Button, interaction: Interaction):
        crop_types = await self.player.db.fetch(
            """
            SELECT crop_type_id AS id, name, growth_period, CONCAT('<:', grown_emoji_name, ':', grown_emoji_id, '>') AS emoji
            FROM utility.crop_types
            """
        )

        embed = Embed(description="")

        for index, crop in enumerate(self.farm):
            if crop:
                # find the relevant crop type
                crop_type = [crop_type for crop_type in crop_types if crop_type["id"] == crop["type"]][0]

                planted_at: datetime = crop["planted_at"]
                ready_at: datetime = planted_at + crop_type["growth_period"]

                # update the embed description to show the crop's progress (i.e. when it will be ready)
                embed.description += (
                    f"` {index + 1} ` {crop_type['emoji']} **{crop_type['name'].capitalize()}** ready <t:{int(ready_at.timestamp())}:R>\n"
                )

        if not embed.description:
            embed.description = "No crops are planted"

        await interaction.send(embed=embed, ephemeral=True)
    
    @button(emoji="🔄")
    async def refresh(self, button: Button, interaction: Interaction):
        """Refresh the page."""
        view = FarmView(interaction, self.player)
        await view.set_up()

        await interaction.response.edit_message(
            **await _get_farm_msg(  # returns a dict with {embed: `embed`, file: `farm_image`}
                self.player, self.farm, self.farm_width
            ),
            view=view,
        )

    async def interaction_check(self, interaction: Interaction) -> bool:
        if not self.is_set_up:  # halt the interaction if `FarmView` is not set up
            embed, view = functions.get_error_message()
            await interaction.send(embed=embed, view=view, ephemeral=True)
            return False

        return await super().interaction_check(interaction)


class PlantView(BaseView):

    """The **plant** page of the `/farm` command. Allows players to plant their crops."""

    def __init__(self, interaction: Interaction, player: Player, farm, farm_width):
        super().__init__(interaction, timeout=180)

        self.player = player  # only the user itself should be able to access `PlantView`
        self.farm = farm
        self.farm_width = farm_width

        self.crops_to_plant = None
        self.type_to_plant = None

    async def update_select_options(self):
        """Update the view's select options. Should be run before sending the message."""
        # update the crops_select select options
        crops_select = [i for i in self.children if i.custom_id == "crops_select"][0]
        crops_select.options = []

        for index, crop in enumerate(self.farm):
            if crop is None:  # check if the farmland is empty
                crops_select.options.append(
                    SelectOption(label=index + 1, value=index)
                )  # + 1 because list uses zero-indexing

        if not crops_select.options:  # if there are no empty tiles, so we disable the select menus
            crops_select.placeholder = "No empty farmland"
            crops_select.options = [
                SelectOption(label="1")
            ]  # dummy select options, if `options` list is empty an error will be raised.
            crops_select.disabled = True
        else:
            crops_select.max_values = len(crops_select.options)

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
                    label=crop_type["name"].capitalize(),
                    value=crop_type["id"],
                    emoji=f"<:{crop_type['emoji_name']}:{crop_type['emoji_id']}>",
                )
            )

    def update_plant_btn(self):
        if self.crops_to_plant and self.type_to_plant:
            plant_btn = [i for i in self.children if i.custom_id == "plant_btn"][0]
            plant_btn.disabled = False

    def get_msg(self, embed: Embed = None, **kwargs):
        if not embed:
            embed = Embed()
        embed.set_author(name=f"{self.interaction.user.name}'s Farm • Planting")

        return _get_farm_msg(self.player, self.farm, self.farm_width, embed=embed, **kwargs)

    @select(placeholder="Choose the tiles...", custom_id="crops_select", min_values=1)
    async def choose_tiles(self, select: Select, interaction: Interaction):
        self.crops_to_plant = [int(value) for value in select.values]

        # make the select menu "sticky"
        for option in select.options:
            option.default = False
            if str(option.value) in select.values:
                option.default = True

        self.update_plant_btn()

        await interaction.response.edit_message(**await self.get_msg(selected_crops=self.crops_to_plant), view=self)

    @select(
        placeholder="Choose the crops to plant...",
        custom_id="type_select",
        min_values=1,
        max_values=1,
    )
    async def choose_crop_type(self, select: Select, interaction: Interaction):
        self.type_to_plant = int(select.values[0])

        embed = Embed()

        # make the select menu "sticky"
        for option in select.options:
            option.default = False
            if str(option.value) in select.values:
                option.default = True
                embed.add_field(name="Planting", value=f"{option.emoji} **{option.label}**")

        self.update_plant_btn()

        await interaction.response.edit_message(**await self.get_msg(embed, selected_crops=self.crops_to_plant), view=self)

    @button(label="Go Back", row=3)
    async def return_to_main_view(self, button: Button, interaction: Interaction):
        """Return the the main `FarmView` page."""
        view = FarmView(interaction, self.player)
        await view.set_up()

        await interaction.response.edit_message(
            **await _get_farm_msg(  # returns a dict with {embed: `embed`, file: `farm_image`}
                self.player, self.farm, self.farm_width
            ),
            view=view,
        )

    @button(label="Plant", style=ButtonStyle.green, custom_id="plant_btn", row=3, disabled=True)
    async def plant_crops(self, button: Button, interaction: Interaction):
        """Plant the crops and update the database."""
        # If this button is not disabled,
        # then both `self.crops_to_plant` and `self.type_to_plant` should be filled by values.
        # Therefore, we need not check whether they are not `None`.

        planted_crops = 0

        # alter `self.farm` to "plant" the crops
        for index, crop in enumerate(self.farm):
            if index in self.crops_to_plant:
                self.farm[index] = {
                    "type": self.type_to_plant, 
                    "planted_at": datetime.now(tz=pytz.UTC)
                }
                planted_crops += 1

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

        await interaction.response.edit_message(
            **await _get_farm_msg(  # returns a dict with {embed: `embed`, file: `farm_image`}
                self.player, self.farm, self.farm_width
            ),
            view=view,
        )

        # find the name and emoji of the crop type
        # the default option is the one the user chose, so here we fetch that and get its label and emoji
        type_select = [i for i in self.children if i.custom_id == "type_select"][0]
        type_name, type_emoji = [
            (option.label, option.emoji) for option in type_select.options if option.default == True
        ][0]

        await interaction.send(
            embed=functions.format_with_embed(f"Planted {planted_crops} **{type_name}** {type_emoji}!"), ephemeral=True
        )


class HarvestView(BaseView):

    """
    The **harvest** page of the `/farm` command.

    Allows players to harvest their ready crops, or remove their crops which are not grown.
    """

    def __init__(self, interaction: Interaction, player: Player, farm, farm_width):
        super().__init__(interaction, timeout=180)

        self.player = player  # only the user itself should be able to access `PlantView`
        self.farm = farm
        self.farm_width = farm_width

        self.crops_to_harvest = None

    def update_select_options(self):
        crops_select = [i for i in self.children if i.custom_id == "crops_select"][0]
        crops_select.options = [SelectOption(label=index + 1, value=index) for index, crop in enumerate(self.farm) if crop is not None]
        crops_select.max_values = len(crops_select.options)

    def get_msg(self):
        embed = Embed().set_author(name=f"{self.interaction.user.name}'s Farm • Harvesting")
        return _get_farm_msg(self.player, self.farm, self.farm_width, embed=embed)

    @select(placeholder="Choose the tiles...", custom_id="crops_select", min_values=1)
    async def choose_tiles(self, select: Select, interaction: Interaction):
        self.crops_to_harvest = [int(value) for value in select.values]

        for option in select.options:
            option.default = False
            if str(option.value) in select.values:
                option.default = True

        harvested_btn = [i for i in self.children if i.custom_id == "harvest_btn"][0]
        harvested_btn.disabled = False

        await interaction.response.edit_message(
            **await _get_farm_msg(self.player, self.farm, self.farm_width, selected_crops=self.crops_to_harvest),
            view=self,
        )

    @button(label="Go Back", row=3)
    async def return_to_main_view(self, button: Button, interaction: Interaction):
        """Return the the main `FarmView` page."""
        view = FarmView(interaction, self.player)
        await view.set_up()

        await interaction.response.edit_message(
            **await _get_farm_msg(  # returns a dict with {embed: `embed`, file: `farm_image`}
                self.player, self.farm, self.farm_width
            ),
            view=view,
        )

    @button(label="Harvest", style=ButtonStyle.green, custom_id="harvest_btn", row=3, disabled=True)
    async def harvest_crops(self, button: Button, interaction: Interaction):
        """Harvest the crops and update the database."""
        # If this button is not disabled,
        # then both `self.crops_to_harvest` should be filled by values.
        # Therefore, we need not check whether it is not `None`.

        crop_types = await self.player.db.fetch(
            """
            SELECT crop_type_id AS id, name, growth_period, CONCAT('<:', grown_emoji_name, ':', grown_emoji_id, '>') AS emoji
            FROM utility.crop_types
            """
        )

        now = datetime.now(tz=pytz.UTC)

        crops_select = [i for i in self.children if i.custom_id == "crops_select"][0]
        crops_select.options = []

        altered_crops = {
            "harvested": Counter(),
            "removed": Counter()
        }

        for index, crop in enumerate(self.farm):
            if index in self.crops_to_harvest:
                # find the relevant crop type
                crop_type = [crop_type for crop_type in crop_types if crop_type["id"] == crop["type"]][0]

                # harvest the crop and make the tile empty
                self.farm[index] = None

                # check if it has passed the `ready_at` time, which means the crop is ready to be harvested.
                ready_at: datetime = crop["planted_at"] + crop_type["growth_period"]

                if now > ready_at:
                    altered_crops["harvested"].update({f"{crop_type['emoji']} **{crop_type['name']}**": 1})
                else:
                    altered_crops["removed"].update({f"{crop_type['emoji']} **{crop_type['name']}**": 1})

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

        await interaction.response.edit_message(
            **await _get_farm_msg(  # returns a dict with {embed: `embed`, file: `farm_image`}
                self.player, self.farm, self.farm_width
            ),
            view=view,
        )

        embed = Embed()

        for name, crops in altered_crops.items():
            msg = ""
            for crop, count in crops.items():
                msg += f"\n` {count}x ` {crop.title()}"

            embed.add_field(name=name.capitalize(), value=msg if msg else "Nothing", inline=False)

        await interaction.send(embed=embed, ephemeral=True)

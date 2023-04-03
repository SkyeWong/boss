# nextcord
import nextcord
from nextcord import Embed, Interaction
from nextcord.ui import View, Button, button

# default modules
import random
import math

# database
from utils.postgres_db import Database

# my modules and constants
from utils import functions, constants
from views.template_views import BaseView


class InventoryView(BaseView):
    def __init__(self, slash_interaction: Interaction, user: nextcord.User, inv_type: int):
        super().__init__(slash_interaction, timeout=60)
        self.user = user
        self.inv_type = inv_type
        self.page = 1
        self.items_per_page = 6

        self.message: nextcord.Message = None

    async def get_inv_content(self):
        db: Database = self.interaction.client.db
        self.inv = await db.fetch(
            """
            SELECT items.name, items.emoji_name, items.emoji_id, items.type, inv.quantity
                FROM players.inventory as inv
                INNER JOIN utility.items
                ON inv.item_id = items.item_id
            WHERE inv.player_id = $1 AND inv.inv_type = $2
            ORDER BY items.name
            """,
            self.user.id,
            self.inv_type,
        )

    def get_inv_embed(self):
        user = self.user
        inv = self.inv
        # INVENTORY TYPES
        #   0 --> backpack (when die lose all stuff, only 32 slots)
        #   1 --> chest (when players attack base and lose lose some stuff, infinite slots)
        #   2 --> vault (will never be lost, only 5 slots)
        inv_types = [i for i in constants.INV_TYPES]
        embed = Embed()
        embed.set_author(
            name=f"{user.name}'s {inv_types[self.inv_type]}",
            icon_url=user.display_avatar.url,
        )
        embed.colour = random.choice(constants.EMBED_COLOURS)
        storage_emojis_url = [
            "https://i.imgur.com/AsS2mHU.png",  # backpack
            "https://i.imgur.com/UU7ixCv.png",  # chest
            "https://i.imgur.com/9bQT9Vt.png",  # vault
        ]
        embed.set_thumbnail(url=storage_emojis_url[self.inv_type])
        if len(inv) == 0:
            embed.description = "Empty"
            return embed
        # ITEM TYPES
        #   0 - tool
        #   1 - collectable
        #   2 - power-up
        #   3 - sellable
        #   4 - bundles
        types = [i for i in constants.ITEM_TYPES]
        for item in inv[self.get_page_start_index() : self.get_page_end_index() + 1]:
            embed.add_field(
                name=f"<:{item['emoji_name']}:{item['emoji_id']}>  {item['name']} ─ {item['quantity']}\n",
                value=f"─ {types[item['type']]}",
                inline=False,
            )
        embed.set_footer(text=f"Page {self.page}/{math.ceil(len(self.inv) / self.items_per_page)}")
        return embed

    def get_page_start_index(self):
        return (self.page - 1) * self.items_per_page

    def get_page_end_index(self):
        index = self.get_page_start_index() + self.items_per_page - 1
        inv = self.inv
        return index if index < len(inv) else len(inv) - 1

    def disable_buttons(self):
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
        if self.get_page_end_index() == len(self.inv) - 1:
            next_btn.disabled = True
            last_btn.disabled = True
        else:
            next_btn.disabled = False
            last_btn.disabled = False

    @button(emoji="⏮️", style=nextcord.ButtonStyle.blurple, custom_id="first", disabled=True)
    async def first(self, button: Button, btn_interaction: Interaction):
        await btn_interaction.response.defer()
        self.page = 1
        self.disable_buttons()
        embed = self.get_inv_embed()
        await self.message.edit(embed=embed, view=self)

    @button(emoji="◀️", style=nextcord.ButtonStyle.blurple, disabled=True, custom_id="back")
    async def back(self, button: Button, btn_interaction: Interaction):
        await btn_interaction.response.defer()
        self.page -= 1
        self.disable_buttons()
        embed = self.get_inv_embed()
        await self.message.edit(embed=embed, view=self)

    @button(emoji="▶️", style=nextcord.ButtonStyle.blurple, custom_id="next")
    async def next(self, button: Button, btn_interaction: Interaction):
        await btn_interaction.response.defer()
        self.page += 1
        self.disable_buttons()
        embed = self.get_inv_embed()
        await self.message.edit(embed=embed, view=self)

    @button(emoji="⏭️", style=nextcord.ButtonStyle.blurple, custom_id="last")
    async def last(self, button: Button, btn_interaction: Interaction):
        await btn_interaction.response.defer()
        self.page = math.ceil(len(self.inv) / self.items_per_page)
        self.disable_buttons()
        embed = self.get_inv_embed()
        await self.message.edit(embed=embed, view=self)

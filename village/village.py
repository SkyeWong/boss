# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle, SelectOption
from nextcord.ui import Button, button, Select, select

# database
from utils.postgres_db import Database

import aiohttp

# my modules and constants
from views.template_views import BaseView
from utils.player import Player
from utils import constants, functions
from utils.functions import TextEmbed

# village utils
from village.villagers import *

# default modules
from typing import Optional
import random


class Village(BaseView):
    def __init__(self, slash_interaction: Interaction):
        super().__init__(slash_interaction, timeout=60)
        
    async def send(self):
        embed = self.get_embed()
        self.msg = await self.interaction.send(embed=embed, view=self)

    @button(label="Trade", style=ButtonStyle.blurple, custom_id="trade")
    async def trade(self, button: Button, interaction: Interaction):
        pass
    
class TradeView(BaseView):
    def __init__(self, slash_interaction: Interaction):
        super().__init__(slash_interaction, timeout=60)
        self.villagers: list[Villager] = []
        self.current_villager: Villager = None
        
        self.msg: nextcord.PartialInteractionMessage | nextcord.WebhookMessage = None
        
    async def roll_new_villagers(self, quantity: Optional[int] = 5) -> list[str]:
        params = {
            "nameType": "firstname",
            "quantity": quantity
        }
        headers = {
            "X-Api-Key": "2a4f04bc0708472d9791240ca7d39476"
        }
        async with aiohttp.ClientSession() as session:
            async with session.get("https://randommer.io/api/Name", params=params, headers=headers) as response:
                names = await response.json()
        
        villagers = []
        for name in names:
            job_type = random.choice(Villager.__subclasses__())
            villagers.append(job_type(name, self.interaction.client.db))
        self.villagers = villagers
        
    async def send(self):
        await self.roll_new_villagers()
        self.current_villager = self.villagers[0]
        
        embed = await self.get_embed()
        self.update_view()
        self.msg = await self.interaction.send(embed=embed, view=self)
        
    async def get_embed(self):
        embed = Embed()
        embed.set_author(name="Trading")
        villager = self.current_villager
        embed.title = f"{villager.name} - {villager.job_type}"
        embed.description = f"_{villager.remaining_trades} trades left._"
        
        demand_msg, supply_msg = await villager.format_trade()
                
        embed.add_field(name="I receive", value=demand_msg, inline=False)
        embed.add_field(name="You receive", value=supply_msg, inline=False)
        return embed
    
    def update_view(self):
        choose_villager_select = [i for i in self.children if i.custom_id == "choose_villager"][0]
        choose_villager_select.options = []
        for index, villager in enumerate(self.villagers):
            choose_villager_select.options.append(SelectOption(
                label=f"{villager.name} - {villager.job_type}", 
                # description=f"{villager.demand} --> {villager.supply}",
                value=index,
                default=villager == self.current_villager
            ))
        
    @select(placeholder="Choose a villager", options=[], custom_id="choose_villager")
    async def choose_villager(self, select: Select, interaction: Interaction):
        index = int(select.values[0])
        self.current_villager = self.villagers[index]
        
        embed = await self.get_embed()
        self.update_view()
        await self.msg.edit(embed=embed, view=self)
        await interaction.response.defer()
        
    @button(label="Trade", style=ButtonStyle.blurple, custom_id="trade")
    async def trade(self, button: Button, interaction: Interaction):
        current_villager = self.current_villager
        remaining_trades = current_villager.remaining_trades
        
        if remaining_trades <= 0:
            await interaction.send(embed=TextEmbed(f"{current_villager.name} is out of stock. Maybe try again later."), ephemeral=True)
            return
        
        db: Database = interaction.client.db
        player = Player(db, interaction.user)
        
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                player_scrap = await db.fetchval(
                    """
                    SELECT scrap_metal
                    FROM players.players
                    WHERE player_id = $1
                    """,
                    interaction.user.id,
                )
                
                inventory = await db.fetch(
                    """
                    SELECT item_id, quantity
                    FROM players.inventory
                    WHERE player_id = $1 AND inv_type = 0
                    """,
                    interaction.user.id,
                )

                for trade_type, trade_items in {"demand": current_villager.demand, "supply": current_villager.supply}.items():
                    multiplier = -1 if trade_type == "demand" else 1
                    for item in trade_items:
                        if isinstance(item, TradePrice):
                            if trade_type == "demand" and player_scrap < item.price:
                                await interaction.send(embed=TextEmbed("You don't have enough scrap metal."), ephemeral=True)
                                return
                            
                            required_price = multiplier * item.price
                            await player.modify_scrap(required_price)
                        elif isinstance(item, TradeItem):
                            owned_quantity = next((x["quantity"] for x in inventory if x["item_id"] == item.item_id), 0)
                            if trade_type == "demand" and owned_quantity < item.quantity:
                                await interaction.send(embed=TextEmbed(f"You are {item.quantity - (owned_quantity if owned_quantity else 0)} short in {await item.get_emoji(db)} {await item.get_name(db)}."), ephemeral=True)
                                return
                            
                            required_quantity = multiplier * item.quantity
                            await player.add_item(item.item_id, required_quantity)
                            
        demand_msg, supply_msg = await current_villager.format_trade()
        await interaction.send(embed=TextEmbed(f"You successfully received: {supply_msg}"), ephemeral=True)
        current_villager.remaining_trades -= 1
        
        embed = await self.get_embed()
        self.update_view()
        await self.msg.edit(embed=embed, view=self)
# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle, SelectOption
from nextcord.ui import Button, button, Select, select

# database
from utils.postgres_db import Database

# my modules and constants
from views.template_views import BaseView
from utils.player import Player
from utils import constants, helpers
from utils.helpers import TextEmbed

# village utils
from village.villagers import *

# default modules
import pytz
import datetime


class TradeView(BaseView):
    def __init__(self, interaction: Interaction):
        super().__init__(interaction, timeout=60)
        self.villagers: list[Villager] = []
        self.current_villager: Villager = None
        self.current_index = 0

    async def send(self):
        await self.get_villagers()
        self.current_villager = self.villagers[0]

        embed = await self.get_embed()
        await self.update_view()
        await self.interaction.send(embed=embed, view=self)

    async def get_villagers(self) -> None:
        db: Database = self.interaction.client.db
        res = await db.fetch(
            """
            SELECT 
                name, 
                job_title, 
                id, 
                demands, 
                supplies, 
                (SELECT COALESCE(
                    (SELECT remaining_trades
                    FROM trades.villager_remaining_trades
                    WHERE player_id = $1 AND villager_id = id),
                    num_trades
                )) AS remaining_trades
            FROM trades.villagers
            """,
            self.interaction.user.id,
        )
        for i in res:
            self.villagers.append(
                Villager(
                    i["id"],
                    i["name"],
                    i["job_title"],
                    [
                        TradeItem(j["item_id"], j["quantity"])
                        if j.get("item_id")
                        else TradePrice(j["price"], j["type"])
                        for j in i["demands"]
                    ],
                    [
                        TradeItem(j["item_id"], j["quantity"])
                        if j.get("item_id")
                        else TradePrice(j["price"], j["type"])
                        for j in i["supplies"]
                    ],
                    i["remaining_trades"],
                    db,
                )
            )

    async def get_embed(self):
        embed = Embed()
        embed.set_author(name="Trading")
        villager = self.current_villager
        embed.title = f"{villager.name} - {villager.job_title}"
        embed.description = f"_{villager.remaining_trades} trades left._"
        comment = await self.interaction.client.db.fetchval(
            "SELECT obj_description('trades.villagers'::regclass) AS desc"
        )
        time = datetime.datetime.strptime(comment, "%y-%m-%d %H:%M %Z")
        time = time.replace(tzinfo=pytz.UTC)
        embed.set_footer(text="Trade with items in your backpack!\nVillagers reset every hour. Last updated")
        embed.timestamp = time

        demand_msg, supply_msg = await villager.format_trade()
        embed.add_field(name="I receive", value=demand_msg, inline=False)
        embed.add_field(name="You receive", value=supply_msg, inline=False)

        return embed

    async def get_items_str(self, items: list[TradeItem | TradePrice]):
        db = self.interaction.client.db
        item_strings = [
            f"{i.quantity} {await i.get_name(db)}"
            if isinstance(i, TradeItem)  # eg: "5 Aqua Defender"
            else f"{i.price:,} {i.currency_type.replace('_', ' ')}"  # eg: "123,456,789 Copper"
            for i in items
        ]
        return ", ".join(item_strings)

    async def update_view(self):
        choose_villager_select = [i for i in self.children if i.custom_id == "choose_villager"][0]
        choose_villager_select.options = []

        for index, villager in enumerate(self.villagers):
            description = ""

            if any([isinstance(i, TradeItem) for i in villager.supply]):
                supply_items = await self.get_items_str(villager.supply)
                description = f"Selling {supply_items}"
            else:
                demand_items = await self.get_items_str(villager.demand)
                description = f"Buying {demand_items}"

            if len(description) > 100:
                description = f"{description[:97]}..."

            choose_villager_select.options.append(
                SelectOption(
                    label=f"{villager.name} - {villager.job_title}",
                    description=description,
                    value=index,
                    default=villager == self.current_villager,
                )
            )

    @select(placeholder="Choose a villager", options=[], custom_id="choose_villager")
    async def choose_villager(self, select: Select, interaction: Interaction):
        self.current_index = int(select.values[0])
        self.current_villager = self.villagers[self.current_index]

        embed = await self.get_embed()
        await self.update_view()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="◀️", style=ButtonStyle.gray, custom_id="back")
    async def back(self, button: Button, interaction: Interaction):
        if self.current_index == 0:
            self.current_index = len(self.villagers) - 1
        else:
            self.current_index -= 1
        self.current_villager = self.villagers[self.current_index]

        embed = await self.get_embed()
        await self.update_view()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="▶️", style=ButtonStyle.grey, custom_id="next")
    async def next(self, button: Button, interaction: Interaction):
        if self.current_index == len(self.villagers) - 1:
            self.current_index = 0
        else:
            self.current_index += 1
        self.current_villager = self.villagers[self.current_index]

        embed = await self.get_embed()
        await self.update_view()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(label="Trade", style=ButtonStyle.blurple, custom_id="trade")
    async def trade(self, button: Button, interaction: Interaction):
        current_villager = self.current_villager
        remaining_trades = current_villager.remaining_trades

        if remaining_trades <= 0:
            await interaction.send(
                embed=TextEmbed(f"{current_villager.name} is out of stock. Maybe try again later."),
                ephemeral=True,
            )
            return

        db: Database = interaction.client.db
        player = Player(db, interaction.user)

        async with db.pool.acquire() as conn:
            async with conn.transaction():
                player_currency = await conn.fetchval(
                    """
                    SELECT scrap_metal, copper
                    FROM players.players
                    WHERE player_id = $1
                    """,
                    interaction.user.id,
                )

                inventory = await conn.fetch(
                    """
                    SELECT item_id, quantity
                    FROM players.inventory
                    WHERE player_id = $1 AND inv_type = 0
                    """,
                    interaction.user.id,
                )

                for trade_type, trade_items in {
                    "demand": current_villager.demand,
                    "supply": current_villager.supply,
                }.items():
                    multiplier = -1 if trade_type == "demand" else 1
                    for item in trade_items:
                        if isinstance(item, TradePrice):
                            if trade_type == "demand" and player_currency[item.currency_type] < item.price:
                                await interaction.send(
                                    embed=TextEmbed("You don't have enough scrap metal."),
                                    ephemeral=True,
                                )
                                return

                            required_price = multiplier * item.price
                            await player.modify_currency(item.currency_type, required_price)
                        elif isinstance(item, TradeItem):
                            owned_quantity = next(
                                (x["quantity"] for x in inventory if x["item_id"] == item.item_id),
                                0,
                            )
                            if trade_type == "demand" and owned_quantity < item.quantity:
                                await interaction.send(
                                    embed=TextEmbed(
                                        f"You are {item.quantity - (owned_quantity if owned_quantity else 0)} short in {await item.get_emoji(db)} {await item.get_name(db)}."
                                    ),
                                    ephemeral=True,
                                )
                                return

                            required_quantity = multiplier * item.quantity
                            await player.add_item(item.item_id, required_quantity)

                current_villager.remaining_trades = await db.fetchval(
                    """
                    INSERT INTO trades.villager_remaining_trades AS t (player_id, villager_id, remaining_trades)
                    VALUES (
                        $1, 
                        $2, 
                        (SELECT num_trades FROM trades.villagers WHERE id = $2) - 1
                    )
                    ON CONFLICT(player_id, villager_id) DO UPDATE
                        SET remaining_trades = t.remaining_trades - 1
                    RETURNING remaining_trades
                    """,
                    player.user.id,
                    current_villager.villager_id,
                )

        embed = await self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

        demand_msg, supply_msg = await current_villager.format_trade()
        await interaction.send(embed=TextEmbed(f"You successfully received: {supply_msg}"), ephemeral=True)

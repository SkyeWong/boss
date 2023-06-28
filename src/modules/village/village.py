# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle, SelectOption
from nextcord.ui import Button, button, Select, select, TextInput

# database
from utils.postgres_db import Database

# village utils
from .villagers import Villager
from utils.helpers import BossCurrency, BossItem

# my modules and constants
from utils.template_views import BaseView, BaseModal
from utils.player import Player
from utils import constants, helpers
from utils.helpers import TextEmbed

# default modules
import re
import pytz
import datetime


class TradeView(BaseView):
    def __init__(self, interaction: Interaction):
        super().__init__(interaction, timeout=60)
        self.villagers: list[Villager] = []
        self.current_villager: Villager = None
        self.current_index = 0
        self.msg: nextcord.Message = None

    async def send(self):
        await self.get_villagers()
        self.current_villager = self.villagers[0]

        embed = await self.get_embed()
        await self.update_view()
        self.msg = await self.interaction.send(embed=embed, view=self)

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
                        BossItem(j["item_id"], j["quantity"])
                        if j.get("item_id")
                        else BossCurrency(j["price"], j["type"])
                        for j in i["demands"]
                    ],
                    [
                        BossItem(j["item_id"], j["quantity"])
                        if j.get("item_id")
                        else BossCurrency(j["price"], j["type"])
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

    async def _get_items_str(self, items: list[BossItem | BossCurrency]):
        db = self.interaction.client.db
        item_strings = [
            f"{i.quantity} {await i.get_name(db)}"
            if isinstance(i, BossItem)  # eg: "5 Aqua Defender"
            else f"{i.price:,} {i.currency_type.replace('_', ' ')}"  # eg: "123,456,789 Copper"
            for i in items
        ]
        return ", ".join(item_strings)

    async def update_view(self):
        db: Database = self.interaction.client.db
        choose_villager_select = [i for i in self.children if i.custom_id == "choose_villager"][0]
        choose_villager_select.options = []

        for index, villager in enumerate(self.villagers):
            description = ""

            if any([isinstance(i, BossItem) for i in villager.supply]):
                item = next((i for i in villager.supply if isinstance(i, BossItem)))
                emoji = await item.get_emoji(db)
                supply_items = await self._get_items_str(villager.supply)
                description = f"Selling {supply_items}"
            else:
                item = next((i for i in villager.demand if isinstance(i, BossItem)))
                emoji = await item.get_emoji(db)
                demand_items = await self._get_items_str(villager.demand)
                description = f"Buying {demand_items}"
            description += f", {villager.remaining_trades} trades left"

            if len(description) > 100:
                description = f"{description[:97]}..."

            choose_villager_select.options.append(
                SelectOption(
                    label=f"{villager.name} - {villager.job_title}",
                    description=description,
                    emoji=emoji,
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

    @button(label="Trade Once", style=ButtonStyle.blurple, custom_id="trade_once")
    async def trade_once(self, button: Button, interaction: Interaction):
        """Trade with a villager once"""
        await self.trade(interaction, trade_quantity=1)

    @button(label="Trade Custom Amount", style=ButtonStyle.blurple, custom_id="trade_custom")
    async def trade_custom(self, button: Button, interaction: Interaction):
        """Trade with a villager for a custom amount that the user specifies."""
        db: Database = interaction.client.db
        currencies = await db.fetchrow(
            """
            SELECT scrap_metal, copper
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
        # calculate the max amount of times that the user can trade with, and set it to the default value of the modal input
        num_trades = []  # a list to store how many times the user can trade for each item
        for item in self.current_villager.demand:
            if isinstance(item, BossItem):
                owned_quantity = next((i["quantity"] for i in inventory if i["item_id"] == item.item_id), 0)
                num_trades.append(owned_quantity // item.quantity)
            elif isinstance(item, BossCurrency):
                num_trades.append(currencies[item.currency_type] // item.price)
        # the user can trade for `max_num_trades` at most
        # note that if we use max() then users may not have enough of all items, so we need to use min()
        # also we append the remaining trades in `min()` function,
        # so that either the max remaining trades or max number of trades with the user's resources will be shown
        max_num_trades = min(num_trades + [self.current_villager.remaining_trades])

        async def modal_callback(modal_interaction: Interaction):
            input = [i for i in modal.children if i.custom_id == "input"][0]
            quantity: str = input.value
            if re.search(r"\D", quantity):
                await modal_interaction.send(embed=TextEmbed("That's not a number."), ephemeral=True)
            else:
                await self.trade(interaction, trade_quantity=int(quantity))

        modal = BaseModal(
            title="Trade Custom Amount",
            inputs=[TextInput(label="Times to trade", required=True, placeholder=max_num_trades, custom_id="input")],
            callback=modal_callback,
        )
        await interaction.response.send_modal(modal)

    async def trade(self, interaction: Interaction, trade_quantity: int):
        """Handle the player's trade with a villager."""
        current_villager = self.current_villager

        # If there are no remaining trades for the villager, send a message to the player and return
        if current_villager.remaining_trades < trade_quantity:
            await interaction.send(
                embed=TextEmbed(f"{current_villager.name} does not have that much stock."),
                ephemeral=True,
            )
            return

        db: Database = interaction.client.db
        player = Player(db, interaction.user)
        remaining_currency = None
        remaining_inventory = []

        async with db.pool.acquire() as conn:
            async with conn.transaction():
                # Retrieve the player's inventory from the database
                inventory = await conn.fetch(
                    """
                    SELECT item_id, quantity
                    FROM players.inventory
                    WHERE player_id = $1 AND inv_type = 0
                    """,
                    interaction.user.id,
                )

                # Iterate through the villager's demands and supplies
                for trade_type, trade_items in {
                    "demand": current_villager.demand,
                    "supply": current_villager.supply,
                }.items():
                    multiplier = -1 if trade_type == "demand" else 1
                    for item in trade_items:
                        if isinstance(item, BossCurrency):
                            try:
                                # Deduct the required amount of currency from the player's account
                                required_price = multiplier * item.price * trade_quantity
                                remaining_currency = (
                                    item.currency_type,
                                    await player.modify_currency(item.currency_type, required_price),
                                )
                            except helpers.NegativeBalance:
                                # The player does not have enough currency, send a message to the player and return
                                await interaction.send(
                                    embed=TextEmbed("You don't have enough scrap metal."),
                                    ephemeral=True,
                                )
                                return
                        elif isinstance(item, BossItem):
                            # get the quantity of the item the player owns with a generator expression
                            owned_quantity = next((i["quantity"] for i in inventory if i["item_id"] == item.item_id), 0)
                            try:
                                # Add/remove the required amount of items to/from the player's inventory
                                required_quantity = multiplier * item.quantity * trade_quantity
                                new_quantity = await player.add_item(item.item_id, required_quantity)
                                remaining_inventory.append(
                                    BossItem(
                                        item.item_id,
                                        new_quantity,
                                    )
                                )
                            except helpers.NegativeInvQuantity:
                                # The player does not have enough of the item, send a message to the player and return
                                await interaction.send(
                                    embed=TextEmbed(
                                        f"You are {item.quantity * trade_quantity - owned_quantity} short in {await item.get_emoji(db)} {await item.get_name(db)}."
                                    ),
                                    ephemeral=True,
                                )
                                return

                # Update the remaining trades for the current villager with the player in the database
                current_villager.remaining_trades = await db.fetchval(
                    """
                    INSERT INTO trades.villager_remaining_trades AS t (player_id, villager_id, remaining_trades)
                    VALUES (
                        $1, 
                        $2, 
                        (SELECT num_trades FROM trades.villagers WHERE id = $2) - $3
                    )
                    ON CONFLICT(player_id, villager_id) DO UPDATE
                        SET remaining_trades = t.remaining_trades - $3
                    RETURNING remaining_trades
                    """,
                    player.user.id,
                    current_villager.villager_id,
                    trade_quantity,
                )

        # Update the message to show the new remaining trades
        embed = await self.get_embed()
        await self.msg.edit(embed=embed, view=self)
        # Send a message to the player indicating what they received from the trade
        supply_msg = ""
        for i in current_villager.supply:
            if isinstance(i, BossCurrency):
                supply_msg += f"\n- {constants.CURRENCY_EMOJIS[i.currency_type]} ` {i.price * trade_quantity:,} `"
            elif isinstance(i, BossItem):
                supply_msg += f"\n- ` {i.quantity * trade_quantity}x ` {await i.get_emoji(db)} {await i.get_name(db)}"  # fmt: skip
        # Send a message to the player indicating how many resources they still have
        if remaining_currency is not None:
            # some trades may not include scrap metal/copper, then `remaining_currency` will be `None`
            remaining_msg = f"\n- {constants.CURRENCY_EMOJIS[remaining_currency[0]]} ` {remaining_currency[1]:,} `"
        else:
            remaining_msg = ""
        for i in remaining_inventory:
            remaining_msg += f"\n- ` {i.quantity}x ` {await i.get_emoji(db)} {await i.get_name(db)}"  # fmt: skip

        await interaction.send(
            embed=TextEmbed(f"You successfully received: {supply_msg}\n\nYou now have: {remaining_msg}"),
            ephemeral=True,
        )

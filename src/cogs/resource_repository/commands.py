# default modules
from typing import Literal
import random
import datetime
import operator
import math
import asyncio
import json
import logging

# nextcord
import nextcord
from nextcord.ext import commands, tasks
from nextcord.ui import View, Button
from nextcord import Interaction, SlashOption, ButtonStyle

import cooldowns
from cooldowns import SlashBucket

import aiohttp
import asyncpg

from numerize import numerize

import pytz

# my modules and constants
from utils import constants, helpers
from utils.postgres_db import Database
from utils.constants import SCRAP_METAL, COPPER, COPPER_SCRAP_RATE, EmbedColour
from utils.helpers import (
    check_if_not_dev_guild,
    command_info,
    BossItem,
    BossCurrency,
    BossInteraction,
    TextEmbed,
    BossEmbed,
)
from utils.player import Player

# command views
from utils.template_views import ConfirmView, BaseView
from cogs.resource_repository.views import FarmView, InventoryView

# trade
from modules.village.village import TradeView
from modules.village.villagers import Villager

# maze
from modules.maze.maze import Maze


class ResourceRepository(commands.Cog, name="Resource Repository"):
    """Currency management, trading, and base building"""

    COG_EMOJI = "🪙"

    cooldowns.define_shared_cooldown(
        1, 8, SlashBucket.author, cooldown_id="sell_items", check=check_if_not_dev_guild
    )
    cooldowns.define_shared_cooldown(
        1, 6, SlashBucket.author, cooldown_id="check_inv", check=check_if_not_dev_guild
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_villagers.start()
        self.update_villagers.add_exception_type(
            asyncpg.PostgresConnectionError,
            asyncpg.exceptions.InterfaceError,
        )

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

    @nextcord.slash_command(name="item", description="Get information of an item.")
    async def item(
        self,
        interaction: BossInteraction,
        itemname: str = SlashOption(
            name="item",
            description="The item to search for",
            autocomplete_callback=choose_item_autocomplete,
        ),
    ):
        db: Database = self.bot.db
        item = await db.fetchrow(self.GET_ITEM_SQL, itemname)
        if not item:
            await interaction.send_text("The item is not found!")
        else:
            res = await db.fetch(
                """
                SELECT inv_type, quantity
                FROM players.inventory
                WHERE player_id = $1 AND item_id = $2
                """,
                interaction.user.id,
                item["item_id"],
            )
            owned_quantities = {
                str(constants.InventoryType(inv_type)): quantity for inv_type, quantity in res
            }
            embed = helpers.get_item_embed(item, owned_quantities)
            await interaction.send(embed=embed)

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def trade(self, interaction: Interaction):
        """Trade with villagers for valuable and possibly unique items!"""
        await TradeView.send(interaction)

    @tasks.loop(hours=1)
    async def update_villagers(self):
        # get a list of names
        params = {"nameType": "firstname", "quantity": random.randint(10, 18)}
        headers = {"X-Api-Key": "2a4f04bc0708472d9791240ca7d39476"}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://randommer.io/api/Name", params=params, headers=headers
            ) as response:
                names = await response.json()

        # generate the villagers
        villagers: list[Villager] = []
        job_types = random.choices(Villager.__subclasses__(), k=len(names))
        for job_type, name in zip(job_types, names):
            villagers.append(job_type(name, self.bot.db))

        # update villagers to database
        db: Database = self.bot.db
        if db.pool is None:
            return

        await db.connect()
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    TRUNCATE table trades.villagers;
                    TRUNCATE table trades.villager_remaining_trades;
                    """
                )
                # insert the villagers and their trades
                await conn.executemany(
                    """
                    INSERT INTO trades.villagers (id, name, job_title, demands, supplies, num_trades)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    """,
                    [
                        (
                            i + 1,
                            villager.name,
                            villager.job_title,
                            # the composite type `trade_item` has the following fields:
                            #   - item_id  (items)
                            #   - quantity (items)
                            #   - price    (currencies)
                            #   - type     (currencies)
                            # therefore if the item in question is an item, leave the last 2 fields empty
                            # if it is a currency/price, leave the first 2 columns blank
                            [
                                (item.id, item.quantity, None, None)
                                if isinstance(item, BossItem)
                                else (None, None, item.price, item.currency_type)
                                for item in villager.demand
                            ],
                            [
                                (item.id, item.quantity, None, None)
                                if isinstance(item, BossItem)
                                else (None, None, item.price, item.currency_type)
                                for item in villager.supply
                            ],
                            villager.remaining_trades,
                        )
                        for i, villager in enumerate(villagers)
                    ],
                )
        utc = pytz.timezone("UTC")
        now = datetime.datetime.now(tz=utc).strftime("%y-%#m-%#d %#H:%#M %Z")
        await db.execute(f"COMMENT ON TABLE trades.villagers IS '{now}'")
        await self.bot.get_guild(919223073054539858).get_channel(1120926567930007582).send(
            embed=TextEmbed(f"villagers updated at {now}")
        )
        logging.info("Updated villagers.")

    @update_villagers.before_loop
    async def before_update_villagers(self):
        now = datetime.datetime.now()
        # Wait until the start of the next hour before starting the task loop,
        # so that the trades get updated at the start of hours (HH:00)
        start_of_next_hour = (now + datetime.timedelta(hours=1)).replace(
            minute=0, second=0, microsecond=0
        )
        await nextcord.utils.sleep_until(start_of_next_hour)

    @nextcord.slash_command(name="farm")
    async def farm(self, interaction: BossInteraction):
        """Engage yourself in a virtual farm - plant, harvest, and discover new crops!"""
        pass

    @farm.before_invoke
    @staticmethod
    async def create_farm(interaction: BossInteraction):
        # if the user hasn't started his/her farm, then we need to insert his/her record into the table
        # if the user has already started farming, then do nothing (ON CONFLICT DO NOTHING)
        await interaction.client.db.execute(
            """
            INSERT INTO players.farm(player_id, farm)
            VALUES($1, $2)
            ON CONFLICT(player_id) DO NOTHING
            """,
            interaction.user.id,
            [None] * 4,
        )

    @farm.subcommand(name="view", inherit_hooks=True)
    async def farm_view(
        self,
        interaction: BossInteraction,
        user: nextcord.User = SlashOption(
            description="The user to view the farm of", required=False, default=None
        ),
    ):
        """Check your crops' progress."""
        if user is None:
            user = interaction.user

        player = Player(self.bot.db, user)
        view = FarmView(interaction, player)

        await view.send_message(interaction, with_view=True if user == interaction.user else False)

    def get_sell_item_embed(self, sold_items: tuple, total_price):
        embed = BossEmbed()
        embed.title = "BOSS Cash Receipt"
        embed.description = "─" * (len(embed.title) + 5)
        embed.description += "\n"

        sold_items = sorted(sold_items, key=lambda item: item["quantity"], reverse=True)
        quantities = {item["quantity"] for item in sold_items}
        # get the length of the item with the largest quantity,
        # so that the quantities indents nicely like this:
        # (the emojis are removed)
        #     ──────────────────────
        #     ` 139x ` Banknote (9,452,000)
        #     `  99x ` Cow (2,970,000)
        #     `  78x ` Deer (7,799,922)
        #     `  56x ` Wheat (1,680,000)
        #     `  43x ` Carrot (1,720,000)
        #     ──────────────────────
        max_quantity_length = len(str(max(quantities)))

        for item in sold_items:
            embed.description += f"` {item['quantity']: >{max_quantity_length}}x ` {item['emoji']} {item['name']} ({SCRAP_METAL} {item['sell_price'] * item['quantity']:,})\n"

        embed.description += "─" * (len(embed.title) + 5)
        embed.description += f"\n**`Total`**: {SCRAP_METAL} __{total_price:,}__"
        return embed

    async def sell_all_player_items(self, button, interaction: BossInteraction):
        async with self.bot.db.pool.acquire() as conn:
            async with conn.transaction():
                sold_items = await conn.fetch(
                    """
                    UPDATE players.inventory AS inv
                    SET quantity = 0
                    FROM utility.items AS i
                    WHERE 
                        inv.item_id = i.item_id AND 

                        player_id = $1 AND 
                        inv_type = 0 AND 
                        i.sell_price > 0 AND
                        NOT i.item_id = ANY($2::int[])
                    RETURNING 
                        i.name, 
                        CONCAT('<:_:', i.emoji_id, '>') AS emoji,
                        i.sell_price,
                        (SELECT quantity As old_quantity 
                        FROM players.inventory 
                        WHERE player_id = $1 AND inv_type = 0 AND item_id = i.item_id) As quantity 
                    """,
                    interaction.user.id,
                    interaction.attached.exclude_items,
                )

                player = Player(self.bot.db, interaction.user)
                total_price = 0
                for item in sold_items:
                    total_price += item["sell_price"] * item["quantity"]
                await player.modify_scrap(total_price)
        return total_price

    GET_SELLABLE_SQL = """
        SELECT i.item_id, i.name, CONCAT('<:_:', i.emoji_id, '>') AS emoji, i.sell_price, bp.quantity
            FROM utility.items AS i
            INNER JOIN utility.SearchItem($2) AS s
            ON i.item_id = s.item_id
            LEFT JOIN 
                (SELECT inv.item_id, inv.quantity
                FROM players.inventory AS inv
                WHERE inv.player_id = $1 AND inv.inv_type = 0) AS bp
            ON bp.item_id = i.item_id
        WHERE i.sell_price > 0;
    """

    async def choose_backpack_sellable_autocomplete(self, interaction: BossInteraction, data: str):
        """Returns a list of autocompleted choices of the sellable items in a user's backpack"""
        db: Database = self.bot.db
        items = await db.fetch(self.GET_SELLABLE_SQL, interaction.user.id, data)
        await interaction.response.send_autocomplete([i["name"] for i in items][:25])

    @nextcord.slash_command()
    async def sell(self, interaction):
        """Sell items to me and earn some money!"""
        pass

    @sell.subcommand(name="all")
    @cooldowns.shared_cooldown("sell_items")
    async def sell_all(
        self,
        interaction: BossInteraction,
        exclude_item_names: str = SlashOption(
            name="exclude-items",
            description="The items to exclude in your inventory. Seperate them with '/'",
            required=False,
            default="",
        ),
    ):
        """Sell every sellable items in your backpack, basically: all items except the ones you exclude."""
        db: Database = self.bot.db

        exclude_items = []
        if exclude_item_names:
            exclude_item_names = exclude_item_names.split("/")

            for item_name in exclude_item_names:
                item = await db.fetchrow(
                    self.GET_SELLABLE_SQL,
                    interaction.user.id,
                    item_name,
                )
                # the item is not found, or the user does not own any
                if item is None:
                    await interaction.send_text(
                        f"The item `{item_name}` doesn't exist.", EmbedColour.WARNING
                    )

                    return
                if item["quantity"] is None:
                    await interaction.send_text(
                        f"You don't own any {item['emoji']} **{item['name']}**", EmbedColour.WARNING
                    )
                    return

                exclude_items.append(item["item_id"])

        # get the remaining sellable items in the user's backpack where the item is not excluded
        sellable_items = await db.fetch(
            """
                SELECT i.item_id, i.name, CONCAT('<:_:', i.emoji_id, '>') AS emoji, inv.quantity, i.sell_price
                    FROM players.inventory AS inv
                    INNER JOIN utility.items AS i
                    ON inv.item_id = i.item_id
                WHERE 
                    inv.player_id = $1 AND 
                    inv.inv_type = 0 AND
                    i.sell_price > 0 AND
                    NOT i.item_id = ANY($2::int[])
            """,
            interaction.user.id,
            exclude_items,
        )
        if not sellable_items:
            await interaction.send_text("You sold nothing! What a shame...")
            return

        # calculate the total price of the sold items
        total_price = 0
        for item in sellable_items:
            total_price += item["sell_price"] * item["quantity"]

        view = ConfirmView(
            interaction=interaction,
            embed=self.get_sell_item_embed(sellable_items, total_price),
            confirm_func=self.sell_all_player_items,
            confirmed_title="BOSS Cash Receipt",
            exclude_items=exclude_items,
        )
        view.embed.title = "Pending Confirmation"
        await view.send()

    @sell.subcommand(name="item")
    @cooldowns.shared_cooldown("sell_items")
    async def sell_item(
        self,
        interaction: BossInteraction,
        item_name: str = SlashOption(
            name="item",
            description="The item to sell",
            required=True,
            autocomplete_callback=choose_backpack_sellable_autocomplete,
        ),
        quantity: int = SlashOption(
            description="Amount of items to sell. Defaults to selling every one of the item.",
            required=False,
            min_value=1,
        ),
    ):
        """Sell a specific item in your backpack."""
        db: Database = self.bot.db
        item = await db.fetchrow(
            self.GET_SELLABLE_SQL,
            interaction.user.id,
            item_name,
        )
        if not item:
            await interaction.send_text("The item does not exist.", EmbedColour.WARNING)
            return

        if not item["sell_price"]:
            await interaction.send_text(
                "The item can't be sold! Try trading them.", EmbedColour.WARNING
            )
            return

        if not item["quantity"]:
            await interaction.send_text("You don't own any of the item.", EmbedColour.WARNING)
            return

        inv_quantity = item["quantity"]
        if quantity is None:
            quantity = inv_quantity
        if inv_quantity < quantity:
            await interaction.send_text(
                f"You only have {inv_quantity}x {item['emoji']} {item['name']}, which is {quantity - inv_quantity} short."
                "Don't imagine yourself as such a rich person, please."
            )
            return

        item = dict(item)  # convert the item into a dictionary so that we can modify it
        item["quantity"] = quantity
        total_price = item["sell_price"] * quantity

        async def sell_player_items(*args, **kwargs):
            async with db.pool.acquire() as conn:
                async with conn.transaction():
                    player = Player(db, interaction.user)
                    await player.modify_scrap(total_price)
                    await player.add_item(item["item_id"], -quantity)

        if total_price > 100_000:
            view = ConfirmView(
                interaction=interaction,
                embed=self.get_sell_item_embed((item,), total_price),
                confirm_func=sell_player_items,
                confirmed_title="BOSS Cash Receipt",
            )
            view.embed.title = "Pending Confirmation"
            await view.send()
        else:
            await sell_player_items()
            embed = self.get_sell_item_embed((item,), total_price)
            await interaction.send(embed=embed)

    @nextcord.slash_command(name="exchange")
    async def exchange_currency_cmd(self, interaction: BossInteraction):
        """Exchange your currency between scrap metals and coppers."""
        pass

    async def exchange_currencies(
        self,
        interaction: BossInteraction,
        from_currency: Literal["scrap_metal", "copper"],
        to_currency: Literal["scrap_metal", "copper"],
        amount: str,
    ):
        """Convert from one currency to another."""
        if from_currency not in ("scrap_metal", "copper") or to_currency not in (
            "scrap_metal",
            "copper",
        ):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")

        try:
            amount = helpers.text_to_num(amount)
        except ValueError:
            await interaction.send_text("The amount is invalid.")
            return

        from_currency_msg = from_currency.replace("_", " ")
        to_currency_msg = to_currency.replace("_", " ")

        if amount <= 0:
            await interaction.send_text(
                f"Enter a positive amount of {from_currency_msg} to exchange into {to_currency_msg}."
            )
            return

        # set the exchange rate so that the user loses some of the currency's value when they exchange them
        if from_currency == "scrap_metal":
            exchange_rate = constants.COPPER_SCRAP_RATE * random.uniform(1, 1.2)
            op = operator.truediv
        elif from_currency == "copper":
            exchange_rate = constants.COPPER_SCRAP_RATE * random.uniform(0.8, 1)
            op = operator.mul

        exchange_rate = round(exchange_rate)
        exchanged_amount = round(op(amount, exchange_rate))

        if exchanged_amount <= 0:  # The user has not exchanged enough scrap metal to have 1 copper
            await interaction.send_text(
                f"{amount} {from_currency_msg} is not enough to make 1 {to_currency_msg}."
            )
            return

        db: Database = interaction.client.db
        player = Player(db, interaction.user)

        # when we use transactions, if an error occurs/the function returns in the context manager,
        # then changes will be rolled back
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    from_amount = await player.modify_currency(from_currency, -amount)
                    to_amount = await player.modify_currency(to_currency, exchanged_amount)
                except ValueError:
                    await interaction.send_text(
                        f"You don't have enough {from_currency_msg} to make this exchange."
                    )
                    return

        embed = interaction.Embed()
        embed.description = (
            f"The current exchange rate is **{exchange_rate}** {to_currency_msg} for 1 {from_currency_msg}.\n"
            f"You got **{exchanged_amount:,} {constants.CURRENCY_EMOJIS[to_currency]}**."
        )

        embed.add_field(
            name="Current Balance",
            value=f"{from_currency_msg.title()}: {constants.CURRENCY_EMOJIS[from_currency]} `{from_amount:,}`\n"
            f"{to_currency_msg.title()}: {constants.CURRENCY_EMOJIS[to_currency]} `{to_amount:,}`\n",
        )
        await interaction.send(embed=embed)

    @exchange_currency_cmd.subcommand(name="to-copper")
    @command_info(
        notes=[
            "⚠️ You will lose some value of your cash when exchanging.",
            "For example, if you converted 5m scrap metals to copper and back again, you will get less than 5m.",
        ]
    )
    async def exchange_to_copper(
        self,
        interaction: BossInteraction,
        scrap_metal: str = SlashOption(
            name="scrap-metal", description="Amount of scrap metal to exchange"
        ),
    ):
        """Convert your scrap metals to coppers."""

        await self.exchange_currencies(
            interaction,
            "scrap_metal",
            "copper",
            scrap_metal,
        )

    @exchange_currency_cmd.subcommand(name="to-scrap")
    @command_info(
        notes=[
            "⚠️ You will lose some value of your cash when exchanging.",
            "For example, if you converted 50 copper to scrap metals and back again, you will get less than 50.",
        ]
    )
    async def exchange_to_scrap(
        self,
        interaction: BossInteraction,
        copper: str = SlashOption(description="Amount of copper to exchange"),
    ):
        """Convert your coppers to scrap metals."""

        await self.exchange_currencies(
            interaction,
            "copper",
            "scrap_metal",
            copper,
        )

    GET_BACKPACK_SQL = """
        SELECT i.*, CONCAT('<:_:', i.emoji_id, '>') AS emoji, bp.quantity
        FROM utility.items AS i
        INNER JOIN utility.SearchItem($2) AS s
        ON i.item_id = s.item_id
        LEFT JOIN 
            (SELECT inv.item_id, inv.quantity
            FROM players.inventory AS inv
            WHERE inv.player_id = $1 AND inv.inv_type = 0) AS bp
        ON bp.item_id = i.item_id
    """

    async def choose_backpack_autocomplete(self, interaction: BossInteraction, data: str):
        """Returns a list of autocompleted choices of all the items in a user's backpack"""
        db: Database = self.bot.db
        items = await db.fetch(self.GET_BACKPACK_SQL, interaction.user.id, data if data else "")
        await interaction.response.send_autocomplete(
            [i["name"] for i in items if i["quantity"] is not None][:25]
        )

    @nextcord.slash_command(name="use", description="Use an item to activiate its unique ability!")
    @command_info(
        notes="For information on what's the effect of an item, use </item:1006811041025507379> and search for the selected item."
    )
    @cooldowns.cooldown(1, 12, SlashBucket.author, check=check_if_not_dev_guild)
    async def use(
        self,
        interaction: BossInteraction,
        item_name: str = SlashOption(
            name="item",
            description="The item to use",
            autocomplete_callback=choose_backpack_autocomplete,
        ),
        quantity: int = SlashOption(
            description="Amount of the item to be used", required=None, default=1
        ),
    ):
        db: Database = self.bot.db
        item = await db.fetchrow(self.GET_BACKPACK_SQL, interaction.user.id, item_name)

        # perform some checks to see if the user can use their items
        if item is None:
            await interaction.send_text("The item does not exist.", EmbedColour.WARNING)
            return
        if item["quantity"] is None:
            await interaction.send_text(
                f"You don't have any of the {item['emoji']} **{item['name']}** in your backpack, and therefore can't use it.",
                EmbedColour.WARNING,
            )
            return
        if item["quantity"] < quantity:
            await interaction.send_text(
                f"You don't have enough {item['emoji']} **{item['name']}**!", EmbedColour.WARNING
            )
            return

        item = dict(
            item
        )  # convert the item from asyncpg.Record into a dict for the match-case statement
        player = Player(db, interaction.user)

        match item:
            case {"type": constants.ItemType.FOOD.value}:
                # the mininum and maximum hunger value that 1 unit of the food replenishes
                other_attributes = json.loads(item["other_attributes"])
                food_min, food_max = other_attributes.get("food_value_min"), other_attributes.get(
                    "food_value_max"
                )
                if not food_min or not food_max:
                    await interaction.send_text(
                        "This particular piece of food cannot be consumed, somehow."
                    )
                    return

                food_value = random.randint(food_min, food_max) * quantity
                old_hunger = await db.fetchval(
                    """
                        UPDATE players.players
                        SET hunger = hunger + $1
                        WHERE player_id = $2
                        RETURNING 
                            (SELECT hunger
                            FROM players.players
                            WHERE player_id = $2) AS old_hunger
                    """,
                    food_value,
                    interaction.user.id,
                )
                if old_hunger >= 100:
                    await interaction.send_text(
                        "Your hunger is already full, why are you even eating???"
                    )
                    return

                # perform another query because we need to wait for the trigger function to occur
                # the trigger function makes sure that the hunger is in range of [0, 100]
                # note that we cannot simply perform `old_hunger + food_value` because it may be larger than 100, in which case it will be set to 100
                # we would not want to check it here since other checks might be added in the future and we need to update both the database and the code here
                new_hunger = await db.fetchval(
                    """
                        SELECT hunger
                        FROM players.players
                        WHERE player_id = $1
                    """,
                    interaction.user.id,
                )
                msg = (
                    f"You ate {quantity} {item['emoji']} **{item['name']}**.\n"
                    f"Your hunger is now {new_hunger}, increased by {new_hunger - old_hunger}."
                )

            case {"item_id": 61}:  # health potion
                # add 60-80 points of health to the player
                value = random.randint(60, 80)
                new_health = await player.modify_health(value)
                msg = (
                    f"You drank {quantity} {item['emoji']} **{item['name']}**.\n"
                    f"Your health is now {new_health}, increased by {value}."
                )

            case {"type": constants.ItemType.ANIMAL.value}:
                # convert the animal to "food" item
                await player.add_item(55, quantity)
                food_item = BossItem(55, quantity)
                msg = (
                    f"You roasted {quantity} {item['emoji']} **{item['name']}** over the fire and "
                    f"got {quantity} {await food_item.get_emoji(db)} **{await food_item.get_name(db)}**!"
                )

            case {"item_id": 44}:  # Iron ore
                await player.add_item(50, quantity)
                msg = f"Converted {quantity} iron ore into ingots!"

            case {"item_id": 57}:  # jungle explorer map
                if quantity > 1:
                    await interaction.send_text(
                        f"{item['emoji']} **{item['name']}** could not be used for multiple times at once."
                    )
                    return

                async def confirm_func(button, btn_interaction: BossInteraction):
                    maze_size = (random.randint(25, 30), random.randint(25, 30))
                    view = Maze(
                        btn_interaction,
                        maze_size,
                        rewards=[
                            BossCurrency.from_range("5m", "6m"),
                            BossItem(15),  # hoho
                            BossItem(16),  # keith
                            BossItem(17),  # karson
                        ],
                    )
                    await player.add_item(57, -quantity)
                    await view.send()

                view = ConfirmView(
                    interaction=interaction,
                    confirm_func=confirm_func,
                    embed=TextEmbed(
                        "The map leads you to a pyramid, in which a maze is placed. "
                        "The maze has tons of dangerous obstacles preventing people from getting into its secret room, "
                        "which has valuable treasure that makes everyone rich beyond their wildest dreams.\n"
                        "### Do you want to continue?"
                    ),
                    confirmed_title="",
                    cancelled_title="",
                )
                await view.send()
                return

            case _:
                await interaction.send_text("You can't use this item", EmbedColour.WARNING)
                return
        # do something universal of all items able to be used
        new_quantity = await player.add_item(item["item_id"], -quantity)
        view = View()
        button = Button(
            label=f"You have {new_quantity if new_quantity is not None else 0}x {item['name']} left",
            emoji=item["emoji"],
            style=ButtonStyle.grey,
            disabled=True,
        )
        view.add_item(button)
        await interaction.send(embed=interaction.TextEmbed(msg), view=view)

    @nextcord.slash_command(name="profile", description="Check the profile of a user.")
    @command_info(notes="If you leave the `user` parameter empty, you can view your own profile.")
    @cooldowns.cooldown(1, 8, SlashBucket.author, check=check_if_not_dev_guild)
    async def profile(
        self,
        interaction: BossInteraction,
        user: nextcord.User = SlashOption(
            name="user",
            description="The user to check the profile. Leave the option empty to view yours.",
            required=False,
            default=None,
        ),
    ):
        if user is None:
            user = interaction.user
        db: Database = self.bot.db

        player = Player(db, user)
        if not await player.is_present():
            await interaction.send_text(
                "The user hasn't started playing BOSS yet! Maybe invite them over?"
            )
            return

        profile = await db.fetchrow(
            """
            SELECT scrap_metal, copper, safe_scrap, experience, health, hunger, commands_run
            FROM players.players
            WHERE player_id = $1
            """,
            user.id,
        )

        embed = interaction.Embed(
            title=f"{user.name}'s Profile", colour=EmbedColour.INFO, with_url=True
        )
        embed.set_thumbnail(url=user.display_avatar.url)

        exp = profile["experience"]

        unique_items, total_items = await db.fetchrow(
            """
            SELECT COUNT(DISTINCT item_id) as unique_items, COALESCE(SUM(quantity), 0) as total_items
            FROM players.inventory
            WHERE player_id = $1
            """,
            user.id,
        )

        item_worth = await db.fetchval(
            """
            SELECT SUM(items.trade_price * inv.quantity)::bigint As item_worth
                FROM players.inventory As inv

                INNER JOIN utility.items
                ON inv.item_id = items.item_id
                
                INNER JOIN players.players
                ON inv.player_id = players.player_id
            WHERE inv.player_id = $1
            """,
            user.id,
        )
        if item_worth is None:
            item_worth = 0
        money_worth = (
            profile["scrap_metal"] + profile["copper"] * COPPER_SCRAP_RATE + profile["safe_scrap"]
        )
        net_worth = item_worth + money_worth

        # Fields row 1
        embed.add_field(
            name="Health",
            value=f"`{profile['health']}/100`\n {helpers.create_pb(profile['health'])}",
        )
        embed.add_field(
            name="Hunger",
            value=f"`{profile['hunger']}/100`\n {helpers.create_pb(profile['hunger'])}",
        )
        embed.add_field(
            name="Experience",
            value=f"Level: `{math.floor(exp / 100)}` (`{exp % 100}/100`)\n {helpers.create_pb(exp % 100)}",
        )
        # Fields row 2
        embed.add_field(
            name="Money",
            value=f"Pocket: {SCRAP_METAL} `{numerize.numerize(profile['scrap_metal'], 1)}`\n"
            f"Pocket: {COPPER} `{numerize.numerize(profile['copper'], 1)}`\n"
            f"Safe: {SCRAP_METAL} `{numerize.numerize(profile['safe_scrap'], 1)}`\n",
        )
        embed.add_field(
            name="Items",
            value=f"Unique: `{unique_items}`\n"
            f"Total: `{total_items}`\n"
            f"Worth: {SCRAP_METAL} `{numerize.numerize(item_worth, 1)}`\n",
        )
        embed.add_field(
            name="Net Worth",
            value=f"Money: {SCRAP_METAL} `{numerize.numerize(money_worth, 1)}`\n"
            f"Item: {SCRAP_METAL} `{numerize.numerize(item_worth, 1)}`\n"
            f"**Net**: {SCRAP_METAL} `{numerize.numerize(net_worth, 1)}`",
        )
        await interaction.send(embed=embed)

    @nextcord.slash_command(
        name="balance", description="Check a user's balance. Cash, item worth, and net."
    )
    @cooldowns.cooldown(1, 8, SlashBucket.author, check=check_if_not_dev_guild)
    async def balance(
        self,
        interaction: BossInteraction,
        user: nextcord.User = SlashOption(
            name="user",
            description="The user to check the balance. Leave the option empty to view yours.",
            required=False,
            default=None,
        ),
    ):
        if user is None:
            user = interaction.user
        db: Database = self.bot.db
        player = Player(db, user)
        if not await player.is_present():
            await interaction.send_text(
                "The user hasn't started playing BOSS yet! Maybe invite them over?"
            )
            return

        scrap_metal, copper, safe_scrap, item_worth = await db.fetchrow(
            """
            SELECT scrap_metal, copper, safe_scrap, SUM(items.trade_price * inv.quantity)::bigint As item_worth
                FROM players.inventory As inv
                INNER JOIN utility.items
                ON inv.item_id = items.item_id
                INNER JOIN players.players
                ON inv.player_id = players.player_id
            WHERE inv.player_id = $1
            GROUP BY scrap_metal, copper, safe_scrap
            """,
            user.id,
        )
        safe_space = round(scrap_metal * 0.2)
        used_safe = round(safe_scrap / safe_space * 100)

        if item_worth is None:
            item_worth = 0

        net_worth = item_worth + scrap_metal + copper * COPPER_SCRAP_RATE + safe_scrap

        rank = await db.fetchval(
            """
            SELECT rank 
            FROM (
                SELECT 
                    p.player_id, 
                    PERCENT_RANK() OVER (ORDER BY (p.scrap_metal + $2)) AS rank
                FROM players.players AS p
            ) AS ranks
            WHERE player_id = $1
            """,
            user.id,
            item_worth,
        )

        embed = interaction.Embed(
            title=f"{user.name}'s Balance", colour=EmbedColour.INFO, with_url=True
        )
        # row 1
        embed.add_field(name="Scrap Metal", value=f"{SCRAP_METAL} {scrap_metal:,}")
        embed.add_field(name="Safe", value=f"{SCRAP_METAL} {safe_scrap:,}")
        embed.add_field(
            name="Safe space", value=f"{SCRAP_METAL} {safe_space:,} ({used_safe}% full)"
        )
        # row 2
        embed.add_field(name="Copper", value=f"{COPPER} {copper:,}")
        embed.add_field(name="Item worth", value=f"{SCRAP_METAL} {item_worth:,}")
        embed.add_field(name="Net worth", value=f"{SCRAP_METAL} {net_worth:,}")

        embed.set_footer(
            text=f"{'You are' if user == interaction.user else f'{user.name} is'} ahead of {round(rank * 100, 1)}% of users!"
        )
        await interaction.send(embed=embed)

    @nextcord.slash_command(
        description="See the richest men in the (BOSS) world, who is probably not Elon Musk."
    )
    @command_info(notes="This command is global. We will add a server-specific scope soon.")
    @cooldowns.cooldown(1, 20, SlashBucket.author, check=check_if_not_dev_guild)
    async def leaderboard(self, interaction: BossInteraction):
        lb = await self.bot.db.fetch(
            """
            SELECT players.player_id, COALESCE(SUM(items.trade_price * inv.quantity)::bigint, 0) + players.scrap_metal + players.copper * $1 As net_worth
                FROM players.players
                LEFT JOIN players.inventory AS inv
                    ON inv.player_id = players.player_id
                LEFT JOIN utility.items
                    ON inv.item_id = items.item_id
            GROUP BY players.player_id
            ORDER BY net_worth DESC
            LIMIT 8
            """,
            COPPER_SCRAP_RATE,
        )
        embed = interaction.Embed(
            title="Net Worth Leaderboard", description="", colour=EmbedColour.INFO
        )
        medal_emojis = {
            1: "🥇",
            2: "🥈",
            3: "🥉",
        }
        for i, (id, net_worth) in enumerate(lb):
            user = await self.bot.fetch_user(id)
            emoji = medal_emojis.get(i + 1, "🔹")
            embed.description += f"{emoji} ` {net_worth:,} ` - {user.name}\n"
        await interaction.send(embed=embed)

    @nextcord.slash_command()
    @cooldowns.shared_cooldown("check_inv")
    async def backpack(
        self,
        interaction: BossInteraction,
        user: nextcord.Member = SlashOption(
            name="user",
            description="The user to check the backpack of",
            required=False,
            default=None,
        ),
        page: int = SlashOption(
            description="The page to start in", required=False, min_value=1, default=1
        ),
    ):
        """Check the backpack of your own or others."""
        if user == None:
            user = interaction.user
        await InventoryView.send(
            interaction=interaction, user=user, inv_type=constants.InventoryType.BACKPACK, page=page
        )

    @nextcord.slash_command()
    @cooldowns.shared_cooldown("check_inv")
    async def chest(
        self,
        interaction: BossInteraction,
        user: nextcord.Member = SlashOption(
            name="user",
            description="The user to check the chest of",
            required=False,
            default=None,
        ),
        page: int = SlashOption(
            description="The page to start in", required=False, min_value=1, default=1
        ),
    ):
        """Check the chest of your own or others."""
        if user == None:
            user = interaction.user
        await InventoryView.send(
            interaction=interaction, user=user, inv_type=constants.InventoryType.CHEST, page=page
        )

    @nextcord.slash_command()
    @cooldowns.shared_cooldown("check_inv")
    async def vault(
        self,
        interaction: BossInteraction,
        page: int = SlashOption(
            description="The page to start in", required=False, min_value=1, default=1
        ),
    ):
        """Check the vault of your own."""
        await InventoryView.send(
            interaction=interaction,
            user=interaction.user,
            inv_type=constants.InventoryType.VAULT,
            page=page,
        )

    @vault.before_invoke
    @staticmethod
    async def vault_before_invoke(interaction: BossInteraction):
        await interaction.response.defer(ephemeral=True)

    async def choose_inv_autocomplete(self, interaction: BossInteraction, data: str):
        """Returns a list of autocompleted choices of a user's inventory"""
        db: Database = self.bot.db
        items = await db.fetch(
            """
            SELECT i.name
            FROM utility.items AS i
            INNER JOIN utility.SearchItem($2) AS s
            ON i.item_id = s.item_id
            INNER JOIN 
                (SELECT DISTINCT item_id
                FROM players.inventory
                WHERE player_id = $1) AS inv
            ON inv.item_id = i.item_id
            """,
            interaction.user.id,
            data,
        )
        await interaction.response.send_autocomplete([item[0] for item in items][:25])

    async def _move_items(
        self,
        player_id: int,
        item_from: int,
        item_to: int,
        item_id: int,
        quantity: int = None,
    ) -> dict[str, int]:
        """
        Moves an item from an inventory type to another one.
        If `quantity` is not provided all items will be moved.

        Should be used with try/except to catch errors when
        1) there are not enough items
        2) the slots are full
        3) the player is trying to move battlegear that he/she equipped
        """
        db: Database = self.bot.db
        quantities_after = {}
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                if quantity is None:  # move all items of that name in that specific inv_type
                    quantity = await conn.fetchval(
                        """
                        UPDATE players.inventory
                        SET quantity = 0
                        WHERE player_id = $1 AND inv_type = $2 AND item_id = $3
                        RETURNING (SELECT quantity As old_quantity FROM players.inventory WHERE player_id = $1 AND inv_type = $2 AND item_id = $3) As quantity 
                        """,
                        player_id,
                        item_from,
                        item_id,
                    )
                    if quantity is None:
                        raise MoveItemException("Not enough items to move!")
                    quantities_after["from"] = 0
                else:  # moves specific number of the item out of from_place
                    quantities_after["from"] = await conn.fetchval(
                        """
                        UPDATE players.inventory
                        SET quantity = quantity - $4
                        WHERE player_id = $1 AND inv_type = $2 AND item_id = $3
                        RETURNING quantity
                        """,
                        player_id,
                        item_from,
                        item_id,
                        quantity,
                    )
                    if quantities_after["from"] < 0:
                        raise MoveItemException("Not enough items to move!")

                is_equipped_battlegear = await conn.fetchval(
                    "SELECT EXISTS (SELECT item_id FROM players.battlegear WHERE player_id = $1 AND item_id = $2 LIMIT 1)",
                    player_id,
                    item_id,
                )
                if is_equipped_battlegear and quantities_after["from"] <= 0:
                    raise MoveItemException(
                        "You need at least 1 of the battlegear in your backpack."
                    )

                # moves item to to_place
                quantities_after["to"] = await conn.fetchval(
                    """
                    INSERT INTO players.inventory (player_id, inv_type, item_id, quantity)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT(player_id, inv_type, item_id) DO UPDATE
                        SET quantity = inventory.quantity + excluded.quantity
                    RETURNING quantity
                    """,
                    player_id,
                    item_to,
                    item_id,
                    quantity,
                )

                if quantities_after["to"] != quantity:  # a new item is not added
                    return quantities_after

                inv_items_count = await db.fetch(
                    """
                    SELECT inv_type, COUNT(item_id)
                    FROM players.inventory
                    WHERE player_id = $1
                    GROUP BY inv_type
                    ORDER BY inv_type
                    """,
                    player_id,
                )
                for inv_type, n_items in inv_items_count:
                    # transaction has not been committed, items are not updated
                    # so we check for the old values
                    if (
                        item_to == inv_type == constants.InventoryType.BACKPACK.value
                        and n_items >= 32
                    ):
                        raise MoveItemException("Backpacks only have 32 slots!")
                    if item_to == inv_type == constants.InventoryType.VAULT.value and n_items >= 5:
                        raise MoveItemException("Vaults only have 5 slots!")

        return quantities_after

    @nextcord.slash_command(name="move-item")
    @cooldowns.cooldown(1, 180, SlashBucket.author, check=check_if_not_dev_guild)
    async def move_item_command(
        self,
        interaction: BossInteraction,
        item_name: str = SlashOption(
            name="item",
            description="The item to move",
            required=True,
            autocomplete_callback=choose_inv_autocomplete,
        ),
        item_from: int = SlashOption(
            name="from",
            description="Where are you going to move the items from?",
            required=True,
            choices=constants.InventoryType.to_dict(),
        ),
        item_to: int = SlashOption(
            name="to",
            description="Where are you going to move the item to?",
            required=True,
            choices=constants.InventoryType.to_dict(),
        ),
        quantity: int = SlashOption(
            description="How many of the item do you want to move? Defaults to all you own.",
            required=False,
            default=None,
        ),
    ):
        """Moves items from one place to other."""

        if item_from == item_to:
            await interaction.send_text("Choose different locations to move to!")
            return

        db: Database = self.bot.db
        item = await db.fetchrow(self.GET_ITEM_SQL, item_name)
        if not item:
            await interaction.send_text("The item is not found!")
            return

        try:
            quantities_after = await self._move_items(
                player_id=interaction.user.id,
                item_from=item_from,
                item_to=item_to,
                item_id=item["item_id"],
                quantity=quantity,
            )

        except MoveItemException as e:
            await interaction.send_text(e.text, EmbedColour.FAIL)
            return

        msg = await interaction.send_text("Moving your items...\n||* intentional wait *||")
        await asyncio.sleep(random.uniform(3, 8))

        embed = interaction.Embed(colour=EmbedColour.SUCCESS)
        embed.set_author(
            name=f"Updated {interaction.user.name}'s inventory!",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.description = f">>> Item: **{item['name']}**"
        embed.description += (
            f"\nQuantity in {constants.InventoryType(item_from)}: `{quantities_after['from']}`"
        )
        embed.description += (
            f"\nQuantity in {constants.InventoryType(item_to)}: `{quantities_after['to']}`"
        )
        embed.set_thumbnail(url=f"https://cdn.discordapp.com/emojis/{item['emoji_id']}.png")
        await msg.edit(embed=embed)

    async def _change_balance(
        self, interaction: BossInteraction, action: Literal["deposit", "withdraw"], amount: int
    ):
        """Deposit or withdraw a user's scrap metals."""
        async with interaction.client.db.pool.acquire() as conn:
            async with conn.transaction():
                new_scrap, new_safe = await conn.fetchrow(
                    """
                    UPDATE players.players
                    SET 
                        scrap_metal = scrap_metal - $2,
                        safe_scrap = safe_scrap + $2
                    WHERE player_id = $1
                    RETURNING scrap_metal, safe_scrap
                    """,
                    interaction.user.id,
                    amount if action == "deposit" else -amount,
                )
                if new_safe > new_scrap * 0.2:
                    await interaction.send_text(
                        "You already have a full safe!\n"
                        "You can only store at most 20% of your scrap metals in your safe.",
                        EmbedColour.WARNING,
                    )
                    raise ValueError

        embed = interaction.Embed(colour=EmbedColour.DEFAULT)
        embed.description = (
            f"**{'Deposited' if action == 'deposit' else 'Withdrew'}**\n {SCRAP_METAL} {amount:,}"
        )
        embed.add_field(name="Current Scrap Metals", value=f"{SCRAP_METAL} {new_scrap:,}")
        embed.add_field(name="Current Safe Balance", value=f"{SCRAP_METAL} {new_safe:,}")
        await interaction.send(embed=embed)

    @nextcord.slash_command(description="Store your scrap metals in your safe where it'll be safe!")
    async def deposit(
        self,
        interaction: BossInteraction,
        amount: str = SlashOption(
            description="A constant number (1234), shorthand (3k), or relative keyword (50%/all)"
        ),
    ):
        scrap, safe = await interaction.client.db.fetchrow(
            "SELECT scrap_metal, safe_scrap FROM players.players WHERE player_id = $1",
            interaction.user.id,
        )
        # calculated by complicated math:
        #   (safe + amt) / (scrap - amt) = 0.2  --> change subject
        available_safe = (scrap - 5 * safe) / 6
        amount = amount.strip().lower()

        if amount.endswith("%"):
            try:
                amount = amount.removesuffix("%")
                amount = float(amount) if "." in amount else int(amount)
            except ValueError:
                await interaction.send_text("That is not a valid relative keyword (eg 50%).")
                return
            if amount > 100 or amount <= 0:
                await interaction.send_text("The percentage must be within the range 0-100.")
                return
            amount = amount / 100 * available_safe
        elif amount in ("all", "max"):
            amount = available_safe
        else:  # constant number/shorthand
            try:
                amount = helpers.text_to_num(amount)
            except ValueError:
                await interaction.send_text("That is not a valid amount.")
                return
            if amount > scrap:
                await interaction.send_text("You don't have that much scrap metals.")
                return
            if amount <= 0:
                await interaction.send_text("Enter a positive amount of scrap metals.")
                return

        amount = math.floor(amount)
        if amount <= 0:
            await interaction.send_text("You already have a full safe!")
            return
        try:
            await self._change_balance(interaction, "deposit", amount)
        except ValueError:
            pass

    @nextcord.slash_command(description="Withdraw money from your safe into your pocket.")
    async def withdraw(
        self,
        interaction: BossInteraction,
        amount: str = SlashOption(
            description="A constant number (1234), shorthand (3k), or relative keyword (50%/all)"
        ),
    ):
        safe = await interaction.client.db.fetchval(
            "SELECT safe_scrap FROM players.players WHERE player_id = $1", interaction.user.id
        )
        amount = amount.strip().lower()

        if amount.endswith("%"):
            try:
                amount = amount.removesuffix("%")
                amount = float(amount) if "." in amount else int(amount)
            except ValueError:
                await interaction.send_text("That is not a valid relative keyword (eg 50%).")
                return
            if amount > 100 or amount <= 0:
                await interaction.send_text("The percentage must be within the range 0-100.")
                return
            amount = amount / 100 * safe
        elif amount in ("all", "max"):
            amount = safe
        else:  # constant number/shorthand
            try:
                amount = helpers.text_to_num(amount)
            except ValueError:
                await interaction.send_text("That is not a valid amount.")
                return
            if amount > safe:
                await interaction.send_text("You don't have that much scrap metals in your safe.")
                return
            if amount <= 0:
                await interaction.send_text("Enter a positive amount of scrap metals.")
                return

        amount = math.floor(amount)
        try:
            await self._change_balance(interaction, "withdraw", amount)
        except ValueError:
            pass

    @nextcord.slash_command(description="Protect yourself with battlegear!")
    async def battlegear(self, interaction: BossInteraction):
        # base commands will not be run
        pass

    async def choose_battlegear_autocomplete(self, interaction: BossInteraction, data: str):
        """Returns a list of autocompleted choices of all the items in a user's backpack"""
        db: Database = self.bot.db
        items = await db.fetch(
            """
                SELECT i.*, CONCAT('<:_:', i.emoji_id, '>') AS emoji
                FROM utility.items AS i
                INNER JOIN utility.SearchItem($1) AS s
                ON i.item_id = s.item_id
                WHERE i.other_attributes ? 'battlegear_type'
            """,
            data if data else "",
        )
        await interaction.response.send_autocomplete([i["name"] for i in items][:25])

    @battlegear.subcommand(description="Equip your battlegear")
    async def equip(
        self,
        interaction: BossInteraction,
        item_name: str = SlashOption(
            name="item",
            description="The battlegear to equip",
            autocomplete_callback=choose_battlegear_autocomplete,
        ),
    ):
        db: Database = self.bot.db
        item = await db.fetchrow(self.GET_BACKPACK_SQL, interaction.user.id, item_name)

        # perform some checks to see if the user can equip the battlegear
        if item is None:
            await interaction.send_text("The item does not exist.", EmbedColour.WARNING)
            return
        other_attributes = json.loads(item["other_attributes"])
        if not (battlegear_type := other_attributes.get("battlegear_type")):
            await interaction.send_text(
                f"**{item['name']}** {item['emoji']} is not a piece of battlegear.",
                EmbedColour.WARNING,
            )
            return
        if item["quantity"] is None:
            await interaction.send_text(
                f"You don't have any **{item['name']}** {item['emoji']} in your backpack.",
                EmbedColour.WARNING,
            )
            return

        old_battlegear_id = await db.fetchval(
            "SELECT item_id FROM players.battlegear WHERE player_id = $1 AND type = $2",
            interaction.user.id,
            battlegear_type,
        )
        # the user was previously using the same armour
        if old_battlegear_id == item["item_id"]:
            await interaction.send_text(
                f"You have already equipped the **{item['name']}** {item['emoji']}!"
            )
            return

        async def change_battlegear(*args, **kwargs):
            await db.execute(
                """
                INSERT INTO players.battlegear
                VALUES ($1, $2, $3)
                ON CONFLICT(player_id, type) DO UPDATE
                    SET item_id = $3
                RETURNING (SELECT item_id FROM players.battlegear WHERE player_id = $1 AND type = $2) AS old_id
                """,
                interaction.user.id,
                battlegear_type,
                item["item_id"],
            )
            await interaction.send_text(
                f"Your equipped {battlegear_type} is now {item['emoji']} **{item['name']}**.",
                EmbedColour.SUCCESS,
            )

        # the user previously has not equipped any armour
        if old_battlegear_id is None:
            await change_battlegear()
            return

        old_battlegear = await db.fetchrow(
            """
            SELECT 
            name, CONCAT('<:_:', emoji_id, '>') AS emoji
            FROM utility.items
            WHERE item_id = $1
            """,
            old_battlegear_id,
        )
        embed = interaction.Embed(
            title="Pending Confirmation",
            description=f"Do you want to replace {old_battlegear['emoji']} **{old_battlegear['name']}** with {item['emoji']} **{item['name']}** as your {battlegear_type}?",
        )
        # the armour is changed, so we ask the user for confirmation
        await ConfirmView(
            interaction=interaction, confirm_func=change_battlegear, embed=embed
        ).send()

    @battlegear.subcommand(description="Remove your equipped battlegear")
    async def remove(
        self,
        interaction: BossInteraction,
        battlegear_type: str = SlashOption(
            name="battlegear-type",
            description="The type of battlegear to remove",
            choices=["helmet", "chestplate", "leggings", "boots", "sword"],
        ),
    ):
        db: Database = self.bot.db
        old_battlegear_id = await db.fetchval(
            """
            DELETE FROM players.battlegear
            WHERE player_id = $1 AND type = $2
            RETURNING item_id AS old_id
            """,
            interaction.user.id,
            battlegear_type,
        )
        # the user previously has not equipped any armour
        if old_battlegear_id is None:
            await interaction.send_text(
                f"You have not equipped any {battlegear_type} previously.", EmbedColour.WARNING
            )
            return
        old_battlegear = await db.fetchrow(
            """
            SELECT 
            name, CONCAT('<:_:', emoji_id, '>') AS emoji
            FROM utility.items
            WHERE item_id = $1
            """,
            old_battlegear_id,
        )
        # tell the users that the battlegear has been removed
        await interaction.send_text(
            f"Successfully un-equipped **{old_battlegear['name']}** {old_battlegear['emoji']}!"
        )

    @battlegear.subcommand(description="View a user's list of equipped battlegear")
    async def view(
        self,
        interaction: BossInteraction,
        user: nextcord.User = SlashOption(
            description="The user to view the list of battlegear of. Leave this empty to check your own.",
            required=False,
        ),
    ):
        if not user:
            user = interaction.user
        db: Database = self.bot.db

        async def get_embed():
            battlegear = await db.fetch(
                """
                SELECT 
                    type_name, 
                    i.name AS item_name, 
                    CASE 
                        WHEN i.emoji_id IS NOT NULL THEN CONCAT('<:_:', i.emoji_id, '>')
                        ELSE ''
                    END AS emoji,
                    i.other_attributes
                FROM players.battlegear AS b
                    RIGHT JOIN unnest(enum_range(NULL::utility.battlegear_type)) AS type_name
                    ON b.type = type_name AND b.player_id = $1
                    LEFT JOIN utility.items AS i
                    ON b.item_id = i.item_id
                    ORDER BY type_name
                """,
                user.id,
            )
            embed = interaction.Embed(
                title=f"{user.name}'s Equipped Battlegear", colour=EmbedColour.INFO
            )
            player = Player(db, user)
            armour_prot, weapon_dmg, combat = await player.calc_combat()

            battlegear_msg = ""
            max_name_len = max(len(i["item_name"] or i["type_name"]) for i in battlegear)
            for i in battlegear:
                battlegear_msg += (
                    f"\n` {i['item_name'] :>{max_name_len}} ` {i['emoji']}"
                    if i["item_name"]
                    else f"\n_` {i['type_name'] :>{max_name_len}} `_"
                )
            embed.add_field(name="Battlegear", value=battlegear_msg)

            COLOURS = {
                80: 36,
                50: 34,
                20: 33,
                0: 31,
            }  # min_value: colour, must be sorted descending
            get_colour = lambda x, max=100: next(
                (v for k, v in COLOURS.items() if x / max >= k / 100), 0
            )
            get_colour_fmt = (
                lambda value, max=100, format=2: f"[{format};{get_colour(value, max)}m{value}[0m"
            )

            combat_msg = "```ansi"
            combat_msg += f"\nArmour Protection: {get_colour_fmt(armour_prot)}"
            combat_msg += f"\nWeapon Damage: {get_colour_fmt(weapon_dmg, 30)}"
            combat_msg += f"\n[1;40mOverall: {get_colour_fmt(combat, format=1)}"
            combat_msg += f"\n```{helpers.create_pb(combat)}"
            embed.add_field(name="Combat", value=combat_msg)

            return embed

        # create a view to let users reload the embed
        view = BaseView(interaction, timeout=300)  # timeout is 5 minutes
        button = Button(emoji="🔄")

        async def reload_missions(btn_inter: BossInteraction):
            await btn_inter.response.edit_message(embed=await get_embed())

        button.callback = reload_missions
        view.add_item(button)

        await interaction.send(embed=await get_embed(), view=view)


class MoveItemException(Exception):
    def __init__(self, text) -> None:
        self.text = text


def setup(bot: commands.Bot):
    cog = ResourceRepository(bot)
    bot.add_cog(cog)

# nextcord
import nextcord
from nextcord.ext import commands, tasks
from nextcord.ui import View, Button
from nextcord import Interaction, Embed, SlashOption, ButtonStyle

# slash command cooldowns
import cooldowns
from cooldowns import SlashBucket

import aiohttp

# database
from utils.postgres_db import Database
import asyncpg

# my modules and constants
from utils import constants, helpers
from utils.constants import SCRAP_METAL, COPPER, COPPER_SCRAP_RATE, EmbedColour
from utils.helpers import MoveItemException, TextEmbed, check_if_not_dev_guild, command_info, BossItem, BossCurrency
from utils.player import Player

# command views
from utils.template_views import ConfirmView
from .views import FarmView, InventoryView

# trade
from modules.village.village import TradeView
from modules.village.villagers import Villager

# maze
from modules.maze.maze import Maze

from numerize import numerize

# default modules
from collections import defaultdict
from typing import Literal
import random
import datetime
import pytz
import operator
import math
import asyncio


class Resource(commands.Cog, name="Resource Repository"):
    """Currency management, trading, and base building"""

    COG_EMOJI = "🪙"

    cooldowns.define_shared_cooldown(1, 8, SlashBucket.author, cooldown_id="sell_items", check=check_if_not_dev_guild)
    cooldowns.define_shared_cooldown(1, 6, SlashBucket.author, cooldown_id="check_inv", check=check_if_not_dev_guild)

    def __init__(self, bot):
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
        interaction: Interaction,
        itemname: str = SlashOption(
            name="item",
            description="The item to search for",
            autocomplete_callback=choose_item_autocomplete,
        ),
    ):
        db: Database = self.bot.db
        item = await db.fetchrow(self.GET_ITEM_SQL, itemname)
        if not item:
            await interaction.send(embed=TextEmbed("The item is not found!"))
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
            owned_quantities = {str(constants.InventoryType(inv_type)): quantity for inv_type, quantity in res}
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
            async with session.get("https://randommer.io/api/Name", params=params, headers=headers) as response:
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
        print(f"\033[1;30mUpdated villagers at {now}.\033[0m")
        await db.execute(f"COMMENT ON TABLE trades.villagers IS '{now}'")
        await self.bot.get_guild(919223073054539858).get_channel(1120926567930007582).send(
            embed=TextEmbed(f"villagers updated at {now}")
        )

    @update_villagers.before_loop
    async def before_update_villagers(self):
        now = datetime.datetime.now()
        # Wait until the start of the next hour before starting the task loop,
        # so that the trades get updated at the start of hours (HH:00)
        start_of_next_hour = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        await nextcord.utils.sleep_until(start_of_next_hour)

    @nextcord.slash_command(name="farm")
    async def farm(self, interaction: Interaction):
        """Engage yourself in a virtual farm - plant, harvest, and discover new crops!"""
        pass

    @farm.before_invoke
    async def create_farm(interaction: Interaction):
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
        interaction: Interaction,
        user: nextcord.User = SlashOption(description="The user to view the farm of", required=False, default=None),
    ):
        """Check your crops' progress."""
        if user is None:
            user = interaction.user

        player = Player(self.bot.db, user)
        view = FarmView(interaction, player)

        await view.send_message(interaction, with_view=True if user == interaction.user else False)

    def get_sell_item_embed(self, sold_items: tuple, total_price):
        embed = Embed()
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

    async def sell_all_player_items(self, button, interaction: Interaction):
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
                        CONCAT('<:', i.emoji_name, ':', i.emoji_id, '>') AS emoji,
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
        SELECT i.item_id, i.name, CONCAT('<:', i.emoji_name, ':', i.emoji_id, '>') AS emoji, i.sell_price, bp.quantity
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

    async def choose_backpack_sellable_autocomplete(self, interaction: Interaction, data: str):
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
        interaction: Interaction,
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
                    await interaction.send(
                        embed=TextEmbed(f"The item `{item_name}` doesn't exist.", EmbedColour.WARNING)
                    )
                    return
                if item["quantity"] is None:
                    await interaction.send(
                        embed=TextEmbed(f"You don't own any {item['emoji']} **{item['name']}**", EmbedColour.WARNING)
                    )
                    return

                exclude_items.append(item["item_id"])

        # get the remaining sellable items in the user's backpack where the item is not excluded
        sellable_items = await db.fetch(
            """
                SELECT i.item_id, i.name, CONCAT('<:', i.emoji_name, ':', i.emoji_id, '>') AS emoji, inv.quantity, i.sell_price
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
            await interaction.send(embed=TextEmbed("You sold nothing! What a shame..."))
            return

        # calculate the total price of the sold items
        total_price = 0
        for item in sellable_items:
            total_price += item["sell_price"] * item["quantity"]

        view = ConfirmView(
            slash_interaction=interaction,
            embed=self.get_sell_item_embed(sellable_items, total_price),
            confirm_func=self.sell_all_player_items,
            confirmed_title="BOSS Cash Receipt",
            exclude_items=exclude_items,
        )
        view.embed.title = "Pending Confirmation"
        await interaction.send(embed=view.embed, view=view)

    @sell.subcommand(name="item")
    @cooldowns.shared_cooldown("sell_items")
    async def sell_item(
        self,
        interaction: Interaction,
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
            await interaction.send(
                embed=TextEmbed("The item does not exist.", EmbedColour.WARNING),
            )
            return

        if not item["sell_price"]:
            await interaction.send(embed=TextEmbed("The item can't be sold! Try trading them.", EmbedColour.WARNING))
            return

        if not item["quantity"]:
            await interaction.send(embed=TextEmbed("You don't own any of the item.", EmbedColour.WARNING))
            return

        inv_quantity = item["quantity"]
        if quantity is None:
            quantity = inv_quantity
        if inv_quantity < quantity:
            embed = Embed()
            embed.description = (
                f"You only have {inv_quantity}x {item['emoji']} {item['name']}, which is {quantity - inv_quantity} short."
                "Don't imagine yourself as such a rich person, please."
            )
            await interaction.send(embed=embed)
            return

        item = dict(item)  # convert the item into a dictionary so that we can modify it
        item["quantity"] = quantity
        total_price = item["sell_price"] * quantity

        async def sell_player_items(button=None, btn_inter=None):
            async with db.pool.acquire() as conn:
                async with conn.transaction():
                    player = Player(db, interaction.user)
                    await player.modify_scrap(total_price)
                    await player.add_item(item["item_id"], -quantity)

        if total_price > 100_000:
            view = ConfirmView(
                slash_interaction=interaction,
                embed=self.get_sell_item_embed((item,), total_price),
                confirm_func=sell_player_items,
                confirmed_title="BOSS Cash Receipt",
            )
            view.embed.title = "Pending Confirmation"
            await interaction.send(embed=view.embed, view=view)
        else:
            await sell_player_items()
            embed = self.get_sell_item_embed((item,), total_price)
            await interaction.send(embed=embed)

    @nextcord.slash_command(name="exchange")
    async def exchange_currency_cmd(self, interaction: Interaction):
        """Exchange your currency between scrap metals and coppers."""
        pass

    async def exchange_currencies(
        self,
        interaction: Interaction,
        from_currency: Literal["scrap_metal", "copper"],
        to_currency: Literal["scrap_metal", "copper"],
        amount: str,
    ):
        """Convert from one currency to another."""
        if from_currency not in ("scrap_metal", "copper") or to_currency not in ("scrap_metal", "copper"):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")

        try:
            amount = helpers.text_to_num(amount)
        except helpers.TextToNumException:
            await interaction.send(embed=TextEmbed("The amount is invalid."))
            return

        from_currency_msg = from_currency.replace("_", " ")
        to_currency_msg = to_currency.replace("_", " ")

        if amount <= 0:
            await interaction.send(
                embed=TextEmbed(f"Enter a positive amount of {from_currency_msg} to exchange into {to_currency_msg}.")
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
            await interaction.send(
                embed=TextEmbed(f"{amount} {from_currency_msg} is not enough to make 1 {to_currency_msg}.")
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
                except helpers.NegativeBalance:
                    await interaction.send(
                        embed=TextEmbed(f"You don't have enough {from_currency_msg} to make this exchange.")
                    )
                    return

        embed = Embed()
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
        interaction: Interaction,
        scrap_metal: str = SlashOption(name="scrap-metal", description="Amount of scrap metal to exchange"),
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
        interaction: Interaction,
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
        SELECT i.item_id, i.name, CONCAT('<:', i.emoji_name, ':', i.emoji_id, '>') AS emoji, i.type, bp.quantity
        FROM utility.items AS i
        INNER JOIN utility.SearchItem($2) AS s
        ON i.item_id = s.item_id
        LEFT JOIN 
            (SELECT inv.item_id, inv.quantity
            FROM players.inventory AS inv
            WHERE inv.player_id = $1 AND inv.inv_type = 0) AS bp
        ON bp.item_id = i.item_id
    """

    async def choose_backpack_autocomplete(self, interaction: Interaction, data: str):
        """Returns a list of autocompleted choices of all the items in a user's backpack"""
        db: Database = self.bot.db
        items = await db.fetch(
            self.GET_BACKPACK_SQL,
            interaction.user.id,
            data if data else "",
        )
        await interaction.response.send_autocomplete([i["name"] for i in items][:25])

    @nextcord.slash_command(name="use", description="Use an item to activiate its unique ability!")
    @command_info(
        notes="For information on what's the effect of an item, use </item:1006811041025507379> and search for the selected item."
    )
    @cooldowns.cooldown(1, 12, SlashBucket.author, check=check_if_not_dev_guild)
    async def use(
        self,
        interaction: Interaction,
        item_name: str = SlashOption(
            name="item", description="The item to use", autocomplete_callback=choose_backpack_autocomplete
        ),
        quantity: int = SlashOption(description="Amount of the item to be used", required=None, default=1),
    ):
        db: Database = self.bot.db
        item = await db.fetchrow(
            self.GET_BACKPACK_SQL,
            interaction.user.id,
            item_name,
        )

        # perform some checks to see if the user can use their items
        if item is None:
            await interaction.send(embed=TextEmbed("The item does not exist.", EmbedColour.WARNING))
            return
        if item["quantity"] is None:
            await interaction.send(
                embed=TextEmbed(
                    f"You don't have any of the {item['emoji']} **{item['name']}** in your backpack, and therefore can't use it.",
                    EmbedColour.WARNING,
                )
            )
            return
        if item["quantity"] < quantity:
            await interaction.send(
                embed=TextEmbed(f"You don't have enough {item['emoji']} **{item['name']}**!", EmbedColour.WARNING)
            )
            return

        item = dict(item)  # convert the item from asyncpg.Record into a dict for the match-case statement
        player = Player(db, interaction.user)

        match item:
            case {"type": constants.ItemType.FOOD.value}:
                # the mininum and maximum hunger value that 1 unit of the food replenishes
                food_min, food_max = await db.fetchrow(
                    """
                        SELECT food_value_min, food_value_max
                        FROM utility.items
                        WHERE item_id = $1
                    """,
                    item["item_id"],
                )
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
                    await interaction.send(
                        embed=TextEmbed("Your hunger is already full, why are you even eating???", EmbedColour.WARNING)
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
                embed = TextEmbed(
                    f"You ate {quantity} {item['emoji']} **{item['name']}**.\n"
                    f"Your hunger is now {new_hunger}, increased by {new_hunger - old_hunger}.",
                    EmbedColour.SUCCESS,
                )

            case {"type": constants.ItemType.ANIMAL.value}:
                # convert the animal to "food" item
                await player.add_item(55, quantity)
                food_item = BossItem(55, quantity)
                embed = TextEmbed(
                    f"You roasted {quantity} {item['emoji']} **{item['name']}** over the fire and "
                    f"got {quantity} {await food_item.get_emoji(db)} **{await food_item.get_name(db)}**!",
                    EmbedColour.SUCCESS,
                )

            case {"item_id": 44}:  # Iron ore
                await player.add_item(50, quantity)
                embed = TextEmbed(f"Converted {quantity} iron ore into ingots!", EmbedColour.SUCCESS)

            case {"item_id": 57}:  # jungle explorer map
                if quantity > 1:
                    await interaction.send(
                        embed=TextEmbed(
                            f"{item['emoji']} **{item['name']}** could not be used for multiple times at once.",
                            EmbedColour.WARNING,
                        )
                    )
                    return

                async def confirm_func(button, btn_interaction: Interaction):
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
                    slash_interaction=interaction,
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
                await interaction.send(embed=view.embed, view=view)
                return

            case _:
                await interaction.send(embed=TextEmbed("You can't use this item", colour=EmbedColour.WARNING))
                return
        # do something universal of all items able to be used
        new_quantity = await player.add_item(item["item_id"], -quantity)
        view = View()
        button = Button(
            label=f"You have {new_quantity}x {item['name']} left",
            emoji=item["emoji"],
            style=ButtonStyle.grey,
            disabled=True,
        )
        view.add_item(button)
        await interaction.send(embed=embed, view=view)

    @nextcord.slash_command(name="profile", description="Check the profile of a user.")
    @command_info(notes="If you leave the `user` parameter empty, you can view your own profile.")
    @cooldowns.cooldown(1, 8, SlashBucket.author, check=check_if_not_dev_guild)
    async def profile(
        self,
        interaction: Interaction,
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
            await interaction.send(
                embed=TextEmbed("The user hasn't started playing BOSS yet! Maybe invite them over?"),
                ephemeral=True,
            )
            return

        profile = await db.fetchrow(
            """
            SELECT scrap_metal, copper, experience, health, hunger, commands_run
            FROM players.players
            WHERE player_id = $1
            """,
            user.id,
        )

        embed = Embed()
        embed.colour = EmbedColour.DEFAULT
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_author(name=f"{helpers.upper(user.name)}'s Profile")

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
            GROUP BY players.scrap_metal
            """,
            user.id,
        )
        if item_worth is None:
            item_worth = 0
        net_worth = item_worth + profile["scrap_metal"] + profile["copper"] * COPPER_SCRAP_RATE

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
            name="Currency",
            value=f"{SCRAP_METAL} `{numerize.numerize(profile['scrap_metal'])}`\n"
            f"{COPPER} `{numerize.numerize(profile['copper'])}`\n",
        )
        embed.add_field(name="Items", value=f"Unique: `{unique_items}`\nTotal: `{total_items}`\n")
        embed.add_field(
            name="Net",
            value=f"Item worth: {SCRAP_METAL} `{numerize.numerize(item_worth)}`\n"
            f"**Net**: {SCRAP_METAL} `{numerize.numerize(net_worth)}`",
        )
        await interaction.send(embed=embed)

    @nextcord.slash_command(name="balance", description="Check a user's balance. Cash, item worth, and net.")
    @cooldowns.cooldown(1, 8, SlashBucket.author, check=check_if_not_dev_guild)
    async def balance(
        self,
        interaction: Interaction,
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
            await interaction.send(
                embed=TextEmbed("The user hasn't started playing BOSS yet! Maybe invite them over?"),
                ephemeral=True,
            )
            return

        scrap_metal, copper = await db.fetchrow(
            """
            SELECT scrap_metal, copper
            FROM players.players
            WHERE player_id = $1
            """,
            user.id,
        )

        embed = Embed(title=f"{helpers.upper(user.name)}'s Balance", colour=EmbedColour.INFO)

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

        rank = await db.fetchval(
            """
            WITH item_worths AS (
                SELECT inv.player_id, SUM(i.trade_price * inv.quantity) AS item_worth
                FROM players.inventory AS inv
                INNER JOIN utility.items AS i
                ON inv.item_id = i.item_id
                WHERE player_id = $1
                GROUP BY inv.player_id
            ),
            percent_ranks AS (
                SELECT 
                    p.player_id, 
                    PERCENT_RANK() OVER (ORDER BY (p.scrap_metal + COALESCE(i.item_worth, 0))) AS rank
                FROM players.players AS p
                LEFT JOIN item_worths AS i
                ON p.player_id = i.player_id
            )
            SELECT rank FROM percent_ranks
            WHERE player_id = $1
            """,
            user.id,
        )

        embed.description = (
            f"**Scrap Metal**: {SCRAP_METAL} {scrap_metal:,}\n"
            f"**Copper**: {COPPER} {copper:,}\n\n"
            f"**Item worth**: {SCRAP_METAL} {item_worth:,}\n\n"
            f"**Net worth**: {SCRAP_METAL} {item_worth + scrap_metal + copper * 25:,}"
        )
        embed.set_footer(
            text=f"{'You are' if user == interaction.user else f'{helpers.upper(user.name)} is'} ahead of {round(rank * 100, 1)}% of users!\n"
            f"Items are valued with scrap metals. 1 copper is worth {constants.COPPER_SCRAP_RATE} scrap metals."
        )

        await interaction.send(embed=embed)

    @nextcord.slash_command(description="See the richest men in the (BOSS) world, who is probably not Elon Musk.")
    @command_info(notes="This command is global. We will add a server-specific scope soon.")
    @cooldowns.cooldown(1, 20, SlashBucket.author, check=check_if_not_dev_guild)
    async def leaderboard(self, interaction: Interaction):
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
        embed = Embed(title="Net Worth Leaderboard", description="")
        medal_emojis = {
            1: "🥇",
            2: "🥈",
            3: "🥉",
        }
        for i, (id, net_worth) in enumerate(lb):
            user = await self.bot.fetch_user(id)
            emoji = medal_emojis.get(i + 1, "🔹")
            embed.description += f"{emoji} ` {net_worth:,} ` - {helpers.upper(user.name)}\n"
        await interaction.send(embed=embed)

    @nextcord.slash_command()
    @cooldowns.shared_cooldown("check_inv")
    async def backpack(
        self,
        interaction: Interaction,
        user: nextcord.Member = SlashOption(
            name="user",
            description="The user to check the backpack of",
            required=False,
            default=None,
        ),
        page: int = SlashOption(description="The page to start in", required=False, min_value=1, default=1),
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
        interaction: Interaction,
        user: nextcord.Member = SlashOption(
            name="user",
            description="The user to check the chest of",
            required=False,
            default=None,
        ),
        page: int = SlashOption(description="The page to start in", required=False, min_value=1, default=1),
    ):
        """Check the chest of your own or others."""
        if user == None:
            user = interaction.user
        await InventoryView.send(interaction=interaction, user=user, inv_type=constants.InventoryType.CHEST, page=page)

    @nextcord.slash_command()
    @cooldowns.shared_cooldown("check_inv")
    async def vault(
        self,
        interaction: Interaction,
        page: int = SlashOption(description="The page to start in", required=False, min_value=1, default=1),
    ):
        """Check the vault of your own."""
        await InventoryView.send(
            interaction=interaction, user=interaction.user, inv_type=constants.InventoryType.VAULT, page=page
        )

    @vault.before_invoke
    async def vault_before_invoke(interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

    async def choose_inv_autocomplete(self, interaction: Interaction, data: str):
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

                inv_items = await db.fetch(
                    """
                    SELECT inv_type, item_id
                    FROM players.inventory
                    WHERE player_id = $1
                    """,
                    player_id,
                )

                num_of_items_in_inv = defaultdict(set)
                for item in inv_items:
                    num_of_items_in_inv[item["inv_type"]].add(item["item_id"])

                for inv_type, items in num_of_items_in_inv.items():
                    # transaction has not been committed, items are not updated
                    # so we check for the old values
                    if (
                        item_to == inv_type == constants.InventoryType.BACKPACK.value
                        and len(items) >= 32
                        and item_id not in items
                    ):
                        raise MoveItemException("Backpacks only have 32 slots!")
                    if (
                        item_to == inv_type == constants.InventoryType.VAULT.value
                        and len(items) >= 5
                        and item_id not in items
                    ):
                        raise MoveItemException("Vaults only have 5 slots!")
        return quantities_after

    @nextcord.slash_command(name="move-item")
    @cooldowns.cooldown(1, 18, SlashBucket.author, check=check_if_not_dev_guild)
    async def move_item_command(
        self,
        interaction: Interaction,
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
            await interaction.send(
                embed=TextEmbed("Choose different locations to move to!"),
            )
            return

        db: Database = self.bot.db
        item = await db.fetchrow(self.GET_ITEM_SQL, item_name)
        if not item:
            await interaction.send(embed=TextEmbed("The item is not found!"))
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
            await interaction.send(embed=TextEmbed(e.text, EmbedColour.FAIL), ephemeral=True)
            return

        embed = TextEmbed("Moving your items...", EmbedColour.DEFAULT)
        msg = await interaction.send(embed=embed)
        await asyncio.sleep(random.uniform(2, 5))

        embed = Embed(colour=EmbedColour.SUCCESS)
        embed.set_author(
            name=f"Updated {helpers.upper(interaction.user.name)}'s inventory!",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.description = f">>> Item: **{item['name']}**"
        embed.description += f"\nQuantity in {constants.InventoryType(item_from)}: `{quantities_after['from']}`"
        embed.description += f"\nQuantity in {constants.InventoryType(item_to)}: `{quantities_after['to']}`"
        embed.set_thumbnail(url=f"https://cdn.discordapp.com/emojis/{item['emoji_id']}.png")
        await msg.edit(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Resource(bot))

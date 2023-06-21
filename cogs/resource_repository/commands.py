# nextcord
import nextcord
from nextcord.ext import commands, tasks
from nextcord import Interaction, Embed, SlashOption

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
from utils.helpers import MoveItemException, TextEmbed, check_if_not_dev_guild, command_info
from utils.player import Player

# command views
from utils.template_views import ConfirmView
from .views import FarmView, InventoryView

# trade
from modules.village.village import TradeView
from utils.helpers import BossItem
from modules.village.villagers import Villager

# use
from modules.use_item import use_item

from numerize import numerize

# default modules
from collections import defaultdict
from typing import Literal
import random
import datetime
import pytz
import operator
import math


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

    async def choose_item_autocomplete(self, interaction: Interaction, data: str):
        sql = """
            SELECT name
            FROM utility.items
            ORDER BY name
        """
        db: Database = self.bot.db
        result = await db.fetch(sql)
        items = [i[0] for i in result]
        if not data:
            # return full list
            await interaction.response.send_autocomplete(items[:25])
            return
        else:
            # send a list of nearest matches from the list of item
            near_items = [item for item in items if data.lower() in item.lower()][:25]
            await interaction.response.send_autocomplete(near_items)

    async def choose_backpack_autocomplete(self, interaction: Interaction, data: str):
        """Returns a list of autocompleted choices of a user's backpack"""
        db: Database = self.bot.db
        items = await db.fetch(
            """
            SELECT items.name
                FROM players.inventory as inv
                INNER JOIN utility.items
                ON inv.item_id = items.item_id
            WHERE inv.player_id = $1 AND inv.inv_type = 0 AND items.sell_price > 0
            """,
            interaction.user.id,
        )
        if not data:
            # return full list
            return sorted([item[0] for item in items])[:25]
        # send a list of nearest matches from the list of item
        near_items = sorted([item[0] for item in items if item[0].lower().startswith(data.lower())])
        return near_items[:25]

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
        sql = """
            SELECT *
            FROM utility.items
            WHERE name ILIKE $1 or emoji_name ILIKE $1
            ORDER BY name ASC
        """
        db: Database = self.bot.db
        item = await db.fetchrow(sql, f"%{itemname.lower()}%")
        if not item:
            await interaction.send(embed=Embed(description="The item is not found!"), ephemeral=True)
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
        view = TradeView(interaction)
        await view.send()

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
        for name in names:
            job_type = random.choice(Villager.__subclasses__())
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
                            [
                                (item.item_id, item.quantity, None, None)
                                if isinstance(item, BossItem)
                                else (None, None, item.price, item.currency_type)
                                for item in villager.demand
                            ],
                            [
                                (item.item_id, item.quantity, None, None)
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
        await self.bot.get_guild(919223073054539858).get_channel(988046548309016586).send(
            embed=TextEmbed(f"villagers updated at {now}")
        )

    @update_villagers.before_loop
    async def before_update_villagers(self):
        now = datetime.datetime.now()
        # Wait until the start of the next hour before starting the task loop
        start_of_next_hour = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        await nextcord.utils.sleep_until(start_of_next_hour)

    @nextcord.slash_command(name="farm")
    async def farm(self, interaction: Interaction):
        """Engage yourself in a virtual farm - plant, harvest, and discover new crops!"""
        pass

    @farm.before_invoke
    async def create_farm(interaction: Interaction):
        await interaction.client.db.execute(
            """
            INSERT INTO players.farm(player_id, farm)
            VALUES(
                $1,
                $2
            )
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
        max_quantity_length = len(str(max(quantities)))

        for item in sold_items:
            embed.description += f"` {item['quantity']: >{max_quantity_length}}x ` <:{item['emoji_name']}:{item['emoji_id']}> {item['name']} ({SCRAP_METAL} {item['sell_price'] * item['quantity']:,})\n"

        embed.description += "─" * (len(embed.title) + 5)
        embed.description += f"\n**`Total`**: {SCRAP_METAL} __{total_price:,}__"
        return embed

    async def sell_all_player_items(self, button, interaction: Interaction):
        async with self.bot.db.pool.acquire() as conn:
            async with conn.transaction():
                sold_items = await conn.fetch(
                    """
                    UPDATE players.inventory As inv
                    SET quantity = 0
                    FROM utility.items
                    WHERE 
                        inv.item_id = items.item_id AND 

                        player_id = $1 AND 
                        inv_type = 0 AND 
                        items.sell_price > 0 AND
                        NOT items.item_id = ANY($2::int[])
                    RETURNING 
                        items.name, 
                        items.emoji_name,
                        items.emoji_id,
                        items.sell_price,
                        (SELECT quantity As old_quantity FROM players.inventory WHERE player_id = $1 AND inv_type = 0 AND item_id = items.item_id) As quantity 
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
                    """
                    SELECT items.item_id
                        FROM players.inventory as inv
                        INNER JOIN utility.items
                        ON inv.item_id = items.item_id
                    WHERE 
                        inv.player_id = $1 AND 
                        inv.inv_type = 0 AND 
                        items.sell_price > 0 AND
                        (items.name ILIKE $2 OR items.emoji_name ILIKE $2)
                    """,
                    interaction.user.id,
                    f"%{item_name}%",
                )
                # the item is not found, or the user does not own any
                if item is None:
                    await interaction.send(
                        embed=Embed(
                            description=f"Either you don't have any `{item_name}` in your backpack or it doesn't exist."
                        )
                    )
                    return

                exclude_items.append(item["item_id"])

        sellable_items = await db.fetch(
            """
            SELECT items.item_id, items.name, items.emoji_name, items.emoji_id, inv.quantity, items.sell_price
                FROM players.inventory as inv
                INNER JOIN utility.items
                ON inv.item_id = items.item_id
            WHERE 
                inv.player_id = $1 AND 
                inv.inv_type = 0 AND
                items.sell_price > 0 AND
                NOT items.item_id = ANY($2::int[])
            """,
            interaction.user.id,
            exclude_items,
        )
        if not sellable_items:
            await interaction.send(embed=Embed(description="You sold nothing! What a shame..."))
            return

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
            autocomplete_callback=choose_backpack_autocomplete,
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
            """
            SELECT items.item_id, items.name, items.emoji_name, items.emoji_id, items.sell_price, inv.quantity
                FROM players.inventory As inv
                INNER JOIN utility.items
                ON inv.item_id = items.item_id
            WHERE inv.player_id = $1 AND inv.inv_type = 0 AND (items.name ILIKE $2 or items.emoji_name ILIKE $2)
            ORDER BY name ASC
            """,
            interaction.user.id,
            f"%{item_name}%",
        )
        if not item:
            await interaction.send(
                embed=Embed(description="Either you don't own the item or it does not exist!"),
            )
            return

        if not item["sell_price"]:
            await interaction.send(embed=Embed(description="The item can't be sold! Try trading them."))
            return

        inv_quantity = item["quantity"]
        if quantity is None:
            quantity = inv_quantity
        if inv_quantity < quantity:
            embed = Embed()
            embed.description = (
                f"You only have {inv_quantity}x <:{item['emoji_name']}:{item['emoji_id']}>{item['name']}, which is {quantity - inv_quantity} short."
                "Don't imagine yourself as such a rich person, please."
            )
            await interaction.send(embed=embed)
            return

        async with db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    UPDATE players.inventory
                    SET quantity = quantity - $3
                    WHERE player_id = $1 AND inv_type = 0 AND item_id = $2
                    """,
                    interaction.user.id,
                    item["item_id"],
                    quantity,
                )

                player = Player(db, interaction.user)
                total_price = item["sell_price"] * quantity
                await player.modify_scrap(total_price)
        item = dict(item)
        item["quantity"] = quantity
        embed = self.get_sell_item_embed((item,), total_price)

        await interaction.send(f"{interaction.user.mention}, you successfully sold the items!", embed=embed)

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

        if from_currency == "scrap_metal":
            exchange_rate = constants.COPPER_SCRAP_RATE * random.uniform(1, 1.2)
            op = operator.truediv
        elif from_currency == "copper":
            exchange_rate = constants.COPPER_SCRAP_RATE * random.uniform(0.8, 1)
            op = operator.mul

        exchange_rate = round(exchange_rate)
        exchanged_amount = round(op(amount, exchange_rate))

        db: Database = interaction.client.db
        player = Player(db, interaction.user)

        async with db.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    from_amount = await player.modify_currency(from_currency, -amount)
                    to_amount = await player.modify_currency(to_currency, exchanged_amount)
                except helpers.NegativeBalance:
                    await interaction.send(
                        embed=TextEmbed(f"You don't have that enough {from_currency_msg} to make this exchange.")
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

    @nextcord.slash_command()
    @helpers.work_in_progress(dev_guild_only=True)
    async def use(
        self,
        interaction: Interaction,
        item_name: str = SlashOption(
            name="item", description="The item to use", autocomplete_callback=choose_backpack_autocomplete
        ),
        quantity: int = SlashOption(description="Amount of the item to be used", required=None, default=1),
    ):
        """Use an item to activiate its unique ability!"""
        db: Database = self.bot.db
        item = await db.fetchrow(
            """
            SELECT items.item_id, items.name, items.emoji_name, items.emoji_id, items.sell_price, inv.quantity
                FROM players.inventory As inv
                INNER JOIN utility.items
                ON inv.item_id = items.item_id
            WHERE inv.player_id = $1 AND inv.inv_type = 0 AND (items.name ILIKE $2 or items.emoji_name ILIKE $2)
            ORDER BY name ASC
            """,
            interaction.user.id,
            f"%{item_name}%",
        )
        if item is None:
            await interaction.send(embed=TextEmbed("The item does not exist.", colour=EmbedColour.WARNING))
            return
        if func := getattr(use_item, f"use_item_{item['item_id']}", None):
            await func(interaction, quantity)
        else:
            await interaction.send(embed=TextEmbed("You can't use this item", colour=EmbedColour.WARNING))

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 8, SlashBucket.author, check=check_if_not_dev_guild)
    async def profile(
        self,
        interaction: Interaction,
        user: nextcord.User = SlashOption(
            name="user",
            description="The user to check the profile. Leave this empty to view yours.",
            required=False,
            default=None,
        ),
    ):
        """Check the profile of your own or others."""
        if user is None:
            user = interaction.user
        db: Database = self.bot.db

        player = Player(db, user)
        if not await player.is_present():
            await interaction.send(
                embed=Embed(description="The user hasn't started playing BOSS yet! Maybe invite them over?"),
                ephemeral=True,
            )
            return

        profile = await db.fetchrow(
            """
            SELECT scrap_metal, copper, experience
            FROM players.players
            WHERE player_id = $1
            """,
            user.id,
        )

        profile_ui = Embed()
        profile_ui.colour = random.choice(constants.EMBED_COLOURS)
        profile_ui.set_thumbnail(url=user.display_avatar.url)
        profile_ui.set_author(name=f"{user.name}'s Profile")

        experience = profile["experience"]

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

        profile_ui.add_field(
            name="Scrap Metal",
            value=f"{SCRAP_METAL} `{numerize.numerize(profile['scrap_metal'])}`",
        )
        profile_ui.add_field(name="Copper", value=f"{COPPER} `{numerize.numerize(profile['copper'])}`")
        experience_progress_bar_filled = round((experience % 100) / 10)
        profile_ui.add_field(
            name="Experience",
            inline=False,
            value=f"Level: `{math.floor(experience / 100)}`\n"
            f"Progress: `{experience % 100}/100` "
            f"[`{'█' * experience_progress_bar_filled}{' ' * (10 - experience_progress_bar_filled)}`]",
        )
        profile_ui.add_field(
            name="Items",
            value=f"Unique: `{unique_items}`\n"
            f"Total: `{total_items}`\n"
            f"Worth: {SCRAP_METAL} `{numerize.numerize(item_worth)}`\n",
            inline=False,
        )
        profile_ui.add_field(
            name="Net worth",
            value=f"{SCRAP_METAL} `{numerize.numerize(item_worth + profile['scrap_metal'])}`",
            inline=False,
        )
        await interaction.send(embed=profile_ui)

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 8, SlashBucket.author, check=check_if_not_dev_guild)
    async def balance(
        self,
        interaction: Interaction,
        user: nextcord.User = SlashOption(
            name="user",
            description="The user to check the balance. Leave this empty to view yours.",
            required=False,
            default=None,
        ),
    ):
        """Check your or other user's balance."""
        if user is None:
            user = interaction.user
        db: Database = self.bot.db

        player = Player(db, user)
        if not await player.is_present():
            await interaction.send(
                embed=Embed(description="The user hasn't started playing BOSS yet! Maybe invite them over?"),
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

        embed = Embed()
        embed.colour = random.choice(constants.EMBED_COLOURS)
        embed.title = f"{user}'s Balance"

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
            text=f"{'You are' if user == interaction.user else f'{user.name} is'} ahead of {round(rank * 100, 1)}% of users!\n"
            f"Items are valued with scrap metals. 1 copper is worth {constants.COPPER_SCRAP_RATE} scrap metals."
        )

        await interaction.send(embed=embed)

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 20, SlashBucket.author, check=check_if_not_dev_guild)
    async def leaderboard(self, interaction: Interaction):
        """See the richest men in the (BOSS) world, who is probably not Elon Musk."""
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
            embed.description += f"{emoji} ` {net_worth:,} ` - {user}\n"
        await interaction.send(embed=embed)

    @nextcord.slash_command()
    @cooldowns.shared_cooldown("check_inv")
    async def backpack(
        self,
        interaction: Interaction,
        user: nextcord.Member = SlashOption(
            name="user",
            description="The user to check the backpack",
            required=False,
            default=None,
        ),
    ):
        """Check the backpack of your own or others."""
        if user == None:
            user = interaction.user
        view = InventoryView(
            interaction=interaction,
            user=user,
            inv_type=constants.InventoryType.BACKPACK.value,
        )
        await view.send()

    @nextcord.slash_command()
    @cooldowns.shared_cooldown("check_inv")
    async def chest(
        self,
        interaction: Interaction,
        user: nextcord.Member = SlashOption(
            name="user",
            description="The user to check the chest",
            required=False,
            default=None,
        ),
    ):
        """Check the chest of your own or others."""
        if user == None:
            user = interaction.user
        view = InventoryView(
            interaction=interaction,
            user=user,
            inv_type=constants.InventoryType.CHEST.value,
        )
        await view.send()

    @nextcord.slash_command()
    @cooldowns.shared_cooldown("check_inv")
    async def vault(self, interaction: Interaction):
        """Check the vault of your own."""
        user = interaction.user
        view = InventoryView(
            interaction=interaction,
            user=user,
            inv_type=constants.InventoryType.VAULT.value,
        )
        await view.send()

    async def choose_inv_autocomplete(self, interaction: Interaction, data: str):
        """Returns a list of autocompleted choices of a user's inventory"""
        db: Database = self.bot.db
        items = await db.fetch(
            """
            SELECT items.name
                FROM players.inventory as inv
                INNER JOIN utility.items
                ON inv.item_id = items.item_id
            WHERE inv.player_id = $1
            """,
            interaction.user.id,
        )
        if not data:
            # return full list
            return sorted(list({item[0] for item in items}))
        # send a list of nearest matches from the list of item
        near_items = sorted(list({item[0] for item in items if item[0].lower().startswith(data.lower())}))
        return near_items

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
                    if quantities_after["from"] is None or quantities_after["from"] < 0:
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
                    if (
                        item_to == inv_type == constants.InventoryType.BACKPACK
                        and len(items) >= 32
                        and item_id not in items
                    ):
                        raise MoveItemException("Backpacks only have 32 slots!")
                    if (
                        item_to == inv_type == constants.InventoryType.vault
                        and len(items) >= 5
                        and item_id not in items
                    ):
                        raise MoveItemException("Vaults only have 5 slots!")
        return quantities_after

    @nextcord.slash_command(name="move-item")
    @cooldowns.cooldown(1, 18, SlashBucket.author, check=check_if_not_dev_guild)
    async def move_item(
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
        item = await db.fetchrow(
            """
            SELECT item_id, name, emoji_id
            FROM utility.items
            WHERE name ILIKE $1 or emoji_name ILIKE $1
            ORDER BY name ASC
            """,
            f"%{item_name}%",
        )
        if not item:
            await interaction.send(embed=Embed(description="The item is not found!"), ephemeral=True)
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
            await interaction.send(embed=Embed(description=e.text), ephemeral=True)
            return

        # **inv_types**
        # backpack: 0
        # chest: 1
        # vault: 2
        embed = Embed(colour=EmbedColour.SUCCESS)
        embed.set_author(
            name=f"Updated {interaction.user.name}'s inventory!",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.description = f">>> Item: **{item['name']}**"
        embed.description += f"\nQuantity in {constants.InventoryType(item_from)}: `{quantities_after['from']}`"
        embed.description += f"\nQuantity in {constants.InventoryType(item_to)}: `{quantities_after['to']}`"
        embed.set_thumbnail(url=f"https://cdn.discordapp.com/emojis/{item['emoji_id']}.png")
        await interaction.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Resource(bot))

# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Interaction, Embed, SlashOption

# slash command cooldowns
import cooldowns
from cooldowns import SlashBucket

# database
from utils.postgres_db import Database

# my modules and constants
from utils import functions, constants
from utils.player import Player
from utils.functions import TextEmbed
from utils.constants import SCRAP_METAL, COPPER
from views.template_views import ConfirmView

# default modules
import random
from typing import Literal
import operator


class Currency(commands.Cog, name="Resource Reserve"):
    COG_EMOJI = "💰"
    cooldowns.define_shared_cooldown(1, 8, SlashBucket.author, cooldown_id="sell_items")

    def __init__(self, bot):
        self.bot = bot

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
        near_items = sorted(
            [item[0] for item in items if item[0].lower().startswith(data.lower())]
        )
        return near_items[:25]

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
        async with await self.bot.db.pool.acquire() as conn:
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
                    WHERE inv.player_id = $1 AND inv.inv_type = 0 AND (items.name ILIKE $2 or items.emoji_name ILIKE $2)
                    """,
                    interaction.user.id,
                    f"%{item_name}%",
                )
                # the item is not found, or the user does not own any
                if item is None:
                    await interaction.send(
                        embed=Embed(
                            description=f"Either you don't own the item `{item_name}` or it doesn't exist"
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
            await interaction.send(
                embed=Embed(description="You sold nothing! What a shame...")
            )
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
            description="Amount of items to sell",
            required=False,
            default=1,
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
                embed=Embed(
                    description="Either you don't own the item or it does not exist!"
                ),
            )
            return

        if not item["sell_price"]:
            await interaction.send(
                embed=Embed(description="The item can't be sold! Try trading them.")
            )
            return

        inv_quantity = item["quantity"]
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

        await interaction.send(
            f"{interaction.user.mention}, you successfully sold the items!", embed=embed
        )

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
        if from_currency not in ("scrap_metal", "copper") or to_currency not in (
            "scrap_metal",
            "copper",
        ):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")

        try:
            amount = functions.text_to_num(amount)
        except functions.TextToNumException:
            await interaction.send(embed=TextEmbed("The amount is invalid."))
            return

        from_currency_msg = from_currency.replace("_", " ")
        to_currency_msg = to_currency.replace("_", " ")

        if amount <= 0:
            await interaction.send(
                embed=TextEmbed(
                    f"Enter a positive amount of {from_currency_msg} to exchange into {to_currency_msg}."
                )
            )
            return

        if from_currency == "scrap_metal":
            exchange_rate = constants.COPPER_SCRAP_RATE * random.uniform(0, 1.2)
            op = operator.truediv
        elif from_currency == "copper":
            exchange_rate = constants.COPPER_SCRAP_RATE * random.uniform(0.8, 0)
            op = operator.mul

        exchange_rate = round(exchange_rate)
        exchanged_amount = round(op(amount, exchange_rate))

        db: Database = interaction.client.db
        player = Player(db, interaction.user)

        async with db.pool.acquire() as conn:
            async with conn.transaction():
                try:
                    from_amount = await player.modify_currency(from_currency, -amount)
                    to_amount = await player.modify_currency(
                        to_currency, exchanged_amount
                    )
                except functions.NegativeBalance:
                    await interaction.send(
                        embed=TextEmbed(
                            f"You don't have that enough {from_currency_msg} to make this exchange."
                        )
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
    async def exchange_to_scrap(
        self,
        interaction: Interaction,
        copper: str = SlashOption(
            name="copper", description="Amount of copper to exchange"
        ),
    ):
        """Convert your coppers to scrap metals."""

        await self.exchange_currencies(
            interaction,
            "copper",
            "scrap_metal",
            copper,
        )


def setup(bot: commands.Bot):
    bot.add_cog(Currency(bot))

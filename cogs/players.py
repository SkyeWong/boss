# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Embed, Interaction, SlashOption

# command cooldowns
import cooldowns
from cooldowns import SlashBucket

# numerize
from numerize import numerize

# database
from utils.postgres_db import Database

# my modules and constants
from utils.player import Player
from utils import functions, constants
from utils.functions import check_if_not_dev_guild
from utils.functions import MoveItemException
from views.players_views import InventoryView

# default modules
import math
import random
from collections import defaultdict


class Players(commands.Cog, name="Apocalypse Elites"):
    COG_EMOJI = "🏆"
    cooldowns.define_shared_cooldown(
        1, 6, SlashBucket.author, cooldown_id="check_inventory"
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
                embed=Embed(
                    description="The user hasn't started playing BOSS yet! Maybe invite them over?"
                ),
                ephemeral=True,
            )
            return

        profile = await db.fetchrow(
            """
            SELECT scrap_metal, experience
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
            name="Scrap Metal", value=f"`◎ {numerize.numerize(profile['scrap_metal'])}`"
        )
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
            f"Worth: `◎ {numerize.numerize(item_worth)}`\n",
            inline=False,
        )
        profile_ui.add_field(
            name="Net worth",
            value=f"`◎ {numerize.numerize(item_worth + profile['scrap_metal'])}`",
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
                embed=Embed(
                    description="The user hasn't started playing BOSS yet! Maybe invite them over?"
                ),
                ephemeral=True,
            )
            return

        scrap_metal = await db.fetchval(
            """
            SELECT scrap_metal
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

        embed.description = (
            f"**Scrap Metal**: ◎ {scrap_metal:,}\n"
            f"**Item worth**: ◎ {item_worth:,}\n\n"
            f"**Net worth**: ◎ {item_worth + scrap_metal:,}"
        )
        await interaction.send(embed=embed)

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 20, SlashBucket.author, check=check_if_not_dev_guild)
    async def leaderboard(self, interaction: Interaction):
        """See the richest man in the (BOSS) world, who is probably not Elon Musk."""
        lb = await self.bot.db.fetch(
            """
            SELECT players.player_id, COALESCE(SUM(items.trade_price * inv.quantity)::bigint, 0) + players.scrap_metal As net_worth
                FROM players.players
                LEFT JOIN players.inventory AS inv
                    ON inv.player_id = players.player_id
                LEFT JOIN utility.items
                    ON inv.item_id = items.item_id
            GROUP BY players.player_id
            ORDER BY net_worth DESC
            LIMIT 8
            """,
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
    @cooldowns.shared_cooldown("check_inventory")
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
            inv_type=constants.InventoryType.backpack.value,
        )
        await view.get_inv_content()
        view.disable_buttons()
        embed = view.get_inv_embed()
        view.message = await interaction.send(embed=embed, view=view)

    @nextcord.slash_command()
    @cooldowns.shared_cooldown("check_inventory")
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
            inv_type=constants.InventoryType.chest.value,
        )
        await view.get_inv_content()
        view.disable_buttons()
        embed = view.get_inv_embed()
        view.message = await interaction.send(embed=embed, view=view)

    @nextcord.slash_command()
    @cooldowns.shared_cooldown("check_inventory")
    async def vault(self, interaction: Interaction):
        """Check the vault of your own."""
        user = interaction.user
        view = InventoryView(
            interaction=interaction,
            user=user,
            inv_type=constants.InventoryType.vault.value,
        )
        await view.get_inv_content()
        view.disable_buttons()
        embed = view.get_inv_embed()
        view.message = await interaction.send(embed=embed, view=view)

    async def get_autocompleted_items(
        self, user: nextcord.User, inv_type: int, data: str
    ):
        db: Database = self.bot.db
        items = await db.fetch(
            """
            SELECT items.name
                FROM players.inventory as inv
                INNER JOIN utility.items
                ON inv.item_id = items.item_id
            WHERE inv.player_id = $1 AND inv.inv_type = $2
            ORDER BY items.name
            """,
            user.id,
            inv_type,
        )
        if not data:
            # return full list
            return [item[0] for item in items]
        # send a list of nearest matches from the list of item
        near_items = [
            item[0] for item in items if item[0].lower().startswith(data.lower())
        ]
        return near_items

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
        near_items = sorted(
            list(
                {item[0] for item in items if item[0].lower().startswith(data.lower())}
            )
        )
        return near_items

    async def move_items(
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
                if (
                    quantity is None
                ):  # move all items of that name in that specific inv_type
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
                        item_to == inv_type == constants.InventoryType.backpack
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
            description="How many of the item do you want to move? DEFAULTS to ALL",
            required=False,
            default=None,
        ),
    ):
        """Moves item from one place to other."""

        if item_from == item_to:
            await interaction.send(
                embed=Embed(description="Choose different locations to move to!"),
                ephemeral=True,
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
            await interaction.send(
                embed=Embed(description="The item is not found!"), ephemeral=True
            )
            return

        try:
            quantities_after = await self.move_items(
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
        embed = Embed()
        embed.colour = random.choice(constants.EMBED_COLOURS)
        embed.set_author(
            name=f"Updated {interaction.user.name}'s inventory!",
            icon_url=interaction.user.display_avatar.url,
        )
        embed.description = f">>> Item: **{item['name']}**"
        embed.description += f"\nQuantity in {[inv.name for inv in constants.InventoryType if inv.value == item_from][0]}: `{quantities_after['from']}`"
        embed.description += f"\nQuantity in {[inv.name for inv in constants.InventoryType if inv.value == item_to][0]}: `{quantities_after['to']}`"
        embed.set_thumbnail(
            url=f"https://cdn.discordapp.com/emojis/{item['emoji_id']}.png"
        )
        await interaction.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Players(bot))

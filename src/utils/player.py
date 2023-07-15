# nextcord
import nextcord
from nextcord import Interaction, Embed

# database
from utils.postgres_db import Database
import asyncpg

# my modules
from utils import helpers, constants
from utils.helpers import BossItem
from utils.constants import EmbedColour, SCRAP_METAL

# default modules
from typing import Literal
import json
from datetime import datetime


class Player:
    """Represents a BOSS player."""

    def __init__(self, db: Database, user: nextcord.User):
        self.db = db
        self.user = user  # the underlying `nextcord.User` object

    async def is_present(self):
        """Check if the player exists in BOSS's database."""
        res = await self.db.fetchval(
            """
            SELECT *
            FROM players.players
            WHERE player_id = $1
            """,
            self.user.id,
        )
        return bool(res)

    async def create_profile(self):
        """Create a profile for the player."""
        return await self.db.fetchval(
            """
            INSERT INTO players.players (player_id)
            VALUES ($1)
            ON CONFLICT DO NOTHING
            RETURNING player_id
            """,
            self.user.id,
        )

    async def modify_currency(self, currency: Literal["scrap_metal", "copper"], value: int):
        """Modify the player's currency, scrap_metal or copper."""
        if currency not in ("scrap_metal", "copper"):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")

        try:
            return await self.db.fetchval(
                f"""
                UPDATE players.players
                SET {currency} = {currency} + $1
                WHERE player_id = $2
                RETURNING {currency}
                """,
                value,
                self.user.id,
            )
        except asyncpg.exceptions.CheckViolationError:
            raise helpers.NegativeBalance()

    async def modify_scrap(self, value: int):
        """The shorthand function for `Player.modify_currency("scrap_metal", value)`."""
        return await self.modify_currency("scrap_metal", value)

    async def modify_copper(self, value: int):
        """The shorthand function for `Player.modify_currency("copper", value)`."""
        return await self.modify_currency("copper", value)

    async def set_currency(self, currency: Literal["scrap_metal", "copper"], value: int):
        """Set the player's currency, scrap_metal or copper."""
        if currency not in ("scrap_metal", "copper"):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")

        try:
            return await self.db.fetchval(
                f"""
                UPDATE players.players
                SET {currency} = $1
                WHERE player_id = $2
                RETURNING (SELECT {currency} FROM players.players WHERE player_id = $2)
                """,
                value,
                self.user.id,
            )
        except asyncpg.exceptions.CheckViolationError:
            raise helpers.NegativeBalance()

    async def set_scrap(self, value: int):
        """The shorthand function for `Player.set_currency("scrap_metal", value)`."""
        return await self.set_currency("scrap_metal", value)

    async def set_copper(self, value: int):
        """The shorthand function for `Player.set_currency("copper", value)`."""
        return await self.set_currency("copper", value)

    async def modify_hunger(self, value: int):
        """Modify the player's hunger"""
        return await self.db.fetchval(
            """
            UPDATE players.players
                SET hunger = hunger + $1
            WHERE player_id = $2
            RETURNING hunger
            """,
            value,
            self.user.id,
        )

    async def modify_health(self, value: int):
        """Modify the player's health"""
        new_health = await self.db.fetchval(
            """
            UPDATE players.players
                SET health = health + $1
            WHERE player_id = $2
            RETURNING health
            """,
            value,
            self.user.id,
        )
        if new_health <= 0:
            embed = Embed(title="You died!", colour=EmbedColour.FAIL)
            # Choose a random item from the user's backpack
            lost_item = await self.db.fetchrow(
                """
                SELECT i.item_id, i.name, CONCAT('<:_:', i.emoji_id, '>') AS emoji, inv.quantity
                FROM utility.items AS i
                    INNER JOIN players.inventory AS inv
                    ON i.item_id = inv.item_id
                WHERE inv.inv_type = 0 AND inv.player_id = $1
                ORDER BY RANDOM()
                LIMIT 1
                """,
                self.user.id,
            )
            # Remove all of that item from the user's backpack
            await self.add_item(lost_item["item_id"], -lost_item["quantity"])
            # Remove all scrap_metal of the user
            lost_money = await self.set_scrap(0)
            embed.description = f"You lost {SCRAP_METAL} **{lost_money:,}**, and you also lost {lost_item['quantity']} {lost_item['emoji']} **{lost_item['name']}**"

            embed.timestamp = datetime.now()
            await self.user.send(embed=embed)
            # Reset the health of the user to 100
            await self.db.fetchval(
                """
                UPDATE players.players
                SET health = 100
                WHERE player_id = $1
                RETURNING health
                """,
                self.user.id,
            )
        return new_health

    async def set_in_inter(self, value: bool):
        """Modify whether the player is running a command"""
        return await self.db.fetchval(
            """
            UPDATE players.players
                SET in_interaction = $1
            WHERE player_id = $2
            RETURNING in_interaction
            """,
            value,
            self.user.id,
        )

    async def check_in_inter(self):
        """Check whether the player is running a command"""
        return await self.db.fetchval(
            """
            SELECT in_interaction
            FROM players.players
            WHERE player_id = $1
            """,
            self.user.id,
        )

    async def get_farm(self):
        """
        Fetches the player's farm.

        Returns a `tuple` containing the crops, farm_width, and farm_height.
        """
        return await self.db.fetchrow(
            """
            SELECT farm, width, height
            FROM players.farm
            WHERE player_id = $1
            """,
            self.user.id,
        )

    async def add_item(self, item_id: int, quantity: int = 1, inv_type: int = 0):
        """Add an item into the player's inventory."""
        async with self.db.pool.acquire() as conn:
            async with conn.transaction():
                quantity = await conn.fetchval(
                    """
                    INSERT INTO players.inventory (player_id, inv_type, item_id, quantity)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT(player_id, inv_type, item_id) DO UPDATE
                        SET quantity = inventory.quantity + $4
                    RETURNING quantity
                    """,
                    self.user.id,
                    inv_type,
                    item_id,
                    quantity,
                )
                if quantity < 0:
                    raise helpers.NegativeInvQuantity()
        return quantity

    async def update_missions(self, interaction: Interaction, mission_id: int, amount: int = 1):
        # if the user has a mission of the type of the command, update its progress
        mission = await self.db.fetchrow(
            """
                UPDATE players.missions
                SET finished_amount = finished_amount + $3
                WHERE player_id = $1 AND mission_id = $2 AND finished = FALSE
                RETURNING finished_amount, total_amount, finished, reward
            """,
            self.user.id,
            mission_id,
            amount,
        )
        if mission is None:  # the mission does not exist
            return

        # check whether the mission has been finished (finished > total) and check that it has not been finished before
        if mission["finished_amount"] >= mission["total_amount"] and mission["finished"] == False:
            cog = interaction.client.get_cog("Apocalyptic Adventures")

            embed = Embed(colour=EmbedColour.SUCCESS)
            embed.set_thumbnail("https://i.imgur.com/OzmCuvW.png")
            embed.description = "### You completed a mission!\n"
            embed.description += (
                f"- Mission: {cog.MISSION_TYPES[mission_id]['description'].format(quantity=mission['total_amount'])}\n"
            )

            # generate the "reward" string
            reward = json.loads(mission["reward"])
            if reward["type"] == "item":
                item = BossItem(reward["id"], reward["amount"])
                await self.add_item(item.id, item.quantity)
                reward_msg = f"{reward['amount']}x {await item.get_emoji(self.db)} {await item.get_name(self.db)}"
            else:
                # reward["type"] will be "scrap_metal" or "copper"
                await self.modify_currency(reward["type"], reward["amount"])
                reward_msg = f"{constants.CURRENCY_EMOJIS[reward['type']]} {reward['amount']}"
            embed.description += f"You received {reward_msg}\n"

            await interaction.send(embed=embed, ephemeral=True)

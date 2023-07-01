# nextcord
import nextcord
from nextcord import Interaction, Embed

# database
from utils.postgres_db import Database
import asyncpg

# my modules
from utils import helpers, constants
from utils.helpers import BossItem
from utils.constants import EmbedColour

# default modules
from typing import Literal
import json


class Player:
    """Represents a BOSS player."""

    def __init__(self, db: Database, user: nextcord.User):
        self.db = db
        self.user = user

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
        if await self.is_present():
            if currency not in ("scrap_metal", "copper"):
                raise ValueError("Currency must be either `scrap_metal` or `copper`.")

            return await self.db.fetchval(
                """
                UPDATE players.players
                    SET $1 = $1 + $2
                WHERE player_id = $3
                RETURNING $1
                """,
                currency,
                value,
                self.user.id,
            )
        else:
            raise helpers.PlayerNotExist()

    async def modify_currency(self, currency: Literal["scrap_metal", "copper"], value: int):
        """Modify the player's currency, scrap_metal or copper."""
        if await self.is_present():
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
        else:
            raise helpers.PlayerNotExist()

    async def modify_scrap(self, value: int):
        """The shorthand function for `Player.modify_currency("scrap_metal", value)`."""
        return await self.modify_currency("scrap_metal", value)

    async def modify_copper(self, value: int):
        """The shorthand function for `Player.modify_currency("copper", value)`."""
        return await self.modify_currency("copper", value)

    async def set_currency(self, currency: Literal["scrap_metal", "copper"], value: int):
        """Set the player's currency, scrap_metal or copper."""
        if await self.is_present():
            if currency not in ("scrap_metal", "copper"):
                raise ValueError("Currency must be either `scrap_metal` or `copper`.")

            try:
                return await self.db.fetchval(
                    f"""
                    UPDATE players.players
                    SET {currency} = $1
                    WHERE player_id = $2
                    RETURNING {currency}
                    """,
                    value,
                    self.user.id,
                )
            except asyncpg.exceptions.CheckViolationError:
                raise helpers.NegativeBalance()
        else:
            raise helpers.PlayerNotExist()

    async def set_scrap(self, value: int):
        """The shorthand function for `Player.set_currency("scrap_metal", value)`."""
        return await self.set_currency("scrap_metal", value)

    async def set_copper(self, value: int):
        """The shorthand function for `Player.set_currency("copper", value)`."""
        return await self.set_currency("copper", value)

    async def get_farm(self):
        """
        Fetches the player's farm.

        Returns a `tuple` containing the crops, farm_width, and farm_height.
        """
        if await self.is_present():
            return await self.db.fetchrow(
                """
                SELECT farm, width, height
                FROM players.farm
                WHERE player_id = $1
                """,
                self.user.id,
            )
        else:
            raise helpers.PlayerNotExist()

    async def add_item(self, item_id: int, quantity: int = 1, inv_type: int = 0):
        """Add an item into the player's inventory."""
        if await self.is_present():
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
        else:
            raise helpers.PlayerNotExist()

    async def update_missions(self, interaction: Interaction, mission_id: int, amount: int = 1):
        # if the user has a mission of the type of the command, update its progress
        if mission_id:
            mission = await self.db.fetchrow(
                """
                    UPDATE players.missions
                    SET finished_amount = finished_amount + 1
                    WHERE player_id = $1 AND mission_type_id = $2 AND finished = FALSE
                    RETURNING 
                        finished_amount, 
                        total_amount, 
                        finished, 
                        reward, 
                        (SELECT description FROM utility.mission_types WHERE id = $2) AS description
                """,
                self.user.id,
                mission_id,
            )
            if mission is None:  # the mission does not exist
                return

            # check whether the mission has been finished (finished > total) and check that it has not been finished before
            if mission["finished_amount"] >= mission["total_amount"] and mission["finished"] == False:
                embed = Embed(colour=EmbedColour.SUCCESS)
                embed.set_thumbnail("https://i.imgur.com/OzmCuvW.png")
                embed.description = "### You completed a mission!\n"
                embed.description += f"- Mission: {mission['description'].format(quantity=mission['total_amount'])}\n"

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

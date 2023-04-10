# nextcord
import nextcord

# default modules
from datetime import datetime
import json

# database
from utils.postgres_db import Database

from utils import functions


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

    async def modify_gold(self, gold_to_modify: int):
        """Modify the player's gold."""
        if await self.is_present():
            return await self.db.fetchval(
                """
                UPDATE players.players
                    SET gold = gold + $1
                WHERE player_id = $2
                RETURNING gold
                """,
                gold_to_modify,
                self.user.id,
            )
        else:
            raise functions.PlayerNotExist()

    async def set_gold(self, gold_to_set: int):
        if await self.is_present() == True:
            return await self.db.fetchval(
                """
                UPDATE players.players
                    SET gold = $1
                WHERE player_id = $2
                RETURNING gold
                """,
                gold_to_set,
                self.user.id,
            )
        else:
            raise functions.PlayerNotExist()

    async def get_farm(self):
        """
        Fetches the player's farm.

        Returns a `tuple` containing the crops, farm_width, and farm_height."""
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
            raise functions.PlayerNotExist()

    async def add_item(self, item_id: int, quantity: int = 1, inv_type: int = 0):
        """Add an item into the player's inventory."""
        if await self.is_present():
            return await self.db.fetchval(
                """
                INSERT INTO players.inventory (player_id, inv_type, item_id, quantity)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT(player_id, inv_type, item_id) DO UPDATE
                    SET quantity = inventory.quantity + excluded.quantity
                RETURNING quantity
                """,
                self.user.id,
                inv_type,
                item_id,
                quantity,
            )
        else:
            raise functions.PlayerNotExist()

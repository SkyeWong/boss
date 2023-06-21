# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Interaction, Embed

# database
from utils.postgres_db import Database

# my modules and constants
from utils import constants, helpers
from utils.constants import SCRAP_METAL, COPPER, EmbedColour
from utils.helpers import TextEmbed
from utils.player import Player

# default modules
import random


async def use_item_44(interaction: Interaction, quantity: int):
    """Allows users to use the item `Iron Ore`. (item_id: 44)"""
    db: Database = interaction.client.db
    player = Player(db, interaction.user)
    await player.add_item(50, quantity)
    await player.add_item(44, -quantity)
    await interaction.send(embed=TextEmbed(f"Converted {quantity} iron ore into ingots!", EmbedColour.SUCCESS))
    return True


async def use_item_48(interaction: Interaction, quantity: int):
    """Allows users to use the item `Bread`. (item_id: 48)"""
    db: Database = interaction.client.db
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
        random.randint(20 * quantity, 30 * quantity),
        interaction.user.id,
    )
    if old_hunger >= 100:
        await interaction.send(
            embed=TextEmbed("Your hunger is already full, why are you even eating???", EmbedColour.WARNING)
        )
        return False

    # perform another query because we need to wait for the trigger function to occur
    # the trigger function makes sure that the hunger is in range of [0, 100]
    new_hunger = await db.fetchval(
        """
            SELECT hunger
            FROM players.players
            WHERE player_id = $1
        """,
        interaction.user.id,
    )
    await interaction.send(
        embed=TextEmbed(
            f"Ate {quantity} bread.\nYour hunger is now {new_hunger}, increased by {new_hunger - old_hunger}",
            EmbedColour.SUCCESS,
        )
    )

    return True


# maybe just add an "active item" in database?

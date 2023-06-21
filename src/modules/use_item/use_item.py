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


async def use_item_44(interaction: Interaction, quantity: int):
    """Allows users to use the item `Iron Ore`. (item_id: 44)"""
    db: Database = interaction.client.db
    player = Player(db, interaction.user)
    await player.add_item(50, quantity)
    await player.add_item(44, -quantity)
    await interaction.send(embed=TextEmbed(f"Converted {quantity} iron ore into ingots!", EmbedColour.SUCCESS))


# maybe just add an "active item" in database?

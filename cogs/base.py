# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Interaction, Embed, SlashOption

# database
from utils.postgres_db import Database

# my modules and constants
from utils.player import Player
from utils import functions, constants

# command views
from views.base_views import FarmView

# maze
from maze.maze import Maze

# default modules


class Base(commands.Cog, name="Resilient Residence"):
    COG_EMOJI = "🏡"

    def __init__(self, bot):
        self.bot = bot

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
        user: nextcord.User = SlashOption(
            description="The user to view the farm of", required=False, default=None
        ),
    ):
        """Check your crops' progress."""
        if user is None:
            user = interaction.user

        player = Player(self.bot.db, user)
        view = FarmView(interaction, player)

        await view.send_message(
            interaction, with_view=True if user == interaction.user else False
        )

    @nextcord.slash_command(
        name="maze",
        description="Wander in a (very) hard maze and maybe get stuck there!",
    )
    async def maze(
        self,
        interaction: Interaction,
    ):
        view = Maze(interaction)
        embed = view.get_embed()
        view.message = await interaction.send(embed=embed, view=view)


def setup(bot: commands.Bot):
    bot.add_cog(Base(bot))

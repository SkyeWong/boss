# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Interaction, Embed, SlashOption

# slash command cooldowns
import cooldowns
from cooldowns import SlashBucket

# default modules
import random

# database
from utils.postgres_db import Database

# my modules and constants
from utils.player import Player
from views.template_views import ConfirmView

# maze
from maze.maze import Maze


class Exploring(commands.Cog, name="Exploring"):
    COG_EMOJI = "🗺️"

    def __init__(self, bot):
        self.bot = bot

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author)
    async def hunt(self, interaction: Interaction):
        """Go hunting and bring back some animals if you are lucky!"""
        db: Database = self.bot.db
        player = Player(db, interaction.user)
        # `% getting one of them`: `list of animals`
        animals = {
            30: [None],  # --fail--
            40: (  # --common--
                23,  # duck
                24,  # rabbit
                26,  # skunk
            ),
            20: (  # --uncommon--
                18,  # deer
                22,  # cow
                25,  # sheep
            ),
            7: (21,),  # --rare--  # boar
            3: (20,),  # --downright impossible--  # dragon
        }
        animal_category = random.choices(list(animals.values()), list(animals.keys()))[0]
        item_id = random.choice(animal_category)

        if item_id is None:
            await interaction.send(
                embed=Embed(description="You went hunting but found nothing... No dinner tonight ig")
            )
            return

        await player.add_item(item_id)
        item = await db.fetchrow(
            """
            SELECT name, emoji_name, emoji_id
            FROM utility.items
            WHERE item_id = $1
            """,
            item_id,
        )
        embed = Embed(
            description=f"You went hunting and found a **{item['name']}** <:{item['emoji_name']}:{item['emoji_id']}>!"
        )
        await interaction.send(embed=embed)

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author)
    async def dig(self, interaction: Interaction):
        """Dig in the ground and find some buried treasure."""
        db: Database = self.bot.db
        player = Player(db, interaction.user)
        # `% getting one of them`: `list of animals`
        items = {
            90: (  # --fail--
                None,  # nothing
                28,  # dirt
            ),
            10: (27,),  # --common--  # Anicient Coin
        }
        item_category = random.choices(list(items.values()), list(items.keys()))[0]
        item_id = random.choice(item_category)

        if item_id is None:
            await interaction.send(
                embed=Embed(
                    description="With that little stick of yours, you shouldn't really expect to find anything."
                )
            )
            return

        await player.add_item(item_id)
        item = await db.fetchrow(
            """
            SELECT name, emoji_name, emoji_id
            FROM utility.items
            WHERE item_id = $1
            """,
            item_id,
        )
        embed = Embed(
            description=f"You went bonkers and finally found a **{item['name']}** <:{item['emoji_name']}:{item['emoji_id']}> after hours of work!"
        )
        await interaction.send(embed=embed)

    async def adventure_pyramid(self, button, interaction: Interaction):
        maze_size = (random.randint(15, 20), random.randint(15, 20))
        view = Maze(interaction, maze_size)
        embed = view.get_embed()
        view.message = await interaction.send(embed=embed, view=view)

    async def adventure_village(self, button, interaction: Interaction):
        if random.randint(1, 5) > 2:
            await interaction.send(
                embed=Embed(
                    description="OH GOD they are **FOES**! They chased you for 10 km, luckily you outran them."
                ),
                ephemeral=True,
            )
        else:
            db: Database = self.bot.db
            villages = await db.fetch(
                """
                SELECT structure_id, name
                FROM utility.structures
                WHERE structure_type_id = 1
                """
            )
            village = random.choice(villages)

            # add village to player's discovered structures list
            await db.execute(
                """
                INSERT INTO players.discovered_structures (player_id, structure_id)
                VALUES ($1, $2)
                """,
                interaction.user.id,
                village["structure_id"],
            )
            await interaction.send(
                embed=Embed(
                    description=f"It turns out you came across the lovely village, **{village['name']}**.\n"
                    "The villagers are very willing to meet you and trade with you!\n"
                    "Use </visit:1081863670189006868> to visit the village."
                ),
                ephemeral=True,
            )

    async def adventure_gold(self, button, interaction: Interaction):
        player = Player(self.bot.db, interaction.user)
        if random.randint(1, 5) > 2:
            gold = random.randint(1000, 8000)
            await player.modify_gold(gold)
            await interaction.send(
                embed=Embed(description=f"Lucky you, you got home safely without injuries, but with 🪙 {gold}"),
                ephemeral=True,
            )
        else:
            await interaction.send(
                embed=Embed(description="Someone was lurking around! You got attacked..."),
                ephemeral=True,
            )

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 60, SlashBucket.author, cooldown_id="adventure")
    async def adventure(
        self,
        interaction: Interaction,
    ):
        """Go explore, discover some structures and obtain some treasure!"""
        if random.randint(1, 10) > 4:
            # 60% to have an adventure
            outcomes = {
                20: (
                    "You found a creepy pyramid that goes DEEP down! Do you want to continue?",
                    self.adventure_pyramid,
                ),
                30: (
                    "While you were wandering in the woods, you saw some smoke rising in the sky. You walked forward and saw civilisation! Wanna meet the people?",
                    self.adventure_village,
                ),
                50: (
                    "A bag of gold was lying on the ground. You saw no one around you. Have you finally decided on whether to snatch it yet?",
                    self.adventure_gold,
                ),
            }
            outcome = random.choices(list(outcomes.values()), list(outcomes.keys()))[0]
            view = ConfirmView(
                slash_interaction=interaction,
                confirm_func=outcome[1],
                embed_content=outcome[0],
            )
            embed = view.get_embed(title="Adventure time!")
            await interaction.send(embed=embed, view=view)
        else:
            # 40% fail
            msg = [
                "You don't see anything in sight, so you just went home.",
                "It's getting dark. Feeling scared, you rushed back to your little hut and slept with a cute little plush.",
                "You found out that you actually don't have enough courage to explore on your own.",
                "After getting scared by a rock that seems to [move by itself](https://www.youtube.com/watch?v=iu8vnVz5cYQ), you fled towards your shack.",
            ]
            await interaction.send(embed=Embed(description=random.choice(msg)))
            cooldowns.reset_cooldown("adventure")

    async def choose_structure_autocomplete(self, interaction: Interaction, data: str):
        """Returns a list of autocompleted choices of a user's discovered structures."""
        db: Database = self.bot.db
        structures = await db.fetch(
            """
            SELECT INITCAP(CONCAT(st.name, ' - ', s.name))
                FROM players.discovered_structures As ds

                INNER JOIN utility.structures As s
                ON ds.structure_id = s.structure_id
                
                INNER JOIN utility.structure_types As st
                ON s.structure_type_id = st.structure_type_id
            WHERE ds.player_id = $1
            """,
            interaction.user.id,
        )
        if not data:
            # return full list
            return sorted([structure[0] for structure in structures])
        # send a list of nearest matches from the list of item
        near_structures = sorted(
            [structure[0] for structure in structures if structure[0].lower().startswith(data.lower())]
        )
        return near_structures

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 60, SlashBucket.author)
    async def visit(
        self,
        interaction: Interaction,
        structure_name: str = SlashOption(
            name="structure",
            description="The structure to visit",
            required=True,
            autocomplete_callback=choose_structure_autocomplete,
        ),
    ):
        """Visit a structure that you have unlocked!"""
        structure_type, structure_name = structure_name.split(" - ")
        await interaction.send(f"You visited a {structure_type} called {structure_name}")


def setup(bot: commands.Bot):
    bot.add_cog(Exploring(bot))

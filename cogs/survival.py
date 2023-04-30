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
from utils import functions
from utils.functions import TextEmbed, check_if_not_dev_guild
from utils.player import Player
from views.template_views import ConfirmView

# maze
from maze.maze import Maze

# trade
from village.village import TradeView


class Survival(commands.Cog, name="Wasteland Wandering"):
    COG_EMOJI = "🗺️"

    def __init__(self, bot):
        self.bot = bot

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def hunt(self, interaction: Interaction):
        """Go hunting and bring back some animals if you are lucky!"""
        db: Database = self.bot.db
        player = Player(db, interaction.user)
        # `% getting one of them`: `list of animals`
        animals = [
            [20, [None]],  # --fail--
            [40, (  # --common--
                23,  # duck
                24,  # rabbit
                26,  # skunk
            )],
            [30, (  # --uncommon--
                18,  # deer
                22,  # cow
                25,  # sheep
            )],
            [7, (21,)],  # --rare--  # boar
            [3, (20,)],  # --downright impossible--  # dragon
        ]
        animal_category = random.choices([i[1] for i in animals], [i[0] for i in animals])[0]
        item_id = random.choice(animal_category)

        if item_id is None:
            await interaction.send(
                embed=Embed(
                    description="You went hunting but found nothing... No dinner tonight ig"
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
            description=f"You went hunting and found a **{item['name']}** <:{item['emoji_name']}:{item['emoji_id']}>!"
        )
        await interaction.send(embed=embed)

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def dig(self, interaction: Interaction):
        """Dig in the ground and find some buried treasure."""
        db: Database = self.bot.db
        player = Player(db, interaction.user)
        # `% getting one of them`: `list of rewards`
        items = [
            [90, (  # --fail--
                None,  # nothing
                31,  # dirt
            )],
            [10, (27,)],  # --common--  # Anicient Coin
        ]
        item_category = random.choices([i[1] for i in items], [i[0] for i in items])[0]
        item_id = random.choice(item_category)

        if item_id is None:
            fail_msgs = [
                "With that little stick of yours, you shouldn't really expect to find anything.",
                "You found nothing! What a waste of time.",
                "After you saw a spider climbing in the dirt, you gave it up as a bad job.",
                "Wait... what's that? Aww, it's just another worm."
            ]
            await interaction.send(embed=TextEmbed(
                random.choice(fail_msgs)
            ))
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
        
    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def mine(self, interaction: Interaction):
        """Go mining in the caves!"""
        db: Database = self.bot.db
        player = Player(db, interaction.user)
        # `% getting one of them`: `list of rewards`
        items = [
            [30, [None]],  # --fail--
            [40, (  # --common--
                44,  # Iron ore
            )],
            [25, (  # --rare--
                45,  # Emerald ore
            )],
            [5, (  # --epic--
                34,  # Diamond ore
            )]
        ]
        item_category = random.choices([i[1] for i in items], [i[0] for i in items])[0]
        item_id = random.choice(item_category)

        if item_id is None:
            fail_msgs = [
                "The cave was too dark. You ran away in a hurry.",
                "Well, you certainly know how to find the empty spots in a cave.",
                "What were you doing in your garage for the past 5 hours? You didn't mistake it as a cave... did you?",
                "You've managed to mine nothing but air. Your pickaxe must be thrilled.",
                "You mine and you mine, but all you find are rocks.",
                "Looks like you struck out. Maybe next time you'll get lucky and find a diamond... or not.",
                "Breaking rocks all day, yet nothing to show for it. You're a real master at mining for disappointment."
            ]
            await interaction.send(embed=TextEmbed(
                random.choice(fail_msgs)
            ))
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
        if item_id == 33:  # only stone
            await interaction.send(embed=TextEmbed(f"Looks like you found a... **{item['name']}** <:{item['emoji_name']}:{item['emoji_id']}>. How exciting. Maybe try a little deeper next time?"))
            return
        
        success_msgs = [
            "Wow, you actually found a {item}. I suppose even a blind squirrel finds a nut every once in a while.",
            "You hit the jackpot and obtained a {item}! Just kidding, you got lucky.",
            "You found a {item}! It's almost like you knew what you were doing... or maybe you just got lucky.",
            "Well, looks like you're not as useless as I thought. You found a {item}.",
            "You found a {item}! It's almost like you have a sixth sense for mining... or maybe you just stumbled upon it.",
        ]
        embed = TextEmbed(random.choice(success_msgs).format(item=f"**{item['name']}** <:{item['emoji_name']}:{item['emoji_id']}>"))
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

    async def adventure_scrap_metal(self, button, interaction: Interaction):
        player = Player(self.bot.db, interaction.user)
        if random.randint(1, 5) > 2:
            scrap_metal = random.randint(1000, 8000)
            await player.modify_scrap(scrap_metal)
            await interaction.send(
                embed=Embed(
                    description=f"Lucky you, you got home safely without injuries, but with 🪙 {scrap_metal}"
                ),
                ephemeral=True,
            )
        else:
            await interaction.send(
                embed=Embed(
                    description="Someone was lurking around! You got attacked..."
                ),
                ephemeral=True,
            )

    async def adventure_slave(self, button, interaction: Interaction):
        player = Player(self.bot.db, interaction.user)
        if random.randint(1, 5) > 2:
            await player.add_item(32)
            await interaction.send(
                embed=TextEmbed(
                    "Wow, you found yourself a slave! However, what he is able to do, I don't know."
                ),
                ephemeral=True,
            )
        else:
            player_scrap = await self.bot.db.fetchval(
                """
                SELECT scrap_metal
                FROM players.players
                WHERE player_id = $1
                """,
                interaction.user.id,
            )
            # use min() with user's scrap_metal so the scrap_metal will not be negative
            lost_scrap = min(player_scrap, random.randint(120, 800))
            await player.modify_scrap(-lost_scrap)
            await interaction.send(
                embed=TextEmbed(
                    f"Shame on you, he was a bandits. He attacked you and you lost 🪙 {lost_scrap}",
                ),
                ephemeral=True,
            )

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 60, SlashBucket.author, cooldown_id="adventure", check=check_if_not_dev_guild)
    async def adventure(
        self,
        interaction: Interaction,
    ):
        """Go explore, discover some structures and obtain some treasure!"""
        if random.randint(1, 10) > 4:
            # 60% to have an adventure
            outcomes = {
                10: (
                    "You found a creepy pyramid that goes DEEP down! Do you want to continue?",
                    self.adventure_pyramid,
                ),
                10: (
                    "Wait what? You found... a random slave! Adopt him, he'd like to.",
                    self.adventure_slave,
                ),
                30: (
                    "While you were wandering in the woods, you saw some smoke rising in the sky. You walked forward and saw civilisation! Wanna meet the people?",
                    self.adventure_village,
                ),
                50: (
                    "A bag of scrap_metal was lying on the ground. You saw no one around you. Have you finally decided on whether to snatch it yet?",
                    self.adventure_scrap_metal,
                ),
            }
            outcome = random.choices(list(outcomes.values()), list(outcomes.keys()))[0]

            embed = Embed(title="Adventure time!", description=outcome[0])

            view = ConfirmView(
                slash_interaction=interaction,
                confirm_func=outcome[1],
                cancel_func=lambda button, interaction: cooldowns.reset_cooldown(
                    "adventure"
                ),
                embed=embed,
            )
            await interaction.send(embed=view.embed, view=view)
        else:
            # 40% fail
            msg = (
                "You don't see anything in sight, so you just went home.",
                "It's getting dark. Feeling scared, you rushed back to your little hut and slept with a cute little plushie.",
                "You found out that you actually don't have enough courage to explore on your own.",
                "After getting scared by a rock that seems to [move by itself](https://www.youtube.com/watch?v=iu8vnVz5cYQ), you fled towards your shack.",
                "What's happening? You wanted to move, but your body just doesn't seem to obey your mind.",
            )
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
            [
                structure[0]
                for structure in structures
                if structure[0].lower().startswith(data.lower())
            ]
        )
        return near_structures

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 60, SlashBucket.author, check=check_if_not_dev_guild)
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
        await interaction.send(
            f"You visited a {structure_type} called {structure_name}"
        )
    
    @nextcord.slash_command()
    @cooldowns.cooldown(1, 120, SlashBucket.author, check=check_if_not_dev_guild)
    async def trade(self, interaction: Interaction):
        """Trade with villagers for valuable and possibly unique items!"""
        view = TradeView(interaction)
        await view.send()


def setup(bot: commands.Bot):
    bot.add_cog(Survival(bot))

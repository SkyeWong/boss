# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Embed, Interaction, SlashOption

# command cooldowns
import cooldowns
from cooldowns import SlashBucket

# my modules and constants
from utils import constants, helpers
from utils.postgres_db import Database
from utils.helpers import check_if_not_dev_guild, TextEmbed

# command views
from .views import (
    FightPlayer,
    FightView,
    TriviaQuestion,
    TriviaView,
)

# maze
from modules.maze.maze import Maze
import aiohttp

# default modules
import random


class Fun(commands.Cog, name="Survivor's Playground"):
    """Fun commands and mini-games for entertainment"""

    COG_EMOJI = "🎢"

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @nextcord.slash_command(name="roll", description="Roll a random number between two of them.")
    @cooldowns.cooldown(1, 20, SlashBucket.author, check=check_if_not_dev_guild)
    async def roll(
        self,
        interaction: Interaction,
        first: int = SlashOption(description="First number", min_value=1, required=True),
        second: int = SlashOption(
            description="Second number. Leave this empty to roll between 1 and the first number",
            min_value=2,
            required=False,
        ),
    ):
        if not second:
            first, second = 1, first
        elif second < first:
            first, second = second, first
        elif second == first:
            await interaction.send(embed=Embed(description="BOTH numbers are the same! What do you expect me to do?"))
            return

        number = random.randint(first, second)

        embed = Embed(
            title=f"{interaction.user.name} rolls {number} ({first}-{second})",
            colour=random.choice(constants.EMBED_COLOURS),
        )
        await interaction.send(embed=embed)

    @nextcord.slash_command(name="coinflip", description="Flip a coin!")
    @cooldowns.cooldown(1, 20, SlashBucket.author, check=check_if_not_dev_guild)
    async def coinflip(self, interaction: Interaction):
        embed = Embed()
        embed.title = "Flipped a coin..."
        embed.colour = random.choice(constants.EMBED_COLOURS)
        result = random.choice(range(2))
        if result == 0:
            embed.description = "**`HEADS`**"
            embed.set_thumbnail(url="https://i.imgur.com/8BSllkX.png")
        else:
            embed.description = "**`TAIL`**"
            embed.set_thumbnail(url="https://i.imgur.com/VcqwLpT.png")
        await interaction.send(embed=embed)

    @nextcord.slash_command(name="8ball", description="I can tell you the future and make decisions! 🎱")
    @cooldowns.cooldown(1, 20, SlashBucket.author, check=check_if_not_dev_guild)
    async def eight_ball(
        self,
        interaction: Interaction,
        whattodecide: str = SlashOption(name="what-to-decide", description="Something to ask me...", max_length=100),
    ):
        RESPONSES = {
            "yes": [
                0x6BA368,
                [
                    "It is [32mcertain[0m.",
                    "It is [32mdecidedly so[0m.",
                    "[32mWithout[0m a doubt.",
                    "[32mYes[0m definitely.",
                    "You may [32mrely[0m on it.",
                    "As I see it, [32myes[0m.",
                    "Most [32mlikely[0m.",
                    "Outlook [32mgood[0m.",
                    "[32mYes[0m.",
                    "Signs point to [32myes[0m.",
                ],
            ],
            "undecided": [
                0xEEF36A,
                [
                    "Reply hazy, [33mtry again[0m.",
                    "Ask again [33mlater[0m.",
                    "Better [33mnot tell[0m you now.",
                    "[33mCannot predict[0m now.",
                    "Concentrate and [33mask again[0m.",
                ],
            ],
            "no": [
                0xFF4365,
                [
                    "[31mDon't count[0m on it.",
                    "My reply is [31mno[0m.",
                    "My sources say [31mno[0m.",
                    "Outlook [31mnot so good[0m.",
                    "Very [31mdoubtful[0m.",
                ],
            ],
        }

        embed = Embed()
        embed.set_author(name="You shook me and some words appeared...")
        category = RESPONSES[random.choice(list(RESPONSES.keys()))]
        embed.colour = category[0]
        response = random.choice(category[1])
        embed.add_field(name=f"_{whattodecide}_", value=f"\n```ansi\n{response}\n[0m\n```")
        await interaction.send(embed=embed)

    @nextcord.slash_command(name="fight", description="Fight with another user!")
    @cooldowns.cooldown(1, 60, SlashBucket.author, check=check_if_not_dev_guild)
    async def fight(
        self,
        interaction: Interaction,
        user: nextcord.User = SlashOption(
            description="The user to fight with",
        ),
    ):
        if interaction.user == user:
            await interaction.send("Who are you fighting with, not... yourself? 😂", ephemeral=True)
            return
        if user.bot:
            await interaction.send(
                "Why are you fighting with a bot?! ||We might be implementing an AI soon tho...||",
                ephemeral=True,
            )
            return

        players = [FightPlayer(interaction.user), FightPlayer(user)]
        view = FightView(interaction, *players)
        embed = view.get_embed()
        await interaction.send(embed=embed, view=view)
        view.msg = await interaction.original_message()

    @nextcord.slash_command()
    async def trivia(
        self,
        interaction: Interaction,
        category: str = SlashOption(
            description="Category of the trivia question",
            choices={  # category_name: id
                "Animals": "27",
                "Art": "25",
                "Celebrities": "26",
                "Entertainment: Board Games": "16",
                "Entertainment: Books": "10",
                "Entertainment: Cartoon & Animations": "32",
                "Entertainment: Comics": "29",
                "Entertainment: Film": "11",
                "Entertainment: Japanese Anime & Manga": "31",
                "Entertainment: Music": "12",
                "Entertainment: Musicals & Theatres": "13",
                "Entertainment: Television": "14",
                "Entertainment: Video Games": "15",
                "General Knowledge": "9",
                "Geography": "22",
                "History": "23",
                "Mythology": "20",
                "Politics": "24",
                "Science & Nature": "17",
                "Science: Computers": "18",
                "Science: Gadgets": "30",
                "Science: Mathematics": "19",
                "Sports": "21",
                "Vehicles": "28",
            },
            required=False,
            default=None,
        ),
        difficulty: str = SlashOption(
            description="Difficulty of the trivia question",
            choices={i: i.lower() for i in ("Easy", "Medium", "Hard")},
            required=False,
            default=None,
        ),
    ):
        """Test your knowledge with a random trivia question!"""
        params = {
            # predefined
            "type": "multiple",
            "amount": 1,
        }
        # user-defined
        if category:
            params.update(category=category)
        if difficulty:
            params.update(difficulty=difficulty)

        while True:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://opentdb.com/api.php", params=params) as response:
                    question_res = await response.json()

                    if question_res["response_code"] != 0:  # error response code
                        await interaction.send(
                            embed=TextEmbed("An error occured. Please try again"),
                            ephemeral=True,
                        )
                        return

                    question_res = question_res["results"][0]

            kwargs = {k: v for k, v in question_res.items() if k in TriviaQuestion.__slots__}
            try:
                question = TriviaQuestion(**kwargs)
            except helpers.ComponentLabelTooLong:
                continue
            else:
                view = TriviaView(interaction, question)
                break

        await view.send()

    @nextcord.slash_command(
        name="maze",
        description="Wander in a (very) hard maze! You'll probably get stuck there tho...",
    )
    async def maze(
        self,
        interaction: Interaction,
    ):
        view = Maze(interaction)
        embed = view.get_embed()
        view.message = await interaction.send(embed=embed, view=view)


def setup(bot: commands.Bot):
    bot.add_cog(Fun(bot))

# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Embed, Interaction, SlashOption
from nextcord.ui import View, Button

# command cooldowns
import cooldowns
from cooldowns import SlashBucket

# default modules
import random
from PIL import Image
from io import BytesIO
import asyncio

# my modules and constants
from utils import constants

# command views
from views.fun_views import FightPlayer, FightView, EmojiView

# mazelib
from mazelib import Maze
from mazelib.generate.Prims import Prims
from mazelib.solve.BacktrackingSolver import BacktrackingSolver

# requests
import requests


class Fun(commands.Cog, name="Fun"):
    COG_EMOJI = "🎡"

    def __init__(self):
        self._last_member = None

    @nextcord.slash_command(name="roll", description="Roll a random number between two of them.")
    @cooldowns.cooldown(1, 20, SlashBucket.author)
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
    @cooldowns.cooldown(1, 20, SlashBucket.author)
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
    @cooldowns.cooldown(1, 20, SlashBucket.author)
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

    @nextcord.slash_command(
        name="generate-maze",
        description="Generates a maze using the Mazelib Python library",
    )
    @cooldowns.cooldown(1, 180, SlashBucket.author)
    async def gen_maze(
        self,
        interaction: Interaction,
        width: int = SlashOption(description="The width of the maze", max_value=100),
        height: int = SlashOption(
            description="The length of the maze. If not set, will be set to `width`.",
            required=False,
            max_value=100,
        ),
        difficulty: int = SlashOption(
            description="0 to 9 --> 0: easiest, 9: hardest. The bot generates 10 mazes and finds the `n`th short maze",
            required=False,
            min_value=0,
            max_value=9,
        ),
        start: bool = SlashOption(
            description="Whether the maze starts on an outer wall. Ignored if difficulty is set.",
            required=False,
            default=True,
        ),
        end: bool = SlashOption(
            description="Whether the maze ends on an outer wall. Ignored if difficulty is set.",
            required=False,
            default=True,
        ),
    ):
        embed = Embed()
        embed.colour = random.choice(constants.EMBED_COLOURS)
        embed.set_author(name="Generating maze... Please wait patiently")
        embed.description = "I will ping you when it has finished!"
        embed.description += "\n`1.` Your request has been received and is processing... "
        msg = await interaction.send(embed=embed)

        height = width if not height else height

        if height < 3 or width < 3:
            await msg.edit(content="The maze must be at least 3x3 large!", embed=None)
            return

        m = Maze()
        m.generator = Prims(height, width)
        m.solver = BacktrackingSolver()

        loop = asyncio.get_running_loop()

        if difficulty:
            future = loop.run_in_executor(None, m.generate_monte_carlo, 10, 1, difficulty / 10)
            embed.description += "**`Done`**!\n`2.` Generating multiple mazes and finding one with set difficulty... "
            embed.insert_field_at(
                0,
                name="⚠️ Caution",
                value="\n```fix\nThis will take a while since the difficulty is set and I'll test many maze combinations!```",
                inline=False,
            )
            await msg.edit(embed=embed)
        else:
            embed.description += "**`Done`**!\n`2.` Generating maze grid... "
            await msg.edit(embed=embed)

            m.generate()
            m.generate_entrances(start_outer=start, end_outer=end)

            embed.description += "**`Done`**!\n`3.` Solving maze... "
            await msg.edit(embed=embed)

            future = loop.run_in_executor(None, m.solve)

        loop.run_until_complete(future)

        embed.add_field(name="Solution length", value=f"`{len(m.solutions[0])}` cells")
        embed.add_field(name="Start ➡ End", value=f"`{m.start[::-1]}` ➡ `{m.end[::-1]}`")
        embed.description += f"**`Done`**!\n`{'3' if difficulty else '4'}.` Generating maze image... "

        if difficulty:
            embed.remove_field(0)
            embed.add_field(name="Difficulty", value=difficulty)

        await msg.edit(embed=embed)

        # Convert the string into an image
        m_str = m.tostring(True, True)

        SPRITES = {
            "ground": Image.open("resources/maze/ground.png"),
            "wall": Image.open("resources/maze/wall.png"),
            "path": Image.open("resources/maze/path.png"),
            "start": Image.open("resources/maze/start.png"),
            "finish": Image.open("resources/maze/finish.png"),
        }

        sprite_width = 36

        for k, v in SPRITES.items():
            SPRITES[k] = v.resize((sprite_width, sprite_width))

        maze_img = Image.new("RGBA", (sprite_width * len(m.grid[0]), sprite_width * len(m.grid)))

        for y_i, y in enumerate(m_str.splitlines()):
            for x_i, x in enumerate(y):
                if x == "#":
                    sprite = SPRITES["wall"]
                elif x == " ":
                    sprite = SPRITES["ground"]
                elif x == "+":
                    sprite = SPRITES["path"]
                elif x == "S":
                    sprite = SPRITES["start"]
                elif x == "E":
                    sprite = SPRITES["finish"]
                maze_img.paste(sprite, (x_i * sprite_width, y_i * sprite_width))

        output = BytesIO()
        maze_img.thumbnail((1600, 1600))
        maze_img.save(output, format="PNG")
        output.seek(0)

        file = nextcord.File(output, "maze.png")
        embed.set_image("attachment://maze.png")

        embed.set_author(name="Generating maze successful!")
        embed.description = f"**Width (inputted - actual)**: `{width}` - `{len(m.grid[0])}`\n"
        embed.description += f"**Height (inputted - actual)**: `{height}` - `{len(m.grid)}`"
        await msg.edit(file=file, embed=embed)

        view = View()
        button = Button(label="View", url=msg.jump_url)
        view.add_item(button)
        int_time = int(interaction.created_at.timestamp())
        await interaction.send(
            interaction.user.mention,
            embed=Embed(
                description=f"Your {width}x{height} maze requested at <t:{int_time}:R> | <t:{int_time}:f> has been successfully generated!"
            ),
            view=view,
            ephemeral=True,
        )

    @nextcord.slash_command(name="fight", description="Fight with another user!")
    @cooldowns.cooldown(1, 60, SlashBucket.author)
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

    async def emoji_autocomplete_callback(self, interaction: Interaction, data):
        """Returns a list of autocompleted choices of emojis of a server's emoji."""
        emojis = interaction.guild.emojis

        if not data:
            # return full list
            return sorted([emoji.name for emoji in emojis])[:25]
        # send a list of nearest matches from the list of item
        near_emojis = sorted([emoji.name for emoji in emojis if emoji.name.lower().startswith(data.lower())])
        return near_emojis[:25]

    @nextcord.slash_command(
        name="emoji",
        description="Search for emojis!",
    )
    @cooldowns.cooldown(1, 15, SlashBucket.author)
    async def emoji(
        self,
        interaction: Interaction,
        emoji_name: str = SlashOption(
            name="emoji",
            description="Emoji to search for, its id or name. If left empty, all emojis in this server will be shown.",
            required=False,
            autocomplete_callback=emoji_autocomplete_callback,
        ),
    ):
        if not emoji_name:  # send full list
            guild_emojis = sorted(interaction.guild.emojis, key=lambda emoji: emoji.name)

            if guild_emojis:  # guild has no emojis
                view = EmojiView(interaction, guild_emojis)
                embed = view.get_embed()
                view.disable_buttons()

                await interaction.send(
                    f"There are `{len(guild_emojis)}` emojis in `{interaction.guild.name}`.",
                    embed=embed,
                    view=view,
                )
            else:
                await interaction.send(embed=Embed(description="This server has no emojis!"))

            return

        if len(emoji_name) < 2:
            await interaction.send(embed=Embed(description="The search term must be longer than 2 characters."))
        else:  # perform a search on emojis
            emojis_found = [
                emoji
                for emoji in interaction.guild.emojis
                if emoji_name.lower() in emoji.name.lower() or emoji_name == str(emoji.id)
            ]

            emojis_found.sort(key=lambda emoji: emoji.name)

            if emojis_found:
                view = EmojiView(interaction, emojis_found)
                embed = view.get_embed()
                view.disable_buttons()

                await interaction.send(
                    f"There are `{len(emojis_found)}` results for `{emoji_name}`.",
                    embed=embed,
                    view=view,
                )
            else:
                await interaction.send(embed=Embed(description=f"No emojis are found for `{emoji_name}`."))


def setup(bot: commands.Bot):
    bot.add_cog(Fun())

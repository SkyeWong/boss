# nextcord
import nextcord
from nextcord.ext import commands, tasks, application_checks
from nextcord import Embed, Interaction, SlashOption
from nextcord.ui import View, Button

# command cooldowns
import cooldowns
from cooldowns import SlashBucket

# my modules and constants
from utils import constants, functions
from utils.postgres_db import Database
from utils.functions import check_if_not_dev_guild, TextEmbed

# command views
from views.misc_views import (
    HelpView,
    GuideView,
    FightPlayer,
    FightView,
    EmojiView,
    TriviaQuestion,
    TriviaView,
    WeatherView,
    PersistentWeatherView,
    VideoView,
    Video,
    MtrLine,
    LINE_STATION_CODES,
    Train,
    NextTrainView,
)

# mazelib
from mazelib import Maze
from mazelib.generate.Prims import Prims
from mazelib.solve.BacktrackingSolver import BacktrackingSolver

import requests
import aiohttp

import googleapiclient.discovery
from pytube import Search

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

import pytz

# default modules
import datetime
import random
from PIL import Image
from io import BytesIO
import asyncio
import os
import base64
import html
from contextlib import suppress
from typing import Optional


class Misc(commands.Cog, name="Apocalypse Amusements"):

    COG_EMOJI = "🛠️"

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        try:
            response = requests.get("https://www.hko.gov.hk/json/DYN_DAT_MINDS_RHRREAD.json")
            response = response.json().get("DYN_DAT_MINDS_RHRREAD")

            self.location_list = {}
            for k, v in response.items():
                if "LocationName" in k:
                    if not v["Val_Eng"] or not v["Val_Chi"]:
                        self.location_list[k.replace("LocationName", "")] = k.replace("LocationName", "")
                    else:
                        self.location_list[html.unescape(f"{v['Val_Eng']} - {v['Val_Chi']}")] = k.replace(
                            "LocationName", ""
                        )
            self.location_list = dict(sorted(self.location_list.items()))
        except:
            print("Failed to update location list from HKO")
        self.announce_temp.start()

    def search_subcommand(self, cmd: nextcord.SlashApplicationCommand, cmd_name):
        """Search for a subcommand with its name."""
        cmd_found = False
        subcommands = cmd.children.values()
        for x in subcommands:
            if x.qualified_name in cmd_name:
                if cmd_name == x.qualified_name:
                    cmd_found = True
                    cmd = x
                    break
                elif x.children:
                    return self.search_subcommand(x, cmd_name)

        if not cmd_found:
            raise functions.CommandNotFound()
        return cmd

    def get_all_subcmd_names(self, guild_id: int, cmd):
        """Get all subcommand names of a command."""
        cmd_names = []
        for subcmd in cmd.children.values():
            base_cmd = cmd
            while not isinstance(base_cmd, nextcord.SlashApplicationCommand):
                base_cmd = base_cmd.parent_cmd
            cmd_in_guild = False
            if base_cmd.is_global:
                cmd_in_guild = True
            elif guild_id in base_cmd.guild_ids:
                cmd_in_guild = True
            if cmd_in_guild == True:
                cmd_names.append(subcmd.qualified_name)
            if len(subcmd.children) > 0:
                cmd_names.extend(self.get_all_subcmd_names(guild_id, subcmd))
        return cmd_names

    async def choose_command_autocomplete(self, interaction: Interaction, data: str):
        """
        Return every command and subcommand in the bot.
        Returns command that match `data` if it is provided.
        """
        base_cmds = interaction.client.get_all_application_commands()
        cmd_names = []
        for base_cmd in base_cmds:
            cmd_in_guild = False
            if base_cmd.is_global:
                cmd_in_guild = True
            elif interaction.guild_id in base_cmd.guild_ids:
                cmd_in_guild = True
            if cmd_in_guild == True:
                cmd_names.append(base_cmd.name)
            if hasattr(base_cmd, "children") and len(base_cmd.children) > 0:
                cmd_names.extend(self.get_all_subcmd_names(interaction.guild_id, base_cmd))
        cmd_names.sort()
        if not data:
            # return full list
            await interaction.response.send_autocomplete(cmd_names[:25])
        else:
            # send a list of nearest matches from the list of item
            near_items = [cmd for cmd in cmd_names if data.lower() in cmd.lower()]
            await interaction.response.send_autocomplete(near_items[:25])

    @nextcord.slash_command()
    async def help(
        self,
        interaction: Interaction,
        cmd_name: str = SlashOption(
            name="command",
            description="Get extra info for this command. Tip: prefix the query with '$' to search for partial matches.",
            default=None,
            required=False,
            autocomplete_callback=choose_command_autocomplete,
        ),
    ):
        """Get a list of commands or info of a specific command."""
        mapping = functions.get_mapping(interaction, self.bot)

        if not cmd_name:  # send full command list
            view = HelpView(interaction, mapping)
            embed = view.help_embed()
            view.btn_disable()
            await interaction.send(embed=embed, view=view)
        else:
            # find a specific command
            cmd_name = cmd_name.strip()
            if cmd_name.startswith("$"):  # search for commands, not just exact matches
                cmd_name = cmd_name[1:]  # remove "$" prefix
                if len(cmd_name) < 3:
                    await interaction.send(embed=TextEmbed("Use search terms at least 3 characters long."))
                    return

                cmds = []
                search_command = (
                    lambda command: cmd_name in command.qualified_name
                    or cmd_name.lower() in command.description.lower()
                )
                for i in interaction.client.get_all_application_commands():
                    # prioritise subcommands
                    if subcmds := [j for j in i.children.values() if search_command(j)]:
                        cmds.extend(subcmds)
                    elif subsubcmds := [
                        k for j in i.children.values() for k in j.children.values() if search_command(k)
                    ]:
                        cmds.extend(subsubcmds)
                    elif search_command(i):
                        cmds.append(i)

                if not cmds:
                    await interaction.send(
                        embed=TextEmbed(
                            f"There are no commands matching _{cmd_name}_. Use </help:964753444164501505> for a list of available commands"
                        )
                    )
                    return

                # at least 1 command has been found, send the view with the command list
                view = HelpView(interaction, mapping)
                view.cmd_list = cmds
                embed = view.help_embed(
                    author_name=f"Commands matching '{cmd_name}'",
                )

                # disable some paginating buttons
                view.btn_disable()

                # remove the select menu to choose between cogs
                select = [i for i in view.children if i.custom_id == "cog_select"][0]
                view.remove_item(select)
                await interaction.send(embed=embed, view=view)
            else:  # search for exact matches since the user is likely to have selected it from autocomplete
                cmd = None

                for i in interaction.client.get_all_application_commands():
                    # search for the command name
                    if i.is_global or interaction.guild_id in i.guild_ids:  # command is available to user
                        if i.name == cmd_name:  # matched exact command
                            cmd = i
                            break
                        elif i.children and i.qualified_name in cmd_name:  # subcommand
                            try:
                                cmd = self.search_subcommand(i, cmd_name)
                            except functions.CommandNotFound:
                                continue
                            else:
                                break

                if cmd is None:  # no exact match of command
                    await interaction.send(
                        embed=TextEmbed(
                            "The command is not found! Use </help:964753444164501505> for a list of available commands"
                        )
                    )
                    return

                # the exact match has been found
                embed = Embed()
                name = cmd.qualified_name
                embed.title = f"Info of </{name}:{list(cmd.command_ids.values())[0]}>"
                embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)

                if len(cmd.children) > 0:
                    # this command has subcommands, send a list of the subcommands
                    view = HelpView(interaction, mapping)
                    view.cmd_list = cmd.children.values()
                    embed = view.help_embed(
                        description=f">>> {cmd.description}",
                        author_name=f"Subcommands of /{name}",
                    )

                    # disable some paginating buttons
                    view.btn_disable()

                    # remove the select menu to choose between cogs
                    select = [i for i in view.children if i.custom_id == "cog_select"][0]
                    view.remove_item(select)
                    await interaction.send(embed=embed, view=view)
                else:
                    # this command does not have subcommands,
                    # send values of the command itself
                    embed.description = cmd.description

                    cmd_options = [i for i in list(cmd.options.values())]
                    usage = f"`/{name} "

                    options_txt = ""
                    for option in cmd_options:
                        if option.required == True:
                            usage += f"<{option.name}> "
                        else:
                            usage += f"[{option.name}] "

                        options_txt += (
                            f"**`{option.name}`**: {option.description}\n"
                            if option.description != "No description provided."
                            else ""
                        )

                    usage = usage[:-1]  # remove the last space
                    usage += "`"  # make it monospace

                    embed.add_field(name="Usage", value=usage, inline=False)
                    if options_txt != "":
                        embed.add_field(name="Options", value=options_txt, inline=False)

                    embed.set_footer(text="Syntax: <required> [optional]")
                    embed.colour = random.choice(constants.EMBED_COLOURS)
                    await interaction.send(embed=embed)

    async def choose_item_autocomplete(self, interaction: Interaction, data: str):
        sql = """
            SELECT name
            FROM utility.items
            ORDER BY name
        """
        db: Database = self.bot.db
        result = await db.fetch(sql)
        items = [i[0] for i in result]
        if not data:
            # return full list
            await interaction.response.send_autocomplete(items)
            return
        else:
            # send a list of nearest matches from the list of item
            near_items = [item for item in items if data.lower() in item.lower()][:25]
            await interaction.response.send_autocomplete(near_items)

    @nextcord.slash_command()
    async def item(
        self,
        interaction: Interaction,
        itemname: str = SlashOption(
            name="item",
            description="The item to search for",
            autocomplete_callback=choose_item_autocomplete,
        ),
    ):
        """Get information of an item."""
        sql = """
            SELECT *
            FROM utility.items
            WHERE name ILIKE $1 or emoji_name ILIKE $1
            ORDER BY name ASC
        """
        db: Database = self.bot.db
        item = await db.fetchrow(sql, f"%{itemname.lower()}%")
        if not item:
            await interaction.send(embed=Embed(description="The item is not found!"), ephemeral=True)
        else:
            res = await db.fetch(
                """
                SELECT inv_type, quantity
                FROM players.inventory
                WHERE player_id = $1 AND item_id = $2
                """,
                interaction.user.id,
                item["item_id"],
            )
            owned_quantities = {constants.InventoryType(inv_type).name: quantity for inv_type, quantity in res}
            embed = functions.get_item_embed(item, owned_quantities)
            await interaction.send(embed=embed)

    @nextcord.slash_command()
    async def guide(self, interaction: Interaction):
        """Get help navigating the wasteland with BOSS's guide."""
        view = GuideView(interaction)
        await view.send()

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

    @nextcord.slash_command(
        name="generate-maze",
        description="Generates a maze using the Mazelib Python library",
    )
    @cooldowns.cooldown(1, 180, SlashBucket.author, check=check_if_not_dev_guild)
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
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
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
            except functions.ComponentLabelTooLong:
                continue
            else:
                view = TriviaView(interaction, question)
                break

        await view.send()

    @nextcord.slash_command()
    async def encrypt(
        self,
        interaction: Interaction,
        plaintext: str = SlashOption(description="The message to encrypt"),
        key: str = SlashOption(
            description="The base64-encoded key to be used in AES. If not provided will be generated randomly.",
            required=False,
        ),
    ):
        """Send (truly) private messages with your friend using AES!"""
        if key is None:
            key = os.urandom(32)
        else:
            try:
                key = base64.b64decode(key)
            except:
                await interaction.send(embed=TextEmbed("The key is not properly encoded in base64."))
                return

        # Encrypt data with AES
        try:
            cipher = AES.new(key, AES.MODE_ECB)
        except:
            await interaction.send(embed=TextEmbed("The key is invalid!"))
            return

        b = plaintext.encode("UTF-8")
        padded_data = pad(b, AES.block_size)
        ciphertext = cipher.encrypt(padded_data)

        data = {
            "Plaintext": plaintext,
            "Ciphertext": ciphertext,
            "AES Key": key,
        }
        embed = Embed()
        for k, v in data.items():
            embed.add_field(
                name=k,
                value=f"```{base64.b64encode(v).decode()}```" if isinstance(v, bytes) else f"```{v}```",
                inline=False,
            )
        await interaction.send(embed=embed)

    @nextcord.slash_command()
    async def decrypt(
        self,
        interaction: Interaction,
        ciphertext: str = SlashOption(description="The message to decrypt"),
        key: str = SlashOption(description="The base64-encoded key to be used in AES."),
    ):
        """Decrypt that gibberish your friend just sent you!"""
        data = {
            "ciphertext": ciphertext,
            "key": key,
        }
        for k, v in data.items():
            try:
                data[k] = base64.b64decode(v)
            except:
                await interaction.send(embed=TextEmbed(f"The {k} is not properly encoded in base64."))
                return

        # Decrypt data with AES
        try:
            cipher = AES.new(data["key"], AES.MODE_ECB)
        except:
            await interaction.send(embed=TextEmbed("The key is invalid!"))
            return

        try:
            data = cipher.decrypt(data["ciphertext"])
            unpadded_data = unpad(data, AES.block_size).decode("UTF-8")
        except:
            await interaction.send(
                embed=TextEmbed(
                    "The message could not be decrypted. Are you sure that both of you are using the same key AND initalization vector?"
                ),
                ephemeral=True,
            )
            return

        data = {
            "Decrypted message": unpadded_data,
            "Ciphertext": ciphertext,
        }
        embed = Embed()
        for k, v in data.items():
            embed.add_field(
                name=k,
                value=f"```{base64.b64encode(v).decode()}```" if isinstance(v, bytes) else f"```{v}```",
                inline=False,
            )
        await interaction.send(embed=embed)

    @encrypt.before_invoke
    @decrypt.before_invoke
    async def defer_ephemeral(interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

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

    async def get_temperature(self, location: str, language="Val_Eng"):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.hko.gov.hk/json/DYN_DAT_MINDS_RHRREAD.json") as response:
                html = await response.json()

        temp_list: dict[dict] = html.get("DYN_DAT_MINDS_RHRREAD")

        date = temp_list.get("BulletinDate")[language]
        time = temp_list.get("BulletinTime")[language]
        hk_tz = pytz.timezone("Asia/Hong_Kong")
        temp_time = datetime.datetime.strptime(date + time, "%Y%m%d%H%M").replace(tzinfo=hk_tz)
        if not location:
            location_name = "Hong Kong Observatory"
            temp = temp_list.get("HongKongObservatoryTemperature")[language]
        else:
            try:
                location_name = temp_list.get(f"{location}LocationName")[language]
                temp = temp_list.get(f"{location}Temperature")[language]
            except TypeError:
                return temp_time, location_name

        humidty = temp_list.get("HongKongObservatoryRelativeHumidity")[language]
        messages = []
        # using 2 seperate for loops to make sure `Message` always goes first.
        for k, v in temp_list.items():
            if "Message" in k and v[language] != "":
                messages.append(v[language])
        for k, v in temp_list.items():
            if "AdditionalInformation" in k and v[language] != "":
                messages.append(v[language])

        return (
            temp_time,
            location_name,
            float(temp),
            float(humidty),
            "\n".join(messages),
        )

    async def get_weather_forecast(self, language="Val_Eng"):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.hko.gov.hk/json/DYN_DAT_MINDS_FLW.json") as response:
                html = await response.json()

        response: dict[dict] = html.get("DYN_DAT_MINDS_FLW")
        date = response.get("BulletinDate")[language]
        time = response.get("BulletinTime")[language]
        hk_tz = pytz.timezone("Asia/Hong_Kong")
        forecast_time = datetime.datetime.strptime(date + time, "%Y%m%d%H%M").replace(tzinfo=hk_tz)

        situation = response.get("FLW_WxForecastGeneralSituation")[language]
        situation += "\n\n"
        situation += response.get("FLW_WxForecastWxDesc")[language]

        outlook = response.get("FLW_WxOutlookContent")[language]

        return forecast_time, situation, outlook

    def get_weather_embed(self, temp):
        embed = Embed()
        embed.set_author(
            name=f"Information fetched from HK Observatory",
            url="https://www.hko.gov.hk/en/",
        )

        if len(temp) > 2:  # fetching info succeeded
            embed.add_field(name=f"Temperature", value=f"{temp[1]} - {temp[2]}°C", inline=True)
            embed.add_field(name=f"Humidty", value=f"{temp[3]}%", inline=True)
            if temp[2] > 12:
                embed.colour = 0xFF4365
            elif temp[2] > 9:
                embed.colour = 0xEEF36A
            else:
                embed.colour = 0x6BA368
        else:
            embed.add_field(
                name="Unavailable",
                value=f"Required information is not available for the location `{temp[1]}`",
            )
        if temp[4]:
            embed.add_field(name="Message", value=temp[4], inline=False)
        embed.timestamp = temp[0]

        return embed

    async def choose_location_autocomplete(self, interaction: Interaction, data: str):
        if not data:
            # return full list
            await interaction.response.send_autocomplete(dict(sorted(self.location_list.items())[:25]))
        else:
            # send a list of nearest matches from the list of item
            near_locations = {
                k: v for k, v in self.location_list.items() if data.lower() in k.lower() or data.lower() in v.lower()
            }
            await interaction.response.send_autocomplete(dict(sorted(near_locations.items())[:25]))

    @nextcord.slash_command(name="weather", description="Fetches the latest temperature from HK observatory")
    async def fetch_forecast(
        self,
        interaction: Interaction,
        location: str = SlashOption(
            description="Choose a specific location",
            required=False,
            default=None,
            autocomplete_callback=choose_location_autocomplete,
        ),
        language: str = SlashOption(
            description="Language to display the forecasts in",
            required=False,
            default="Val_Eng",
            choices={"English": "Val_Eng", "Chinese": "Val_Chi"},
        ),
    ):
        if location and location not in self.location_list.keys() and location not in self.location_list.values():
            await interaction.send(f"District not found\n`{location=}`\n", ephemeral=True)
            return

        temp = await self.get_temperature(location, language)
        forecast = await self.get_weather_forecast(language)
        # icon_src = self.get_weather_icon()

        embed = self.get_weather_embed(temp)
        view = WeatherView(forecast)

        view.msg = await interaction.send(embed=embed, view=view)

    @tasks.loop(time=datetime.time(23, 5))  # 07:05 am
    async def announce_temp(self):
        guild: nextcord.Guild = await self.bot.fetch_guild(827537903634612235)
        channel = await guild.fetch_channel(1056236722654031903)

        temp = await self.get_temperature("TseungKwanO", "Val_Eng")
        forecast = await self.get_weather_forecast("Val_Eng")

        embed = self.get_weather_embed(temp)
        view = PersistentWeatherView(forecast)

        await channel.send(embed=embed, view=view)

    async def search_yt_autocomplete(self, interaction: Interaction, data):
        if not data:
            await interaction.response.send_autocomplete(["Searching..."])
            return

        s = Search(data)
        results = None

        with suppress(KeyError):
            # the pytube library sometimes raises

            # self._completion_suggestions = self._initial_results['refinements']
            #                                    ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^
            # KeyError: 'refinements'

            # when there are no errors, so we suppress it here

            results = s.completion_suggestions

        if results is None:
            await interaction.response.send_autocomplete([data])
        else:
            await interaction.response.send_autocomplete([data] + results[:24])

    @nextcord.slash_command(name="search-channel")
    @application_checks.is_owner()
    async def find_yt_channel(
        self,
        interaction: Interaction,
        channel: str = SlashOption(
            description="The name of the channel to search for",
            autocomplete_callback=search_yt_autocomplete,
        ),
    ):
        """Finds the newest videos of a channel"""
        api_service_name = "youtube"
        api_version = "v3"
        dev_key = "AIzaSyA9Ba9ntb537WecGTfR9izUCT6Y1ULkQIY"

        youtube = googleapiclient.discovery.build(api_service_name, api_version, developerKey=dev_key)
        search_response = (
            youtube.search().list(part="snippet", type="channel", q=channel, maxResults=1).execute()["items"][0]
        )

        channel_response = (
            youtube.channels()
            .list(
                part="snippet,contentDetails",
                id=search_response["snippet"]["channelId"],
                maxResults=25,
            )
            .execute()["items"][0]
        )

        playlist = channel_response["contentDetails"]["relatedPlaylists"]["uploads"]

        playlist_response = (
            youtube.playlistItems().list(part="contentDetails", playlistId=playlist, maxResults=25).execute()["items"]
        )

        videos_response = (
            youtube.videos()
            .list(
                part="snippet,contentDetails,statistics",
                id=",".join([video["contentDetails"]["videoId"] for video in playlist_response]),
            )
            .execute()["items"]
        )

        videos = [Video.from_api_response(video) for video in videos_response]
        view = VideoView(interaction, videos)

        embed = view.get_embed()

        view.msg = await interaction.send(embed=embed, view=view)

    @nextcord.slash_command(name="search-youtube")
    @application_checks.is_owner()
    async def search_youtube(
        self,
        interaction: Interaction,
        query: str = SlashOption(
            description="Search query",
            autocomplete_callback=search_yt_autocomplete,
            required=True,
            min_length=3,
        ),
    ):
        """Searches for videos on Youtube"""
        s = Search(query)

        video_ids = [video.video_id for video in s.results][:25]

        api_service_name = "youtube"
        api_version = "v3"
        dev_key = "AIzaSyA9Ba9ntb537WecGTfR9izUCT6Y1ULkQIY"

        youtube = googleapiclient.discovery.build(api_service_name, api_version, developerKey=dev_key)

        videos_response = (
            youtube.videos().list(part="snippet,contentDetails,statistics", id=",".join(video_ids)).execute()["items"]
        )

        videos = [Video.from_api_response(video) for video in videos_response]
        view = VideoView(interaction, videos)

        embed = view.get_embed()

        view.msg = await interaction.send(embed=embed, view=view)

    @nextcord.slash_command(name="upload-imgur")
    async def upload_imgur(
        self,
        interaction: Interaction,
        image: nextcord.Attachment = SlashOption(description="Image to upload", required=True),
        title: str = SlashOption(description="Title of image (optional)", required=False),
        description: str = SlashOption(description="Description of image (optional)", required=False),
    ):
        """Uploads an image to imgur anonymously and returns the link"""
        payload = {
            "image": image.url,
            "type": "url",
            "title": title,
            "description": description,
        }

        headers = {"Authorization": "Client-ID 826be6012a5dd28"}

        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.imgur.com/3/image", headers=headers, data=payload) as response:
                html = await response.json()

        if not html.get("success"):
            embed = Embed(title="Uploading image failed!", description="Please try again.")
            embed.add_field(
                name="Causes",
                value="`-` an incompatible file format is uploaded; or\n`-` an internal error has occured",
            )
            embed.add_field(
                name="Error",
                value=f"```py\n{html['data']['error']}```",
                inline=False,
            )
            await interaction.send(embed=embed, ephemeral=True)
            return

        data = html["data"]
        link = data["link"]

        embed = Embed()

        embed.set_author(name="Uploading image successful!", url=link)
        embed.set_image(url=link)

        embed.description = f"`LINK` - **{link}**"
        embed.add_field(
            name="Post",
            value=(
                f"**`TITLE`** - {title if title else '_n/a_'}\n"
                f"**`DESCRIPTION`** - {description if description else '_n/a_'}\n"
                f"**`UPLOADED AT`** - <t:{data['datetime']}:R> | <t:{data['datetime']}:f>"
            ),
        )
        embed.add_field(
            name="Image",
            value=(
                f"**`WIDTH`** - {data['width']}\n" f"**`HEIGHT`** - {data['height']}\n" f"**`TYPE`** - `{data['type']}`"
            ),
        )
        await interaction.send(embed=embed)

    @nextcord.slash_command(name="next-train")
    async def next_train(
        self,
        interaction: Interaction,
        line: str = SlashOption(
            description="The railway line",
            choices={i.name.replace("_", " "): i.value for i in MtrLine},
        ),
        station: str = SlashOption(name="station", description="Any station in the line"),
    ):
        """Shows information of the HK MTR train system."""
        # validate data
        # `line` is verified by discord, we only need to check `station`
        if station not in LINE_STATION_CODES[line].values():
            await interaction.send(embed=TextEmbed("Please input a valid line-station pair."))
            return

        params = {"line": line, "sta": station}
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php", params=params
            ) as response:
                train_res = await response.json()

        if train_res["status"] == 0:  # special train arrangements/an error occured.
            msg = train_res["message"]
            if url := train_res.get("url"):
                msg += f"\n{url}"
            await interaction.send(embed=TextEmbed(f"{msg}\nPlease try again."))
            return

        if train_res.get("sys_time") == "-":  # data is absent.
            await interaction.send(embed=TextEmbed("The data is currently unavailable."))
            return

        trains = Train.from_api_response(train_res)
        if trains["UP"] or trains["DOWN"]:
            view = NextTrainView(interaction, trains)
            embed = view.get_embed()
            view.update_view()
            await interaction.send(embed=embed, view=view)
        else:  # neither up or down directions are available --> no trains will come
            station_name = [name for name, code in LINE_STATION_CODES[line].items() if code == station][0]
            embed = Embed()
            embed.description = f"No trains will arrive at **{station_name}** in the near future."
            await interaction.send(embed=embed)

    @next_train.on_autocomplete("station")
    async def station_autocomplete(self, interaction: Interaction, station: str, line: Optional[str] = None):
        """
        If `line` is empty, tell users to choose a line first.
        Otherwise, search for a specifc station.
        """

        if not line:
            await interaction.response.send_autocomplete(
                [
                    "Open the slash command again and choose a line first.",
                    "If you want to switch to a new line, do that too.",
                ]
            )
            return
        if line and not station:
            stations = dict([(name, code) for name, code in LINE_STATION_CODES[line].items()][:25])
            await interaction.response.send_autocomplete(stations)
            return

        station = station.strip()
        # search for stations
        near_stations = dict(
            sorted(
                [(name, code) for name, code in LINE_STATION_CODES[line].items() if station.lower() in name.lower()]
            )[:25]
        )
        await interaction.response.send_autocomplete(near_stations)


def setup(bot: commands.Bot):
    bot.add_cog(Misc(bot))

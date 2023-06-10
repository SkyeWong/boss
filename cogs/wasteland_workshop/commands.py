# nextcord
import nextcord
from nextcord.ext import commands, tasks, application_checks
from nextcord import Embed, Interaction, SlashOption, SelectOption
from nextcord.ui import View, Button, Select

# command cooldowns
import cooldowns
from cooldowns import SlashBucket

# my modules and constants
from utils import constants, helpers
from utils.helpers import check_if_not_dev_guild, TextEmbed

# command views
from .views import (
    EmojiView,
    WeatherView,
    PersistentWeatherView,
    VideoView,
    ChannelVideoView,
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

from quickchart import QuickChart

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


class Misc(commands.Cog, name="Wasteland Workshop"):
    """A collection of misc commands and other features"""

    COG_EMOJI = "🧰"

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
        self.AES_KEY = os.urandom(32)

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
            raise helpers.CommandNotFound()
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

    @nextcord.slash_command(
        name="generate-maze",
        description="Generates a maze using the Mazelib Python library",
    )
    @cooldowns.cooldown(1, 180, SlashBucket.author, check=check_if_not_dev_guild)
    async def generate_maze(
        self,
        interaction: Interaction,
        width: int = SlashOption(description="The width of the maze", required=True, max_value=60),
        height: int = SlashOption(
            description="The length of the maze. If not set, will be set to `width`.",
            required=False,
            max_value=60,
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
                    "The message could not be decrypted. Are you sure that both of you are using the same key?"
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

    async def get_hko_weather_forecast(self, language="Val_Eng"):
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

    def get_hko_weather_embed(self, temp):
        embed = Embed()
        embed.set_author(
            name=f"Information fetched from HK Observatory",
            url="https://www.hko.gov.hk/en/",
        )

        if len(temp) > 2:  # fetching info succeeded
            embed.add_field(name=f"Temperature", value=f"{temp[1]} - {temp[2]}°C", inline=True)
            embed.add_field(name=f"Humidty", value=f"{temp[3]}%", inline=True)
            if temp[2] >= 35:
                embed.colour = 0x9F294C  # dark red
            elif temp[2] >= 31:
                embed.colour = 0xC38A54  # orange
            elif temp[2] >= 26:
                embed.colour = 0xC09D63  # yellow
            elif temp[2] >= 21:
                embed.colour = 0x879A84  # green
            elif temp[2] >= 16:
                embed.colour = 0x438190  # turqoise
            elif temp[2] >= 10:
                embed.colour = 0x275B80  # dark blue
            else:
                embed.colour = 0x39517F  # indigo
        else:
            embed.add_field(
                name="Unavailable",
                value=f"Required information is not available for the location `{temp[1]}`",
            )
        if temp[4]:
            embed.add_field(name="Message", value=temp[4], inline=False)
        embed.timestamp = temp[0]

        return embed

    @nextcord.slash_command(name="weather")
    async def weather(self, interaction: Interaction):
        """Get real-time weather forecasts from multiple providers."""
        pass

    async def open_meteo_location_autocomplete(self, interaction: Interaction, data: str):
        if not data:
            await interaction.response.send_autocomplete(["Start typing to search for locations"])
        else:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://geocoding-api.open-meteo.com/v1/search", params={"name": data}
                ) as response:
                    locations = await response.json()
            if results := locations.get("results"):
                choices = {}
                for i in results:
                    # Encrypt location data with AES to prevent users from faking location
                    plaintext = f"{i['name']}&{i['latitude']}&{i['longitude']}".encode("UTF-8")
                    padded = pad(plaintext, AES.block_size)
                    cipher = AES.new(self.AES_KEY, AES.MODE_ECB)
                    ciphertext = cipher.encrypt(padded)
                    # convert the ciphertext (bytes) into base 64 text
                    ciphertext = base64.b64encode(ciphertext).decode()

                    choices[f"{i['name']} ({i['timezone']})"] = ciphertext
                await interaction.response.send_autocomplete(choices)
            else:
                await interaction.response.send_autocomplete([])

    DIRECTIONS = [
        ("South", "<:CH_S:1091550953376858182>"),  # south
        ("South East", "<:CH_SE:1091550956363206676>"),  # south east
        ("East", "<:CH_E:1091550939908943882>"),  # east
        ("North East", "<:CH_NE:1091550945478987836>"),  # north east
        ("North", "<:CH_N:1091550941733462047>"),  # north
        ("North West", "<:CH_NW:1091550949761351710>"),  # north west
        ("West", "<:CH_W:1091550936079544321>"),  # west
        ("South West", "<:CH_SW:1091550959555063909>"),  # south west
        ("South", "<:CH_S:1091550953376858182>"),  # south
    ]
    WEATHER_CODES = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog and depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow fall",
        73: "Moderate snow fall",
        75: "Heavy snow fall",
        77: "Snow grains",
        80: "Slight rain showers",
        81: "Moderate rain showers",
        82: "Violent rain showers",
        85: "Slight snow showers",
        86: "Heavy snow showers",
        95: "Slight or moderate thunderstorm",
        96: "Slight thunderstorm with hail",
        99: "Heavy thunderstorm with hail",
    }

    @weather.subcommand(name="open-meteo")
    async def open_meteo_weather(
        self,
        interaction: Interaction,
        encrypted_location: str = SlashOption(
            name="location",
            description="Choose a specific location <name (timezone)>",
            autocomplete_callback=open_meteo_location_autocomplete,
        ),
    ):
        """Fetches the current weather data, anywhere in the world!"""
        cipher = AES.new(self.AES_KEY, AES.MODE_ECB)
        try:
            encrypted_location = base64.b64decode(encrypted_location)
            data = cipher.decrypt(encrypted_location)
            decrypted_location = unpad(data, AES.block_size).decode("UTF-8")
        except:
            await interaction.send(embed=TextEmbed("Choose a valid location from the list."))
            return

        # split the text passed from the autocomplete into 3 parts
        name, latitude, longitude = decrypted_location.split("&")
        # fetch the data from open-meteo.com
        params = dict(
            latitude=latitude,
            longitude=longitude,
            current_weather="true",
            hourly="temperature_2m,relativehumidity_2m,apparent_temperature,uv_index",
            forecast_days=1,
            timezone="auto",
        )
        async with aiohttp.ClientSession() as session:
            async with session.get("https://api.open-meteo.com/v1/forecast", params=params) as response:
                data = await response.json()

        weather = data["current_weather"]

        embed = Embed()
        wind_direction = self.DIRECTIONS[round(weather["winddirection"] / 45)]
        embed.description = (
            f"\n## {name}"
            f"\n**{self.WEATHER_CODES.get(weather['weathercode'], 'Unknown')}**"
            f"\n- Temperature: `{weather['temperature']} °C`"
            f"\n- Wind: `{weather['windspeed']} km/h` (from: {wind_direction[1]} {wind_direction[0]})"
        )

        # Parse the date string into a datetime object
        data_time = datetime.datetime.strptime(weather["time"], "%Y-%m-%dT%H:%M")
        # Create a timezone object based on the timezone string
        timezone = pytz.timezone(data["timezone"])
        # Attach the timezone object to the datetime object
        data_time = timezone.localize(data_time)
        embed.description += f"\n(at <t:{int(data_time.timestamp())}:f>)"

        # Create the chart
        qc = QuickChart()
        qc.version = 4
        qc.width = 600
        qc.height = 360
        qc.background_color = "#282B30"
        y_min = helpers.rounddown(min(data["hourly"]["apparent_temperature"] + data["hourly"]["temperature_2m"]), 8)
        y_max = helpers.roundup(max(data["hourly"]["apparent_temperature"] + data["hourly"]["temperature_2m"]), 10)

        qc.config = {
            "type": "line",
            "data": {
                "labels": data["hourly"]["time"],
                "datasets": [
                    {
                        "label": "Temperature",
                        "data": data["hourly"]["temperature_2m"],
                        "fill": False,
                        "borderColor": "#f2b5d4",
                        "yAxisID": "y_temperature",
                        "tension": 0.3,
                    },
                    {
                        "label": "Apparent Temperature",
                        "data": data["hourly"]["apparent_temperature"],
                        "fill": False,
                        "borderColor": "#eff7f6",
                        "yAxisID": "y_temperature",
                        "tension": 0.3,
                    },
                    {
                        "label": "Relative Humidity",
                        "data": data["hourly"]["relativehumidity_2m"],
                        "fill": False,
                        "borderColor": "#7bdff2",
                        "yAxisID": "y_humidity",
                        "tension": 0.3,
                    },
                ],
            },
            "options": {
                "layout": {"padding": {"x": 20, "y": 30}},
                "plugins": {
                    "title": {
                        "display": True,
                        "text": name,
                        "padding": 15,
                        "font": {
                            "family": "Noto Sans Display",
                            "size": 24,
                        },
                    },
                    "legend": {
                        "display": True,
                        "position": "bottom",
                        "labels": {
                            "font": {
                                "family": "Noto Sans",
                                "size": 16,
                            },
                        },
                    },
                    "annotation": {
                        "annotations": [
                            {
                                "type": "line",
                                "scaleID": "x",
                                "value": data["current_weather"]["time"],
                                "borderColor": "#ffffff",
                                "borderWidth": 2,
                                "label": {
                                    "enabled": True,
                                    "content": "Now",
                                    "position": "start",
                                    "yAdjust": -30,
                                    "color": "white",
                                    "backgroundColor": "#52b2cf",
                                },
                            }
                        ],
                    },
                    "colorschemes": {"scheme": "brewer.RdBu5"},
                },
                "scales": {
                    "y_temperature": {
                        "title": {
                            "display": True,
                            "text": "Temperature (°C)",
                            "font": {
                                "family": "Noto Sans",
                                "size": 20,
                            },
                        },
                        "ticks": {
                            "font": {
                                "family": "Noto Sans",
                                "size": 12,
                            },
                            "beginAtZero": False,
                        },
                        "min": y_min,
                    },
                    "y_humidity": {
                        "position": "right",
                        "grid": {  # grid line settings
                            "drawOnChartArea": False,  # only want the grid lines for one axis to show up
                        },
                        "title": {
                            "display": True,
                            "text": "Humidity (%)",
                            "font": {
                                "family": "Noto Sans",
                                "size": 20,
                            },
                        },
                        "ticks": {
                            "font": {
                                "family": "Noto Sans",
                                "size": 12,
                            },
                            "beginAtZero": False,
                        },
                        "max": 100,
                    },
                    "x": {
                        "type": "time",
                        "title": {
                            "display": True,
                            "text": f"Time ({data['timezone_abbreviation']})",
                            "font": {
                                "family": "Noto Sans",
                                "size": 18,
                            },
                        },
                        "ticks": {
                            "font": {
                                "family": "Noto Sans",
                                "size": 16,
                            },
                        },
                    },
                },
            },
        }
        embed.set_image(qc.get_short_url())

        await interaction.send(embed=embed)

    async def hko_location_autocomplete(self, interaction: Interaction, data: str):
        if not data:
            # return full list
            await interaction.response.send_autocomplete(dict(sorted(self.location_list.items())[:25]))
        else:
            # send a list of nearest matches from the list of item
            near_locations = {
                k: v for k, v in self.location_list.items() if data.lower() in k.lower() or data.lower() in v.lower()
            }
            await interaction.response.send_autocomplete(dict(sorted(near_locations.items())[:25]))

    @weather.subcommand(name="hk-observatory")
    async def hko_weather(
        self,
        interaction: Interaction,
        location: str = SlashOption(
            description="Choose a specific location",
            required=False,
            default=None,
            autocomplete_callback=hko_location_autocomplete,
        ),
        language: str = SlashOption(
            description="Language to display the forecasts in",
            required=False,
            default="Val_Eng",
            choices={"English": "Val_Eng", "Chinese": "Val_Chi"},
        ),
    ):
        """Fetches the latest temperature from HK observatory"""
        if location and location not in self.location_list.keys() and location not in self.location_list.values():
            await interaction.send(f"District not found\n`{location=}`\n", ephemeral=True)
            return

        temp = await self.get_temperature(location, language)
        forecast = await self.get_hko_weather_forecast(language)
        # icon_src = self.get_weather_icon()

        embed = self.get_hko_weather_embed(temp)
        view = WeatherView(forecast)

        view.msg = await interaction.send(embed=embed, view=view)

    @tasks.loop(time=datetime.time(23, 5))  # 07:05 am
    async def announce_temp(self):
        guild: nextcord.Guild = await self.bot.fetch_guild(827537903634612235)
        channel = await guild.fetch_channel(1056236722654031903)

        temp = await self.get_temperature("TseungKwanO", "Val_Eng")
        forecast = await self.get_hko_weather_forecast("Val_Eng")

        embed = self.get_hko_weather_embed(temp)
        view = PersistentWeatherView(forecast)

        await channel.send(embed=embed, view=view)
        utc = pytz.timezone("UTC")
        now = datetime.datetime.now(tz=utc).strftime("%y-%#m-%#d %#H:%#M %Z")
        print(f"\033[1;30mAnnounced temperature at {now}.\033[0m")

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

    @nextcord.slash_command(name="youtube", guild_ids=[constants.DEVS_SERVER_ID])
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
        order: str = SlashOption(
            description="How the results should be arranged.",
            choices={
                "Date - reverse order of when the results are created": "date",
                "Rating - descending order of the results' likes.": "rating",
                "Relevance - how closely results match the search query": "relevance",
                "Title - sorted alphabetically by the results' titles": "title",
                "Views - descending number of views": "viewCount",
            },
            default="relevance",
            required=False,
        ),
        filter_duration: str = SlashOption(
            description="Filter video search results based on their duration.",
            choices={
                "No Filters": "any",
                "Long - longer than 20 minutes": "long",
                "Medium - between 4 minutes and 20 minutes long": "medium",
                "Short - shorter than 4 minutes": "short",
            },
            default="any",
            required=False,
        ),
        limit_channel: bool = SlashOption(
            description="Whether to filter the results on only 1 channel. This unsets any filters",
            required=False,
            default=False,
        ),
    ):
        """Searches for videos on Youtube"""
        # initalise the youtube api cilent
        api_service_name = "youtube"
        api_version = "v3"
        dev_key = "AIzaSyA9Ba9ntb537WecGTfR9izUCT6Y1ULkQIY"
        youtube = googleapiclient.discovery.build(api_service_name, api_version, developerKey=dev_key)

        if limit_channel:
            # limit the responses to only 1 channel, here we search for the channels that match the name
            channels = youtube.search().list(part="snippet", type="channel", q=query, maxResults=25).execute()["items"]
            # let users select a channel through a select menu
            view = View()
            embed = TextEmbed("Choose a channel:")
            channel_select = Select(
                # the value of the option is set to the channel id
                options=[SelectOption(label=i["snippet"]["title"], value=i["id"]["channelId"]) for i in channels]
            )

            async def choose_channel(select_interaction: Interaction):
                # fetch the "uploads" playlist of the channel selected
                channel = (
                    youtube.channels()
                    .list(
                        part="snippet,contentDetails",
                        id=channel_select.values[0],
                        maxResults=1,
                    )
                    .execute()["items"][0]
                )
                playlist_id = channel["contentDetails"]["relatedPlaylists"]["uploads"]
                playlist_response = (
                    youtube.playlistItems().list(part="contentDetails", playlistId=playlist_id, maxResults=25).execute()
                )

                # fetch the the details of each video in the playlist
                videos_response = (
                    youtube.videos()
                    .list(
                        part="snippet,contentDetails,statistics",
                        id=",".join([video["contentDetails"]["videoId"] for video in playlist_response["items"]]),
                    )
                    .execute()
                )
                videos = [Video.from_api_response(video) for video in videos_response["items"]]
                # the ChannelVideoView view overrides the default "show next page" behaviour
                view = ChannelVideoView(
                    interaction,
                    videos,
                    playlist_id,
                    prev_page_token=playlist_response.get("prevPageToken"),
                    next_page_token=playlist_response.get("nextPageToken"),
                )
                embed = view.get_embed()
                view.msg = await select_interaction.response.edit_message(embed=embed, view=view)

            channel_select.callback = choose_channel
            view.add_item(channel_select)
            await interaction.send(embed=embed, view=view)
        else:
            # search for videos with the given query, note that only "snippet" part is supported
            search_response = (
                youtube.search()
                .list(part="snippet", type="video", q=query, order=order, videoDuration=filter_duration, maxResults=25)
                .execute()
            )
            video_ids = [i["id"]["videoId"] for i in search_response["items"]]
            # get more details on the videos
            videos_response = (
                youtube.videos().list(part="snippet,contentDetails,statistics", id=",".join(video_ids)).execute()
            )

            videos = [Video.from_api_response(video) for video in videos_response["items"]]
            view = VideoView(
                interaction,
                videos,
                query,
                prev_page_token=search_response.get("prevPageToken"),
                next_page_token=search_response.get("nextPageToken"),
            )

            embed = view.get_embed()
            view.disable_buttons()

            view.msg = await interaction.send(embed=embed, view=view)

    @nextcord.slash_command(name="upload-imgur", guild_ids=[constants.DEVS_SERVER_ID])
    @application_checks.is_owner()
    async def upload_imgur(
        self,
        interaction: Interaction,
        image: nextcord.Attachment = SlashOption(description="Image to upload", required=True),
        title: str = SlashOption(description="Title of image (optional)", required=False),
        description: str = SlashOption(description="Description of image (optional)", required=False),
    ):
        """Uploads an image to imgur anonymously and returns the link. Only available to owners."""
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
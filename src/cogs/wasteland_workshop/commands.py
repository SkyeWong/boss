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
from utils.template_views import BaseView
from utils.helpers import check_if_not_dev_guild, TextEmbed, command_info
from utils.constants import EmbedColour

# command views
from .views import (
    WeatherView,
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
        self.AES_KEY = os.urandom(32)

    @nextcord.slash_command(name="generate-maze", description="Generate a maze using the Mazelib Python library")
    @command_info(
        long_help="You can set multiple properties of the maze from its size, to difficulty and more!\n"
        "> Note: this command takes a while to run, so be patient!",
        examples={
            "generate-maze width:20": "Generates a maze with a width of 50 cells.",
            "generate-maze width:10 difficulty: 9": "Makes 10 mazes and choose the one with the longest solution",
        },
    )
    @cooldowns.cooldown(1, 180, SlashBucket.author, check=check_if_not_dev_guild)
    async def generate_maze_cmd(
        self,
        interaction: Interaction,
        width: int = SlashOption(description="The width of the maze", required=True, max_value=30),
        height: int = SlashOption(
            description="The length of the maze. If not set, will be set to `width`.",
            required=False,
            max_value=30,
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
        embed.colour = EmbedColour.DEFAULT
        embed.set_author(name="Generating maze... Please wait patiently")
        embed.description = "I will ping you when it has finished!"
        msg = await interaction.send(embed=embed)

        height = width if not height else height

        if height < 3 or width < 3:
            await msg.edit(embed=TextEmbed("The maze must be at least 3x3 large!"))
            return

        embed.description += "\n`1.` Generating maze... "
        await msg.edit(embed=embed)

        m = self._generate_maze(width, height, difficulty / 10 if difficulty else None, start, end)

        embed.description += f"**`Done`**!\n`2.` Generating the image... "
        await msg.edit(embed=embed)

        maze_str = m.tostring(True, True)
        solved_img = self._generate_solved_img(maze_str, len(m.grid[0]), len(m.grid))
        unsolved_img = self._generate_unsolved_img(maze_str, self.SPRITE_WIDTH, solved_img)

        embed.add_field(name="Solution length", value=f"`{len(m.solutions[0])}` cells")
        embed.add_field(name="Start ➡ End", value=f"`{m.start[::-1]}` ➡ `{m.end[::-1]}`")
        if difficulty:
            embed.add_field(name="Difficulty", value=difficulty)
        embed.set_image("attachment://maze.png")
        embed.set_author(name="Generating maze successful!")
        embed.colour = EmbedColour.SUCCESS
        embed.description = f"**Width**: `{width}`\n"
        embed.description += f"**Height**: `{height}`"

        solve_view = BaseView(interaction, timeout=180)
        solve_button = Button(label="Solve")

        async def toggle_solve(button_interaction: Interaction):
            embed.set_footer(text="Changing image, please wait...")
            solve_button.disabled = True
            await button_interaction.response.edit_message(embed=embed, view=solve_view)
            if solve_button.label == "Solve":
                # change the image to "solved" image
                solve_button.label = "Unsolve"
                future = loop.run_in_executor(None, self._save_img, solved_img)
            else:
                # change the image to "unsolved" image
                solve_button.label = "Solve"
                future = loop.run_in_executor(None, self._save_img, unsolved_img)
            output = loop.run_until_complete(future)
            maze_img_file = nextcord.File(output, "maze.png")
            solve_button.disabled = False
            embed.set_footer(text=None)  # clear the footer text
            await msg.edit(file=maze_img_file, embed=embed, view=solve_view)

        solve_button.callback = toggle_solve
        solve_view.add_item(solve_button)

        loop = asyncio.get_running_loop()
        # default to the unsolved image
        future = loop.run_in_executor(None, self._save_img, unsolved_img)
        output = loop.run_until_complete(future)
        maze_img_file = nextcord.File(output, "maze.png")

        msg = await msg.edit(file=maze_img_file, embed=embed, view=solve_view)

        # send a message to notify users that the maze has finished generating,
        # and add a "jump" button to let users jump to the maze message
        jump_view = View()
        jump_button = Button(label="View", url=msg.jump_url)
        jump_view.add_item(jump_button)
        int_time = int(interaction.created_at.timestamp())
        await interaction.send(
            interaction.user.mention,
            embed=TextEmbed(
                f"Your {width}x{height} maze requested at <t:{int_time}:R> | <t:{int_time}:f> has been successfully generated!"
            ),
            view=jump_view,
            ephemeral=True,
        )

    def _generate_maze(self, width: int, height: int, difficulty: float | None, start: bool, end: bool) -> Maze:
        m = Maze()
        m.generator = Prims(height, width)
        m.solver = BacktrackingSolver()

        loop = asyncio.get_running_loop()

        if difficulty:
            future = loop.run_in_executor(None, m.generate_monte_carlo, 10, 1, difficulty)
        else:
            m.generate()
            m.generate_entrances(start_outer=start, end_outer=end)
            future = loop.run_in_executor(None, m.solve)

        loop.run_until_complete(future)
        return m

    SPRITES = {
        "ground": Image.open("resources/maze/ground.png"),
        "wall": Image.open("resources/maze/wall.png"),
        "path": Image.open("resources/maze/path.png"),
        "start": Image.open("resources/maze/start.png"),
        "finish": Image.open("resources/maze/finish.png"),
    }
    SPRITE_WIDTH = 36

    def _generate_solved_img(self, maze_str, width, height):
        solved_img = Image.new("RGBA", (self.SPRITE_WIDTH * width, self.SPRITE_WIDTH * height))

        # generate the solved maze image
        for y_i, y in enumerate(maze_str.splitlines()):
            for x_i, x in enumerate(y):
                if x == "#":
                    sprite = self.SPRITES["wall"]
                elif x == " ":
                    sprite = self.SPRITES["ground"]
                elif x == "S":
                    sprite = self.SPRITES["start"]
                elif x == "E":
                    sprite = self.SPRITES["finish"]
                elif x == "+":
                    sprite = self.SPRITES["path"]
                # paste the cell into solved image
                solved_img.paste(sprite, (x_i * self.SPRITE_WIDTH, y_i * self.SPRITE_WIDTH))
        return solved_img

    def _generate_unsolved_img(self, maze_str, sprite_width, solved_img):
        unsolved_img = solved_img.copy()
        # convert every path image into ground image in unsolved image
        for y_i, y in enumerate(maze_str.splitlines()):
            for x_i, x in enumerate(y):
                if x == "+":
                    unsolved_img.paste(self.SPRITES["ground"], (x_i * sprite_width, y_i * sprite_width))
        return unsolved_img

    def _save_img(self, image: Image.Image) -> BytesIO:
        output = BytesIO()
        image.thumbnail((1600, 1600))
        image.save(output, format="PNG")
        output.seek(0)
        return output

    @nextcord.slash_command(name="encrypt", description="Send (truly) private messages with your friend using AES!")
    @command_info(
        long_help="This performs a bit of complex magic that converts your human readable text into random characters, "
        "which can be shown again using </decrypt:1100243607065219193>.",
        notes=[
            "you can enter an optional `key` for the encryption. Be sure to only keep it between the people you are communicating with!"
        ],
        examples={
            "encrypt plaintext:hello world": "Encrypts _hello world_ with a random generated key.",
            "encrypt plaintext:hello world key:<key>": "Encrypts _hello world_ with the provided key. "
            "If the same message is encrypted with the same key twice, it will yield the same results.",
        },
    )
    async def encrypt(
        self,
        interaction: Interaction,
        plaintext: str = SlashOption(description="The message to encrypt"),
        key: str = SlashOption(
            description="The base64-encoded key to be used in AES. If not provided will be generated randomly.",
            required=False,
        ),
    ):
        if key is None:
            key = os.urandom(16)
        else:
            try:
                key = base64.b64decode(key)
            except ValueError:
                await interaction.send(embed=TextEmbed("The key is not properly encoded in base64."))
                return

        # Encrypt data with AES
        try:
            cipher = AES.new(key, AES.MODE_ECB)
        except ValueError:
            await interaction.send(embed=TextEmbed("The key is invalid!", EmbedColour.FAIL))
            return

        b = plaintext.encode("UTF-8")
        padded_data = pad(b, AES.block_size)
        ciphertext = cipher.encrypt(padded_data)

        embed = Embed(colour=EmbedColour.SUCCESS)
        embed.add_field(
            name="Plaintext",
            value=f"```{plaintext}```",
            inline=False,
        )
        embed.add_field(
            name="Ciphertext (base64)",
            value=f"```{base64.b64encode(ciphertext).decode()}```",
            inline=False,
        )
        embed.add_field(
            name="AES Key (base 64)",
            value=f"```{base64.b64encode(key).decode()}```",
            inline=False,
        )
        for i in embed.fields:
            if len(i.value) > 1024:
                await interaction.send(embed=TextEmbed("The message is too long!", EmbedColour.WARNING))
                return
        await interaction.send(embed=embed)

    @nextcord.slash_command(name="decrypt", description="Decrypt that gibberish your friend just sent you!")
    @command_info(
        long_help="This turns the random characters produced from </encrypt:1100243604896759910> back to normal text.",
        notes=["you do need the key to work, so maybe ask your friend to send you it beforehand"],
        examples={
            "decrypt ciphertext:<random characters> key:<key>": "Decrypts the random characters.",
        },
    )
    async def decrypt(
        self,
        interaction: Interaction,
        ciphertext: str = SlashOption(description="The message to decrypt"),
        key: str = SlashOption(description="The base64-encoded key to be used in AES."),
    ):
        data = {
            "ciphertext": ciphertext,
            "key": key,
        }
        for k, v in data.items():
            try:
                data[k] = base64.b64decode(v)
            except ValueError:
                await interaction.send(embed=TextEmbed(f"The {k} is not properly encoded in base64.", EmbedColour.FAIL))
                return

        # Decrypt data with AES
        try:
            cipher = AES.new(data["key"], AES.MODE_ECB)
        except ValueError:
            await interaction.send(embed=TextEmbed("The key is invalid!"))
            return

        try:
            data = cipher.decrypt(data["ciphertext"])
            unpadded_data = unpad(data, AES.block_size).decode("UTF-8")
        except ValueError:
            await interaction.send(
                embed=TextEmbed(
                    "The message could not be decrypted. Are you sure that both of you are using the same key?",
                    EmbedColour.FAIL,
                ),
                ephemeral=True,
            )
            return
        embed = Embed(color=EmbedColour.SUCCESS)
        embed.add_field(
            name="Decrypted message",
            value=f"```{unpadded_data}```",
            inline=False,
        )
        embed.add_field(
            name="Ciphertext (base 64)",
            value=f"```{ciphertext}```",
            inline=False,
        )
        await interaction.send(embed=embed)

    @encrypt.before_invoke
    @decrypt.before_invoke
    @staticmethod
    async def defer_ephemeral(interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

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

    @weather.subcommand(name="global", description="Have a look at the current weather, anywhere in the world!")
    @command_info(
        long_help="This uses the [Open Meteo API](https://api.open-meteo.com) to shows the real-time, up-to-date weather around the globe.\n"
        "Choose a location from the autocompleted results.",
    )
    async def open_meteo_weather(
        self,
        interaction: Interaction,
        encrypted_location: str = SlashOption(
            name="location",
            description="Choose a specific location <name (timezone)>",
            autocomplete_callback=open_meteo_location_autocomplete,
        ),
    ):
        cipher = AES.new(self.AES_KEY, AES.MODE_ECB)
        try:
            encrypted_location = base64.b64decode(encrypted_location)
            data = cipher.decrypt(encrypted_location)
            decrypted_location = unpad(data, AES.block_size).decode("UTF-8")
        except ValueError:
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

        embed = Embed(color=EmbedColour.INFO)
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

        FONT_FAMILY = "Noto Sans"
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
                                "family": FONT_FAMILY,
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
                                "family": FONT_FAMILY,
                                "size": 20,
                            },
                        },
                        "ticks": {
                            "font": {
                                "family": FONT_FAMILY,
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
                                "family": FONT_FAMILY,
                                "size": 20,
                            },
                        },
                        "ticks": {
                            "font": {
                                "family": FONT_FAMILY,
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
                                "family": FONT_FAMILY,
                                "size": 18,
                            },
                        },
                        "ticks": {
                            "font": {
                                "family": FONT_FAMILY,
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

    async def _get_hko_weather_forecast(self, language="Val_Eng"):
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

    def _get_hko_weather_embed(self, temp):
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

    @weather.subcommand(name="hong-kong", description="Show the latest weather from HK observatory")
    @command_info(
        long_help="Displays the weather at Hong Kong using the API provided by [HK Observatory](https://www.hko.gov.hk/), along with a forecast and any warnings the HKO hoisted."
    )
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
        if location and location not in self.location_list.keys() and location not in self.location_list.values():
            await interaction.send(f"District not found\n`{location=}`\n", ephemeral=True)
            return

        temp = await self.get_temperature(location, language)
        forecast = await self._get_hko_weather_forecast(language)

        embed = self._get_hko_weather_embed(temp)
        view = WeatherView(forecast)

        view.msg = await interaction.send(embed=embed, view=view)

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
        """Searches for videos on Youtube. Only available for the owners."""
        # initalise the youtube api cilent
        api_service_name = "youtube"
        api_version = "v3"
        dev_key = os.getenv("GOOGLE_API_KEY")
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
            value=(f"**`WIDTH`** - {data['width']}\n**`HEIGHT`** - {data['height']}\n**`TYPE`** - `{data['type']}`"),
        )
        await interaction.send(embed=embed)

    @nextcord.slash_command(name="next-train", description="View information about the HK MTR train system.")
    @command_info(
        long_help="With this command, you can get the real-time info of when trains are departing/arriving at a station!\n",
        notes=[
            "not all railway lines are supported yet, we hope that MTR will update their API soon.",
            "when using this command, make sure to choose the `line` first before you choose a `station`.",
        ],
    )
    async def next_train(
        self,
        interaction: Interaction,
        line: str = SlashOption(
            description="The railway line",
            choices={i.name.replace("_", " "): i.value for i in MtrLine},
        ),
        station: str = SlashOption(name="station", description="Any station in the line"),
    ):
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

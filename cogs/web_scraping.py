# nextcord
import nextcord
from nextcord import Embed, Interaction, SlashOption
from nextcord.ext import commands, tasks, application_checks

import aiohttp, requests

import googleapiclient.discovery
from pytube import Search

from utils import functions

# views
from views.scraping_views import WeatherView, PersistentWeatherView, VideoView, Video

# default modules
import json
import datetime
import html
import pytz
from contextlib import suppress
from typing import Optional


class WebScraping(commands.Cog, name="Web Scraping"):
    COG_EMOJI = "📶"

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._last_member = None

        response = requests.get("https://www.hko.gov.hk/json/DYN_DAT_MINDS_RHRREAD.json").content.decode("utf-8")
        response: dict[dict] = json.loads(response).get("DYN_DAT_MINDS_RHRREAD")
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
        self.announce_temp.start()

    async def get_temperature(self, location: str, language="Val_Eng"):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.hko.gov.hk/json/DYN_DAT_MINDS_RHRREAD.json") as response:
                html = await response.text()

        temp_list: dict[dict] = json.loads(html).get("DYN_DAT_MINDS_RHRREAD")

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

        return temp_time, location_name, float(temp), float(humidty)

    async def get_weather_forecast(self, language="Val_Eng"):
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.hko.gov.hk/json/DYN_DAT_MINDS_FLW.json") as response:
                html = await response.text()

        response: dict[dict] = json.loads(html).get("DYN_DAT_MINDS_FLW")
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
        
    LINE_CODES = {
            "Airport Express": "AEL",
            "Tung Chung Line": "TCL",
            "Tuen Ma Line": "TML",
            "Tseung Kwan O Line": "TKL",
            "East Rail Line": "EAL",
            "South Island Line": "SIL",
            "Tseun Wan Line": "TWL",
        }
    LINE_STATION_CODES = {
        "AEL": {
            "Hong Kong": "HOK",
            "Kowloon": "KOW",
            "Tsing Yi": "TSY",
            "Airport": "AIR",
            "AsiaWorld Expo": "AWE",
        },
        "TCL": {
            "Hong Kong": "HOK",
            "Kowloon": "KOW",
            "Olympic": "OLY",
            "Nam Cheong": "NAC",
            "Lai King": "LAK",
            "Tsing Yi": "TSY",
            "Sunny Bay": "SUN",
            "Tung Chung": "TUC",
        },
        "TML": {
            "Wu Kai Sha": "WKS",
            "Ma On Shan": "MOS",
            "Heng On": "HEO",
            "Tai Shui Hang": "TSH",
            "Shek Mun": "SHM",
            "City One": "CIO",
            "Sha Tin Wai": "STW",
            "Che Kung Temple": "CKT",
            "Tai Wai": "TAW",
            "Hin Keng": "HIK",
            "Diamond Hill": "DIH",
            "Kai Tak": "KAT",
            "Sung Wong Toi": "SUW",
            "To Kwa Wan": "TKW",
            "Ho Man Tin": "HOM",
            "Hung Hom": "HUH",
            "East Tsim Sha Tsui": "ETS",
            "Austin": "AUS",
            "Nam Cheong": "NAC",
            "Mei Foo": "MEF",
            "Tsuen Wan West": "TWW", 
            "Kam Sheung Road": "KSR", 
            "Yuen Long": "YUL", 
            "Long Ping": "LOP", 
            "Tin Shui Wai": "TIS", 
            "Siu Hong": "SIH", 
            "Tuen Mun": "TUM", 
        },
        "TKL": {
            "North Point": "NOP", 
            "Quarry Bay": "QUB", 
            "Yau Tong": "YAT", 
            "Tiu Keng Leng": "TIK", 
            "Tseung Kwan O": "TKO", 
            "LOHAS Park": "LHP", 
            "Hang Hau": "HAH", 
            "Po Lam": "POA", 
        },
        "EAL": {
            "Admiralty": "ADM", 
            "Exhibition Centre": "EXC", 
            "Hung Hom": "HUH", 
            "Mong Kok East": "MKK", 
            "Kowloon Tong": "KOT", 
            "Tai Wai": "TAW", 
            "Sha Tin": "SHT", 
            "Fo Tan": "FOT", 
            "Racecourse": "RAC", 
            "University": "UNI", 
            "Tai Po Market": "TAP", 
            "Tai Wo": "TWO", 
            "Fanling": "FAN", 
            "Sheung Shui": "SHS", 
            "Lo Wu": "LOW", 
            "Lok Ma Chau": "LMC", 
        },
        "SIL": {
            "Admiralty": "ADM", 
            "Ocean Park": "OCP", 
            "Wong Chuk Hang": "WCH", 
            "Lei Tung": "LET", 
            "South Horizons": "SOH", 
        },
        "TWL": {
            "Central": "CEN", 
            "Admiralty": "ADM", 
            "Tsim Sha Tsui": "TST", 
            "Jordan": "JOR", 
            "Yau Ma Tei": "YMT", 
            "Mong Kok": "MOK", 
            "Price Edward": "PRE", 
            "Sham Shui Po": "SSP", 
            "Cheung Sha Wan": "CSW", 
            "Lai Chi Kok": "LCK", 
            "Mei Foo": "MEF", 
            "Lai King": "LAK", 
            "Kwai Fong": "KWF", 
            "Kwai Hing": "KWH", 
            "Tai Wo Hau": "TWH", 
            "Tsuen Wan": "TSW", 
        },
    }
        
    @nextcord.slash_command(name="next-train")
    async def next_train(
        self, 
        interaction: Interaction,
        line: str=SlashOption(
            description="The railway line",
            choices=LINE_CODES
        ),
        station: str=SlashOption(name="station", description="Any station in the line")
    ):
        """Shows information of the HK MTR train system."""
        # validate data
        # `line` is verified by discord, we only need to check `station`
        if station not in self.LINE_STATION_CODES[line].values():
            await interaction.send(embed=functions.format_with_embed("Please input a valid line-station pair."))
            return
        
        params = {"line": line, "sta": station}
        async with aiohttp.ClientSession() as session:
            async with session.get("https://rt.data.gov.hk/v1/transport/mtr/getSchedule.php", params=params) as response:
                train_res = await response.json()
        
        if train_res["status"] == 0:  # special train arrangements/an error occured.
            msg = train_res['message']
            if url := train_res.get("url"):
                msg += f"\n{url}"
            await interaction.send(embed=functions.format_with_embed(f"{msg}\nPlease try again."))
            return
        
        if train_res.get("sys_time") == "-":  # data is absent.
            await interaction.send(embed=functions.format_with_embed("The data is currently unavailable."))
            return
        
        # successful response
        data = train_res["data"][f"{line}-{station}"]
        trains = data.get("UP", []) + data.get("DOWN", [])  # use empty list for default in case station is at either end of line
        station_name = [name for name, code in self.LINE_STATION_CODES[line].items() if code == station][0]
        
        embed = Embed(title=f"The next trains arriving at **{station_name}**")
        hk_tz = pytz.timezone("Asia/Hong_Kong")
        if trains:
            for train in trains:
                destination_name = [name for name, code in self.LINE_STATION_CODES[line].items() if code == train["dest"]][0]
                arrival_time = datetime.datetime.strptime(train["time"], "%Y-%m-%d %H:%M:%S")
                embed.add_field(
                    name=f"Destination: `{destination_name}`",
                    value=f"Arriving <t:{int(arrival_time.timestamp())}:R>\n" \
                        f"Platform: {train['plat']}" \
                        f"> via Racecourse" if train.get("route") else "",
                    inline=False
                )
        else:
            embed.description = f"No trains will arrive at **{station_name}** in the near future."
            
        await interaction.send(embed=embed)
                
    @next_train.on_autocomplete("station")
    async def station_autocomplete(self, interaction: Interaction, station: str, line: Optional[str] = None):
        """
        If `line` is empty, tell users to choose a line first.
        Otherwise, search for a specifc station.
        """
        
        if not line:
            await interaction.response.send_autocomplete(["Open the slash command again and choose a line first.", "If you want to switch to a new line, do that too."])
            return
        if line and not station:
            stations = dict(sorted(
                [(name, code) for name, code in self.LINE_STATION_CODES[line].items()]
            )[:25])
            await interaction.response.send_autocomplete(stations)
            return
        
        station = station.strip()
        # search for stations
        near_stations = dict(sorted(
            [(name, code) for name, code in self.LINE_STATION_CODES[line].items() if station.lower() in name.lower()]
        )[:25])
        await interaction.response.send_autocomplete(near_stations)


def setup(bot: commands.Bot):
    bot.add_cog(WebScraping(bot))

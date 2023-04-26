# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle, SelectOption
from nextcord.ui import View, Button, button, Select, select

# numerize
from numerize import numerize

import pytz

# my modules
from views.template_views import BaseView

# default modules
import datetime
from typing import Optional
import enum


def get_weather_view(self, forecast):
    view = View()

    situation_btn = Button(label="Current Situation")

    async def send_situation(interaction: Interaction):
        await interaction.send(
            embed=Embed(
                title=f"Current Situation - <t:{int(forecast[0].timestamp())}:f>",
                description=forecast[1],
            ),
            ephemeral=True,
        )

    situation_btn.callback = send_situation
    view.add_item(situation_btn)

    outlook_btn = Button(label="Future Outlook")

    async def send_outlook(interaction: Interaction):
        await interaction.send(
            embed=Embed(
                title=f"Future Outlook - <t:{int(forecast[0].timestamp())}:f>",
                description=forecast[2],
            ),
            ephemeral=True,
        )

    outlook_btn.callback = send_outlook
    view.add_item(outlook_btn)

    return view


async def send_situation(interaction: Interaction, forecast):
    await interaction.send(
        embed=Embed(
            title=f"Current Situation - <t:{int(forecast[0].timestamp())}:f>",
            description=forecast[1],
        ),
        ephemeral=True,
    )


async def send_outlook(interaction: Interaction, forecast):
    await interaction.send(
        embed=Embed(
            title=f"Future Outlook - <t:{int(forecast[0].timestamp())}:f>",
            description=forecast[2],
        ),
        ephemeral=True,
    )


class WeatherView(View):
    """#### A view for displaying weather information in a slash command which is `NOT` persistent."""

    def __init__(self, forecast):
        super().__init__(timeout=30)
        self.forecast = forecast

    @button(label="Current Situation")
    async def send_situation(self, button: Button, interaction: Interaction):
        await send_situation(interaction, self.forecast)

    @button(label="Future Outlook")
    async def send_outlook(self, button: Button, interaction: Interaction):
        await send_outlook(interaction, self.forecast)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        msg: nextcord.Message = self.msg
        await msg.edit(view=self)


class PersistentWeatherView(View):
    """#### A `persistent` view for displaying weather information daily."""

    def __init__(self, forecast):
        super().__init__(timeout=None)
        self.forecast = forecast

    @button(
        label="Current Situation",
        custom_id=f"weather_current_situation_{datetime.datetime.now().strftime('%m-%d')}",
    )
    async def send_situation(self, button: Button, interaction: Interaction):
        await send_situation(interaction, self.forecast)

    @button(
        label="Future Outlook",
        custom_id=f"weather_future_outlook{datetime.datetime.now().strftime('%m-%d')}",
    )
    async def send_outlook(self, button: Button, interaction: Interaction):
        await send_outlook(interaction, self.forecast)


class Video:

    """A helper class that is designed to represent a Youtube video and be displayed in VideoView."""

    def __init__(
        self,
        title,
        description,
        channel_title,
        link,
        published_time,
        thumbnail_url,
        duration,
        views,
        likes,
    ):
        self.title = title
        self.description = description
        self.channel_title = channel_title
        self.link = link
        self.published_time = published_time
        self.thumbnail_url = thumbnail_url
        self.duration = duration
        self.views = int(views)
        self.likes = int(likes)

    @classmethod
    def from_api_response(cls, video_response):
        """Generates a `Video` from the youtube api response. Should include `snippet`, `contentDetails`, `statistics` for the response `part`."""
        title = video_response["snippet"]["title"]
        description = video_response["snippet"]["description"]

        channel_title = video_response["snippet"]["channelTitle"]

        link = f"https://www.youtube.com/watch?v={video_response['id']}"
        published_time = int(
            datetime.datetime.strptime(video_response["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=datetime.timezone.utc)
            .astimezone(tz=None)
            .timestamp()
        )
        thumbnail_url = video_response["snippet"]["thumbnails"]["high"]["url"]

        duration_str = video_response["contentDetails"]["duration"][2:]

        separators = (
            "W",
            "D",
            "H",
            "M",
            "S",
        )
        duration_vals = {}
        for sep in separators:
            partitioned = duration_str.partition(sep)
            if partitioned[1] == sep:
                # Matched this unit
                duration_str = partitioned[2]

                dur_str = partitioned[0]

                if dur_str:
                    dur_val = float(dur_str) if "." in dur_str else int(dur_str)
                    duration_vals.update({sep.lower(): dur_val})
            else:
                # No match for this unit: it's absent
                duration_vals.update({sep.lower(): 0})

        duration = " ".join([f"{value}{unit}" for unit, value in duration_vals.items() if not value == 0])

        views = video_response["statistics"].get("viewCount", 0)
        likes = video_response["statistics"].get("likeCount", 0)
        return cls(
            title,
            description,
            channel_title,
            link,
            published_time,
            thumbnail_url,
            duration,
            views,
            likes,
        )


class VideoView(BaseView):
    def __init__(self, slash_interaction: Interaction, videos: list[Video]):
        super().__init__(slash_interaction, timeout=60)
        self.videos = videos
        self.page = 0

        video_select = [i for i in self.children if i.custom_id == "video_select"][0]
        video_select.options = [
            SelectOption(label=video.title[:100], description=video.channel_title, value=index)
            for index, video in enumerate(self.videos)
        ]

    def get_embed(self):
        embed = Embed()
        video = self.videos[self.page]

        embed.set_author(name=video.channel_title)
        embed.colour = 0xDBFCFF

        embed.set_footer(text=f"Page {self.page + 1}/{len(self.videos)}")  # + 1 because self.page uses zero-indexing

        embed.set_thumbnail(url=video.thumbnail_url)

        embed.title = video.title
        embed.url = video.link

        if len(video.description) > 200:
            embed.add_field(
                name="Description",
                value=f"\n>>> {video.description[:200]}...",
                inline=False,
            )
        else:
            embed.add_field(name="Description", value=f"\n>>> {video.description}", inline=False)

        embed.add_field(
            name="Publish time",
            value=f"<t:{video.published_time}:F> • <t:{video.published_time}:R>",
            inline=False,
        )

        embed.add_field(name="Duration", value=video.duration)
        embed.add_field(name="Views", value=numerize.numerize(video.views))
        embed.add_field(name="Likes", value=numerize.numerize(video.likes))

        return embed

    def disable_buttons(self):
        back_btn = [i for i in self.children if i.custom_id == "back"][0]
        first_btn = [i for i in self.children if i.custom_id == "first"][0]
        if self.page == 0:
            back_btn.disabled = True
            first_btn.disabled = True
        else:
            back_btn.disabled = False
            first_btn.disabled = False
        next_btn = [i for i in self.children if i.custom_id == "next"][0]
        last_btn = [i for i in self.children if i.custom_id == "last"][0]
        if self.page == len(self.videos) - 1:
            next_btn.disabled = True
            last_btn.disabled = True
        else:
            next_btn.disabled = False
            last_btn.disabled = False

    @select(placeholder="Choose a video...", custom_id="video_select")
    async def choose_video(self, select: Select, interaction: Interaction):
        self.page = int(select.values[0])  # the value is set to the index of the video

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="⏮️", style=ButtonStyle.blurple, custom_id="first", disabled=True)
    async def first(self, button: Button, interaction: Interaction):
        self.page = 0

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="◀️", style=ButtonStyle.blurple, disabled=True, custom_id="back")
    async def back(self, button: Button, interaction: Interaction):
        self.page -= 1

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)
        
    @button(emoji="📃", style=ButtonStyle.grey, custom_id="description")
    async def show_description(self, button: Button, interaction: Interaction):
        embed = Embed()
        video = self.videos[self.page]

        embed.set_author(name=video.title)
        embed.set_thumbnail(url=video.thumbnail_url)
        embed.description = video.description[:4096]  # upper limit for description length is 4096.
        await interaction.send(embed=embed, ephemeral=True)

    @button(emoji="▶️", style=ButtonStyle.blurple, custom_id="next")
    async def next(self, button: Button, interaction: Interaction):
        self.page += 1

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="⏭️", style=ButtonStyle.blurple, custom_id="last")
    async def last(self, button: Button, interaction: Interaction):
        self.page = len(self.videos) - 1

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

class MtrLine(enum.Enum):
    Airport_Express = "AEL"
    Tung_Chung_Line = "TCL"
    Tuen_Ma_Line = "TML"
    Tseung_Kwan_O_Line = "TKL"
    East_Rail_Line = "EAL"
    South_Island_Line = "SIL"
    Tseung_Wan_Line = "TWL"


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


class Train:

    """A helper class that is designed to represent a MTR Train and be represented in `NextTrainView`."""

    def __init__(
        self,
        line: MtrLine,
        arriving_station,
        arrival_time: datetime.datetime,
        sequence: int,
        destination,
        platform: int,
        via_racecourse: Optional[bool] = None
    ):
        self.line = line
        self.arriving_station = arriving_station
        self.arrival_time = arrival_time
        self.sequence = sequence
        self.destination = destination
        self.platform = platform
        self.via_racecourse = via_racecourse
        
    @classmethod
    def from_api_response(cls, next_train_response):
        """
        Class method to generate a dict of "UP" and "DOWN" `Train`s from the Next Train api response.
        ### Data structure of returned value:
        
        ```
        trains = {
            "UP": list[UP trains],
            "DOWN": list[DOWN trains]
        }
        ```
        
        Can be used for the `trains` parameter in `NextTrainView`
        """
        data = next_train_response["data"]
        key = list(data.keys())[0]  # eg: "TKL-TIK"
        line = MtrLine(key[:3])  # eg: "TKL"
        arriving_station = key[4:]  # eg: "TIK"
        
        values = list(data.values())[0]
        trains = {
            "UP": values.get("UP", []),
            "DOWN": values.get("DOWN", [])
        }  # use empty list for default in case station is at either end of line
        
        hk_tz = pytz.timezone("Asia/Hong_Kong")
        for train_type, trains_res in trains.items():
            for index, train in enumerate(trains_res):
                destination_code = train["dest"]
                # destination_name = [name for name, code in LINE_STATION_CODES[line].items() if code == destination_code][0]
                sequence = train["seq"]
                platform = train["plat"]
                via_racecourse = bool(train.get("route"))
                arrival_time = datetime.datetime.strptime(train["time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=hk_tz)
                
                trains[train_type][index] = cls(
                    line, 
                    arriving_station,
                    arrival_time,
                    sequence,
                    destination_code,
                    platform,
                    via_racecourse
                )
        
        return trains
        
        
class NextTrainView(BaseView):
    """
    Shows a list of trains returned from Next Train API.
    # Features
    `Paginating buttons`: automated (which disable themselves) according to the current page
    `Type Switching`: Can be switched between "UP" and "DOWN" trains
    # Parameters
    `slash_interaction`: `nextcord.Interaction` from the slash command.
    Used for identifying the user and timing out the view.
    `trains`: a `dict` containing "UP" and "DOWN" trains
    """
    def __init__(self, slash_interaction: Interaction, trains: dict[str, list[Train]]):
        super().__init__(slash_interaction, timeout=60)
        self.trains = trains
        
        type_button = [i for i in self.children if i.custom_id == "type"][0]
        if not self.trains["UP"]:  # only down directions are available, disable the type button
            self.type = "DOWN"
            type_button.disabled = True
        elif not self.trains["DOWN"]:  # only up directions are available, disable the type button
            self.type = "UP"
            type_button.disabled = True
        else:  # both directions are available.
            self.type = "UP"
            type_button.disabled = False
        self.page = 0
    
    def get_embed(self):
        embed = Embed()
        train = self.trains[self.type][self.page]

        arriving_station = [name for name, code in LINE_STATION_CODES[train.line.value].items() if code == train.arriving_station][0]
        embed.title = f"Next trains arriving at {arriving_station}"

        embed.set_footer(text=f"{self.type} trains • Page {self.page + 1}/{len(self.trains)}")  # + 1 because self.page uses zero-indexing

        destination_name = [name for name, code in LINE_STATION_CODES[train.line.value].items() if code == train.destination][0]
        embed.add_field(
            name="Destination",
            value=destination_name,
        )
        embed.add_field(name="Platform", value=train.platform)
        if train.via_racecourse:
            embed.description = "> via Racecourse"
            
        arrival_timestamp = int(train.arrival_time.timestamp())
        hk_tz = pytz.timezone("Asia/Hong_Kong")
        embed.add_field(
            name="Arrival time" if train.arrival_time > datetime.datetime.now(tz=hk_tz) else "Departure time",
            value=f"<t:{arrival_timestamp}:F> • <t:{arrival_timestamp}:R>",
            inline=False
        )

        return embed

    def update_view(self):
        back_btn = [i for i in self.children if i.custom_id == "back"][0]
        if self.page == 0:
            back_btn.disabled = True
        else:
            back_btn.disabled = False
        next_btn = [i for i in self.children if i.custom_id == "next"][0]
        if self.page == len(self.trains) - 1:
            next_btn.disabled = True
        else:
            next_btn.disabled = False
            
        type_button = [i for i in self.children if i.custom_id == "type"][0]
        if self.type == "UP":
            type_button.emoji = "🔽"
        elif self.type == "DOWN":
            type_button.emoji = "🔼"

    @button(emoji="◀️", style=ButtonStyle.blurple, disabled=True, custom_id="back")
    async def back(self, button: Button, interaction: Interaction):
        self.page -= 1

        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="▶️", style=ButtonStyle.blurple, custom_id="next")
    async def next(self, button: Button, interaction: Interaction):
        self.page += 1

        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)
        
    @button(emoji="🔼", style=ButtonStyle.grey, custom_id="type")
    async def change_type(self, button: Button, interaction: Interaction):
        self.page = 0
        if self.type == "UP":
            self.type = "DOWN"
        elif self.type == "DOWN":
            self.type = "UP"
        
        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)
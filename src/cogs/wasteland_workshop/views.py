# default modules
import datetime
import enum
import os
import re
from typing import Literal, Optional

import googleapiclient.discovery
import nextcord
import pytz
from nextcord import ButtonStyle, Embed, SelectOption
from nextcord.ui import Button, Select, View, button, select
from numerize import numerize

from utils.helpers import BossInteraction
from utils.template_views import BaseView


class WeatherView(View):
    """A view for displaying weather information in a slash command."""

    def __init__(self, forecast):
        super().__init__(timeout=30)
        self.forecast = forecast
        self.msg: nextcord.PartialInteractionMessage | nextcord.WebhookMessage = None

    @button(label="Current Situation")
    async def send_situation(self, btn: Button, interaction: BossInteraction):
        await interaction.send(
            embed=Embed(
                title=f"Current Situation - <t:{int(self.forecast[0].timestamp())}:f>",
                description=self.forecast[1],
            ),
            ephemeral=True,
        )

    @button(label="Future Outlook")
    async def send_outlook(self, btn: Button, interaction: BossInteraction):
        await interaction.send(
            embed=Embed(
                title=f"Future Outlook - <t:{int(self.forecast[0].timestamp())}:f>",
                description=self.forecast[2],
            ),
            ephemeral=True,
        )

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        await self.msg.edit(view=self)


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
        """Initializes a Video object.

        Args:
            title: The title of the video.
            description: The description of the video.
            channel_title: The title of the channel that uploaded the video.
            link: The URL of the video.
            published_time: The time at which the video was published.
            thumbnail_url: The URL of the thumbnail image for the video.
            duration: The duration of the video in seconds.
            views: The number of views that the video has received.
            likes: The number of likes that the video has received.
        """
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
        """Generates a `Video` from the YouTube API response.

        Args:
            video_response: The YouTube API response for the video.

        Returns:
            A `Video` object.
        """
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

        duration = " ".join([f"{value}{unit}" for unit, value in duration_vals.items()])

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
    """
    A custom view to display a list of YouTube videos and their details.

    Attributes:
        slash_interaction (BossInteraction): The interaction object for the slash command.
        videos (list[Video]): A list of Video objects.
        query (str): The search query used to find the videos.
        prev_page_token (str): The token for the previous page of videos.
        next_page_token (str): The token for the next page of videos.
        list_index (int): The index of the current list of videos being displayed.
    """

    def __init__(
        self,
        slash_interaction: BossInteraction,
        videos: list[Video],
        query: str,
        prev_page_token: str = None,
        next_page_token: str = None,
        list_index: int = 1,
    ):
        super().__init__(slash_interaction, timeout=600)  # 10 minutes
        self.query = query
        self.prev_page_token = prev_page_token
        self.next_page_token = next_page_token
        self.list_index = list_index
        self.videos = videos
        self.video_page = 0

        video_select = [i for i in self.children if i.custom_id == "video_select"][0]
        video_select.options = [
            SelectOption(label=video.title[:100], description=video.channel_title, value=index)
            for index, video in enumerate(self.videos)
        ]

    def get_embed(self):
        embed = Embed()
        video = self.videos[self.video_page]

        embed.set_author(name=video.channel_title)

        embed.set_footer(
            text=f"Page {self.list_index} • Video {self.video_page + 1}/{len(self.videos)}"
        )  # + 1 because self.page uses zero-indexing

        embed.set_thumbnail(url=video.thumbnail_url)

        embed.title = video.title
        embed.url = video.link

        if video.description:
            video.description = re.sub(r"\n+", "\n\n", video.description)
            description = video.description.partition("\n")[0]
            if len(description) > 200:
                embed.add_field(
                    name="Description",
                    value=f"\n>>> {description[:200]}\n - _To view more, press the 📃 button._",
                    inline=False,
                )
            else:
                embed.add_field(name="Description", value=f"\n>>> {description}", inline=False)

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
        if self.video_page == 0:
            back_btn.disabled = True
            first_btn.disabled = True
        else:
            back_btn.disabled = False
            first_btn.disabled = False
        next_btn = [i for i in self.children if i.custom_id == "next"][0]
        last_btn = [i for i in self.children if i.custom_id == "last"][0]
        if self.video_page == len(self.videos) - 1:
            next_btn.disabled = True
            last_btn.disabled = True
        else:
            next_btn.disabled = False
            last_btn.disabled = False
        less_btn = [i for i in self.children if i.custom_id == "less"][0]
        less_btn.disabled = not bool(self.prev_page_token)
        more_btn = [i for i in self.children if i.custom_id == "more"][0]
        more_btn.disabled = not bool(self.next_page_token)

    @select(placeholder="Choose a video...", custom_id="video_select")
    async def choose_video(self, sel: Select, interaction: BossInteraction):
        self.video_page = int(sel.values[0])  # the value is set to the index of the video

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="⏮️", style=ButtonStyle.blurple, custom_id="first", disabled=True)
    async def first(self, btn: Button, interaction: BossInteraction):
        self.video_page = 0

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="◀️", style=ButtonStyle.blurple, disabled=True, custom_id="back")
    async def back(self, btn: Button, interaction: BossInteraction):
        self.video_page -= 1

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="▶️", style=ButtonStyle.blurple, custom_id="next")
    async def next(self, btn: Button, interaction: BossInteraction):
        self.video_page += 1

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="⏭️", style=ButtonStyle.blurple, custom_id="last")
    async def last(self, btn: Button, interaction: BossInteraction):
        self.video_page = len(self.videos) - 1

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="📽️", style=ButtonStyle.grey, custom_id="video", row=2)
    async def show_video(self, btn: Button, interaction: BossInteraction):
        await interaction.send(self.videos[self.video_page].link, ephemeral=True)

    @button(emoji="📃", style=ButtonStyle.grey, custom_id="description", row=2)
    async def show_description(self, btn: Button, interaction: BossInteraction):
        embed = Embed()
        video = self.videos[self.video_page]

        embed.set_author(name=video.title)
        embed.set_thumbnail(url=video.thumbnail_url)
        embed.description = video.description[:4096]  # upper limit for description length is 4096.
        await interaction.send(embed=embed, ephemeral=True)

    async def show_video_list(self, interaction: BossInteraction, action: Literal["prev", "next"]):
        api_service_name = "youtube"
        api_version = "v3"
        dev_key = os.getenv("GOOGLE_API_KEY")

        youtube = googleapiclient.discovery.build(api_service_name, api_version, developerKey=dev_key)
        search_response = (
            youtube.search()  # pylint: disable=no-member
            .list(
                part="snippet",
                type="video",
                q=self.query,
                pageToken=self.next_page_token if action == "next" else self.prev_page_token,
                maxResults=25,
            )
            .execute()
        )
        video_ids = [i["id"]["videoId"] for i in search_response["items"]]

        videos_response = (
            youtube.videos()  # pylint: disable=no-member
            .list(part="snippet,contentDetails,statistics", id=",".join(video_ids))
            .execute()
        )

        videos = [Video.from_api_response(video) for video in videos_response["items"]]
        view = VideoView(
            interaction,
            videos,
            self.query,
            prev_page_token=search_response.get("prevPageToken"),
            next_page_token=search_response.get("nextPageToken"),
            list_index=self.list_index + (+1 if action == "next" else -1),
        )

        embed = view.get_embed()
        view.disable_buttons()
        await interaction.response.edit_message(embed=embed, view=view)

    @button(label="Prev", style=ButtonStyle.grey, custom_id="less", row=2)
    async def show_less_videos(self, btn: Button, interaction: BossInteraction):
        await self.show_video_list(interaction, "prev")

    @button(label="Next", style=ButtonStyle.grey, custom_id="more", row=2)
    async def show_more_videos(self, btn: Button, interaction: BossInteraction):
        await self.show_video_list(interaction, "next")


class ChannelVideoView(VideoView):
    def __init__(
        self,
        slash_interaction: BossInteraction,
        videos: list[Video],
        playlist_id: str,
        prev_page_token: str = None,
        next_page_token: str = None,
        list_index: int = 1,
    ):
        super().__init__(slash_interaction, videos, "", prev_page_token, next_page_token, list_index)
        self.playlist_id = playlist_id

    async def show_video_list(self, interaction: BossInteraction, action: Literal["prev", "next"]):
        api_service_name = "youtube"
        api_version = "v3"
        dev_key = os.getenv("GOOGLE_API_KEY")

        youtube = googleapiclient.discovery.build(api_service_name, api_version, developerKey=dev_key)
        playlist_response = (
            youtube.playlistItems()  # pylint: disable=no-member
            .list(part="contentDetails", playlistId=self.playlist_id, maxResults=25)
            .execute()
        )

        videos_response = (
            youtube.videos()  # pylint: disable=no-member
            .list(
                part="snippet,contentDetails,statistics",
                id=",".join([video["contentDetails"]["videoId"] for video in playlist_response["items"]]),
            )
            .execute()
        )
        videos = [Video.from_api_response(video) for video in videos_response["items"]]
        view = ChannelVideoView(
            interaction,
            videos,
            self.playlist_id,
            prev_page_token=playlist_response.get("prevPageToken"),
            next_page_token=playlist_response.get("nextPageToken"),
        )
        embed = view.get_embed()
        view.disable_buttons()
        await interaction.response.edit_message(embed=embed, view=view)


class MtrLine(enum.Enum):
    AIRPORT_EXPRESS = "AEL"
    TUNG_CHUNG_LINE = "TCL"
    TUEN_MA_LINE = "TML"
    TSEUNG_KWAN_O_LINE = "TKL"
    EAST_RAIL_LINE = "EAL"
    SOUTH_ISLAND_LINE = "SIL"
    TSUEN_WAN_LINE = "TWL"


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
        via_racecourse: Optional[bool] = None,
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
            "DOWN": values.get("DOWN", []),
        }  # use empty list for default in case station is at either end of line

        hk_tz = pytz.timezone("Asia/Hong_Kong")
        for trains_res in trains.values():
            for index, train in enumerate(trains_res):
                destination_code = train["dest"]
                sequence = train["seq"]
                platform = train["plat"]
                via_racecourse = bool(train.get("route"))
                arrival_time = datetime.datetime.strptime(train["time"], "%Y-%m-%d %H:%M:%S")
                arrival_time = hk_tz.localize(arrival_time)

                trains_res[index] = cls(
                    line,
                    arriving_station,
                    arrival_time,
                    sequence,
                    destination_code,
                    platform,
                    via_racecourse,
                )

        return trains


class NextTrainView(BaseView):
    """
    Shows a list of trains returned from Next Train API.
    # Features
    `Paginating buttons`: automated (which disable themselves) according to the current page
    `Type Switching`: Can be switched between "UP" and "DOWN" trains
    # Parameters
    `slash_interaction`: `nextcord.BossInteraction` from the slash command.
    Used for identifying the user and timing out the view.
    `trains`: a `dict` containing "UP" and "DOWN" trains
    """

    def __init__(self, slash_interaction: BossInteraction, trains: dict[str, list[Train]]):
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

        colours = {
            MtrLine.AIRPORT_EXPRESS: 0x02838A,
            MtrLine.EAST_RAIL_LINE: 0x5EB9E6,
            MtrLine.SOUTH_ISLAND_LINE: 0xCBCD00,
            MtrLine.TSEUNG_KWAN_O_LINE: 0x863E90,
            MtrLine.TUEN_MA_LINE: 0x952E07,
            MtrLine.TUNG_CHUNG_LINE: 0xF39131,
        }
        embed.colour = colours.get(train.line, None)  # black for default

        arriving_station = [
            name for name, code in LINE_STATION_CODES[train.line.value].items() if code == train.arriving_station
        ][0]
        embed.title = f"Trains arriving at {arriving_station}"

        embed.set_footer(
            text=f"{self.type} trains • Page {self.page + 1}/{len(self.trains)}"
        )  # + 1 because self.page uses zero-indexing

        destination_name = [
            name for name, code in LINE_STATION_CODES[train.line.value].items() if code == train.destination
        ][0]
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
            value=f"<t:{arrival_timestamp}:t> • <t:{arrival_timestamp}:R>",
            inline=False,
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
    async def back(self, btn: Button, interaction: BossInteraction):
        self.page -= 1

        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="▶️", style=ButtonStyle.blurple, custom_id="next")
    async def next(self, btn: Button, interaction: BossInteraction):
        self.page += 1

        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="🔼", style=ButtonStyle.grey, custom_id="type")
    async def change_type(self, btn: Button, interaction: BossInteraction):
        self.page = 0
        if self.type == "UP":
            self.type = "DOWN"
        elif self.type == "DOWN":
            self.type = "UP"

        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

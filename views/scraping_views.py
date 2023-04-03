# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle, SelectOption
from nextcord.ui import View, Button, button, Select, select

# numerize
from numerize import numerize

# my modules
from views.template_views import BaseView

# default modules
import datetime


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

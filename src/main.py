# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Embed, Interaction

# nextcord cooldowns
from cooldowns import CallableOnCooldown

# nested asyncio --> perform multiple asyncs at once
import nest_asyncio

# creates a flask app, which
#   lets uptimerobot ping the app to make it stay up, and
#   uploads the boss' website (https://boss-bot.onrender.com/) to the internet
from keep_alive import keep_alive

# my modules
from utils import constants, helpers
from utils.constants import EmbedColour
from utils.helpers import TextEmbed, CommandCheckException
from utils.postgres_db import Database

# default modules
import os
import random
import sys
import logging
from typing import Union, Optional
from datetime import datetime, timezone


nest_asyncio.apply()

werkzeug_logger = logging.getLogger("werkzeug")
werkzeug_logger.setLevel(logging.ERROR)

root = logging.getLogger()
root.setLevel(logging.INFO)

nextcord_logger = logging.getLogger("nextcord")
nextcord_logger.setLevel(logging.ERROR)

handler = logging.StreamHandler(sys.stderr)
handler.setLevel(logging.INFO)
handler.setFormatter(
    logging.Formatter(
        "\033[1;30m{asctime} ({name}, {levelname}) - \033[0m{message}", datefmt="%d %B %Y %H:%M", style="{"
    )
)
nextcord_logger.addHandler(handler)
root.addHandler(handler)


class BossBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(
            activity=nextcord.Game(name="/help"),
            owner_ids={
                806334528230129695,
                706126877668147272,
                708141816020729867,
                798720829583523861,
                823522605352484916,
            },
            *args,
            **kwargs,
        )
        self.persistent_views_added = False

        # dicts showing all macro views at the time
        # it maps the user id to his/her `RunMacroView` / `RecordMacroView`
        self.running_macro_views = {}
        self.recording_macro_views = {}
        self.villagers = None
        self.db = Database()
        self.pool = self.db.pool

        # Get the modules of all cogs whose directory structure is ./cogs/<module_name>
        for folder in os.listdir("cogs"):
            if folder != "__pycache__":
                self.load_extension(f"cogs.{folder}.commands")
        self.load_extension("utils.application_hooks")

    async def on_ready(self):
        if not self.persistent_views_added:
            # Register the persistent view for listening here.
            # This does not send the view to any message.
            self.add_view(PersistentWeatherView((datetime.now(), "", "")))
            self.persistent_views_added = True

        # Connect to the bot database
        if not self.db.connected:
            self.pool = await self.db.connect()

        logging.info(
            f"\033[1;36m{self.user.name} (ID: {self.user.id})\033[0m has connected to discord \033[0;34min {len(self.guilds)} servers!\033[0m"
        )

    async def on_disconnect(self):
        await self.db.disconnect()
        logging.info("Bot disconnected.")

    async def on_close(self):
        await self.db.disconnect()
        logging.info("Bot closed, event loop closing...")

    async def on_application_command_error(self, interaction: Interaction, error: Exception):
        error = getattr(error, "original", error)

        # don't meet application check requirement
        if isinstance(error, nextcord.ApplicationCheckFailure):
            await interaction.send(
                embed=TextEmbed("You do not have the necessary permissions to use this command.", EmbedColour.WARNING),
                ephemeral=True,
            )
            return

        # should be handled in cmd_check, and the command execution is halted
        if isinstance(error, CommandCheckException):
            return

        # is in cooldown
        if isinstance(error, CallableOnCooldown):
            interaction.attached["in_cooldown"] = True
            await interaction.send(embed=cd_embed(interaction, error))
            return

        embed, view = helpers.get_error_message()
        await interaction.send(embed=embed, view=view)
        raise error

    async def on_error(self, event: str, *args, **kwargs) -> None:
        exc = sys.exc_info()
        logging.error("An error occured", exc_info=exc)

    @staticmethod
    async def get_or_fetch_member(guild: nextcord.Guild, member_id: int) -> Union[nextcord.Member, None]:
        """Looks up a member in cache or fetches if not found. If the member is not in the guid, returns `None`."""
        member = guild.get_member(member_id)
        if member is not None:
            return member

        member = await guild.fetch_member(member_id)
        return member

    async def get_or_fetch_channel(
        self, channel_id: int
    ) -> Optional[
        Union[nextcord.abc.GuildChannel, nextcord.Thread, nextcord.abc.PrivateChannel, nextcord.PartialMessageable]
    ]:
        """Looks up a channel in cache or fetches if not found."""
        channel = self.get_channel(channel_id)
        if channel:
            return channel

        channel = await self.fetch_channel(channel_id)
        return channel

    async def get_or_fetch_guild(self, guild_id: int) -> nextcord.Guild:
        """Looks up a guild in cache or fetches if not found."""
        guild = self.get_guild(guild_id)
        if guild:
            return guild

        guild = await self.fetch_guild(guild_id)
        return guild

    async def get_or_fetch_user(self, user_id: int) -> Union[nextcord.User, None]:
        """Looks up a user in cache or fetches if not found."""
        user = self.get_user(user_id)
        if user:
            return user

        user = await self.fetch_user(user_id)
        return user


bot = BossBot()


def cd_embed(interaction: Interaction, error: CallableOnCooldown):
    cd_ui = Embed()
    titles = [
        "Woah, chill.",
        "Spamming ain't good bro",
        "Stop.",
        "Calm down and relax. You need to.",
        "It's better if you pause.",
        "Touch grass, my man.",
    ]
    cd_ui.title = random.choice(titles)
    command = interaction.application_command
    resets_at = error.resets_at.replace(tzinfo=timezone.utc).astimezone()
    cd_ui.description = (
        f"You can use {command.get_mention(interaction.guild)} again <t:{int(resets_at.timestamp())}:R>!"
    )
    cd_ui.colour = random.choice(constants.EMBED_COLOURS)
    return cd_ui


keep_alive()
bot.run(constants.TOKEN)

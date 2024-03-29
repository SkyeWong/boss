# default modules
import asyncio
import logging
import os
import random
import sys
from datetime import timezone
from typing import Optional, Union

import nest_asyncio

# third-party
import nextcord
from cooldowns import CallableOnCooldown
from nextcord import Embed, Interaction
from nextcord.ext import commands

# creates a flask app, which
#   lets uptimerobot ping the app to make it stay up, and
#   uploads the boss' website (https://boss-bot.onrender.com/) to the internet
from keep_alive import keep_alive
from modules.macro.run_macro import RunMacroView

# my modules
from utils import constants, helpers
from utils.constants import EmbedColour
from utils.helpers import BossInteraction
from utils.postgres_db import Database

nest_asyncio.apply()


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

        # dicts showing all macro views at the time
        # it maps the user id to his/her `RunMacroView` / `RecordMacroView`
        self.running_macro_views = {}
        self.recording_macro_views = {}
        self.villagers = None

        self.persistent_views_added = False

        self.db = Database()
        self.pool = self.db.pool
        self.has_connected_db = asyncio.Event()

    async def on_ready(self):
        if not self.persistent_views_added:
            # Register the persistent view for listening here.
            # This does not send the view to any message.
            self.add_view(RunMacroView())
            self.persistent_views_added = True

        # Connect to the bot database
        if not self.db.connected:
            self.pool = await self.db.connect()
        self.has_connected_db.set()

        logging.info(
            "\033[1;36m%s (ID: %s)\033[0m has connected to discord \033[0;34min %s servers!\033[0m",
            self.user.name,
            self.user.id,
            len(self.guilds),
        )

    async def on_disconnect(self):
        await self.db.disconnect()
        logging.info("Bot disconnected.")

    async def on_close(self):
        await self.db.disconnect()
        logging.info("Bot closed, event loop closing...")

    def get_interaction(self, data, *, cls=nextcord.Interaction):  # pylint: disable=useless-parent-delegation
        # tell the bot to use `BossInteraction`s instead of normal `nextcord.Interaction`s
        return super().get_interaction(data, cls=BossInteraction)

    async def on_application_command_error(self, interaction: BossInteraction, error: Exception):
        error = getattr(error, "original", error)

        # don't meet application check requirement
        if isinstance(error, nextcord.ApplicationCheckFailure):
            # If an error is caught in `utils.application_hooks.cmd_check`, the interaction is "handled"
            if not interaction.attached.get("handled"):
                await interaction.send_text(
                    "You do not have the necessary permissions to use this command.",
                    EmbedColour.WARNING,
                    ephemeral=True,
                )
            return

        # is in cooldown
        if isinstance(error, CallableOnCooldown):
            interaction.attached["in_cooldown"] = True
            await interaction.send(embed=get_cooldown_embed(interaction, error))
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
        Union[
            nextcord.abc.GuildChannel,
            nextcord.Thread,
            nextcord.abc.PrivateChannel,
            nextcord.PartialMessageable,
        ]
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


def get_cooldown_embed(interaction: Interaction, error: CallableOnCooldown) -> Embed:
    """Returns an embed showing the command in cooldown and the time that the cooldown resets."""
    embed = Embed()
    titles = [
        "Woah, chill.",
        "Spamming ain't good bro",
        "Stop.",
        "Calm down and relax. You need to.",
        "It's better if you pause.",
        "Touch grass, my man.",
    ]
    embed.title = random.choice(titles)
    command = interaction.application_command
    resets_at = error.resets_at.replace(tzinfo=timezone.utc).astimezone()
    embed.description = (
        f"You can use {command.get_mention(interaction.guild)} again <t:{int(resets_at.timestamp())}:R>!"
    )
    embed.colour = EmbedColour.WARNING
    return embed


async def main():
    # Setup logging handlers
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
            "\033[1;30m%(asctime)s (%(name)s, %(levelname)s) - \033[0m%(message)s",
            datefmt="%d/%m/%y %H:%M",
        )
    )
    nextcord_logger.addHandler(handler)
    root.addHandler(handler)

    # load all the cogs and extensions, then start and login the bot to discord
    bot = BossBot()
    # Get the modules of all cogs whose directory structure is ./cogs/<module_name>
    for folder in os.listdir("cogs"):
        if folder != "__pycache__":
            bot.load_extension(f"cogs.{folder}.commands")
    bot.load_extension("utils.application_hooks")
    await bot.start(constants.TOKEN)


keep_alive()
asyncio.run(main())

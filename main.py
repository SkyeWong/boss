# default modules
import os, random, sys, traceback
from datetime import datetime, timezone

# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Embed, Interaction, ApplicationCheckFailure

# nextcord cooldowns
from cooldowns import CallableOnCooldown

# nested asyncio --> perform multiple asyncs at once
import nest_asyncio

import pytz

# my modules
from utils import functions, constants
from utils.player import Player
from utils.postgres_db import Database
from views.scraping_views import PersistentWeatherView
from utils.functions import CommandCheckException

# creates a flask app, which lets uptimerobot ping the app to make it stay up
from keep_alive import keep_alive

nest_asyncio.apply()


class BossBot(commands.Bot):
    LIVE = False

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

        self.db = Database()
        self.pool = self.db.pool

        for filename in os.listdir("cogs"):
            if filename.endswith("py") and filename != "__init__.py":
                self.load_extension(f"cogs.{filename[:-3]}")

    async def on_ready(self):
        if not self.persistent_views_added:
            # Register the persistent view for listening here.
            # Note that this does not send the view to any message.
            # To do that, you need to send a message with the View as shown below.
            # If you have the message_id you can also pass it as a keyword argument, but for this example
            # we don't have one.
            self.add_view(PersistentWeatherView((datetime.now(), "", "")))
            self.persistent_views_added = True

        # Connect to the bot database
        if not await self.db.connected:
            self.pool = await self.db.connect()
        print(
            f"\033[1;36m{self.user.name} (ID: {self.user.id})\033[0m has connected to discord \033[0;34min {len(self.guilds)} servers!\033[0m"
        )

    async def on_disconnect(self):
        await self.db.disconnect()
        print("Disconnected.")

    async def on_close(self):
        await self.db.disconnect()
        print("Closed")

    async def on_application_command_error(self, interaction: Interaction, error: Exception):
        error = getattr(error, "original", error)

        # don't meet application check requirement
        if isinstance(error, nextcord.ApplicationCheckFailure):
            await interaction.send(
                embed=Embed(description="You can't use this command bruh"),
                ephemeral=True,
            )
            return

        if isinstance(error, CommandCheckException):
            return

        # is in cooldown
        if isinstance(error, CallableOnCooldown):
            await interaction.send(embed=cd_embed(interaction, error))
            return

        embed, view = functions.get_error_message()
        embed.set_image("https://i.imgur.com/PX67hRV.png")
        if not self.LIVE:
            embed.add_field(name="Error", value=f"```py\n{str(error)[:1000]}\n```")
        await interaction.send(embed=embed, view=view)

        error_log = self.get_channel(1071712392020500530)
        cmd_name = interaction.application_command.qualified_name
        embed.title = f"{embed.title[:17]} while running `/{cmd_name}`"
        embed.description = ""
        await error_log.send(embed=embed)
        raise error

    async def on_error(self, event_method: str, *args, **kwargs) -> None:
        embed = Embed(title="An error occured while running!")
        embed.description = "**Error**"
        exc = sys.exc_info()

        exc_formatted = traceback.format_exc()
        print(exc_formatted)

        embed.description += f"```py\n{exc_formatted[:4060]}\n```"
        embed.set_image("https://i.imgur.com/LjH76fq.png")
        error_log = self.get_channel(1071712392020500530)
        await error_log.send(embed=embed)


bot = BossBot()


def cd_embed(interaction: Interaction, error: CallableOnCooldown):
    cd_ui = Embed()
    titles = [
        "Woah, chill.",
        "Spamming ain't good bro",
        "Stop.",
        "Calm down and relax. You need it.",
        "It's better if you pause.",
        "Touch grass, my man.",
    ]
    cd_ui.title = random.choice(titles)
    command = interaction.application_command
    resets_at = error.resets_at.replace(tzinfo=timezone.utc).astimezone()
    cd_ui.description = f"You can use </{command.qualified_name}:{list(command.command_ids.values())[0]}> again <t:{int(resets_at.timestamp())}:R>!"
    cd_ui.colour = random.choice(constants.EMBED_COLOURS)
    return cd_ui


@bot.application_command_check
async def cmd_check(interaction: Interaction):
    cmd = interaction.application_command

    # Reconnect to the database if it is not
    if not await bot.db.connected or bot.db.reconnecting:
        msg = await interaction.send(
            embed=Embed(
                description=("We are reconnecting to the database, please be patient and wait for a few seconds.")
            ),
            ephemeral=True,
        )
        await bot.db.connect()

        await msg.edit(
            embed=Embed(
                description="We have successfully connected to the database!\n"
                f"Use </{cmd.qualified_name}:{list(cmd.command_ids.values())[0]}> again."
            )
        )
        raise functions.DatabaseReconnect()

    # Pause execution if command is disabled
    if interaction.guild_id != constants.DEVS_SERVER_ID:  # only check for disabled commands if its not the dev server.
        db = bot.db
        res = await db.fetchrow(
            """
            SELECT until, reason, extra_info
            FROM utility.disabled_commands
            WHERE $1 LIKE command_name
            """,
            cmd.qualified_name,
        )

        if res is not None:
            until = res[0]

            utc = pytz.UTC

            if until is None or until > datetime.now(tz=utc):  # until is None --> permanently disabled
                embed = Embed()
                embed.title = f"</{cmd.qualified_name}:{list(cmd.command_ids.values())[0]}> is disabled!"

                embed.add_field(name="Reason", value=res[1], inline=False)
                embed.add_field(name="Extra info", value=res[2], inline=False)

                await interaction.send(embed=embed, ephemeral=True)
                raise functions.DisabledCommand()

            if until <= datetime.now(tz=utc):
                await db.execute(
                    """
                    DELETE FROM utility.disabled_commands 
                    WHERE command_name = $1
                    """,
                    cmd.qualified_name,
                )

    # Add player to database if he/she is new
    player = Player(bot.db, interaction.user)
    if not await player.is_present():
        await player.create_profile()

        await interaction.send(
            embed=Embed(
                description=(
                    f"Welcome! `greet message`...\n"
                    f"Use </{cmd.qualified_name}:{list(cmd.command_ids.values())[0]}> again to continue"  # TODO: add a /guide command and have players use this instead
                )
            )
        )  # TODO: add a greet message to this
        raise functions.NewPlayer()

    return True


@bot.application_command_before_invoke
async def create_user_if_not_exists(interaction: Interaction):
    if not interaction.response.is_done():
        await interaction.response.defer()


@bot.application_command_after_invoke
async def increase_player_experience(interaction: Interaction):
    old_experience_level = (
        await bot.db.fetchval(
            """
        SELECT experience
        FROM players.players
        WHERE player_id = $1
        """,
            interaction.user.id,
        )
        // 100
    )
    new_experience_level = (
        await bot.db.fetchval(
            """
        UPDATE players.players
        SET experience = experience + $1
        WHERE player_id = $2
        RETURNING experience
        """,
            random.randint(1, 5),
            interaction.user.id,
        )
        // 100
    )
    if new_experience_level > old_experience_level:  # player levelled up
        await interaction.user.send(
            embed=Embed(
                title="Level up!",
                description=f"Poggers! You levelled up from level **{old_experience_level}** to level **{new_experience_level}**!",
                timestamp=datetime.now(),
                colour=random.choice(constants.EMBED_COLOURS),
            )
        )


keep_alive()
bot.run(constants.TOKEN)

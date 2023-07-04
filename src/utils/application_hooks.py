import nextcord
from nextcord import Interaction, Embed
from nextcord.ext import commands

from utils import constants, helpers
from utils.player import Player
from utils.helpers import TextEmbed
from utils.constants import EmbedColour
from modules.macro.record_macro import recording_macro_views
from modules.macro.run_macro import running_macro_views

import pytz
from datetime import datetime
import random


async def cmd_check(interaction: Interaction):
    """Check whether the user can use a command. If not, `CommandCheckException` will be raised, which will be caught in `bot.on_application_command_error`."""
    cmd = interaction.application_command
    bot: commands.Bot = interaction.client

    # Reconnect to the database if it is not
    if bot.db.reconnecting or not bot.db.connected:
        msg = await interaction.send(
            embed=TextEmbed("We are reconnecting to the database, please be patient and wait for a few seconds."),
            ephemeral=True,
        )
        await bot.db.connect()

        await msg.edit(
            embed=TextEmbed(
                "We have successfully connected to the database! " f"Use {cmd.get_mention(interaction.guild)} again.",
                EmbedColour.SUCCESS,
            )
        )
        raise helpers.DatabaseReconnect()

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
                raise helpers.DisabledCommand()

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
            embeds=[
                TextEmbed(
                    "> Welcome to BOSS, the Discord bot for a post-apocalyptic world after World War III. "
                    "\n\n> In this world, everything is tarnished and resources are scarce. "
                    "The currency system is based on a variety of items that have value in this new world, "
                    "including scrap metal, ammunition, and other valuable resources that can be traded or used to purchase goods and services."
                    "\n\n> BOSS is here to help you navigate this harsh world by providing a currency system that allows you to earn, spend, and trade valuable resources. "
                    "It makes it easy to manage your currency and track your progress as you explore the post-apocalyptic wasteland. "
                    "Whether you're scavenging for resources, completing missions, or participating in events, BOSS is here to help you earn currency and build your wealth in this new world. "
                    "So, join us in the post-apocalyptic wasteland and let BOSS be your guide to survival and prosperity."
                ),
                TextEmbed(f"Use {cmd.get_mention(interaction.guild)}again to continue"),
            ]
        )  # TODO: add a greet message to this
        raise helpers.NewPlayer()

    if await player.check_in_inter():
        # The user is running a command
        await interaction.send(
            embed=TextEmbed(
                "You are locked from running any commands until all active commands are completed. Complete all ongoing ones or try again later.",
                EmbedColour.WARNING,
            ),
            ephemeral=True,
        )
        raise helpers.CommandCheckException()

    return True


async def before_invoke(interaction: Interaction):
    if not interaction.response.is_done():
        await interaction.response.defer()


async def after_invoke(interaction: Interaction):
    # Running a macro
    if run_macro_view := running_macro_views.get(interaction.user.id):
        await run_macro_view.send_msg(interaction)

    # Recording a macro
    if record_macro_view := recording_macro_views.get(interaction.user.id):
        await record_macro_view.record(interaction)
        # if the max number of commands has reached,
        # `view.record()` will stop recording and set `view.recording` to False.
        # in that case, we do not sent the message to let users continue.
        if record_macro_view.recording:
            await record_macro_view.send_msg(interaction)

    # Update the user's experience and other attributes
    old_exp, new_exp = await interaction.client.db.fetchrow(
        """
        UPDATE players.players
        SET experience = experience + $2, commands_run = commands_run + 1
        WHERE player_id = $1
        RETURNING 
            (SELECT experience
            FROM players.players
            WHERE player_id = $1) AS old_experience, 
            experience
        """,
        interaction.user.id,
        random.randint(1, 5),
    )
    new_level = new_exp // 100
    old_level = old_exp // 100
    if new_level > old_level:  # player levelled up
        await interaction.user.send(
            embed=Embed(
                title="Level up!",
                description=f"Poggers! You levelled up from level **{old_level}** to level **{new_level}**!",
                timestamp=datetime.now(),
                colour=EmbedColour.INFO,
            )
        )


def setup(bot: commands.Bot):
    bot.add_application_command_check(cmd_check)
    bot.application_command_before_invoke(before_invoke)
    bot.application_command_after_invoke(after_invoke)

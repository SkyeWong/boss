from nextcord import Embed
from nextcord.ext import commands

from utils import helpers
from utils.player import Player
from utils.helpers import BossInteraction
from utils.constants import EmbedColour

import datetime
import random


async def cmd_check(interaction: BossInteraction):
    """
    Check whether the user can use a command.
    If not, `CommandCheckException` will be raised, which will be caught in `bot.on_application_command_error`.
    """
    cmd = interaction.application_command
    bot: commands.Bot = interaction.client
    interaction.attached["handled"] = True

    # Reconnect to the database if it is not
    if bot.db.reconnecting or not bot.db.connected:
        msg = await interaction.send_text(
            "We are reconnecting to the database, please be patient and wait for a few seconds.",
            show_macro_msg=False,
            ephemeral=True,
        )
        await bot.db.connect()

        await msg.edit(
            embed=interaction.TextEmbed(
                f"We have successfully connected to the database! Use {cmd.get_mention(interaction.guild)} again.",
                EmbedColour.SUCCESS,
                show_macro_msg=False,
            )
        )
        interaction.attached["reconnected"] = True
        return False

    # Add player to database if he/she is new
    player = Player(bot.db, interaction.user)
    if not await player.is_present():
        await player.create_profile()

        embed = interaction.Embed(
            title="Welcome to BOSS!",
            description=f"Hi, {interaction.user.mention}! BOSS is a bot for set in the post-apocalyptic world after World War III, where everything is tarnished and resources are scarce. "
            "The currency system is based on a variety of items that have value in this new world, including scrap metals, coppers, and other valuable resources. "
            "Navigate this harsh world and earn, spend, and trade valuable resources. "
            "Use </help:964753444164501505> or </guide:1102561144327127201> to learn more about BOSS.",
        )
        await interaction.send(embed=embed)
        return False

    if await player.check_in_inter():
        # The user is running a command
        await interaction.send_text(
            "You are locked from running any commands until all active commands are completed. Complete all ongoing ones or try again later.",
            EmbedColour.WARNING,
            ephemeral=True,
            show_macro_msg=False,
        )
        return False

    return True


async def before_invoke(interaction: BossInteraction):
    if not interaction.response.is_done():
        await interaction.response.defer()
    cog = interaction.client.get_cog("Apocalyptic Adventures")
    missions = await cog.fetch_missions(interaction.user)
    # if the date of missions are not equal to today (daily missions --> update every day),
    # update the list of missions
    if not missions or missions[0]["date"] != datetime.date.today():
        await cog.claim_missions(interaction.user)


async def after_invoke(interaction: BossInteraction):
    # The user is in cooldown, we do not perform any of the after_invoke actions
    if interaction.attached.get("in_cooldown"):
        return

    # Running a macro
    if run_macro_view := interaction.client.running_macro_views.get(interaction.user.id):
        await run_macro_view.send_msg(interaction)

    # Recording a macro
    if record_macro_view := interaction.client.recording_macro_views.get(interaction.user.id):
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
                description=f"Nice! You levelled up from level **{old_level}** to level **{new_level}**!",
                timestamp=datetime.datetime.now(),
                colour=EmbedColour.INFO,
            )
        )


def setup(bot: commands.Bot):
    bot.add_application_command_check(cmd_check)
    bot.application_command_before_invoke(before_invoke)
    bot.application_command_after_invoke(after_invoke)

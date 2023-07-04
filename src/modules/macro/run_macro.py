# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Embed, Interaction, ButtonStyle, ApplicationCommandOptionType as OptionType
from nextcord.ui import Button, button

# my modules
from utils import constants, helpers
from utils.constants import EmbedColour
from utils.helpers import TextEmbed, send
from utils.postgres_db import Database
from utils.template_views import BaseView

# default modules
import json
from contextlib import suppress


class RunMacroView(BaseView):
    """A view to let users run a preset of slash commands through buttons, instead of inputting them in the chat."""

    def __init__(self, interaction: Interaction):
        super().__init__(interaction, timeout=60)  # 1 minute
        self.db: Database = interaction.client.db
        self.bot: commands.Bot = interaction.client
        self.macro_cmds = []  # a list of commands to run in the macro
        self.cmd_index = 0

        # stores the last message sent, if the "run" button is clicked but the message is not equal to the last message, the command will not be run.
        self.latest_msg: nextcord.Message = None

    @classmethod
    async def start(cls, interaction: Interaction, macro_name: str):
        """Starts the macro, loads the commands into the view and add it to `running_macro_views`."""
        res = await interaction.client.db.fetch(
            """
                SELECT m1.name, m1.macro_id, command_name, options
                FROM players.macro_commands AS mc
                INNER JOIN (
                    SELECT m.name, mp.macro_id
                    FROM players.macro_players AS mp
                    INNER JOIN players.macros AS m
                    ON m.macro_id = mp.macro_id
                    WHERE mp.player_id = $1 AND m.name = $2
                    LIMIT 1
                ) AS m1
                ON mc.macro_id = m1.macro_id
                ORDER BY mc.sequence
            """,
            interaction.user.id,
            macro_name,
        )
        if not res:  # the macro is not found. note that the user must own the macro in order to run it.
            await interaction.send(embed=TextEmbed("Enter a valid macro name.", EmbedColour.WARNING))
            return

        running_macro_id, recording_macro_id = await interaction.client.db.fetchrow(
            "SELECT running_macro_id, recording_macro_id FROM players.players WHERE player_id = $1", interaction.user.id
        )
        # if the user is already running a macro, we do not restart it.
        # instead, we send a message to them telling them
        if running_macro_id:
            # check whether the user is running a macro previously
            await interaction.send(embed=TextEmbed("You are already a macro!"))
            return
        # if the user is recording a macro, we halt the execution and tell the user that they can't run a macro while recording one.
        if recording_macro_id is not None:
            await interaction.send(embed=TextEmbed("You cannot run a macro while recording one.", EmbedColour.WARNING))
            return

        # create the view
        run_macro_view = cls(interaction)
        # update the list of commands in the macro with data from the database
        # `macro_commands` will then the following structure:
        #   [
        #       {'command': 'scavenge', 'options': {}},
        #       {'command': 'balance', 'options': {'user': '806334528230129695'}}
        #   ]
        # cmd["command"] stores the full name of the command ([parent names] + cmd name)
        # cmd["options"] stores the options passed into the command (which may be optional)
        run_macro_view.macro_cmds = [{"command": i["command_name"], "options": json.loads(i["options"])} for i in res]
        # update the list of all `RunMacroView` views
        running_macro_views[interaction.user.id] = run_macro_view
        # set the running macro of the user to the current one
        await run_macro_view.db.execute(
            "UPDATE players.players SET running_macro_id = $2 WHERE player_id = $1",
            interaction.user.id,
            res[0]["macro_id"],
        )
        await interaction.send(embed=TextEmbed(f"Started the macro **{res[0]['name']}**."))

    async def send_msg(self, interaction: Interaction):
        """Send a message containing a embed with the next commands and the view to let users run/end the macro."""
        embed = Embed(title="Next commands:", description="", colour=EmbedColour.DEFAULT)
        # Slice and concatenate the next values,
        # this creates a list from the next command to the command before the one of `cmd_index`,
        # i.e. the next commands to run
        next_cmds = self.macro_cmds[self.cmd_index :] + self.macro_cmds[: self.cmd_index]
        next_3_cmds = next_cmds[:3]  # Slice the next three values

        for i in next_3_cmds:
            cmd = helpers.find_command(interaction.client, i["command"])  # search for the command with the name
            # make a message denoting the options of the command
            if i["options"]:
                options_msg = []
                for name, value in i["options"].items():
                    if cmd.options[name].type == OptionType.user.value:
                        user = await interaction.client.get_or_fetch_user(value)
                        value = user.mention
                    options_msg.append(f"{name}: {value}")
                options_msg = ", ".join(options_msg)
                options_msg = f"[{options_msg}]"
            else:
                options_msg = ""

            embed.description += f"\n- {cmd.get_mention(interaction.guild)} {options_msg}"

        # set the label of the "run" button to the next command
        self.run_cmd_btn.label = f"Run /{self.macro_cmds[self.cmd_index]['command']}"

        if len(next_3_cmds) > 1:
            # set the label of the "skip" button to the command after next
            self.skip_cmd_btn.label = f"Skip (run /{next_3_cmds[1]['command']})"
        else:
            # If the macro has only 1 command, then `next_3_cmds` will only have the current command.
            # Therefore we remove the "skip" button since it's useless.
            self.remove_item(self.skip_cmd_btn)

        # update the lastest message of the `RunMacroView`
        self.latest_msg = await send(interaction, embed=embed, view=self, ephemeral=True)

    async def _run_cmd(self, interaction: Interaction, skip: bool = False):
        """
        Runs a command in the current macro.

        Args:
            interaction (Interaction): the interaction of the clicked button
            skip (bool, optional): Whether to skip to the command after next. Defaults to False.
        """

        if not skip:
            macro_cmd = self.macro_cmds[self.cmd_index]
        else:
            current_index = self.cmd_index + 1
            # if the current_index exceeds the number of total commands, decrement it by the total number of commands
            if current_index >= len(self.macro_cmds):
                current_index -= len(self.macro_cmds)
            macro_cmd = self.macro_cmds[current_index]

        # find the slash command with the name
        slash_cmd = helpers.find_command(interaction.client, macro_cmd["command"])

        # handle the options before invoking the slash command
        options = []
        for name, option in slash_cmd.options.items():
            value = macro_cmd["options"].get(name)
            # if the option is stored in the macro, use that value (but convert it into the right type)
            # if the option is not stored, use the default value
            if value is not None:
                match option.type:
                    case OptionType.user:
                        value = await self.bot.fetch_user(int(value))
                    case OptionType.channel:
                        value = await self.bot.fetch_channel(int(value))
                    case OptionType.role:
                        value = interaction.guild.get_role(int(value))
            else:
                value = option.default
            options.append(value)

        self.cmd_index += 1 if not skip else 2
        if self.cmd_index > len(self.macro_cmds) - 1:
            self.cmd_index -= len(self.macro_cmds)
        # store the latest message in `msg`,
        # since the after invoke will change the view's latest msg,
        # but we want to delete the message _after_ the command has been run
        msg = self.latest_msg
        # run the slash command. this will invoke it with the hooks (check, before_invoke, after_invoke)
        await slash_cmd.invoke_callback_with_hooks(interaction._state, interaction, args=options)
        # suppress the message not found error in case it is "dismissed" by the user (dismissed bcs it is a ephemeral message)
        with suppress(nextcord.errors.NotFound):
            await msg.delete()

    @button(label="", style=ButtonStyle.blurple, custom_id="run")
    async def run_cmd_btn(self, button: Button, interaction: Interaction):
        """Run the current command in the list"""
        await self._run_cmd(interaction)

    @button(label="", style=ButtonStyle.grey, custom_id="skip")
    async def skip_cmd_btn(self, button: Button, interaction: Interaction):
        """Run the command after the current one in the list"""
        await self._run_cmd(interaction, skip=True)

    @button(label="End", style=ButtonStyle.grey, custom_id="end")
    async def end_macro(self, button: Button, interaction: Interaction):
        """End the current macro."""
        await self.db.execute(
            "UPDATE players.players SET running_macro_id = NULL WHERE player_id = $1", interaction.user.id
        )
        await interaction.send(embed=TextEmbed("Successfully ended the current macro!"), ephemeral=True)
        running_macro_views.pop(interaction.user.id, None)

    async def on_timeout(self) -> None:
        """Delete the last message, suppressing message not found error."""
        with suppress(nextcord.errors.NotFound):
            await self.latest_msg.delete()

    async def interaction_check(self, interaction: Interaction) -> bool:
        # If the user is not running a macro, halt the execution
        running_macro_id = await self.db.fetchval(
            "SELECT running_macro_id FROM players.players WHERE player_id = $1", interaction.user.id
        )
        if (
            not running_macro_views.get(interaction.user.id) or running_macro_id is None
        ):  # check whether the user is running a macro
            await interaction.send(embed=TextEmbed("You are not running a macro."), ephemeral=True)
            return False

        # check if the button the user clicked is the lastest message
        if not self.latest_msg.id == interaction.message.id:
            await interaction.send(
                embed=TextEmbed("The macro message is outdated. Check the most recent one or restart it."),
                ephemeral=True,
            )
            return False
        return await super().interaction_check(interaction)


# a dict showing all macro views at the time
# it maps the user id to his/her `RunMacroView`
running_macro_views = {}

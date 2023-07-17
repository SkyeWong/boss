# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import ButtonStyle, ApplicationCommandOptionType as OptionType
from nextcord.ui import Button, button, View

# my modules
from utils import helpers
from utils.constants import EmbedColour
from utils.helpers import BossInteraction
from utils.postgres_db import Database

# default modules
import json
from contextlib import suppress


class RunMacroView(View):
    """A view to let users run a preset of slash commands through buttons, instead of inputting them in the chat."""

    def __init__(self):
        super().__init__(timeout=None)
        # created through `RunMacroView.start()`
        self.interaction: BossInteraction
        self.db: Database
        self.bot: commands.Bot
        self.macro_cmds: list  # a list of commands to run in the macro
        self.macro_id: str  # the id of the currently running macro
        self.macro_name: str  # the name of the currently running macro
        self.cmd_index: int  # the index of the current command in the macro
        # stores the last message sent, if the "run" button is clicked but the message is not equal to the last message, the command will not be run.
        self.latest_msg: nextcord.Message

    @classmethod
    async def start(cls, interaction: BossInteraction, macro_name: str):
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
            await interaction.send_text("Enter a valid macro name.", EmbedColour.WARNING, show_macro_msg=False)
            return

        # if the user is already running a macro, we do not restart it.
        # instead, we send a message to them telling them
        if interaction.client.running_macro_views.get(interaction.user.id):
            # check whether the user is running a macro previously
            await interaction.send_text("You are already running a macro!", EmbedColour.WARNING, show_macro_msg=False)
            return
        # if the user is recording a macro, we halt the execution and tell the user that they can't run a macro while recording one.
        if interaction.client.recording_macro_views.get(interaction.user.id):
            await interaction.send_text("You cannot run a macro while recording one.", EmbedColour.WARNING)
            return

        # create the view
        view = cls()
        view.interaction = interaction
        view.db = interaction.client.db
        view.bot = interaction.client
        # update the list of commands in the macro with data from the database
        # `macro_commands` will then the following structure:
        #   [
        #       {'command': 'scavenge', 'options': {}},
        #       {'command': 'balance', 'options': {'user': '806334528230129695'}}
        #   ]
        # cmd["command"] stores the full name of the command ([parent names] + cmd name)
        # cmd["options"] stores the options passed into the command (which may be optional)
        view.macro_cmds = [{"command": i["command_name"], "options": json.loads(i["options"])} for i in res]
        view.macro_id = res[0]["macro_id"]
        view.macro_name = res[0]["name"]
        view.cmd_index = 0
        # update the list of all `RunMacroView` views
        interaction.client.running_macro_views[interaction.user.id] = view
        # use interaction.send() and helpers.TextEmbed to avoid adding "<user> is running a /macro" message
        await interaction.send_text(f"Started the macro **{view.macro_name}**.", show_macro_msg=False)

    async def send_msg(self, interaction: BossInteraction):
        """Send a message containing a embed with the next commands and the view to let users run/end the macro."""
        embed = interaction.Embed(title="Next commands:", description="", with_url=False, show_macro_msg=False)
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

            try:
                embed.description += f"\n- {cmd.get_mention(interaction.guild)} {options_msg}"
            except ValueError:  # the command cannot be run in the guild
                embed.description += f"\n- ~~/{i['command']}~~ (cannot be run)"

        embed.set_footer(text=f"Running '{self.macro_name}' macro - {self.cmd_index + 1}/{len(self.macro_cmds)}")

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
        self.latest_msg = await interaction.send(embed=embed, view=self, ephemeral=True)

    async def _get_current_cmd(
        self, interaction: BossInteraction, macro_cmd
    ) -> tuple[nextcord.SlashApplicationSubcommand, list]:
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

        return slash_cmd, options

    async def _run_cmd(self, interaction: BossInteraction, skip: bool = False):
        """
        Runs a command in the current macro.

        Args:
            interaction (BossInteraction): the interaction of the clicked button
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

        slash_cmd, options = await self._get_current_cmd(interaction, macro_cmd)

        self.cmd_index += 1 if not skip else 2
        if self.cmd_index > len(self.macro_cmds) - 1:
            self.cmd_index -= len(self.macro_cmds)
        # store the latest message in `msg`,
        # since the after invoke will change the view's latest msg,
        # but we want to delete the message _after_ the command has been run
        msg = self.latest_msg
        base_cmd = slash_cmd
        while not isinstance(base_cmd, nextcord.SlashApplicationCommand):
            base_cmd = base_cmd.parent_cmd
        # check if the command can be run in the server
        if not (base_cmd.is_global or interaction.guild_id in base_cmd.guild_ids):
            await interaction.send_text("This command could not be run in this server!", show_macro_msg=False)
            # the check fails and `after_invoke` is not run, so we manually send the message again
            await self.send_msg(interaction)
        else:
            # run the slash command. this will invoke it with the hooks (check, before_invoke, after_invoke)
            await slash_cmd.invoke_callback_with_hooks(interaction._state, interaction, args=options)
        if interaction.attached.get("in_cooldown") or interaction.attached.get("reconnected"):
            # some checks of the command failed, we decrement the command index
            # basically reverse of what was done above
            self.cmd_index -= 1 if not skip else 2
            if self.cmd_index < 0:
                self.cmd_index += len(self.macro_cmds)
        else:
            # suppress the message not found error in case it is "dismissed" by the user (dismissed bcs it is a ephemeral message)
            with suppress(nextcord.errors.NotFound):
                await msg.delete()

    @button(label="", style=ButtonStyle.blurple, custom_id="run_macro_view: run")
    async def run_cmd_btn(self, button: Button, interaction: BossInteraction):
        """Run the current command in the list"""
        await self._run_cmd(interaction)

    @button(label="", style=ButtonStyle.grey, custom_id="run_macro_view: skip")
    async def skip_cmd_btn(self, button: Button, interaction: BossInteraction):
        """Run the command after the current one in the list"""
        await self._run_cmd(interaction, skip=True)

    @button(label="End", style=ButtonStyle.grey, custom_id="run_macro_view: end")
    async def end_macro(self, button: Button, interaction: BossInteraction):
        """End the current macro."""
        interaction.client.running_macro_views.pop(interaction.user.id, None)
        await interaction.send_text("Successfully ended the current macro!", ephemeral=True)

    async def on_timeout(self) -> None:
        """Delete the user's view from the list of them. This is unlikely to be run since the view is persistent."""
        self.interaction.client.running_macro_views.pop(self.interaction.user.id, None)

    async def interaction_check(self, interaction: BossInteraction) -> bool:
        # If the user is not running a macro, halt the execution
        if not interaction.client.running_macro_views.get(interaction.user.id):
            await interaction.send_text("You are not running a macro.", ephemeral=True)
            return False

        # check if the button the user clicked is the lastest message
        if self.latest_msg.id != interaction.message.id:
            await interaction.send_text(
                "The macro message is outdated. Check the most recent one or restart it.",
                ephemeral=True,
                show_macro_msg=False,
            )
            return False
        return await super().interaction_check(interaction)

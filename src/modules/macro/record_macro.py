# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import ButtonStyle, ApplicationCommandOptionType as OptionType
from nextcord.ui import Button, button, TextInput

# my modules
from utils import constants, helpers
from utils.constants import EmbedColour
from utils.helpers import BossInteraction
from utils.postgres_db import Database
from utils.template_views import BaseView, ConfirmView, BaseModal

# default modules
import json
from contextlib import suppress


class RecordMacroView(BaseView):
    SUPPORTED_OPTION_TYPES = (
        # a list of supported types of SlashOptions.
        # if the command includes an option which is not the following type, it will not be recorded
        OptionType.user,
        OptionType.string,
        OptionType.integer,
        OptionType.boolean,
        OptionType.number,
    )
    MAX_NUMBER_OF_COMMANDS = 25

    def __init__(self, interaction: BossInteraction, recording_macro_id: str):
        super().__init__(interaction, timeout=500)
        self.db: Database = interaction.client.db
        self.bot: commands.Bot = interaction.client
        self.recording_macro_id = recording_macro_id
        self.recorded_cmds = []
        self.latest_msg: nextcord.Message = None
        self.saved_macro = False  # flag variable to show if the user has saved the currently recording macro
        self.recording = True  # flag variable to show if the user is currently recording

    @classmethod
    async def start(cls, interaction: BossInteraction):
        """Start recording commands."""
        db: Database = interaction.client.db
        # check if the user already had 5 macros before running /macro record
        # a user can only have 5 macros at most, so if they already have 5 macros, stop the execution
        owned_macros = await db.fetchval(
            "SELECT COUNT(*) FROM players.macro_players WHERE player_id = $1", interaction.user.id
        )
        if owned_macros == 5:
            await interaction.send_text("You can only have up to 5 macros at 1 time.", EmbedColour.WARNING)
            return

        # Check if the user is running a macro.
        # Since they should not record a macro while running one, we halt the execution
        if interaction.client.running_macro_views.get(interaction.user.id):
            await interaction.send_text("You cannot record a macro while running one.", EmbedColour.WARNING)
            return

        # fetch the macro id that the user is recording and set it as the recording_macro_id of the user
        macro_id = await db.fetchval("INSERT INTO players.macros DEFAULT VALUES RETURNING macro_id")
        # create the view
        record_macro_view = cls(interaction, macro_id)
        # update the list of all `RecordMacroView` views
        interaction.client.recording_macro_views[interaction.user.id] = record_macro_view
        # send a message with the instructions on how to record commands
        await interaction.send(
            embed=interaction.Embed(
                title="Macro recording started",
                description="Use commands as usual and they will be recorded!\n"
                "After you have finished, click the ⏹️ button or run </macro record:1124712041307979827> again.\n\n"
                f"You can have {record_macro_view.MAX_NUMBER_OF_COMMANDS} commands in a macro at most.\n"
                "If the max number of commands is reached, the recording will stop automatically.",
                colour=EmbedColour.DEFAULT,
            )
        )

    async def _get_embed(self, interaction: BossInteraction):
        """Returns an embed showing the recorded commands currently"""
        embed = interaction.Embed(description="**Recorded commands:**", colour=EmbedColour.DEFAULT)

        cmds_msg = ""
        for index, i in enumerate(self.recorded_cmds):
            cmd = helpers.find_command(interaction.client, i["command"])  # search for the command with the name
            # make a message denoting the options
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

            cmds_msg += f"\n{index + 1}. {cmd.get_mention(interaction.guild)} {options_msg}"

        if not cmds_msg:
            embed.description += "\nNone"  # there are no any commands recorded yet
        else:
            embed.description += cmds_msg

        return embed

    async def send_msg(self, interaction: BossInteraction):
        """Updates the `latest_msg` attr of the view by sending a message containing the view and an embed."""
        if self.recorded_cmds:
            self.delete_cmd_btn.label = f"Delete /{self.recorded_cmds[-1]['command']}"
            self.delete_cmd_btn.disabled = False
        else:
            self.delete_cmd_btn.label = "Delete last command"
            self.delete_cmd_btn.disabled = True
        self.latest_msg = await interaction.send(embed=await self._get_embed(interaction), view=self, ephemeral=True)

    async def record(self, interaction: BossInteraction):
        cmd = interaction.application_command
        if cmd.qualified_name == "macro record":
            # this is because the user only started to record the macro,
            # and `after_invoke` called `RecordMacroView.record`.
            # Therefore we ignore this.
            return
        option_data = interaction.data.get("options")
        if option_data is not None:
            while option_data and option_data[0].get("type") in (
                OptionType.sub_command,
                OptionType.sub_command_group,
            ):
                # we search through the option_data until the required options are found
                if isinstance(option_data, dict):
                    option_data = option_data["options"]
                else:
                    option_data = option_data[0]["options"]

            if any(i.get("type") not in self.SUPPORTED_OPTION_TYPES for i in option_data):
                # the commands have at least 1 option that is not supported
                await interaction.send_text(
                    "Adding commands with those options are not supported yet. The command is not recorded.",
                    EmbedColour.WARNING,
                )
                await self.latest_msg.delete()
                return

        else:
            # if the command has no options and is a base command (i.e. not a subcommand), `option_data` will be `None`
            # here we convert it into an empty list
            option_data = []

        # update the lsit of recorded commands
        self.recorded_cmds.append(
            {"command": cmd.qualified_name, "options": {i.get("name"): i.get("value") for i in option_data}}
        )
        if len(self.recorded_cmds) == self.MAX_NUMBER_OF_COMMANDS:  # the max length of a macro has reached
            await self.stop_recording.callback(interaction)
        else:
            # suppress the message not found error in case it is "dismissed" by the user (dismissed bcs it is a ephemeral message)
            with suppress(nextcord.errors.NotFound):
                await self.latest_msg.delete()

    @button(label="", style=ButtonStyle.grey, custom_id="delete")
    async def delete_cmd_btn(self, button: Button, interaction: BossInteraction):
        """Deletes the last recorded command"""
        if len(self.recorded_cmds) == 0:
            # should not be run since if there are no commands the button should be disabled,
            # but still added nevertheless as a precaution
            await interaction.send_text("There are no recorded commands.", ephemeral=True, delete_after=5)
            return

        # pop the last command and notify the user that it has been deleted
        cmd = self.recorded_cmds.pop()
        cmd = helpers.find_command(interaction.client, cmd["command"])
        await interaction.send_text(
            f"Successfully deleted {cmd.get_mention(interaction.guild)}",
            ephemeral=True,
            delete_after=5,
        )
        await self.latest_msg.delete()
        await self.send_msg(interaction)

    @button(emoji="⏹", style=ButtonStyle.blurple, custom_id="stop")
    async def stop_recording(self, button: Button = None, interaction: BossInteraction = None):
        """
        Stop responding to the player's command, and let the user confirm whether to save or discard the macro.
        If the user wants to save the macro, ask them to input a name for it.
        """

        async def delete_macro(*args, **kwargs):
            """
            Deletes the macro which is currently recording.
            This will be run either by
                clicking "cancel" in the confirmation message,
                or when the modal has timed out,
                or when there are no commands recorded
            """
            await self.db.execute("DELETE FROM players.macros WHERE macro_id = $1", self.recording_macro_id)

        self.recording = False
        # remove the player from the list of all `RecordMacroViews`
        interaction.client.recording_macro_views.pop(interaction.user.id, None)
        # delete the last message sent (contains a list of recorded commands, if any)
        await self.latest_msg.delete()
        # no commands are recorded, delete the macro and notify the users
        if not self.recorded_cmds:
            await interaction.send_text("There are no commands recorded!", EmbedColour.FAIL)
            await delete_macro()
            return

        await interaction.send_text("Successfully ended the recording!", ephemeral=True)

        async def send_modal(button: Button, btn_inter: BossInteraction):
            """Sends a modal to the user asking them for the name of the macro"""

            async def modal_callback(modal_inter: BossInteraction):
                """Update the list of macros in the database with the name the user provided."""
                # insert the recorded commands into the table `players.macro_commands`
                await self.db.executemany(
                    """
                    INSERT INTO players.macro_commands (macro_id, sequence, command_name, options)
                    VALUES ($1, $2, $3, $4)
                    """,
                    # the `sequence` column is the order in which commands will be run, stored in an ascending order.
                    [
                        (self.recording_macro_id, index, cmd["command"], json.dumps(cmd["options"]))
                        for index, cmd in enumerate(self.recorded_cmds)
                    ],
                )
                # update the list of macros of the user
                await self.db.execute(
                    """
                    INSERT INTO players.macro_players (macro_id, player_id)
                    VALUES ($1, $2)
                    """,
                    self.recording_macro_id,
                    btn_inter.user.id,
                )
                # update the name of the macro
                name = [i for i in modal.children if i.custom_id == "input"][0].value
                await self.db.execute(
                    """
                    UPDATE players.macros
                    SET name = $1
                    WHERE macro_id = $2
                    """,
                    name,
                    self.recording_macro_id,
                )
                # update the confirmation message and notify the users that the macro has been saved
                embed = msg.embeds[0]
                embed.title = f"Saved the macro: {name}"
                embed.set_footer(text=f"ID: {self.recording_macro_id.upper()}")
                await msg.edit(embed=embed)
                self.saved_macro = True
                await modal_inter.response.defer()  # defer the response since the interaction is not used

            # if the user cancelled the modal; or did not submit in time, delete the macro
            async def on_timeout():
                if not self.saved_macro:
                    await delete_macro()
                    embed = msg.embeds[0]
                    embed.title = "Discarded the macro"
                    await msg.edit(embed=embed)

            modal = BaseModal(
                title="Saving macro",
                inputs=[TextInput(label="Name", required=True, min_length=3, max_length=30, custom_id="input")],
                callback=modal_callback,
            )
            modal.on_timeout = on_timeout
            await btn_inter.response.send_modal(modal)

        # send a message to the user asking them whether to save the macro.
        # if the user clicked "confirm", a modal will be sent to let them fill in the name of the macro
        embed = await self._get_embed(interaction)
        embed.title = "Save the macro?"  # set the title of the macro. this will be changed later according to what button the user clicked
        view = ConfirmView(
            slash_interaction=interaction,
            embed=embed,
            confirm_func=send_modal,
            cancel_func=delete_macro,
            confirmed_title="Saving the macro...",
            cancelled_title="Discarded the macro",
        )
        msg = await interaction.send(embed=view.embed, view=view)

    async def on_timeout(self) -> None:
        """Delete the last message, suppressing message not found error."""
        with suppress(nextcord.errors.NotFound):
            await self.latest_msg.delete()

    async def interaction_check(self, interaction: BossInteraction) -> bool:
        if self.latest_msg.id != interaction.message.id:
            await interaction.send_text(
                "The macro message is outdated. Check the most recent one.",
                ephemeral=True,
            )
            return False
        if not interaction.client.recording_macro_views.get(interaction.user.id):
            await interaction.send_text(
                "You are not recording a macro! Use </macro record:1124712041307979827>",
                ephemeral=True,
            )
            return False
        return await super().interaction_check(interaction)

# default modules
from typing import Union

# nextcord
import nextcord
from nextcord import SlashApplicationCommand as SlashCmd
from nextcord import SlashApplicationSubcommand as SlashSubcmd
from nextcord import SlashOption
from nextcord.ext import commands
from nextcord.ui import Button

from cogs.survival_guide.views import GuideView, HelpView
from modules.macro.record_macro import RecordMacroView
from modules.macro.run_macro import RunMacroView
from modules.macro.show_macro import ShowMacrosView

# my modules and constants
from utils.constants import EmbedColour
from utils.helpers import BossInteraction, command_info

# database
from utils.postgres_db import Database


class SurvivalGuide(commands.Cog, name="Survival Guide"):
    """Essential commands to assist you in the wasteland"""

    COG_EMOJI = "📖"

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def get_all_subcommands(self, cmd: Union[SlashCmd, SlashSubcmd]) -> list[SlashCmd, SlashSubcmd]:
        """Get all subcommand names of a command."""
        cmd_names = []
        for subcmd in cmd.children.values():
            if subcmd.children:
                cmd_names.extend(self.get_all_subcommands(subcmd))
            else:
                cmd_names.append(subcmd)
        return cmd_names

    async def choose_command_autocomplete(self, interaction: BossInteraction, data: str) -> list[str]:
        """
        Return every command and subcommand in the bot.
        Returns command that match `data` if it is provided.
        """
        client: nextcord.Client = interaction.client
        cmds = [i for i in client.get_all_application_commands() if isinstance(i, SlashCmd)]

        cmd_names = []
        for cmd in cmds:
            if cmd.is_global or interaction.guild_id in cmd.guild_ids:
                cmd_names.append(cmd.qualified_name)
                if cmd.children:
                    cmd_names.extend([i.qualified_name for i in self.get_all_subcommands(cmd)])

        cmd_names.sort()
        if not data:
            # return full list
            await interaction.response.send_autocomplete(cmd_names[:25])
        else:
            # send a list of nearest matches from the list of item
            near_items = [cmd for cmd in cmd_names if data.lower() in cmd.lower()]
            await interaction.response.send_autocomplete(near_items[:25])

    def parse_command(self, interaction: BossInteraction, cmd_name: str):
        client: nextcord.Client = interaction.client
        all_cmds = [i for i in client.get_all_application_commands() if isinstance(i, SlashCmd)]

        cmd_list = cmd_name.split()
        for item in cmd_list:
            cmd = next((i for i in all_cmds if i.name == item), None)
            if cmd is None:
                raise CommandNotFound()
            if isinstance(cmd, SlashCmd):
                base_cmd = cmd
            all_cmds = cmd.children.values()

        if cmd.qualified_name != cmd_name:
            raise CommandNotFound()

        if not base_cmd.is_global and interaction.guild_id not in base_cmd.guild_ids:
            raise CommandNotFound()

        return cmd

    @nextcord.slash_command()
    @command_info(
        examples={
            "help": "Shows the complete list of commands in BOSS, which you can then filter by category.",
            "help command:hunt": "Teaches you how to use a command, with examples and more!",
        }
    )
    async def help(
        self,
        interaction: BossInteraction,
        cmd_name: str = SlashOption(
            name="command",
            description="Get extra info for this command.",
            default=None,
            required=False,
            autocomplete_callback=choose_command_autocomplete,
        ),
    ):
        """Get a list of commands or info of a specific command."""
        if not cmd_name:
            # send full command list
            view = HelpView(interaction)
            await view.send()
            return

        # search for exact matches since the user is likely to have selected it from autocomplete
        try:
            cmd = self.parse_command(interaction, cmd_name)
        except CommandNotFound:
            await interaction.send_text(
                "The command is not found! Use </help:964753444164501505> for a list of available commands.",
                EmbedColour.WARNING,
            )
            return

        # the exact match has been found
        # generate the full description of the command, including long help messages, notes and examples
        name = cmd.qualified_name
        full_desc = cmd.description
        if long_help := getattr(cmd, "long_help", None):
            full_desc += f"\n{long_help}"
        if notes := getattr(cmd, "notes", None):
            for note in notes:
                full_desc += f"\n- {note}"
        if cmd.children:
            # this command has subcommands, send a list of the subcommands
            view = HelpView(interaction, cmd_list=self.get_all_subcommands(cmd), with_select_menu=False)
            await view.send(
                description=f"{full_desc}\n\n",
                author_name=f"Subcommands of /{name}",
            )
        else:
            # this command does not have subcommands,
            # send values of the command itself
            embed = self._get_command_embed(interaction, cmd, full_desc)
            await interaction.send(embed=embed)

    def _get_command_embed(self, interaction: BossInteraction, cmd: Union[SlashCmd, SlashSubcmd], full_desc: str):
        embed = interaction.embed(with_url=False)
        embed.title = cmd.get_mention(interaction.guild)
        embed.description = full_desc
        embed.colour = EmbedColour.INFO
        embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)

        # show all options of the command and add a field to the embed
        option_msg = []
        for name, option in cmd.options.items():
            if option.required:
                option_msg.append(f"<{name}>")
            else:
                option_msg.append(f"[{name}]")
        usage = f"`/{cmd.qualified_name} {' '.join(option_msg)}`"
        embed.add_field(name="Usage", value=usage, inline=False)

        # add an "examples" field showing how to use the command
        if examples := getattr(cmd, "examples", None):
            example_txt = ""
            for syntax, description in examples.items():
                example_txt += f"`/{syntax}`\n<:reply:1117458829869858917> {description}\n"
            embed.add_field(name="Examples", value=example_txt, inline=False)

        embed.set_footer(text="Syntax: <required> [optional]")
        return embed

    @nextcord.slash_command(description="Get help navigating the wasteland with BOSS's guide.")
    @command_info(
        long_help=(
            "New to the bot? This command introduces you to the apocalyptic world BOSS sets in, and shows you a"
            " step-by-step guide on how to become one of the most supreme survivalists!"
        )
    )
    async def guide(
        self,
        interaction: BossInteraction,
        page: int = SlashOption(
            description="The page of the guide to start in",
            required=False,
            default=0,
            choices={
                f"{page.title} ({index + 1}/{len(GuideView.pages)})": index
                for index, page in enumerate(GuideView.pages)
            },
        ),
    ):
        await GuideView.send(interaction, page)

    @nextcord.slash_command(description="Adjust user specific settings")
    async def settings(
        self,
        interaction: BossInteraction,
        setting: str = SlashOption(
            description="The setting to change",
            choices={
                "Sort the inventory by item worth": "inv_worth_sort",
                "Compact mode": "compact_mode",
            },
        ),
        value: bool = SlashOption(description="The value to change to"),
    ):
        db: Database = self.bot.db
        await db.execute(f"UPDATE players.settings SET {setting} = $1 WHERE player_id = $2", value, interaction.user.id)
        await interaction.send_text("Updated your settings!")

    @nextcord.slash_command(description="Manage your macros - tools to run commands automatically.")
    @command_info(
        long_help=(
            "To see more info on how to use macros, use </guide:1102561144327127201> and select the page about macros."
        )
    )
    async def macro(self, interaction: BossInteraction):
        # The parent command of a subcommand will never be called
        pass

    async def choose_macro_autocomplete(self, interaction: BossInteraction, data: str):
        user_macros = await interaction.client.db.fetch(
            """
                SELECT m.name
                FROM players.macros AS m
                INNER JOIN players.macro_players AS mp
                ON mp.macro_id = m.macro_id
                WHERE mp.player_id = $1
            """,
            interaction.user.id,
        )
        user_macros = [i["name"] for i in user_macros]
        if not data:
            # return full list
            await interaction.response.send_autocomplete(user_macros[:25])
        else:
            near_macros = [i for i in user_macros if data in i][:25]
            await interaction.response.send_autocomplete(near_macros)

    @macro.subcommand(description="Start a macro.")
    async def start(
        self,
        interaction: BossInteraction,
        macro: str = SlashOption(description="The macro to run.", autocomplete_callback=choose_macro_autocomplete),
    ):
        await RunMacroView.start(interaction, macro_name=macro)

    @macro.subcommand(description="Record a macro and save it.")
    async def record(self, interaction: BossInteraction):
        # if the user is recording a macro, stop recording
        # otherwise, start the recording
        if record_macro_view := interaction.client.recording_macro_views.get(interaction.user.id):
            btn: Button = record_macro_view.stop_recording
            await btn.callback(interaction)
        else:
            await RecordMacroView.start(interaction)

    @macro.subcommand(name="list", description="Show your list of added macros.")
    async def show(self, interaction: BossInteraction):
        await ShowMacrosView.send(interaction)


class CommandNotFound(Exception):
    pass


def setup(bot: commands.Bot):
    bot.add_cog(SurvivalGuide(bot))

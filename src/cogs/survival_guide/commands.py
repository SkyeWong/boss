# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Embed, Interaction, SlashOption

# database
from utils.postgres_db import Database

# my modules and constants
from utils import helpers, constants
from utils.constants import EmbedColour
from utils.helpers import TextEmbed, command_info

from .views import HelpView, GuideView

# default modules
import random


class Utility(commands.Cog, name="Survival Guide"):
    """Essential commands to assist you in the wasteland"""

    COG_EMOJI = "📖"

    def __init__(self, bot):
        self.bot = bot
        self._last_member = None

    def search_subcommand(self, cmd: nextcord.SlashApplicationCommand, cmd_name):
        """Search for a subcommand with its name."""
        cmd_found = False
        subcommands = cmd.children.values()
        for x in subcommands:
            if x.qualified_name in cmd_name:
                if cmd_name == x.qualified_name:
                    cmd_found = True
                    cmd = x
                    break
                elif x.children:
                    return self.search_subcommand(x, cmd_name)

        if not cmd_found:
            raise helpers.CommandNotFound()
        return cmd

    def get_all_subcmd_names(self, guild_id: int, cmd):
        """Get all subcommand names of a command."""
        cmd_names = []
        cmd_in_server = lambda cmd: cmd.is_global or guild_id in cmd.guild_ids
        for subcmd in cmd.children.values():
            base_cmd = cmd
            while not isinstance(base_cmd, nextcord.SlashApplicationCommand):
                base_cmd = base_cmd.parent_cmd
            if cmd_in_server(base_cmd):
                cmd_names.append(subcmd.qualified_name)
            if len(subcmd.children) > 0:
                cmd_names.extend(self.get_all_subcmd_names(guild_id, subcmd))
        return cmd_names

    async def choose_command_autocomplete(self, interaction: Interaction, data: str):
        """
        Return every command and subcommand in the bot.
        Returns command that match `data` if it is provided.
        """
        if data.startswith("$"):
            await interaction.response.send_autocomplete([data, "Searching mode: on"])
            return

        base_cmds = interaction.client.get_all_application_commands()
        cmd_names = []
        cmd_in_server = lambda cmd: cmd.is_global or interaction.guild_id in cmd.guild_ids
        for base_cmd in base_cmds:
            if cmd_in_server(base_cmd):
                cmd_names.append(base_cmd.name)
            if hasattr(base_cmd, "children") and len(base_cmd.children) > 0:
                cmd_names.extend(self.get_all_subcmd_names(interaction.guild_id, base_cmd))
        cmd_names.sort()
        if not data:
            # return full list
            await interaction.response.send_autocomplete(cmd_names[:25])
        else:
            # send a list of nearest matches from the list of item
            near_items = [cmd for cmd in cmd_names if data.lower() in cmd.lower()]
            await interaction.response.send_autocomplete(near_items[:25])

    @nextcord.slash_command()
    @command_info(
        examples={
            "help": "Shows the complete list of commands in BOSS, which you can then filter by category.",
            "help command:hunt": "Teaches you how to use a command, with examples and more!",
            "help command:$backpack": "Searches for a command based on the query; it will be found based on its name and description.",
        }
    )
    async def help(
        self,
        interaction: Interaction,
        cmd_name: str = SlashOption(
            name="command",
            description="Get extra info for this command. Tip: prefix the query with '$' to search for partial matches.",
            default=None,
            required=False,
            autocomplete_callback=choose_command_autocomplete,
        ),
    ):
        """Get a list of commands or info of a specific command."""
        if not cmd_name:  # send full command list
            view = HelpView(interaction)
            await view.send()
        else:
            # find a specific command
            cmd_name = cmd_name.strip()
            if cmd_name.startswith("$"):  # search for commands, not just exact matches
                cmd_name = cmd_name[1:]  # remove "$" prefix
                if len(cmd_name) < 3:
                    await interaction.send(embed=TextEmbed("Use search terms at least 3 characters long."))
                    return

                cmds = []
                search_command = (
                    lambda command: cmd_name in command.qualified_name
                    or cmd_name.lower() in command.description.lower()
                )
                for i in interaction.client.get_all_application_commands():
                    # prioritise subcommands
                    if subcmds := [j for j in i.children.values() if search_command(j)]:
                        cmds.extend(subcmds)
                    elif subsubcmds := [
                        k for j in i.children.values() for k in j.children.values() if search_command(k)
                    ]:
                        cmds.extend(subsubcmds)
                    elif search_command(i):
                        cmds.append(i)

                if not cmds:
                    await interaction.send(
                        embed=TextEmbed(
                            f"There are no commands matching _{cmd_name}_. Use </help:964753444164501505> for a list of available commands"
                        )
                    )
                    return

                # at least 1 command has been found, send the view with the command list
                view = HelpView(interaction, cmd_list=cmds, with_select_menu=False)
                await view.send(author_name=f"Commands matching '{cmd_name}'")
            else:  # search for exact matches since the user is likely to have selected it from autocomplete
                cmd = None

                for i in interaction.client.get_all_application_commands():
                    # search for the command name
                    if i.is_global or interaction.guild_id in i.guild_ids:  # command is available to user
                        if i.name == cmd_name:  # matched exact command
                            cmd = i
                            break
                        elif i.children and i.qualified_name in cmd_name:  # subcommand
                            try:
                                cmd = self.search_subcommand(i, cmd_name)
                            except helpers.CommandNotFound:
                                continue
                            else:
                                break

                if cmd is None:  # no exact match of command
                    await interaction.send(
                        embed=TextEmbed(
                            "The command is not found! Use </help:964753444164501505> for a list of available commands."
                        )
                    )
                    return

                # the exact match has been found
                name = cmd.qualified_name
                if len(cmd.children) > 0:
                    # this command has subcommands, send a list of the subcommands
                    view = HelpView(interaction, cmd_list=cmd.children.values(), with_select_menu=False)
                    await view.send(
                        description=f"> {cmd.description}\n\n",
                        author_name=f"Subcommands of /{name}",
                    )
                else:
                    # this command does not have subcommands,
                    # send values of the command itself
                    embed = Embed()
                    embed.title = f"</{name}:{list(cmd.command_ids.values())[0]}>"
                    embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)

                    embed.description = cmd.description
                    if long_help := getattr(cmd, "long_help", None):
                        embed.description += f"\n\n{long_help}"
                    if notes := getattr(cmd, "notes", None):
                        for note in notes:
                            embed.description += f"\n- {note}"

                    # show all options of the command and add a field to the embed
                    cmd_options = [i for i in list(cmd.options.values())]
                    usage = f"`/{name} "
                    for option in cmd_options:
                        if option.required:
                            usage += f"<{option.name}> "
                        else:
                            usage += f"[{option.name}] "
                    usage = usage[:-1]  # remove the last space
                    usage += "`"  # make it monospace
                    embed.add_field(name="Usage", value=usage, inline=False)

                    # add an "examples" field showing how to use the command
                    if examples := getattr(cmd, "examples", None):
                        example_txt = ""
                        for syntax, description in examples.items():
                            example_txt += f"`/{syntax}`\n<:reply:1117458829869858917> {description}\n"
                        embed.add_field(name="Examples", value=example_txt, inline=False)

                    embed.set_footer(text="Syntax: <required> [optional]")
                    embed.colour = EmbedColour.INFO
                    await interaction.send(embed=embed)

    @nextcord.slash_command()
    @command_info(
        long_help="New to the bot? This command introduces you to the apocalyptic world BOSS sets in, and shows you a step-by-step guide on how to become one of the most supreme survivalists!"
    )
    async def guide(self, interaction: Interaction):
        """Get help navigating the wasteland with BOSS's guide."""
        view = GuideView(interaction)
        await view.send()

    @nextcord.slash_command(description="Adjust user specific settings")
    async def settings(
        self,
        interaction: Interaction,
        setting: str = SlashOption(
            description="The setting to change",
            choices={"Sort the inventory by item worth": "inv_worth_sort", "Compact mode": "compact_mode"},
        ),
        value: bool = SlashOption(description="The value to change to"),
    ):
        db: Database = self.bot.db
        await db.execute(
            """
                UPDATE players.settings
                SET {column} = $1
            """.format(
                column=setting
            ),
            value,
        )
        await interaction.send(embed=TextEmbed("Updated your settings!"))


def setup(bot: commands.Bot):
    bot.add_cog(Utility(bot))

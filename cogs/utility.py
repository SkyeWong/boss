# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Embed, Interaction, SlashOption

# database
from utils.postgres_db import Database

# my modules and constants
from utils import helpers, constants
from utils.helpers import TextEmbed

from views.utility_views import HelpView, GuideView

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
        for subcmd in cmd.children.values():
            base_cmd = cmd
            while not isinstance(base_cmd, nextcord.SlashApplicationCommand):
                base_cmd = base_cmd.parent_cmd
            cmd_in_guild = False
            if base_cmd.is_global:
                cmd_in_guild = True
            elif guild_id in base_cmd.guild_ids:
                cmd_in_guild = True
            if cmd_in_guild == True:
                cmd_names.append(subcmd.qualified_name)
            if len(subcmd.children) > 0:
                cmd_names.extend(self.get_all_subcmd_names(guild_id, subcmd))
        return cmd_names

    async def choose_command_autocomplete(self, interaction: Interaction, data: str):
        """
        Return every command and subcommand in the bot.
        Returns command that match `data` if it is provided.
        """
        base_cmds = interaction.client.get_all_application_commands()
        cmd_names = []
        for base_cmd in base_cmds:
            cmd_in_guild = False
            if base_cmd.is_global:
                cmd_in_guild = True
            elif interaction.guild_id in base_cmd.guild_ids:
                cmd_in_guild = True
            if cmd_in_guild == True:
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
        mapping = helpers.get_mapping(interaction, self.bot)

        if not cmd_name:  # send full command list
            view = HelpView(interaction, mapping)
            embed = view.help_embed()
            view.btn_disable()
            await interaction.send(embed=embed, view=view)
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
                view = HelpView(interaction, cmd_list=cmds)
                embed = view.help_embed(
                    author_name=f"Commands matching '{cmd_name}'",
                )

                # disable some paginating buttons
                view.btn_disable()

                # remove the select menu to choose between cogs
                select = [i for i in view.children if i.custom_id == "cog_select"][0]
                view.remove_item(select)
                await interaction.send(embed=embed, view=view)
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
                    view = HelpView(interaction, mapping)
                    view.cmd_list = cmd.children.values()
                    embed = view.help_embed(
                        description=f"> {cmd.description}",
                        author_name=f"Subcommands of /{name}",
                    )

                    # disable certain paginating buttons
                    view.btn_disable()
                    # remove the select menu which allows users to choose different cogs
                    select = [i for i in view.children if i.custom_id == "cog_select"][0]
                    view.remove_item(select)
                    await interaction.send(embed=embed, view=view)
                else:
                    # this command does not have subcommands,
                    # send values of the command itself
                    embed = Embed()
                    embed.title = f"</{name}:{list(cmd.command_ids.values())[0]}>"
                    embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)
                    embed.description = f"> {cmd.description}"

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

                    embed.set_footer(text="Syntax: <required> [optional]")
                    embed.colour = random.choice(constants.EMBED_COLOURS)
                    await interaction.send(embed=embed)

    @nextcord.slash_command()
    async def guide(self, interaction: Interaction):
        """Get help navigating the wasteland with BOSS's guide."""
        view = GuideView(interaction)
        await view.send()


def setup(bot: commands.Bot):
    bot.add_cog(Utility(bot))

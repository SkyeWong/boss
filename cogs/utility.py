# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Embed, Interaction, SlashOption

# command cooldowns
import cooldowns
from cooldowns import SlashBucket

# database
from utils.postgres_db import Database

# my modules and constants
from utils.player import Player
from utils import functions, constants

from views.utility_views import HelpView

# default modules
import random


class Utility(commands.Cog, name="Utility"):
    COG_EMOJI = "🔨"

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
            raise functions.CommandNotFound()
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

    @nextcord.slash_command(name="help")
    @cooldowns.cooldown(1, 12, SlashBucket.author)
    async def help(
        self,
        interaction: Interaction,
        cmd_name: str = SlashOption(
            name="command",
            description="Get extra info for this command",
            default=None,
            required=False,
            autocomplete_callback=choose_command_autocomplete,
        ),
    ):
        """Get a list of commands or info of a specific command."""
        mapping = functions.get_mapping(interaction, self.bot)

        if not cmd_name:  # send full command list
            view = HelpView(interaction, mapping)
            embed = view.help_embed()
            view.btn_disable()
            await interaction.send(embed=embed, view=view)
            return

        # find a specific command
        cmd_name = cmd_name.strip()
        cmd = None

        client: nextcord.Client = interaction.client

        for i in client.get_all_application_commands():
            # search for the command name
            if i.is_global or interaction.guild_id in i.guild_ids:  # command is available to user
                if i.name == cmd_name:  # matched exact command
                    cmd = i
                    break
                elif i.children and i.qualified_name in cmd_name:  # subcommand
                    try:
                        cmd = self.search_subcommand(i, cmd_name)
                    except functions.CommandNotFound:
                        continue
                    else:
                        break

        if cmd is None:
            await interaction.send(
                embed=functions.format_with_embed(
                    "The command is not found! Use </help:964753444164501505> for a list of available commands"
                )
            )
            return

        embed = Embed()
        name = cmd.qualified_name
        embed.title = f"Info of </{name}:{list(cmd.command_ids.values())[0]}>"
        embed.set_author(name=self.bot.user.name, icon_url=self.bot.user.display_avatar.url)

        if len(cmd.children) > 0:
            # this command has subcommands, send a list of the subcommands
            view = HelpView(interaction, mapping)
            view.cmd_list = cmd.children.values()
            embed = view.help_embed(
                description=f">>> {cmd.description}",
                author_name=f"Subcommands of /{name}",
            )

            # disable some paginating buttons
            view.btn_disable()

            # remove the select menu to choose between cogs
            select = [i for i in view.children if i.custom_id == "cog_select"][0]
            view.remove_item(select)
            await interaction.send(embed=embed, view=view)
        else:
            # this command does not have subcommands,
            # send values of the command itself
            embed.description = cmd.description

            cmd_options = [i for i in list(cmd.options.values())]
            usage = f"`/{name} "

            options_txt = ""
            for option in cmd_options:
                if option.required == True:
                    usage += f"<{option.name}> "
                else:
                    usage += f"[{option.name}] "

                options_txt += (
                    f"**`{option.name}`**: {option.description}\n"
                    if option.description != "No description provided."
                    else ""
                )

            usage = usage[:-1]  # remove the last space
            usage += "`"  # make it monospace

            embed.add_field(name="Usage", value=usage, inline=False)
            if options_txt != "":
                embed.add_field(name="Options", value=options_txt, inline=False)

            embed.set_footer(text="Syntax: <required> [optional]")
            embed.colour = random.choice(constants.EMBED_COLOURS)
            await interaction.send(embed=embed)

    async def choose_item_autocomplete(self, interaction: Interaction, data: str):
        sql = """
            SELECT name
            FROM utility.items
            ORDER BY name
        """
        db: Database = self.bot.db
        result = await db.fetch(sql)
        items = [i[0] for i in result]
        if not data:
            # return full list
            await interaction.response.send_autocomplete(items)
            return
        else:
            # send a list of nearest matches from the list of item
            near_items = [item for item in items if data.lower() in item.lower()][:25]
            await interaction.response.send_autocomplete(near_items)

    @nextcord.slash_command(name="item")
    @cooldowns.cooldown(1, 12, SlashBucket.author)
    async def item(
        self,
        interaction: Interaction,
        itemname: str = SlashOption(
            name="item",
            description="The item to search for",
            autocomplete_callback=choose_item_autocomplete,
        ),
    ):
        """Get information of an item."""
        sql = """
            SELECT *
            FROM utility.items
            WHERE name ILIKE $1 or emoji_name ILIKE $1
            ORDER BY name ASC
        """
        db: Database = self.bot.db
        item = await db.fetchrow(sql, f"%{itemname.lower()}%")
        if not item:
            await interaction.send(embed=Embed(description="The item is not found!"), ephemeral=True)
        else:
            res = await db.fetch(
                """
                SELECT inv_type, quantity
                FROM players.inventory
                WHERE player_id = $1 AND item_id = $2
                """,
                interaction.user.id,
                item["item_id"],
            )
            owned_quantities = {
                constants.InventoryType(inv_type).name: quantity
                for inv_type, quantity
                in res
            }
            embed = functions.get_item_embed(item, owned_quantities)
            await interaction.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Utility(bot))
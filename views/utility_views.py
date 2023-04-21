# nextcord
import nextcord
from nextcord import Embed, Interaction, SelectOption
from nextcord.ui import View, Button, button, select

# default modules
import random
import math
from typing import Optional

# my modules and constants
from utils import constants
from views.template_views import BaseView


class HelpView(BaseView):
    def __init__(self, slash_interaction: Interaction, mapping: dict):
        super().__init__(slash_interaction, timeout=90)

        self.mapping = mapping
        self.cmd_list = []

        for cog_name, (cog, commands) in mapping.items():
            self.cmd_list.extend(commands)
        self.cmd_list.sort(key=lambda x: x.qualified_name)
        cog_select_menu = [i for i in self.children if i.custom_id == "cog_select"][0]
        options = self._get_cogs_option()
        cog_select_menu.options = options
        cog_select_menu.max_values = len(options)
        self.page = 1
        self.cmd_per_page = 6
        self.old_selected_values = ["All"]

    def _get_cogs_option(self) -> list[SelectOption]:
        options: list[SelectOption] = [SelectOption(label="All", emoji="🌐", default=True)]
        for cog_name in self.mapping:
            cog = self.mapping[cog_name][0]
            emoji = getattr(cog, "COG_EMOJI", None)
            options.append(SelectOption(label=cog_name, emoji=emoji, default=False))
        options.sort(key=lambda x: x.label)
        return options

    def help_embed(
        self,
        description: Optional[str] = None,
        set_author: bool = True,
        author_name: str = "Commands",
    ):
        command_list = self.cmd_list
        embed = Embed()
        embed.colour = random.choice(constants.EMBED_COLOURS)
        if description:
            embed.description = description
        if set_author:
            avatar = self.interaction.client.user.avatar or self.interaction.client.user.default_avatar
            embed.set_author(name=author_name, icon_url=avatar.url)
        if not command_list:
            for cog_name in self.mapping:
                if cog_name == self.default_cog_name:
                    command_list = self.mapping[cog_name][1]
                    break
        filtered = []
        for i in command_list:
            cmd_in_guild = False
            if isinstance(i, nextcord.SlashApplicationCommand):
                if i.is_global:
                    cmd_in_guild = True
                elif self.interaction.guild_id in i.guild_ids:
                    cmd_in_guild = True
            elif isinstance(i, nextcord.SlashApplicationSubcommand):
                parent_cmd = i.parent_cmd
                while not isinstance(parent_cmd, nextcord.SlashApplicationCommand):
                    parent_cmd = parent_cmd.parent_cmd
                if parent_cmd:
                    if parent_cmd.is_global:
                        cmd_in_guild = True
                    elif self.interaction.guild_id in parent_cmd.guild_ids:
                        cmd_in_guild = True
            if cmd_in_guild:
                filtered.append(i)
        final_cmd_list = filtered[self.get_page_start_index() : self.get_page_end_index() + 1]
        for cmd in final_cmd_list:
            value = cmd.description if cmd.description else "..."
            name = f"</{cmd.qualified_name}:{list(cmd.command_ids.values())[0]}>"
            if len(cmd.children) > 0:
                name += " `has subcommands`"
            embed.add_field(name=name, value=f"`➸` {value}", inline=False)
        embed.set_footer(text=f"Page {self.page}/{math.ceil(len(self.cmd_list) / self.cmd_per_page)}")
        return embed

    @select(
        placeholder="Choose a category...",
        options=[],
        min_values=1,
        max_values=1,
        custom_id="cog_select",
    )
    async def select_cog(self, select: nextcord.ui.Select, interaction: Interaction):
        self.page = 1
        self.cmd_list = []

        selected_values = select.values
        if "All" in [i for i in selected_values if i not in self.old_selected_values]:
            selected_values = ["All"]
        elif "All" in [i for i in self.old_selected_values if i in selected_values]:
            selected_values.remove("All")

        if "All" in selected_values:
            for cog_name, (cog, commands) in self.mapping.items():
                self.cmd_list.extend(commands)
        else:
            for value in selected_values:
                self.cmd_list.extend(self.mapping[value][1])
        self.cmd_list.sort(key=lambda x: x.qualified_name)
        self.btn_disable()
        for option in select.options:
            option.default = False
            if option.label in selected_values:
                option.default = True
        await self.get_embed_and_send_msg(interaction)
        self.old_selected_values = selected_values

    def get_page_start_index(self):
        return (self.page - 1) * self.cmd_per_page

    def get_page_end_index(self):
        index = self.get_page_start_index() + self.cmd_per_page - 1
        return index if index < len(self.cmd_list) else len(self.cmd_list) - 1

    def btn_disable(self):
        back_btn = [i for i in self.children if i.custom_id == "back"][0]
        first_btn = [i for i in self.children if i.custom_id == "first"][0]
        if self.page == 1:
            back_btn.disabled = True
            first_btn.disabled = True
        else:
            back_btn.disabled = False
            first_btn.disabled = False
        next_btn = [i for i in self.children if i.custom_id == "next"][0]
        last_btn = [i for i in self.children if i.custom_id == "last"][0]
        if self.get_page_end_index() == len(self.cmd_list) - 1:
            next_btn.disabled = True
            last_btn.disabled = True
        else:
            next_btn.disabled = False
            last_btn.disabled = False

    async def get_embed_and_send_msg(self, interaction: Interaction):
        embed = self.help_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @button(emoji="⏮️", style=nextcord.ButtonStyle.blurple, custom_id="first", disabled=True)
    async def first(self, button: Button, interaction: Interaction):
        self.page = 1
        self.btn_disable()
        await self.get_embed_and_send_msg(interaction)

    @button(emoji="◀️", style=nextcord.ButtonStyle.blurple, disabled=True, custom_id="back")
    async def back(self, button: Button, interaction: Interaction):
        self.page -= 1
        self.btn_disable()
        await self.get_embed_and_send_msg(interaction)

    @button(emoji="▶️", style=nextcord.ButtonStyle.blurple, custom_id="next")
    async def next(self, button: Button, interaction: Interaction):
        self.page += 1
        self.btn_disable()
        await self.get_embed_and_send_msg(interaction)

    @button(emoji="⏭️", style=nextcord.ButtonStyle.blurple, custom_id="last")
    async def last(self, button: Button, interaction: Interaction):
        self.page = math.ceil(len(self.cmd_list) / self.cmd_per_page)
        self.btn_disable()
        await self.get_embed_and_send_msg(interaction)

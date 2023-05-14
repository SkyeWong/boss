# nextcord
import nextcord
from nextcord import Embed, Interaction, SelectOption, ButtonStyle
from nextcord.ui import Button, button, Select, select

# default modules
import random
import math
from typing import Optional

# my modules and constants
from utils import constants
from utils.constants import CURRENCY_EMOJIS, SCRAP_METAL, COPPER
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
        command_list = sorted(list(self.cmd_list), key=lambda x: x.qualified_name)

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
        if len(selected_values) == len(self.mapping):
            selected_values = ["All"]

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


class EmbedField:
    def __init__(self, name: str, value: str, inline: bool = True) -> None:
        self.name = name
        self.value = value
        self.inline = inline


class GuidePage(Embed):
    def __init__(
        self,
        title: str,
        description: str,
        fields: Optional[tuple[EmbedField]] = None,
        image: Optional[str] = None,
    ):
        super().__init__(title=title, description=description)
        self.set_image(image)
        if fields is not None:
            for field in fields:
                self.add_field(name=field.name, value=field.value, inline=field.inline)


class GuideView(BaseView):
    pages: list[GuidePage] = [
        GuidePage(
            title="Introduction",
            description="Welcome to BOSS, the bot for a **post-apocalyptic wasteland following World War III**. \n"
            "Scavenge for resources, complete missions, and participate in events to earn **valuable currency**. \n\n"
            "With BOSS's help, you can navigate this harsh world and build your wealth. "
            "__So join us and let BOSS be your guide to survival and prosperity!__ \n\n"
            "To start playing, use </help:964753444164501505> to view a list of available commands.",
        ),
        GuidePage(
            title="Currency System",
            description="In the world of BOSS, there are two main types of currency: scrap metal and copper.",
            fields=[
                EmbedField(
                    f"Scrap Metal {SCRAP_METAL}",
                    "Scrap metal is the **basic currency** in BOSS, used for everyday transactions. \n"
                    "It's easy to find and earn, but has a relatively low value compared to other types of currency. "
                    "Users need to manage their scrap metal wisely to build their wealth and survive. ",
                    False,
                ),
                EmbedField(
                    f"Copper {COPPER}",
                    "Copper is a **valuable and versatile currency** in BOSS, used for creating and repairing weapons, armor, and electronic devices. "
                    "Users can earn copper by scavenging for it or completing tasks and challenges. \n"
                    "As a currency, copper is worth more than basic resources like scrap metal or cloth. "
                    "It can be traded for valuable resources like ammunition, fuel, or medicine. \n\n"
                    f"1 copper is worth {constants.COPPER_SCRAP_RATE} scrap metals.",
                    False,
                ),
            ],
        ),
        GuidePage(
            title="How to survive",
            description="The ultimate guide to survive in BOSS.",
            fields=[
                EmbedField(
                    "By scavenging for resources",
                    "Use </hunt:1079601533215330415>, </dig:1079644728921948230>, </mine:1102561135988838410>, </scavenge:1106580684786647180> and more! "
                    "Each activity has its own risks and rewards, and users can use the resources they find to build their wealth and purchase goods and services.",
                    False,
                ),
                EmbedField(
                    "By completing tasks and challenges",
                    "Users can also earn currency by completing tasks and challenges. "
                    "These may include delivering goods, defending against raiders, or completing other objectives. "
                    "Users can use the /missions command to view available missions and track their progress.",
                    False,
                ),
            ],
        ),
        GuidePage(
            title="Manage your wealth",
            description="Use your currency to purchase goods and services. \n\n"
            "Use the /shop command to view available items and their prices, and use the /buy command to purchase items. \n"
            "You can also use the </trade:1102561137893056563> command to trade currency with virtual villagers, and acquire valuable resources to build your wealth. ",
        ),
    ]

    def __init__(self, interaction: Interaction):
        super().__init__(interaction, timeout=180)
        self.current_page = 0
        self.msg: nextcord.WebhookMessage | nextcord.PartialInteractionMessage = None

        choose_page_select = [i for i in self.children if i.custom_id == "choose_page"][0]
        choose_page_select.options = []
        for index, page in enumerate(self.pages):
            choose_page_select.options.append(
                SelectOption(
                    label=f"{page.title} ({index + 1}/{len(self.pages)})",
                    value=index,
                    default=index == self.current_page,
                )
            )

    async def send(self):
        embed = self.get_embed()
        self.update_view()
        self.msg = await self.interaction.send(embed=embed, view=self)

    def get_embed(self):
        return self.pages[self.current_page]

    def update_view(self):
        choose_page_select = [i for i in self.children if i.custom_id == "choose_page"][0]
        for option in choose_page_select.options:
            option: SelectOption
            if option.value == self.current_page:
                option.default = True
            else:
                option.default = False

        back_btn = [i for i in self.children if i.custom_id == "back"][0]
        first_btn = [i for i in self.children if i.custom_id == "first"][0]
        if self.current_page == 0:
            back_btn.disabled = True
            first_btn.disabled = True
        else:
            back_btn.disabled = False
            first_btn.disabled = False
        next_btn = [i for i in self.children if i.custom_id == "next"][0]
        last_btn = [i for i in self.children if i.custom_id == "last"][0]
        if self.current_page == len(self.pages) - 1:
            next_btn.disabled = True
            last_btn.disabled = True
        else:
            next_btn.disabled = False
            last_btn.disabled = False

    @select(placeholder="Choose a page", options=[], custom_id="choose_page")
    async def choose_page(self, select: Select, interaction: Interaction):
        self.current_page = int(select.values[0])

        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="⏮️", style=ButtonStyle.blurple, custom_id="first", disabled=True)
    async def first(self, button: Button, interaction: Interaction):
        self.current_page = 0

        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="◀️", style=ButtonStyle.blurple, disabled=True, custom_id="back")
    async def back(self, button: Button, interaction: Interaction):
        self.current_page -= 1

        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="▶️", style=ButtonStyle.blurple, custom_id="next")
    async def next(self, button: Button, interaction: Interaction):
        self.current_page += 1

        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="⏭️", style=ButtonStyle.blurple, custom_id="last")
    async def last(self, button: Button, interaction: Interaction):
        self.current_page = len(self.pages) - 1

        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

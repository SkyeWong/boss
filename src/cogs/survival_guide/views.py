# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle, SelectOption
from nextcord.ui import Button, button, Select, select

# my modules
from utils import constants, helpers
from utils.constants import SCRAP_METAL, COPPER, EmbedColour
from utils.helpers import TextEmbed
from utils.template_views import BaseView

# default modules
from typing import Optional
import math


class HelpView(BaseView):
    """Displays a list of available commands in BOSS."""

    def __init__(
        self,
        interaction: Interaction,
        cmd_list: list[nextcord.SlashApplicationCommand] = None,
        with_select_menu: bool = True,
    ):
        """Initializes the HelpView.

        Args:
            slash_interaction: The interaction that triggered the view.
            cmd_list: A selected list of commands to display (for example, the subcommands of a command).
            with_select_menu: Whether to display the select menu for cogs. Should be turned off if only some commands are displayed.

        Raises:
            ValueError: If neither `mapping` nor `cmd_list` is provided.
        """

        super().__init__(interaction, timeout=90)

        # Set the mapping of cog names to lists of commands.
        if cmd_list is None:
            self.mapping = helpers.get_mapping(interaction, interaction.client)
            self.cmd_list = []
            for cog_name, (cog, commands) in self.mapping.items():
                self.cmd_list.extend(commands)
        else:
            self.cmd_list = cmd_list
            self.mapping = None

        cog_select_menu = [i for i in self.children if i.custom_id == "cog_select"][0]
        if with_select_menu:
            # set the options of the cog select menu
            options = self._get_cogs_options()
            cog_select_menu.options = options
            cog_select_menu.max_values = len(options)
            # Set the old selected values to ["All"].
            self.old_selected_values = ["All"]
        else:
            self.remove_item(cog_select_menu)

        # Set the initial page number to 1.
        self.page = 1

        # Set the number of commands per page to 6.
        self.cmd_per_page = 6

    def _get_cogs_options(self) -> list[SelectOption]:
        """Gets a list of SelectOption objects for the cogs.

        Returns:
            A list of SelectOption objects.
        """

        if not self.mapping:
            return

        # Create a list of SelectOption objects for the cogs.
        options = []

        # Add an "All" option to select every cog
        options.append(SelectOption(label="All", emoji="🌐", default=True))
        # Add an option for every cog in the mapping
        for cog_name in self.mapping:
            cog = self.mapping[cog_name][0]
            emoji = getattr(cog, "COG_EMOJI", None)
            options.append(
                SelectOption(
                    label=cog_name,
                    description=cog.description[:100] if cog.description else None,
                    emoji=emoji,
                    default=False,
                )
            )

        # Sort the options by label.
        options.sort(key=lambda x: x.label)

        return options

    def help_embed(
        self,
        description: Optional[str] = None,
        set_author: bool = True,
        author_name: str = "Commands",
    ) -> Embed:
        """Creates an embed with a list of all the commands in the bot.

        Args:
            description: Optional description to add to the embed.
            set_author: Whether to set the author of the embed.
            author_name: The name of the author of the embed.

        Returns:
            The created embed.
        """

        embed = Embed(description="", colour=EmbedColour.INFO)

        # If a description is provided, add it to the embed.
        if description:
            embed.description = description

        # If the author should be set, set the author of the embed to the bot's user.
        if set_author:
            avatar = self.interaction.client.user.avatar or self.interaction.client.user.default_avatar
            embed.set_author(name=author_name, icon_url=avatar.url)

        # Get a list of all the commands in the bot.
        command_list = sorted(self.cmd_list, key=lambda x: x.qualified_name)

        # Get the start and end indices of the current page of commands.
        start_index = self.get_page_start_index()
        end_index = self.get_page_end_index() + 1

        # Iterate over the commands on the current page.
        for cmd in command_list[start_index:end_index]:
            # Get the command's description.
            value = (
                f"\n<:reply:1117458829869858917> {cmd.description}"
                if cmd.description != "No description provided."
                else ""
            )

            # Get the command's name.
            name = f"**</{cmd.qualified_name}:{list(cmd.command_ids.values())[0]}>**"

            # If the command has subcommands, add a `has subcommands` suffix to the name.
            if len(cmd.children) > 0:
                name += " `has subcommands`"

            # Add the command (name and description) to the embed description
            embed.description += f"{name}{value}\n"

        # Set the footer of the embed with the current page number and the total number of pages.
        embed.set_footer(
            text=f"Page {self.page}/{math.ceil(len(self.cmd_list) / self.cmd_per_page)} • {len(command_list)} commands in total"
        )

        return embed

    async def send(self, *args, **kwargs):
        """Respond to the interaction by sending a message. *args and **kwargs will be passed to `HelpView.help_embed()`."""
        embed = self.help_embed(*args, **kwargs)
        # disable certain paginating buttons
        self.btn_disable()
        await self.interaction.send(embed=embed, view=self)

    def get_page_start_index(self):
        """
        Returns the start index of the current page of commands.
        For example, if `self.page` is 2 and `self.cmd_per_page` is 6, then the start index will be 6.
        """
        return (self.page - 1) * self.cmd_per_page

    def get_page_end_index(self):
        """
        Returns the end index of the current page of commands.

        For example, if `self.page` is 2 and `self.cmd_per_page` is 6, then the end index will be 11.
        """

        index = self.get_page_start_index() + self.cmd_per_page - 1
        return index if index < len(self.cmd_list) else len(self.cmd_list) - 1

    def btn_disable(self):
        """
        Updates the state of the buttons to disable the previous, current, and next buttons
        if they are not applicable.

        # - For example, if the first page is being shown, then the previous and back buttons will be disabled.
        # - If the last page is being shown, then the next and last buttons will be disabled.
        """

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

    async def get_embed_update_msg(self, interaction: Interaction, **kwargs):
        """
        Updates the embed with the current page of commands.

        The embed is created using the `help_embed()` method and then updated with the current page of commands.
        """

        embed = self.help_embed(**kwargs)
        await interaction.response.edit_message(embed=embed, view=self)

    @select(
        placeholder="Choose a category...",
        options=[],
        min_values=1,
        max_values=1,
        custom_id="cog_select",
    )
    async def select_cog(self, select: nextcord.ui.Select, interaction: Interaction):
        """
        Updates the commands displayed in the embed based on the selected cog.

        The selected cog is passed to the `help_embed()` method and the new embed is then displayed.
        """

        selected_values = select.values
        if "All" in [i for i in selected_values if i not in self.old_selected_values]:
            selected_values = ["All"]
        elif "All" in [i for i in self.old_selected_values if i in selected_values]:
            selected_values.remove("All")

        cmd_list = []
        if "All" in selected_values:
            for cog_name, (cog, commands) in self.mapping.items():
                cmd_list.extend(commands)
        else:
            for value in selected_values:
                cmd_list.extend(self.mapping[value][1])

        self.cmd_list = cmd_list
        self.page = 1
        # disable the buttons, and make the select menu "sticky"
        self.btn_disable()
        for option in select.options:
            option.default = False
            if option.label in selected_values:
                option.default = True

        await self.get_embed_update_msg(interaction)
        self.old_selected_values = selected_values

    @button(emoji="⏮️", style=nextcord.ButtonStyle.blurple, custom_id="first", disabled=True)
    async def first(self, button: Button, interaction: Interaction):
        """Displays the first page of commands"""
        self.page = 1
        self.btn_disable()
        await self.get_embed_update_msg(interaction)

    @button(emoji="◀️", style=nextcord.ButtonStyle.blurple, disabled=True, custom_id="back")
    async def back(self, button: Button, interaction: Interaction):
        """Displays the previous page of commands."""
        self.page -= 1
        self.btn_disable()
        await self.get_embed_update_msg(interaction)

    @button(emoji="▶️", style=nextcord.ButtonStyle.blurple, custom_id="next")
    async def next(self, button: Button, interaction: Interaction):
        """Displays the next page of commands."""
        self.page += 1
        self.btn_disable()
        await self.get_embed_update_msg(interaction)

    @button(emoji="⏭️", style=nextcord.ButtonStyle.blurple, custom_id="last")
    async def last(self, button: Button, interaction: Interaction):
        """Displays the last page of commands."""
        self.page = math.ceil(len(self.cmd_list) / self.cmd_per_page)
        self.btn_disable()
        await self.get_embed_update_msg(interaction)


class EmbedField:
    def __init__(self, name: str, value: str, inline: bool = False) -> None:
        self.name = name
        self.value = value
        self.inline = inline


class GuidePage(Embed):
    def __init__(
        self,
        title: str,
        description: str,
        fields: Optional[tuple[EmbedField]] = None,
        images: Optional[dict[str, str]] = None,
    ):
        super().__init__(title=title, description=description, colour=EmbedColour.INFO)
        if not images:
            images = []
        self.images = images
        if fields is not None:
            for field in fields:
                self.add_field(name=field.name, value=field.value, inline=field.inline)


class GuideView(BaseView):
    pages: list[GuidePage] = [
        GuidePage(
            title="Introduction",
            description="Welcome to BOSS, the bot for a **post-apocalyptic wasteland following World War III**. \n"
            "Scavenge for resources, complete missions, and participate in events to earn **valuable currency**. \n\n"
            "To start playing, use </help:964753444164501505> to view a list of available commands.",
        ),
        GuidePage(
            title="Currency System",
            description="In the world of BOSS, there are two main types of currency: scrap metal and copper. To check your current cash, use </balance:1100243620033994752>.",
            fields=[
                EmbedField(
                    f"Scrap Metal {SCRAP_METAL}",
                    "- The __basic currency__\n- Easy to find and earn, but has a relatively low value. ",
                ),
                EmbedField(
                    f"Copper {COPPER}",
                    "- The __valuable and versatile currency__\n"
                    "- Worth more than basic resources like scrap metal. \n"
                    f"- 1 copper is worth {constants.COPPER_SCRAP_RATE} scrap metals.",
                ),
                EmbedField(
                    f"Exchanging currencies",
                    "You can exchange the currencies using /exchange, but keep in mind that you will lose some value of your money.",
                ),
            ],
            images={
                "Checking your balance": "https://i.imgur.com/OHMF0PG.png",
                "Exchanging scrap metals to coppers": "https://i.imgur.com/2Kzr6QC.png",
            },
        ),
        GuidePage(
            title="How to survive",
            description="The ultimate guide to survive in BOSS.",
            fields=[
                EmbedField(
                    "By scavenging for resources",
                    "Use </hunt:1079601533215330415>, </dig:1079644728921948230>, </mine:1102561135988838410>, </scavenge:1107319706681098291> and more!\n"
                    "They have different rewards to help you grind, but decreases your hunger. When your hunger is below 30, every command run will have a slight delay.",
                ),
                EmbedField(
                    "By completing tasks and challenges",
                    "You can also earn currency by completing tasks and challenges. "
                    "Use the </missions:1107319711944941638> command to view available missions and track their progress.",
                ),
            ],
            images={
                "/scavenge": "https://i.imgur.com/CUCwYXI.png",
                "Checking and completing a mission": "https://i.imgur.com/YgrOEA9.gif",
            },
        ),
        GuidePage(
            title="Inventory System",
            description="In BOSS, there are 3 types of inventory where you can store items.",
            fields=[
                EmbedField(
                    "</backpack:1008017263540047872> 🎒",
                    "- The __every-day rucksack__ that you carry wherever you go. You sell, trade and do almost everything else with the items in it.\n"
                    "- It only has __32 slots__.\n"
                    "- When you die (either by running out of health/hunger), you lose a random item in your backpack.",
                ),
                EmbedField(
                    "</chest:1008017264118874112> 🧰",
                    "- The __crate__ that you store at home. You store most of your items in it and never really care about them.\n"
                    "- It has __infinite slots__.\n"
                    "- You may lose items in your chest if your base gets raided.",
                ),
                EmbedField(
                    "</vault:1008017264936755240> 🔒",
                    "- Your secret __safe__. Only your most valuable items own a place in it.\n"
                    "- It only has __5 slots__.\n"
                    "- Only you can view the contents of your own vault, and you will never lose any of them.",
                ),
                EmbedField(
                    "Transferring items",
                    "You can move items from 1 inventory type to other by </move-item:1008017265901437088>.\n"
                    "Keep note that it uses a few seconds.",
                ),
            ],
            images={"Viewing your inventory": "https://i.imgur.com/hPuwxb4.gif"},
        ),
        GuidePage(
            title="Manage your wealth",
            description="Use your currency to purchase goods and services. \n\n"
            "Use the /shop command to view available items and their prices, and use the /buy command to purchase items. \n"
            "You can also use the </trade:1102561137893056563> command to trade currency with virtual villagers, and acquire valuable resources to build your wealth. ",
            images={"Trading with villagers": "https://i.imgur.com/FyrT5Qy.gif"},
        ),
        GuidePage(
            title="Advanced: macros",
            description="You can run commands automatically (by clicking buttons, not by typing them in the chat) using a macro.",
            fields=[
                EmbedField(
                    "Adding a macro",
                    "You can either record a macro or import one to add them to your list.\n"
                    "\nTo record a macro, use </macro record:1124712041307979827>\n"
                    "> Then you can run commands as usual and they will be recorded!\n"
                    "> When you have finished running all the commands, stop the recording. Then enter a name for it.\n"
                    "> ⚠️ Note that you could not rename the macro afterwards.\n"
                    "\nTo import a macro, click the 'import' button in </macro list:1124712041307979827>\n"
                    "> Enter the ID of the macro. It should be 6 characters long and can have letters and digits.",
                ),
                EmbedField(
                    "Viewing your macros",
                    "Use </macro list:1124712041307979827>. A list of your macros will be shown. You can also remove them or import new ones.",
                ),
                EmbedField(
                    "Running your macros",
                    "Run the command </macro start:1124712041307979827> and choose the macro to start, or"
                    "Turn to the page with your macro and click the 'run' button in </macro list:1124712041307979827>.\n"
                    "You can then run the commands one by one by clicking the buttons."
                    "After you are finished, click the 'end' button.",
                ),
            ],
            images={
                "/macro list": "https://i.imgur.com/NXioI57.png",
                "/macro start": "https://i.imgur.com/5p5wlVd.gif",
                "/macro record": "https://i.imgur.com/hR3mp2v.gif",
            },
        ),
    ]

    def __init__(self, interaction: Interaction):
        super().__init__(interaction, timeout=180)
        self.current_page = 0
        self.msg: nextcord.WebhookMessage | nextcord.PartialInteractionMessage = None

        self.choose_page.options = []
        for index, page in enumerate(self.pages):
            self.choose_page.options.append(
                SelectOption(
                    label=f"{page.title} ({index + 1}/{len(self.pages)})",
                    value=index,
                    default=index == self.current_page,
                )
            )

    @classmethod
    async def send(cls, interaction: Interaction, page: int = 0):
        """Responds to the slash command interaction by sending a message."""
        view = cls(interaction)
        view.current_page = page
        embed = view.get_embed()
        view.update_view()
        view.msg = await interaction.send(embed=embed, view=view)

    def get_embed(self):
        """Returns the current guide page."""
        return self.pages[self.current_page]

    def update_view(self):
        """Update the view, disabling certain paginating buttons and making the select menu "sticky"."""
        for option in self.choose_page.options:
            option: SelectOption
            if option.value == self.current_page:
                option.default = True
            else:
                option.default = False

        if self.pages[self.current_page].images:
            self.show_images.disabled = False
        else:
            self.show_images.disabled = True

        if self.current_page == 0:
            self.back.disabled = True
            self.first.disabled = True
        else:
            self.back.disabled = False
            self.first.disabled = False
        if self.current_page == len(self.pages) - 1:
            self.next.disabled = True
            self.last.disabled = True
        else:
            self.next.disabled = False
            self.last.disabled = False

    async def update_message(self, interaction: Interaction):
        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @select(placeholder="Choose a page", options=[], custom_id="choose_page")
    async def choose_page(self, select: Select, interaction: Interaction):
        """Choose a specific page of the guide through a select menu."""
        self.current_page = int(select.values[0])
        await self.update_message(interaction)

    @button(emoji="⏮️", style=ButtonStyle.blurple, custom_id="first", disabled=True)
    async def first(self, button: Button, interaction: Interaction):
        self.current_page = 0
        await self.update_message(interaction)

    @button(emoji="◀️", style=ButtonStyle.blurple, disabled=True, custom_id="back")
    async def back(self, button: Button, interaction: Interaction):
        self.current_page -= 1
        await self.update_message(interaction)

    @button(emoji="🖼️", style=ButtonStyle.blurple, custom_id="show_image")
    async def show_images(self, button: Button, interaction: Interaction):
        view = ChooseImageView(interaction, self.pages[self.current_page].images)
        view.update_view()
        await interaction.send(embed=view.get_embed(), view=view, ephemeral=True)

    @button(emoji="▶️", style=ButtonStyle.blurple, custom_id="next")
    async def next(self, button: Button, interaction: Interaction):
        self.current_page += 1
        await self.update_message(interaction)

    @button(emoji="⏭️", style=ButtonStyle.blurple, custom_id="last")
    async def last(self, button: Button, interaction: Interaction):
        self.current_page = len(self.pages) - 1
        await self.update_message(interaction)


class ChooseImageView(BaseView):
    def __init__(self, interaction: Interaction, images: dict[str]):
        super().__init__(interaction, timeout=180)
        self.images = images
        self.msg: nextcord.WebhookMessage | nextcord.PartialInteractionMessage = None

        self.current_img = list(images.keys())[0]

        self.choose_image.options = []
        for title in self.images.keys():
            self.choose_image.options.append(SelectOption(label=title))

    def get_embed(self):
        """Returns the current guide page."""
        embed = Embed(title=self.current_img, colour=EmbedColour.DEFAULT)
        embed.set_image(self.images[self.current_img])
        return embed

    def update_view(self):
        """Update the view, disabling certain paginating buttons and making the select menu "sticky"."""
        for option in self.choose_image.options:
            if option.label == self.current_img:
                option.default = True
            else:
                option.default = False

    @select(placeholder="Choose an image", options=[])
    async def choose_image(self, select: Select, interaction: Interaction):
        """Choose a specific image through a select menu."""
        self.current_img = select.values[0]
        embed = self.get_embed()
        self.update_view()
        await interaction.response.edit_message(view=self, embed=embed)

# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle
from nextcord.ui import View, Button, button, Modal, TextInput

# my modules and constants
from utils import constants, helpers
from utils.helpers import TextEmbed

# default modules
from typing import Optional, Callable


class BaseView(View):

    """A template view for the bot with on_timeout and interaction_check methods."""

    def __init__(self, interaction: Interaction, *, timeout=None):
        super().__init__(timeout=timeout)
        self.interaction = interaction

    async def on_timeout(self) -> None:
        for i in self.children:
            i.disabled = True
        await self.interaction.edit_original_message(view=self)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user != self.interaction.user:
            msg = "This is not for you, sorry."

            if command := self.interaction.application_command:
                msg += f"\nUse </{command.qualified_name}:{list(command.command_ids.values())[0]}>"
            await interaction.send(
                embed=TextEmbed(msg),
                ephemeral=True,
            )
            return False
        else:
            return True


class ConfirmView(BaseView):
    def __init__(
        self,
        *,
        slash_interaction: Interaction,
        confirm_func=None,
        cancel_func=None,
        embed: Embed,
        confirmed_title: str = "Action confirmed!",
        cancelled_title: str = "Action cancelled!",
        **kwargs,
    ):
        super().__init__(interaction=slash_interaction)

        self.embed = embed

        self.confirm_func = confirm_func
        self.cancel_func = cancel_func

        self.confirmed_title = confirmed_title
        self.cancelled_title = cancelled_title

        self.kwargs = kwargs
        self.interaction.attached.__dict__.update(**kwargs)

    async def confirm(self, button: Button, interaction: Interaction):
        embed = interaction.message.embeds[0]
        embed.title = self.confirmed_title

        button.style = ButtonStyle.green
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    async def cancel(self, button: Button, interaction: Interaction):
        embed = interaction.message.embeds[0]
        embed.title = self.cancelled_title

        button.style = ButtonStyle.red
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @button(emoji="✅", style=ButtonStyle.blurple)
    async def confirm_callback(self, button: Button, interaction: Interaction):
        interaction.attached.__dict__.update(**self.interaction.attached)
        await self.confirm(button, interaction)
        if self.confirm_func:
            await self.confirm_func(button, interaction)

    @button(emoji="❎", style=ButtonStyle.blurple)
    async def cancel_callback(self, button: Button, interaction: Interaction):
        interaction.attached.__dict__.update(**self.interaction.attached)
        await self.cancel(button, interaction)
        if self.cancel_func:
            await self.cancel_func(button, interaction)


class BaseModal(Modal):
    """A template modal for the bot."""

    def __init__(
        self,
        title: str,
        inputs: list[TextInput],
        callback: Callable,
        timeout: Optional[int] = 3 * 60,  # three minutes
    ):
        """Generates a nextcord modal which lets users input values.

        Args:
            title (str): Title of the modal
            inputs (list[TextInput]): A list of TextInputs for the modal. It is recommended to set their `custom_id`
            callback (Callable): The callback which takes the modal and the interaction as parameters
            timeout (int, optional): The time in seconds before the modal stops responding. Defaults to None.
        """
        super().__init__(title=title, timeout=timeout)
        for input in inputs:
            self.add_item(input)
        self.callback = callback

    async def on_timeout(self) -> None:
        return await super().on_timeout()

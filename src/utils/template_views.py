# default modules
from contextlib import suppress
from typing import Callable, Literal, Optional

# nextcord
import nextcord
from nextcord import ButtonStyle, Embed
from nextcord.ui import Button, Modal, TextInput, View, button

from utils.helpers import BossInteraction

# my modules and constants
from utils.player import Player


class BaseView(View):

    """A template view for the bot with on_timeout and interaction_check methods."""

    def __init__(self, interaction: BossInteraction, *, timeout=None):
        super().__init__(timeout=timeout)
        self.interaction = interaction

    async def on_timeout(self) -> None:
        for i in self.children:
            i.disabled = True
        with suppress(nextcord.errors.NotFound):  # the message might have been deleted
            await self.interaction.edit_original_message(view=self)

    async def interaction_check(self, interaction: BossInteraction) -> bool:
        if interaction.user == self.interaction.user:
            return True
        # If the interaction is triggered by a command, include the command in the message as well.
        if command := self.interaction.application_command:
            cmd_mention = command.get_mention(interaction.guild) + " "
        else:
            cmd_mention = ""
        msg = f"This {cmd_mention}menu is controlled by {self.interaction.user.mention}. Run the command yourself."
        await interaction.send_text(msg, ephemeral=True)
        return False


class ConfirmView(BaseView):
    @staticmethod
    async def _void(*args, **kwargs):
        return None

    def __init__(
        self,
        *,
        interaction: BossInteraction,
        confirm_func: Callable = _void,
        cancel_func: Callable = _void,
        embed: Embed,
        confirmed_title: str = "Action confirmed!",
        cancelled_title: str = "Action cancelled!",
        **kwargs,
    ):
        super().__init__(interaction=interaction)
        self.player = Player(interaction.client.db, interaction.user)

        self.embed = embed

        self.confirm_func = confirm_func
        self.cancel_func = cancel_func

        self.confirmed_title = confirmed_title
        self.cancelled_title = cancelled_title

        self.kwargs = kwargs
        self.interaction.attached.__dict__.update(**kwargs)

    async def send(self):
        message = await self.interaction.send(embed=self.embed, view=self)
        await self.player.set_in_inter(True)
        return message

    async def _btn_response(
        self, interaction: BossInteraction, action: Literal["confirm", "cancel"]
    ):
        if action not in {"confirm", "cancel"}:
            raise ValueError("Action must be one of 'confirm' or 'cancel'.")

        interaction.attached.update(self.interaction.attached)
        # Update the messsage
        embed = interaction.message.embeds[0]
        embed.title = self.confirmed_title if action == "confirm" else self.cancelled_title
        button = [i for i in self.children if i.custom_id == action][0]
        button.style = ButtonStyle.green
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(embed=embed, view=self)

        # run either the confirmed or cancelled function
        if action == "confirm":
            await self.confirm_func(button, interaction)
        else:
            await self.cancel_func(button, interaction)

        if not interaction.response.is_done():  # the interaction has not been responded
            await interaction.response.defer()
        await self.player.set_in_inter(False)

    @button(emoji="✅", style=ButtonStyle.blurple, custom_id="confirm")
    async def confirm_callback(self, button: Button, interaction: BossInteraction):
        await self._btn_response(interaction, "confirm")

    @button(emoji="❎", style=ButtonStyle.blurple, custom_id="cancel")
    async def cancel_callback(self, button: Button, interaction: BossInteraction):
        await self._btn_response(interaction, "cancel")


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

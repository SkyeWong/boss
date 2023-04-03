# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle
from nextcord.ui import View, Button, button

# default modules
import random

# my modules and constants
from utils import constants


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
            command = self.interaction.application_command
            await interaction.send(
                embed=Embed(
                    description=f"This is not for you, sorry.\nUse </{command.qualified_name}:{list(command.command_ids.values())[0]}>",
                ),
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
        embed_content: str = "",
        embed_fields: tuple = (),
        confirmed_title="Action confirmed!",
        cancelled_title="Action cancelled!",
        **kwargs,
    ):
        super().__init__(interaction=slash_interaction)
        self.embed_content = embed_content
        self.embed_fields = embed_fields

        self.confirm_func = confirm_func
        self.cancel_func = cancel_func

        self.confirmed_title = confirmed_title
        self.cancelled_title = cancelled_title

        self.kwargs = kwargs
        self.interaction.attached.__dict__.update(**kwargs)

    async def confirm(self, button: Button, interaction: Interaction):
        embed = self.get_embed(self.confirmed_title)
        button.style = ButtonStyle.green
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    async def cancel(self, button: Button, interaction: Interaction):
        embed = self.get_embed(self.cancelled_title)
        button.style = ButtonStyle.red
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    def get_embed(self, title="Pending Confirmation", content=None, fields=None):
        embed = Embed()
        embed.title = title
        if not content:
            if self.embed_content:
                embed.description = self.embed_content
        if not fields:
            if self.embed_fields:
                for field in self.embed_fields:
                    inline = True
                    if len(field) == 3:
                        name, value, inline = field
                    else:
                        name, value = field
                    embed.add_field(name=name, value=value, inline=inline)
        embed.colour = random.choice(constants.EMBED_COLOURS)
        if image := self.kwargs.get("embed_image"):
            embed.set_image(image)
        if thumbnail := self.kwargs.get("embed_thumbnail"):
            embed.set_thumbnail(thumbnail)
        return embed

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

# default modules
import json

# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle, ApplicationCommandOptionType as OptionType
from nextcord.ui import Button, button, TextInput

# my modules
from utils import helpers
from utils.constants import EmbedColour
from utils.helpers import TextEmbed
from utils.template_views import BaseView, ConfirmView, BaseModal


class ShowMacrosView(BaseView):
    """A view to let users view their list of macros, remove them, or import a foreign macro with the ID."""

    def __init__(self, interaction: Interaction, macro_ids: list[str]):
        super().__init__(interaction, timeout=3 * 60)  # 3 minutes
        self.current_page = 0  # stores the current page/macro in display
        self.macro_ids: list[str] = macro_ids  # a list of macro_ids of the user

        # cache to store values of the macros displayed
        self.macros: dict = {}
        # stores the message sent, which can then be edited.
        self.msg: nextcord.WebhookMessage | nextcord.PartialInteractionMessage = None

    @classmethod
    async def send(cls, interaction: Interaction):
        """Responds to the slash command interaction by sending a message."""
        # Select all the macros of the players
        user_macros = await interaction.client.db.fetch(
            """
            SELECT macro_id
            FROM players.macro_players
            WHERE player_id = $1
            """,
            interaction.user.id,
        )

        view = cls(interaction, [i[0] for i in user_macros])
        # Update the view and send it along with the embed
        view.update_view()
        embed = await view._get_embed(interaction)
        view.msg = await interaction.send(embed=embed, view=view)

    async def update_msg(self, interaction: Interaction):
        """Update the message of the view. Reloads the view and embed, but not data from the database."""
        self.update_view()
        embed = await self._get_embed(interaction)
        if not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self.msg.edit(embed=embed, view=self)

    async def _get_embed(self, interaction: Interaction):
        """Returns an embed showing all the commands stored in the macro."""
        if not self.macro_ids:
            # If the user has no macros, send them a message telling them what to do
            return TextEmbed(
                "You don't have any saved marcos.\nUse </macro record:1124712041307979827>, or import a macro."
            )

        embed = Embed(title="Marcos", colour=EmbedColour.DEFAULT)
        macro_name, macro_commands = await self._get_macro()
        embed.description = f"### {macro_name}\n"
        # `macro_commands` have the following structure:
        #   [
        #       {'command': 'scavenge', 'options': {}},
        #       {'command': 'balance', 'options': {'user': '806334528230129695'}}
        #   ]
        # cmd["command"] stores the full name of the command ([parent names] + cmd name)
        # cmd["options"] stores the options passed into the command (which may be optional)
        for index, i in enumerate(macro_commands):
            cmd = helpers.find_command(
                interaction.client, i["command"]
            )  # search for the command with the name
            # make a message denoting the options
            if i["options"]:
                options_msg = []
                for name, value in i["options"].items():
                    if cmd.options[name].type == OptionType.user.value:
                        user = await interaction.client.get_or_fetch_user(value)
                        value = user.mention
                    options_msg.append(f"{name}: {value}")
                options_msg = ", ".join(options_msg)
                options_msg = f"[{options_msg}]"
            else:
                options_msg = ""

            try:
                cmd_msg = f"{cmd.get_mention(interaction.guild)} {options_msg}"
            except ValueError:  # command can not be run in the current server
                cmd_msg = f"/{i['command']} (can not be run in this sever)"
            embed.description += f"\n{index + 1}. {cmd_msg}"

        embed.set_footer(
            text=f"ID: {self.macro_ids[self.current_page].upper()} • Page {self.current_page + 1}/{len(self.macro_ids)}\n"
            "Add macros using /macro record or by importing one"
        )
        return embed

    async def _get_macro(self):
        """Fetch the name and commands (w/ cmd options) of the macro with the given ID."""
        macro_id = self.macro_ids[self.current_page]
        if macro := self.macros.get(macro_id):
            return macro
        macro = await self.interaction.client.db.fetch(
            """
                SELECT m1.name, command_name, options
                FROM players.macro_commands AS mc
                INNER JOIN (
                    SELECT m.name, mp.macro_id
                    FROM players.macro_players AS mp
                    INNER JOIN players.macros AS m
                    ON m.macro_id = mp.macro_id
                    WHERE mp.player_id = $1 AND m.macro_id = $2
                    LIMIT 1
                ) AS m1
                ON mc.macro_id = m1.macro_id
                ORDER BY mc.sequence
            """,
            self.interaction.user.id,
            macro_id,
        )
        # Update the cache
        name = macro[0]["name"]
        cmds = [{"command": i["command_name"], "options": json.loads(i["options"])} for i in macro]
        self.macros[macro_id] = (name, cmds)
        return name, cmds

    def update_view(self):
        """Update the view and disable certain paginating buttons."""
        # If the user has no macros, only show the "import" button
        if not self.macro_ids:
            self.clear_items()
            self.add_item(self.import_macro)
            return
        # Disable the paginating buttons according to the current page
        if self.current_page == 0:
            self.back.disabled = True
            self.first.disabled = True
        else:
            self.back.disabled = False
            self.first.disabled = False
        if self.current_page == len(self.macro_ids) - 1:
            self.next.disabled = True
            self.last.disabled = True
        else:
            self.next.disabled = False
            self.last.disabled = False

    @button(emoji="⏮️", style=ButtonStyle.blurple, custom_id="first", disabled=True)
    async def first(self, button: Button, interaction: Interaction):
        self.current_page = 0
        await self.update_msg(interaction)

    @button(emoji="◀️", style=ButtonStyle.blurple, disabled=True, custom_id="back")
    async def back(self, button: Button, interaction: Interaction):
        self.current_page -= 1
        await self.update_msg(interaction)

    @button(emoji="🔄", style=ButtonStyle.blurple, custom_id="reload")
    async def reload(self, button: Button, interaction: Interaction):
        user_macros = await interaction.client.db.fetch(
            """
                SELECT macro_id
                FROM players.macro_players
                WHERE player_id = $1
            """,
            interaction.user.id,
        )
        self.macro_ids = [i[0] for i in user_macros]
        self.macros = {}  # delete cache
        await self.update_msg(interaction)

    @button(emoji="▶️", style=ButtonStyle.blurple, custom_id="next")
    async def next(self, button: Button, interaction: Interaction):
        self.current_page += 1
        await self.update_msg(interaction)

    @button(emoji="⏭️", style=ButtonStyle.blurple, custom_id="last")
    async def last(self, button: Button, interaction: Interaction):
        self.current_page = len(self.macro_ids) - 1
        await self.update_msg(interaction)

    @button(label="Start", style=ButtonStyle.grey, custom_id="start")
    async def start(self, button: Button, interaction: Interaction):
        """Start the current macro"""
        client: nextcord.Client = interaction.client
        all_cmds = client.get_all_application_commands()
        # Find the /macro start command,
        # then run it with the name of the current macro
        macro_cmd = next(i for i in all_cmds if i.name == "macro")
        start_cmd = next(i for i in macro_cmd.children.values() if i.name == "start")
        name, _ = await self._get_macro()
        await start_cmd.invoke_callback_with_hooks(
            macro_cmd._state, interaction, kwargs={"macro": name}
        )

    @button(label="Remove", style=ButtonStyle.grey, custom_id="remove")
    async def remove(self, button: Button, interaction: Interaction):
        """Removes the macro from the user's list, and delete it from the database if no other user is using it."""

        async def delete_macro(button: Button, btn_inter: Interaction):
            # Delete the macro from the user's list
            self.macro_ids.remove(macro_to_delete)  # local list
            await interaction.client.db.execute(  # foreign (database) list
                """
                DELETE FROM players.macro_players
                WHERE player_id = $1 AND macro_id = $2 
                """,
                interaction.user.id,
                macro_to_delete,
            )
            # Delete the confirmation message
            msg = await interaction.original_message()
            await msg.delete()

            await btn_inter.send(
                embed=TextEmbed(f"Successfully removed the macro **{name}**!"), ephemeral=True
            )
            # Reset the current page to 0, in case the new "page" may not be available (because the last macro is deleted)
            self.current_page = 0
            await self.update_msg(interaction)

            # Delete the macro from the `players.macros` list if no other user is using it
            await interaction.client.db.execute(
                """
                DELETE FROM players.macros AS m
                WHERE 
                    m.macro_id = $1 AND 
                    (SELECT COUNT(*) FROM players.macro_players AS mp WHERE mp.macro_id = $1) = 0
                """,
                macro_to_delete,
            )

        name, _ = await self._get_macro()
        macro_to_delete = self.macro_ids[self.current_page]
        # Send a message to let users confirm/cancel deleting the macro
        embed = TextEmbed(f"Remove the marco **{name}**?")
        await ConfirmView(interaction=interaction, embed=embed, confirm_func=delete_macro).send()

    @button(label="Import", style=ButtonStyle.grey, custom_id="import")
    async def import_macro(self, button: Button, interaction: Interaction):
        """Import a macro with the given ID."""

        async def modal_callback(modal_inter: Interaction):
            hashed_id = [i for i in modal.children if i.custom_id == "id"][0].value
            # fetch the macro with the given ID from the database
            res = await interaction.client.db.fetchrow(
                """
                SELECT m1.macro_id, m1.name, m2.player_id
                FROM players.macros AS m1
                LEFT JOIN (
                    SELECT player_id, macro_id FROM players.macro_players WHERE player_id = $1
                ) AS m2
                ON m1.macro_id = m2.macro_id
                WHERE m1.macro_id = $2
                """,
                interaction.user.id,
                hashed_id.strip().lower(),
            )

            # perform some checks before inserting the macro into the user's list
            if res is None:
                await modal_inter.send(
                    embed=TextEmbed(
                        "The macro with the given ID does not exist.", EmbedColour.WARNING
                    ),
                    ephemeral=True,
                )
                return
            if res["player_id"] is not None:
                await modal_inter.send(
                    embed=TextEmbed("You already own the macro.", EmbedColour.WARNING),
                    ephemeral=True,
                )
                return

            await interaction.client.db.execute(
                """
                INSERT INTO players.macro_players (player_id, macro_id)
                VALUES ($1, $2)
                """,
                interaction.user.id,
                res["macro_id"],
            )
            await modal_inter.send(
                embed=TextEmbed(f"Successfully imported the macro **{res['name']}**!"),
                ephemeral=True,
            )

            # We want to create a new view since if the user did not have any macros previously,
            # the view will only have the "import" button.
            # Then `view.update_view()` will not work.
            # We also don't want to re-add the buttons to the view again.
            view = self.__class__(
                interaction, self.macro_ids + [res["macro_id"]]
            )  # append the imported macro
            view.update_view()
            embed = await view._get_embed(interaction)
            view.msg = await self.msg.edit(embed=embed, view=view)

        modal = BaseModal(
            title="Importing a macro",
            inputs=[
                TextInput(label="ID", required=True, custom_id="id"),
            ],
            callback=modal_callback,
        )
        await interaction.response.send_modal(modal)

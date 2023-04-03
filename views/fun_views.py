# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle, SelectOption
from nextcord.ui import View, Button, button, Select, select

# default modules
import random
import math

# my modules and constants
from utils import constants
from views.template_views import BaseView


class FightPlayer:
    def __init__(self, user: nextcord.User, hp=100):
        self.user = user
        self.hp = hp


class FightView(BaseView):
    def __init__(self, slash_interaction: Interaction, player1: FightPlayer, player2: FightPlayer):
        super().__init__(interaction=slash_interaction)
        self.players = [player1, player2]
        self._round = 0

    def _next_round(self):
        self._round += 1

    def get_round(self):
        return self._round % 2

    def get_embed(self):
        embed = Embed()
        embed.set_author(name="Fight ⚔️")

        embed.description = f"`{self.players[self.get_round()].user.name}`'s round"
        for player in self.players:
            embed.add_field(name=player.user.name, value=player.hp)
        return embed

    @button(emoji="👊🏻", style=nextcord.ButtonStyle.blurple)
    async def hit(self, button: Button, interaction: Interaction):
        round = self.get_round()
        enemy = self.players[round - 1]
        enemy.hp -= random.randint(25, 50)

        msg: nextcord.Message = self.msg
        if enemy.hp <= 0:
            enemy.hp = 0
            button.disabled = True
            await msg.edit(
                content=f"{self.players[round].user.name} won!",
                embed=self.get_embed(),
                view=self,
            )
            return

        self._next_round()
        await msg.edit(embed=self.get_embed())

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user == self.players[self.get_round()].user:
            return True
        elif [player for player in self.players if player.user == interaction.user]:
            await interaction.send("It is not your round yet!", ephemeral=True)
            return False
        else:
            await interaction.send("This is not for you", ephemeral=True)
            return False


class EmojiView(BaseView):
    def __init__(self, slash_interaction: Interaction, emojis: list[nextcord.Emoji]):
        super().__init__(interaction=slash_interaction, timeout=300)
        self.emojis = emojis

        self._page = 0
        self.update_select_options()

        self.emoji_index = 0

    @property
    def displayed_emojis(self):
        return self.emojis[25 * self._page : 25 * (self._page + 1)]

    @property
    def page(self):
        return self._page

    @page.setter
    def page(self, new_page):
        self._page = new_page
        self.update_select_options()
        return self._page

    def update_select_options(self):
        emoji_select = [i for i in self.children if i.custom_id == "emoji_select"][0]
        emoji_select.options = [
            SelectOption(label=emoji.name, value=index, emoji=emoji)
            for index, emoji in enumerate(self.displayed_emojis)
        ]

    def get_embed(self):
        embed = Embed()
        embed.set_author(
            name="Emoji Searcher:",
            icon_url=self.interaction.client.user.display_avatar.url,
        )

        emojis = self.displayed_emojis
        page = self.emoji_index

        emoji: nextcord.Emoji = emojis[page]

        embed.colour = random.choice(constants.EMBED_COLOURS)
        embed.set_footer(
            text=f"Page {page + 1}/{len(emojis)} • List {self.page + 1}/{math.ceil(len(self.emojis) / 25)}"
        )  # + 1 because self.page uses zero-indexing
        embed.set_thumbnail(url=emoji.url)

        embed.title = f"`{page + 1}` - click for emoji"
        embed.url = emoji.url
        embed.description = str(emoji)

        embed.add_field(
            name=f"\:{emoji.name}:",
            value=f">>> ➼ `Name` - \:{emoji.name}:"
            f"\n➼ `Guild` - {emoji.guild.name}"
            f"\n➼ `ID`    - {emoji.id}"
            f"\n➼ `Url`   - [{emoji.url}]({emoji.url})"
            f"\n➼ `Mention syntax` - \{str(emoji)}",
        )
        return embed

    def disable_buttons(self):
        back_btn = [i for i in self.children if i.custom_id == "back"][0]
        first_btn = [i for i in self.children if i.custom_id == "first"][0]
        if self.emoji_index == 0:
            back_btn.disabled = True
            first_btn.disabled = True
        else:
            back_btn.disabled = False
            first_btn.disabled = False

        next_btn = [i for i in self.children if i.custom_id == "next"][0]
        last_btn = [i for i in self.children if i.custom_id == "last"][0]
        if self.emoji_index == len(self.displayed_emojis) - 1:
            next_btn.disabled = True
            last_btn.disabled = True
        else:
            next_btn.disabled = False
            last_btn.disabled = False

        less_btn = [i for i in self.children if i.custom_id == "less"][0]
        if self.page == 0:
            less_btn.disabled = True
        else:
            less_btn.disabled = False

        more_btn = [i for i in self.children if i.custom_id == "more"][0]
        if self.page == math.ceil(len(self.emojis) / 25) - 1:
            more_btn.disabled = True
        else:
            more_btn.disabled = False

    @select(placeholder="Choose an emoji...", custom_id="emoji_select")
    async def choose_video(self, select: Select, interaction: Interaction):
        self.emoji_index = int(select.values[0])  # the value is set to the index of the emoji

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="⏮️", style=ButtonStyle.blurple, custom_id="first", disabled=True)
    async def first(self, button: Button, interaction: Interaction):
        self.emoji_index = 0

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="◀️", style=ButtonStyle.blurple, disabled=True, custom_id="back")
    async def back(self, button: Button, interaction: Interaction):
        self.emoji_index -= 1

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="▶️", style=ButtonStyle.blurple, custom_id="next")
    async def next(self, button: Button, interaction: Interaction):
        self.emoji_index += 1

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="⏭️", style=ButtonStyle.blurple, custom_id="last")
    async def last(self, button: Button, interaction: Interaction):
        self.emoji_index = len(self.displayed_emojis) - 1

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(label="Less", style=ButtonStyle.gray, custom_id="less", row=2)
    async def less(self, button: Button, interaction: Interaction):
        self.page -= 1
        self.emoji_index = 0  # reset the page because its a new page

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(label="More", style=ButtonStyle.gray, custom_id="more", row=2)
    async def more(self, button: Button, interaction: Interaction):
        self.page += 1
        self.emoji_index = 0  # reset the page because its a new page

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

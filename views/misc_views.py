# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle, SelectOption
from nextcord.ui import View, Button, button, Select, select

# my modules
from utils import constants, functions
from utils.constants import SCRAP_METAL, COPPER
from utils.functions import TextEmbed
from views.template_views import BaseView

from numerize import numerize
import pytz

# default modules
import datetime
from typing import Optional
import enum
import html
import random
import math


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
                while not isinstance(parent_cmd, nextcord.BaseApplicationCommand):
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

    async def get_embed_update_msg(self, interaction: Interaction, **kwargs):
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
        await self.get_embed_update_msg(interaction)
        self.old_selected_values = selected_values

    @button(emoji="⏮️", style=nextcord.ButtonStyle.blurple, custom_id="first", disabled=True)
    async def first(self, button: Button, interaction: Interaction):
        self.page = 1
        self.btn_disable()
        await self.get_embed_update_msg(interaction)

    @button(emoji="◀️", style=nextcord.ButtonStyle.blurple, disabled=True, custom_id="back")
    async def back(self, button: Button, interaction: Interaction):
        self.page -= 1
        self.btn_disable()
        await self.get_embed_update_msg(interaction)

    @button(emoji="▶️", style=nextcord.ButtonStyle.blurple, custom_id="next")
    async def next(self, button: Button, interaction: Interaction):
        self.page += 1
        self.btn_disable()
        await self.get_embed_update_msg(interaction)

    @button(emoji="⏭️", style=nextcord.ButtonStyle.blurple, custom_id="last")
    async def last(self, button: Button, interaction: Interaction):
        self.page = math.ceil(len(self.cmd_list) / self.cmd_per_page)
        self.btn_disable()
        await self.get_embed_update_msg(interaction)


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
            f"\n➼ `Mention syntax` - ` {str(emoji)} `",
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

    @button(label="Previous list", style=ButtonStyle.gray, custom_id="less", row=2)
    async def less(self, button: Button, interaction: Interaction):
        self.page -= 1
        self.emoji_index = 0  # reset the page because its a new page

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(label="Next list", style=ButtonStyle.gray, custom_id="more", row=2)
    async def more(self, button: Button, interaction: Interaction):
        self.page += 1
        self.emoji_index = 0  # reset the page because its a new page

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)


class TriviaQuestion:
    __slots__ = (
        "question",
        "correct_answer",
        "incorrect_answers",
        "category",
        "difficulty",
    )

    def __init__(
        self,
        question: str,
        correct_answer: str,
        incorrect_answers: list[str],
        category: str,
        difficulty: str,
    ) -> None:
        self.question = html.unescape(question)
        if len(question) > 100:
            raise functions.ComponentLabelTooLong(f"Question `{question}` is too long.")

        self.correct_answer = html.unescape(correct_answer)
        if len(correct_answer) > 50:
            raise functions.ComponentLabelTooLong(f"Label of `{correct_answer}` is too long.")

        self.incorrect_answers = [html.unescape(i) for i in incorrect_answers]
        if any([len(i) > 50 for i in self.incorrect_answers]):
            raise functions.ComponentLabelTooLong(f"Label of an incorrect_answer is too long.")

        self.category = category
        self.difficulty = difficulty


class TriviaAnswerButton(Button):
    def __init__(self, label: str):
        super().__init__(label=label)

    async def callback(self, interaction: Interaction):
        await interaction.response.defer()

        view: TriviaView = self.view

        if self.label == view.question.correct_answer:  # the user got the question correct
            self.style = ButtonStyle.green

            msgs = (
                "You got that correct, somehow...",
                "You must have got lucky. How could you got it right otherwise?",
                "Stop, you smart-aleck. Didn't you guess it?",
                "You are bound to get lucky sometimes, ig.",
                "When you get one question right finally after 10+ trials",
                "That's a once-in-a-lifetime coincidence... \nCherish it bcs you'll never get it again.",
                "Who knew that guessing randomly could be such a successful strategy?",
                "Well done, you truly are a master of the game of chance.",
                "Luck was clearly on your side today. Maybe you should consider buying a lottery ticket.",
                "Impressive win, I had no idea that guessing could be such a valuable skill in a trivia game.",
                "I'm sure your, uh, extensive knowledge of the topic had nothing to do with it",
                "You must have a sixth sense for this kind of thing. Or maybe you just got lucky. \nThe latter is far more likely.",
                "You just closed your eyes and picked an answer at random, it's pure luck.",
            )
            msg = random.choice(msgs)  # choose a random msg
        else:  # the user got the question wrong
            self.style = ButtonStyle.red

            msgs = (
                "You dunderhead, that wasn't even hard...",
                "Shame you didn't have your smart panties on.",
                "No wonder you have an IQ lower than that of a dog.",
                "Everyone is ashamed of you.",
                "Could it get easier? Still, you got it wrong.",
                "Fits you to get it wrong, you're unicellular.",
                "Even an amoeba would have got it right.",
                "Sodium said '_na..._' to your answer.\n Bet you didn't get that.",
                "Better luck next time.",
                "Nice try, that was.",
                "You've managed to achieve a new level of incompetence.",
                "I'm impressed, you've managed to achieve a perfect score...for wrong answers.",
                "I'm sure your participation trophy is in the mail. Keep an eye out for it!",
                "Better luck next time, champ. Or maybe just bring a lifeline or two.",
            )
            msg = f"{random.choice(msgs)}\nThe correct answer was _{view.question.correct_answer}_."  # choose a random msg and append it with the correct answer

            # set the correct answer's button to green
            correct_btn = [i for i in view.children if i.label == view.question.correct_answer][0]
            correct_btn.style = ButtonStyle.green

        # disable all buttons
        for i in view.children:
            i.disabled = True
        # add a new embed with the msg to the message
        view.message.embeds.append(TextEmbed(msg))
        await view.message.edit(embeds=view.message.embeds, view=view)
        # set the view to be done so that on_timeout() will not edit the message again.
        view.is_done = True


class TriviaView(BaseView):
    def __init__(self, interaction: Interaction, question: TriviaQuestion):
        timeouts = {
            "easy": 15,
            "medium": 12,
            "hard": 10,
        }  # timeouts with respect to difficulty of the question
        super().__init__(interaction, timeout=timeouts.get(question.difficulty))

        self.question = question

        answers = question.incorrect_answers + [question.correct_answer]
        # make the order of answers random so that the correct answer will not always appear at the same place
        random.shuffle(answers)

        for ans in answers:
            self.add_item(TriviaAnswerButton(ans))

        self.message: nextcord.PartialInteractionMessage | nextcord.WebhookMessage = None

        self.is_done = False

    def _get_embed(self):
        embed = Embed()
        embed.colour = random.choice(constants.EMBED_COLOURS)
        embed.title = self.question.question
        embed.description = f"_You have {self.timeout} seconds to answer._"

        embed.add_field(name="Difficulty", value=self.question.difficulty.title())
        embed.add_field(name="Category", value=self.question.category.title())

        return embed

    async def send(self):
        embed = self._get_embed()
        self.message = await self.interaction.send(embed=embed, view=self)

    async def on_timeout(self):
        if not self.is_done:
            await super().on_timeout()
            embed = self.message.embeds[0]
            await self.message.edit(
                embeds=[
                    embed,
                    TextEmbed("Guess you didn't want to play the trivia after all?"),
                ]
            )


def get_weather_view(self, forecast):
    view = View()

    situation_btn = Button(label="Current Situation")

    async def send_situation(interaction: Interaction):
        await interaction.send(
            embed=Embed(
                title=f"Current Situation - <t:{int(forecast[0].timestamp())}:f>",
                description=forecast[1],
            ),
            ephemeral=True,
        )

    situation_btn.callback = send_situation
    view.add_item(situation_btn)

    outlook_btn = Button(label="Future Outlook")

    async def send_outlook(interaction: Interaction):
        await interaction.send(
            embed=Embed(
                title=f"Future Outlook - <t:{int(forecast[0].timestamp())}:f>",
                description=forecast[2],
            ),
            ephemeral=True,
        )

    outlook_btn.callback = send_outlook
    view.add_item(outlook_btn)

    return view


async def send_situation(interaction: Interaction, forecast):
    await interaction.send(
        embed=Embed(
            title=f"Current Situation - <t:{int(forecast[0].timestamp())}:f>",
            description=forecast[1],
        ),
        ephemeral=True,
    )


async def send_outlook(interaction: Interaction, forecast):
    await interaction.send(
        embed=Embed(
            title=f"Future Outlook - <t:{int(forecast[0].timestamp())}:f>",
            description=forecast[2],
        ),
        ephemeral=True,
    )


class WeatherView(View):
    """#### A view for displaying weather information in a slash command which is `NOT` persistent."""

    def __init__(self, forecast):
        super().__init__(timeout=30)
        self.forecast = forecast

    @button(label="Current Situation")
    async def send_situation(self, button: Button, interaction: Interaction):
        await send_situation(interaction, self.forecast)

    @button(label="Future Outlook")
    async def send_outlook(self, button: Button, interaction: Interaction):
        await send_outlook(interaction, self.forecast)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        msg: nextcord.Message = self.msg
        await msg.edit(view=self)


class PersistentWeatherView(View):
    """#### A `persistent` view for displaying weather information daily."""

    def __init__(self, forecast):
        super().__init__(timeout=None)
        self.forecast = forecast

    @button(
        label="Current Situation",
        custom_id=f"weather_current_situation_{datetime.datetime.now().strftime('%m-%d')}",
    )
    async def send_situation(self, button: Button, interaction: Interaction):
        await send_situation(interaction, self.forecast)

    @button(
        label="Future Outlook",
        custom_id=f"weather_future_outlook{datetime.datetime.now().strftime('%m-%d')}",
    )
    async def send_outlook(self, button: Button, interaction: Interaction):
        await send_outlook(interaction, self.forecast)


class Video:

    """A helper class that is designed to represent a Youtube video and be displayed in VideoView."""

    def __init__(
        self,
        title,
        description,
        channel_title,
        link,
        published_time,
        thumbnail_url,
        duration,
        views,
        likes,
    ):
        self.title = title
        self.description = description
        self.channel_title = channel_title
        self.link = link
        self.published_time = published_time
        self.thumbnail_url = thumbnail_url
        self.duration = duration
        self.views = int(views)
        self.likes = int(likes)

    @classmethod
    def from_api_response(cls, video_response):
        """Generates a `Video` from the youtube api response. Should include `snippet`, `contentDetails`, `statistics` for the response `part`."""
        title = video_response["snippet"]["title"]
        description = video_response["snippet"]["description"]

        channel_title = video_response["snippet"]["channelTitle"]

        link = f"https://www.youtube.com/watch?v={video_response['id']}"
        published_time = int(
            datetime.datetime.strptime(video_response["snippet"]["publishedAt"], "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=datetime.timezone.utc)
            .astimezone(tz=None)
            .timestamp()
        )
        thumbnail_url = video_response["snippet"]["thumbnails"]["high"]["url"]

        duration_str = video_response["contentDetails"]["duration"][2:]

        separators = (
            "W",
            "D",
            "H",
            "M",
            "S",
        )
        duration_vals = {}
        for sep in separators:
            partitioned = duration_str.partition(sep)
            if partitioned[1] == sep:
                # Matched this unit
                duration_str = partitioned[2]

                dur_str = partitioned[0]

                if dur_str:
                    dur_val = float(dur_str) if "." in dur_str else int(dur_str)
                    duration_vals.update({sep.lower(): dur_val})
            else:
                # No match for this unit: it's absent
                duration_vals.update({sep.lower(): 0})

        duration = " ".join([f"{value}{unit}" for unit, value in duration_vals.items() if not value == 0])

        views = video_response["statistics"].get("viewCount", 0)
        likes = video_response["statistics"].get("likeCount", 0)
        return cls(
            title,
            description,
            channel_title,
            link,
            published_time,
            thumbnail_url,
            duration,
            views,
            likes,
        )


class VideoView(BaseView):
    def __init__(self, slash_interaction: Interaction, videos: list[Video]):
        super().__init__(slash_interaction, timeout=60)
        self.videos = videos
        self.page = 0

        video_select = [i for i in self.children if i.custom_id == "video_select"][0]
        video_select.options = [
            SelectOption(label=video.title[:100], description=video.channel_title, value=index)
            for index, video in enumerate(self.videos)
        ]

    def get_embed(self):
        embed = Embed()
        video = self.videos[self.page]

        embed.set_author(name=video.channel_title)
        embed.colour = 0xDBFCFF

        embed.set_footer(text=f"Page {self.page + 1}/{len(self.videos)}")  # + 1 because self.page uses zero-indexing

        embed.set_thumbnail(url=video.thumbnail_url)

        embed.title = video.title
        embed.url = video.link

        if len(video.description) > 200:
            embed.add_field(
                name="Description",
                value=f"\n>>> {video.description[:200]}...",
                inline=False,
            )
        else:
            embed.add_field(name="Description", value=f"\n>>> {video.description}", inline=False)

        embed.add_field(
            name="Publish time",
            value=f"<t:{video.published_time}:F> • <t:{video.published_time}:R>",
            inline=False,
        )

        embed.add_field(name="Duration", value=video.duration)
        embed.add_field(name="Views", value=numerize.numerize(video.views))
        embed.add_field(name="Likes", value=numerize.numerize(video.likes))

        return embed

    def disable_buttons(self):
        back_btn = [i for i in self.children if i.custom_id == "back"][0]
        first_btn = [i for i in self.children if i.custom_id == "first"][0]
        if self.page == 0:
            back_btn.disabled = True
            first_btn.disabled = True
        else:
            back_btn.disabled = False
            first_btn.disabled = False
        next_btn = [i for i in self.children if i.custom_id == "next"][0]
        last_btn = [i for i in self.children if i.custom_id == "last"][0]
        if self.page == len(self.videos) - 1:
            next_btn.disabled = True
            last_btn.disabled = True
        else:
            next_btn.disabled = False
            last_btn.disabled = False

    @select(placeholder="Choose a video...", custom_id="video_select")
    async def choose_video(self, select: Select, interaction: Interaction):
        self.page = int(select.values[0])  # the value is set to the index of the video

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="⏮️", style=ButtonStyle.blurple, custom_id="first", disabled=True)
    async def first(self, button: Button, interaction: Interaction):
        self.page = 0

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="◀️", style=ButtonStyle.blurple, disabled=True, custom_id="back")
    async def back(self, button: Button, interaction: Interaction):
        self.page -= 1

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="📽️", style=ButtonStyle.grey, custom_id="video")
    async def show_video(self, button: Button, interaction: Interaction):
        await interaction.send(self.videos[self.page].link, ephemeral=True)

    @button(emoji="▶️", style=ButtonStyle.blurple, custom_id="next")
    async def next(self, button: Button, interaction: Interaction):
        self.page += 1

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="⏭️", style=ButtonStyle.blurple, custom_id="last")
    async def last(self, button: Button, interaction: Interaction):
        self.page = len(self.videos) - 1

        self.disable_buttons()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    # @button(emoji="📃", style=ButtonStyle.grey, custom_id="description", row=2)
    # async def show_description(self, button: Button, interaction: Interaction):
    #     embed = Embed()
    #     video = self.videos[self.page]

    #     embed.set_author(name=video.title)
    #     embed.set_thumbnail(url=video.thumbnail_url)
    #     embed.description = video.description[
    #         :4096
    #     ]  # upper limit for description length is 4096.
    #     await interaction.send(embed=embed, ephemeral=True)


class MtrLine(enum.Enum):
    Airport_Express = "AEL"
    Tung_Chung_Line = "TCL"
    Tuen_Ma_Line = "TML"
    Tseung_Kwan_O_Line = "TKL"
    East_Rail_Line = "EAL"
    South_Island_Line = "SIL"
    Tseung_Wan_Line = "TWL"


LINE_STATION_CODES = {
    "AEL": {
        "Hong Kong": "HOK",
        "Kowloon": "KOW",
        "Tsing Yi": "TSY",
        "Airport": "AIR",
        "AsiaWorld Expo": "AWE",
    },
    "TCL": {
        "Hong Kong": "HOK",
        "Kowloon": "KOW",
        "Olympic": "OLY",
        "Nam Cheong": "NAC",
        "Lai King": "LAK",
        "Tsing Yi": "TSY",
        "Sunny Bay": "SUN",
        "Tung Chung": "TUC",
    },
    "TML": {
        "Wu Kai Sha": "WKS",
        "Ma On Shan": "MOS",
        "Heng On": "HEO",
        "Tai Shui Hang": "TSH",
        "Shek Mun": "SHM",
        "City One": "CIO",
        "Sha Tin Wai": "STW",
        "Che Kung Temple": "CKT",
        "Tai Wai": "TAW",
        "Hin Keng": "HIK",
        "Diamond Hill": "DIH",
        "Kai Tak": "KAT",
        "Sung Wong Toi": "SUW",
        "To Kwa Wan": "TKW",
        "Ho Man Tin": "HOM",
        "Hung Hom": "HUH",
        "East Tsim Sha Tsui": "ETS",
        "Austin": "AUS",
        "Nam Cheong": "NAC",
        "Mei Foo": "MEF",
        "Tsuen Wan West": "TWW",
        "Kam Sheung Road": "KSR",
        "Yuen Long": "YUL",
        "Long Ping": "LOP",
        "Tin Shui Wai": "TIS",
        "Siu Hong": "SIH",
        "Tuen Mun": "TUM",
    },
    "TKL": {
        "North Point": "NOP",
        "Quarry Bay": "QUB",
        "Yau Tong": "YAT",
        "Tiu Keng Leng": "TIK",
        "Tseung Kwan O": "TKO",
        "LOHAS Park": "LHP",
        "Hang Hau": "HAH",
        "Po Lam": "POA",
    },
    "EAL": {
        "Admiralty": "ADM",
        "Exhibition Centre": "EXC",
        "Hung Hom": "HUH",
        "Mong Kok East": "MKK",
        "Kowloon Tong": "KOT",
        "Tai Wai": "TAW",
        "Sha Tin": "SHT",
        "Fo Tan": "FOT",
        "Racecourse": "RAC",
        "University": "UNI",
        "Tai Po Market": "TAP",
        "Tai Wo": "TWO",
        "Fanling": "FAN",
        "Sheung Shui": "SHS",
        "Lo Wu": "LOW",
        "Lok Ma Chau": "LMC",
    },
    "SIL": {
        "Admiralty": "ADM",
        "Ocean Park": "OCP",
        "Wong Chuk Hang": "WCH",
        "Lei Tung": "LET",
        "South Horizons": "SOH",
    },
    "TWL": {
        "Central": "CEN",
        "Admiralty": "ADM",
        "Tsim Sha Tsui": "TST",
        "Jordan": "JOR",
        "Yau Ma Tei": "YMT",
        "Mong Kok": "MOK",
        "Price Edward": "PRE",
        "Sham Shui Po": "SSP",
        "Cheung Sha Wan": "CSW",
        "Lai Chi Kok": "LCK",
        "Mei Foo": "MEF",
        "Lai King": "LAK",
        "Kwai Fong": "KWF",
        "Kwai Hing": "KWH",
        "Tai Wo Hau": "TWH",
        "Tsuen Wan": "TSW",
    },
}


class Train:

    """A helper class that is designed to represent a MTR Train and be represented in `NextTrainView`."""

    def __init__(
        self,
        line: MtrLine,
        arriving_station,
        arrival_time: datetime.datetime,
        sequence: int,
        destination,
        platform: int,
        via_racecourse: Optional[bool] = None,
    ):
        self.line = line
        self.arriving_station = arriving_station
        self.arrival_time = arrival_time
        self.sequence = sequence
        self.destination = destination
        self.platform = platform
        self.via_racecourse = via_racecourse

    @classmethod
    def from_api_response(cls, next_train_response):
        """
        Class method to generate a dict of "UP" and "DOWN" `Train`s from the Next Train api response.
        ### Data structure of returned value:

        ```
        trains = {
            "UP": list[UP trains],
            "DOWN": list[DOWN trains]
        }
        ```

        Can be used for the `trains` parameter in `NextTrainView`
        """
        data = next_train_response["data"]
        key = list(data.keys())[0]  # eg: "TKL-TIK"
        line = MtrLine(key[:3])  # eg: "TKL"
        arriving_station = key[4:]  # eg: "TIK"

        values = list(data.values())[0]
        trains = {
            "UP": values.get("UP", []),
            "DOWN": values.get("DOWN", []),
        }  # use empty list for default in case station is at either end of line

        hk_tz = pytz.timezone("Asia/Hong_Kong")
        for train_type, trains_res in trains.items():
            for index, train in enumerate(trains_res):
                destination_code = train["dest"]
                # destination_name = [name for name, code in LINE_STATION_CODES[line].items() if code == destination_code][0]
                sequence = train["seq"]
                platform = train["plat"]
                via_racecourse = bool(train.get("route"))
                arrival_time = datetime.datetime.strptime(train["time"], "%Y-%m-%d %H:%M:%S")
                arrival_time = hk_tz.localize(arrival_time)

                trains[train_type][index] = cls(
                    line,
                    arriving_station,
                    arrival_time,
                    sequence,
                    destination_code,
                    platform,
                    via_racecourse,
                )

        return trains


class NextTrainView(BaseView):
    """
    Shows a list of trains returned from Next Train API.
    # Features
    `Paginating buttons`: automated (which disable themselves) according to the current page
    `Type Switching`: Can be switched between "UP" and "DOWN" trains
    # Parameters
    `slash_interaction`: `nextcord.Interaction` from the slash command.
    Used for identifying the user and timing out the view.
    `trains`: a `dict` containing "UP" and "DOWN" trains
    """

    def __init__(self, slash_interaction: Interaction, trains: dict[str, list[Train]]):
        super().__init__(slash_interaction, timeout=60)
        self.trains = trains

        type_button = [i for i in self.children if i.custom_id == "type"][0]
        if not self.trains["UP"]:  # only down directions are available, disable the type button
            self.type = "DOWN"
            type_button.disabled = True
        elif not self.trains["DOWN"]:  # only up directions are available, disable the type button
            self.type = "UP"
            type_button.disabled = True
        else:  # both directions are available.
            self.type = "UP"
            type_button.disabled = False
        self.page = 0

    def get_embed(self):
        embed = Embed()
        train = self.trains[self.type][self.page]

        colours = {
            MtrLine.Airport_Express: 0x02838A,
            MtrLine.East_Rail_Line: 0x5EB9E6,
            MtrLine.South_Island_Line: 0xCBCD00,
            MtrLine.Tseung_Kwan_O_Line: 0x863E90,
            MtrLine.Tuen_Ma_Line: 0x952E07,
            MtrLine.Tung_Chung_Line: 0xF39131,
        }
        embed.colour = colours.get(train.line, None)  # black for default

        arriving_station = [
            name for name, code in LINE_STATION_CODES[train.line.value].items() if code == train.arriving_station
        ][0]
        embed.title = f"Next trains arriving at {arriving_station}"

        embed.set_footer(
            text=f"{self.type} trains • Page {self.page + 1}/{len(self.trains)}"
        )  # + 1 because self.page uses zero-indexing

        destination_name = [
            name for name, code in LINE_STATION_CODES[train.line.value].items() if code == train.destination
        ][0]
        embed.add_field(
            name="Destination",
            value=destination_name,
        )
        embed.add_field(name="Platform", value=train.platform)
        if train.via_racecourse:
            embed.description = "> via Racecourse"

        arrival_timestamp = int(train.arrival_time.timestamp())
        hk_tz = pytz.timezone("Asia/Hong_Kong")
        embed.add_field(
            name="Arrival time" if train.arrival_time > datetime.datetime.now(tz=hk_tz) else "Departure time",
            value=f"<t:{arrival_timestamp}:t> • <t:{arrival_timestamp}:R>",
            inline=False,
        )

        return embed

    def update_view(self):
        back_btn = [i for i in self.children if i.custom_id == "back"][0]
        if self.page == 0:
            back_btn.disabled = True
        else:
            back_btn.disabled = False
        next_btn = [i for i in self.children if i.custom_id == "next"][0]
        if self.page == len(self.trains) - 1:
            next_btn.disabled = True
        else:
            next_btn.disabled = False

        type_button = [i for i in self.children if i.custom_id == "type"][0]
        if self.type == "UP":
            type_button.emoji = "🔽"
        elif self.type == "DOWN":
            type_button.emoji = "🔼"

    @button(emoji="◀️", style=ButtonStyle.blurple, disabled=True, custom_id="back")
    async def back(self, button: Button, interaction: Interaction):
        self.page -= 1

        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="▶️", style=ButtonStyle.blurple, custom_id="next")
    async def next(self, button: Button, interaction: Interaction):
        self.page += 1

        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

    @button(emoji="🔼", style=ButtonStyle.grey, custom_id="type")
    async def change_type(self, button: Button, interaction: Interaction):
        self.page = 0
        if self.type == "UP":
            self.type = "DOWN"
        elif self.type == "DOWN":
            self.type = "UP"

        self.update_view()
        embed = self.get_embed()
        await interaction.response.edit_message(view=self, embed=embed)

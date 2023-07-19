# nextcord
import nextcord
from nextcord import Interaction, ButtonStyle
from nextcord.ui import Button

# my modules
from utils.helpers import TextEmbed, EmbedColour, Embed
from utils.template_views import BaseView

# default modules
import html
import random
from dataclasses import dataclass


@dataclass
class TriviaQuestion:
    """Class for representing a question returned by the Open Trivia Database API."""

    question: str
    correct_answer: str
    incorrect_answers: list[str]
    category: str
    difficulty: str

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
            raise ValueError(f"Question `{question}` is too long.")

        self.correct_answer = html.unescape(correct_answer)
        if len(correct_answer) > 50:
            raise ValueError(f"Label of `{correct_answer}` is too long.")

        self.incorrect_answers = [html.unescape(i) for i in incorrect_answers]
        if any([len(i) > 50 for i in self.incorrect_answers]):
            raise ValueError("Label of an incorrect_answer is too long.")

        self.category = category
        self.difficulty = difficulty


class TriviaAnswerButton(Button):
    def __init__(self, label: str):
        super().__init__(label=label)

    async def callback(self, interaction: Interaction):
        await interaction.response.defer()

        view: TriviaView = self.view
        embed = view.message.embeds[0]

        if self.label == view.question.correct_answer:  # the user got the question correct
            embed.colour = EmbedColour.GREEN
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
            embed.colour = EmbedColour.RED
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
        embed.colour = EmbedColour.GREY
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

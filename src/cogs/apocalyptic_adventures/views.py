# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle
from nextcord.ui import Button

# database
from utils.postgres_db import Database

# my modules and constants
from utils import constants, helpers
from utils.constants import EmbedColour, CURRENCY_EMOJIS
from utils.helpers import TextEmbed, upper, BossItem
from utils.player import Player
from utils.template_views import BaseView

# default modules
import random


class ScoutButton(Button["ScoutView"]):
    def __init__(self, location: dict) -> None:
        super().__init__(label=location["name"], style=ButtonStyle.blurple)
        self.location = location

    async def callback(self, interaction: Interaction) -> None:
        assert self.view is not None
        view: ScoutView = self.view

        # make all buttons disabled, and buttons except the selected one grey
        for i in view.children:
            i.disabled = True
            if i.label != self.label:
                i.style = ButtonStyle.grey

        embed = Embed(description="", colour=EmbedColour.DEFAULT)
        embed.set_author(name=f"{upper(interaction.user.name)} scouted the {self.label}")

        result = random.choices(
            ["nothing", "success", "fail"],
            [self.location["nothing"]["chance"], self.location["success"]["chance"], self.location["fail"]["chance"]],
        )[0]

        db: Database = interaction.client.db
        player = Player(db, interaction.user)
        match result:
            case "nothing":
                embed.description = self.location["nothing"]["msg"]
                await interaction.response.edit_message(embed=embed, view=view)

            case "success":
                money_reward = self.location["success"]["money"]
                money = random.randint(money_reward["min"], money_reward["max"])
                embed.description = self.location["success"]["msg"].format(
                    reward=f"{CURRENCY_EMOJIS[money_reward['type']]} **{money}**"
                )

                item_reward = None
                if item_reward := self.location[result].get("item"):
                    if random.randint(0, 100) < item_reward["chance"]:
                        item = BossItem(item_reward["id"], 1)
                        embed.description += (
                            f"\nYou also found **1x {await item.get_name(db)}** {await item.get_emoji(db)}"
                        )

                await interaction.response.edit_message(embed=embed, view=view)

                await player.modify_currency(money_reward["type"], money)
                if item_reward:
                    await player.add_item(item_reward["id"])

            case "fail":
                embed.description = self.location["fail"]["msg"]

                punishment = self.location["fail"]["punishment"]
                value = random.randint(punishment["min"], punishment["max"])
                embed.description += f"\nYou also lost {value} {punishment['type']}."

                await interaction.response.edit_message(embed=embed, view=view)

                if punishment["type"] == "health":
                    await player.modify_health(-value)
                elif punishment["type"] == "hunger":
                    await player.modify_hunger(-value)

        view.scouting_finished = True


class ScoutView(BaseView):
    def __init__(self, interaction: Interaction) -> None:
        super().__init__(interaction, timeout=12)
        self.msg: nextcord.PartialInteractionMessage | nextcord.WebhookMessage = None
        self.scouting_finished = False

    @classmethod
    async def send(cls, interaction: Interaction, loot_table):
        view = cls(interaction)
        locations = random.sample(loot_table, 3)
        for i in locations:
            view.add_item(ScoutButton(i))

        embed = TextEmbed("**Where do you want to scout?**\n_Click a button to start scouting at the location!_")
        view.msg = await interaction.send(embed=embed, view=view)
        return view

    async def on_timeout(self) -> None:
        if not self.scouting_finished:
            for i in self.children:
                i.disabled = True
            await self.msg.edit(embed=TextEmbed("Guess you didn't want to search anywhere after all?"), view=self)
            self.scouting_finished = True

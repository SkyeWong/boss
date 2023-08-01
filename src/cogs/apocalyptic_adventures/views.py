# default modules
import asyncio
import json
import random
from dataclasses import dataclass
from typing import Optional, Union

# nextcord
import nextcord
from nextcord import ButtonStyle
from nextcord.ui import Button

# my modules and constants
from utils import helpers
from utils.constants import CURRENCY_EMOJIS, EmbedColour
from utils.helpers import BossInteraction, BossItem
from utils.player import Player

# database
from utils.postgres_db import Database
from utils.template_views import BaseView


class ScoutButton(Button["ScoutView"]):
    def __init__(self, location: dict) -> None:
        super().__init__(label=location["name"], style=ButtonStyle.blurple)
        self.location = location

    async def callback(self, interaction: BossInteraction) -> None:
        assert self.view is not None
        view: ScoutView = self.view

        # make all buttons disabled, and buttons except the selected one grey
        for i in view.children:
            i.disabled = True
            if i.label != self.label:
                i.style = ButtonStyle.grey

        embed = interaction.embed(description="", colour=EmbedColour.DEFAULT)
        embed.set_author(name=f"{interaction.user.name} scouted the {self.label}")

        # Choose a result based on the chances defined by `location`
        result = random.choices(
            ["nothing", "success", "fail"],
            [
                self.location["nothing"]["chance"],
                self.location["success"]["chance"],
                self.location["fail"]["chance"],
            ],
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
                if (item_reward := self.location[result].get("item")) and random.randint(0, 100) < item_reward[
                    "chance"
                ]:
                    item = BossItem(item_reward["id"], 1)
                    embed.description += f"\nYou also found **1x {await item.get_name(db)}** {await item.get_emoji(db)}"

                await interaction.response.edit_message(embed=embed, view=view)

                await player.modify_currency(money_reward["type"], money)
                if item_reward:
                    await player.add_item(item_reward["id"])

                await player.update_missions(interaction, 4)

            case "fail":
                embed.description = self.location["fail"]["msg"]

                punishment = self.location["fail"]["punishment"]
                value = random.randint(punishment["min"], punishment["max"])
                embed.description += f"\nYou lost {value} {punishment['type']}."

                await interaction.response.edit_message(embed=embed, view=view)

                if punishment["type"] == "health":
                    await player.modify_health(-value)
                elif punishment["type"] == "hunger":
                    await player.modify_hunger(-value)

        view.scouting_finished = True
        await player.set_in_inter(False)


class ScoutView(BaseView):
    def __init__(self, interaction: BossInteraction) -> None:
        super().__init__(interaction, timeout=12)
        self.player = Player(interaction.client.db, interaction.user)
        self.msg: nextcord.PartialInteractionMessage | nextcord.WebhookMessage = None
        self.scouting_finished = False

    @classmethod
    async def send(cls, interaction: BossInteraction, loot_table):
        view = cls(interaction)
        locations = random.sample(loot_table, 3)
        for i in locations:
            view.add_item(ScoutButton(i))

        embed = interaction.text_embed(
            "**Where do you want to scout?**\n_Click a button to start scouting at the location!_"
        )
        view.msg = await interaction.send(embed=embed, view=view)
        await view.player.set_in_inter(True)

        return view

    async def on_timeout(self) -> None:
        if not self.scouting_finished:
            for i in self.children:
                i.disabled = True
            await self.msg.edit(
                embed=self.interaction.text_embed("Guess you didn't want to search anywhere after all?"),
                view=self,
            )
            self.scouting_finished = True
            await self.player.set_in_inter(False)


@dataclass
class RaidPlayer:
    """Represents a player in /raid."""

    user: nextcord.User
    battlegear: list
    health: int = 100

    @property
    def armour_prot(self) -> float:
        """The sum of protection provided by all the armour the player has,
        as a percentage with range [0, 1]."""
        return sum(i["other_attributes"].get("armour_protection", 0) for i in self.battlegear) / 100

    @property
    def attack_dmg(self) -> int:
        """The attack the player does on each round."""
        return sum(i["other_attributes"].get("weapon_damage", 0) for i in self.battlegear) or 8


class RaidView(BaseView):
    def __init__(self, interaction: BossInteraction, players: list[RaidPlayer]):
        super().__init__(interaction, timeout=None)
        self.message: Union[nextcord.WebhookMessage, nextcord.PartialInteractionMessage] = None
        self.db: Database = interaction.client.db
        self.players = players
        self.round = 1

    @classmethod
    async def create(cls, interaction: BossInteraction, user_1: nextcord.User, user_2: nextcord.User):
        db: Database = interaction.client.db
        players = []
        for i in (user_1, user_2):
            data = await db.fetch(
                """
                SELECT 
                    type_name, 
                    i.name AS item_name, 
                    CASE 
                        WHEN i.emoji_id IS NOT NULL THEN CONCAT('<:_:', i.emoji_id, '>')
                        ELSE ''
                    END AS emoji,
                    i.other_attributes
                FROM players.battlegear AS b
                    RIGHT JOIN unnest(enum_range(NULL::utility.battlegear_type)) AS type_name
                    ON b.type = type_name AND b.player_id = $1
                    LEFT JOIN utility.items AS i
                    ON b.item_id = i.item_id
                    ORDER BY type_name
                """,
                i.id,
            )
            battlegear = []
            for j in data:
                j = dict(j)
                j["other_attributes"] = json.loads(j["other_attributes"] or "{}")
                battlegear.append(j)
            players.append(RaidPlayer(i, battlegear))
        player = Player(interaction.client.db, interaction.user)
        await player.set_in_inter(True)
        return cls(interaction, players)

    async def send(self, msg: Optional[nextcord.Message] = None):
        if msg:
            func = msg.edit
        else:
            func = self.interaction.send
        self.message = await func(embed=self.get_embed(), view=self)
        while all(i.health > 0 for i in self.players):
            await asyncio.sleep(3)
            await self.update()

    def get_embed(self, msgs: list[str] = None):
        embed = self.interaction.embed(show_macro_msg=False)
        embed.set_author(name=f"⚔️ Raid (Round {self.round})")
        for i in self.players:
            player_msg = f"{'❤️' if i.health > 0 else '💀'} {helpers.create_pb(i.health)} **{i.health}%**\n"
            combat = round(i.armour_prot * 50 + i.attack_dmg / 30 * 50)
            player_msg += f"🛡️ {helpers.create_pb(combat)} **{combat}%**\n"
            player_msg += "🏹 " + "".join(j["emoji"] for j in i.battlegear)
            embed.add_field(name=i.user.name, value=player_msg)
        if msgs:
            embed.add_field(name="Last Round", value="\n".join(msgs), inline=False)
        return embed

    FIGHT_ADJS = {
        "fail": [
            "inept",
            "clumsy",
            "weak",
            "unskilled",
            "graceless",
            "slow",
            "clumsy",
            "vulnerable",
            "helpless",
        ],
        "success": [
            "devastating",
            "powerful",
            "efficient",
            "skillful",
            "graceful",
            "quick",
            "agile",
            "vicious",
            "merciless",
        ],
    }

    async def update(self):
        self.round += 1
        won_player = None
        msgs = []
        for index, current_player in enumerate(self.players):
            # get the other player
            other_player = self.players[(index + 1) % 2]
            # calculate the attack based on the current user's weapon, and the other user's armour
            # decide whether the current user is successful
            res = random.choice(("success", "fail"))
            if res == "success":
                attack = current_player.attack_dmg * random.uniform(1.2, 1.5)
            else:
                attack = current_player.attack_dmg * random.uniform(0.6, 0.8)

            damage = min(round(attack * (1 - other_player.armour_prot * 0.6)), other_player.health)
            other_player.health -= damage
            msgs.append(
                f"**{current_player.user.name}** lands a"
                f" {random.choice(RaidView.FIGHT_ADJS[res])} attack, dealing {damage}% damage!"
            )
            if other_player.health <= 0:
                won_player = current_player
        if won_player:
            content = f"{won_player.user.mention} is a legendary fighter!"
            player = Player(self.interaction.client.db, self.interaction.user)
            await player.set_in_inter(False)
        else:
            content = None
        await self.message.edit(
            content=content,
            embed=self.get_embed(msgs),
        )

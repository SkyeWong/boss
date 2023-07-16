# nextcord
import nextcord
from nextcord.ext import commands
from nextcord.ui import Button

# slash command cooldowns
import cooldowns
from cooldowns import SlashBucket

# database
from utils.postgres_db import Database

# my modules and constants
from utils import helpers
from utils.constants import CURRENCY_EMOJIS, EmbedColour
from utils.helpers import check_if_not_dev_guild, BossItem, BossInteraction, command_info, work_in_progress
from utils.player import Player
from utils.template_views import BaseView

from .views import ScoutView

import pytz

# default modules
import random
import asyncio
import json
import datetime
from contextlib import suppress


class Survival(commands.Cog, name="Apocalyptic Adventures"):
    """Missions, quests, exploration, and events"""

    COG_EMOJI = "🗺️"

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_application_command_before_invoke(self, interaction: BossInteraction) -> None:
        hunger = await self.bot.db.fetchval(
            """
            SELECT hunger
            FROM players.players
            WHERE player_id = $1
            """,
            interaction.user.id,
        )
        # if the hunger is smaller than 30, wait for 3 seconds before continuing
        if hunger < 30:
            await interaction.send_text(
                "You are too hungry! Consume some food before running commands again.\nContinuing after 3 seconds...",
                EmbedColour.WARNING,
            )
            await asyncio.sleep(3)

    async def cog_application_command_after_invoke(self, interaction: BossInteraction) -> None:
        # decrease the player's hunger
        old_hunger, new_hunger = await self.bot.db.fetchrow(
            """
            UPDATE players.players
            SET hunger = hunger - $1
            WHERE player_id = $2
            RETURNING 
                (SELECT hunger
                FROM players.players
                WHERE player_id = $2) AS old_hunger, 
                hunger
            """,
            random.randint(0, 1),
            interaction.user.id,
        )
        if old_hunger >= 30 and new_hunger < 30:
            embed = interaction.TextEmbed(
                "Your hunger is smaller than 30! Commands running from now on will have a slight delay.\nConsume some food before continuing.",
                EmbedColour.WARNING,
                show_macro_msg=False,
            )
            embed.timestamp = datetime.datetime.now()
            await interaction.user.send(embed=embed)

    async def _handle_grind_cmd(
        self,
        interaction: BossInteraction,
        loot_table: dict,
        fail_messages: list[str],
        success_message: str,
        mission_id: int = None,
    ):
        """Handles a grind command, which accepts no parameters and choose a random reward for the user.

        Args:
            interaction (BossInteraction): The interaction of the slash command
            loot_table (dict): The loot table, which should be initalised in `Survival.__init__()`
            fail_messages (list[str]): A list of messages to show the user when they get nothing, then a random one will be chosen to shown
            success_message (str): The message to show when they succeed. It must include "{reward}", which will be used to format the reward item
            mission_id (int): The id of the mission type.
        """
        db: Database = self.bot.db
        reward_category = random.choices(list(loot_table.keys()), [i["chance"] for i in loot_table.values()])[0]

        if reward_category == "fail":
            await interaction.send_text(random.choice(fail_messages))
            return

        player = Player(db, interaction.user)
        rewards = loot_table[reward_category]["rewards"]
        reward = random.choices(
            rewards,
            [i["chance"] if i.get("chance") else 1 / len(rewards) for i in rewards],
            # select the chance of the reward if it exists, or make the chance same for all of them
        )[0]
        if reward["type"] == "item":
            quantity = random.randint(reward["min"], reward["max"])
            await player.add_item(reward["id"], quantity)
            item = BossItem(reward["id"], quantity)
            reward = f"{quantity} **{await item.get_name(db)}** {await item.get_emoji(db)}"
        else:
            # reward["type"] will be "scrap_metal" or "copper"
            value = random.randint(reward["min"], reward["max"])
            await player.modify_currency(reward["type"], value)
            reward = f"{CURRENCY_EMOJIS[reward['type']]} **{value}**"
        await interaction.send_text(success_message.format(reward=reward))

        # if the user has a mission of the type of the command, update its progress
        if mission_id is not None:
            await player.update_missions(interaction, mission_id)

    HUNT_LOOT = {
        "fail": {"chance": 20},
        "common": {
            "chance": 40,
            "rewards": [
                {"type": "item", "id": 23, "min": 1, "max": 3},  # duck
                {"type": "item", "id": 24, "min": 1, "max": 3},  # rabbit
                {"type": "item", "id": 26, "min": 1, "max": 3},  # skunk
            ],
        },
        "uncommon": {
            "chance": 30,
            "rewards": [
                {"type": "item", "id": 18, "min": 1, "max": 3},  # deer
                {"type": "item", "id": 22, "min": 1, "max": 3},  # cow
                {"type": "item", "id": 25, "min": 1, "max": 3},  # sheep
            ],
        },
        "rare": {"chance": 8, "rewards": [{"type": "item", "id": 21, "min": 1, "max": 1}]},  # boar
        "epic": {"chance": 2, "rewards": [{"type": "item", "id": 20, "min": 1, "max": 1}]},  # dragon
    }

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def hunt(self, interaction: BossInteraction):
        """Go hunting and bring back some animals if you are lucky!"""
        await self._handle_grind_cmd(
            interaction,
            self.HUNT_LOOT,
            fail_messages=[
                "You went hunting but found nothing... No dinner tonight ig",
                "Looks like you didn't catch anything this time. Maybe next time you should aim for something smaller than a mountain?",
                "Sorry, looks like you missed the memo about animals being able to smell fear.",
                "Looks like the only thing you managed to hunt was disappointment.",
                "I hate to break it to you, but I think the only thing you caught was a cold.",
                "Sorry, looks like the animals decided to take a break from playing hide-and-seek with you.",
                "Well, that was disappointing. Maybe you should stick to playing Minecraft.",
                "Don't worry, there's always next time. Maybe try using a bigger gun?",
            ],
            success_message="You went hunting and found {reward}!",
            mission_id=0,
        )

    DIG_LOOT = {
        "fail": {"chance": 40},
        "common": {
            "chance": 45,
            "rewards": [
                {"type": "item", "id": 31, "min": 1, "max": 5},  # dirt
            ],
        },
        "uncommon": {
            "chance": 10,
            "rewards": [
                {"type": "item", "id": 27, "min": 1, "max": 1},  # ancient coin
                {"type": "item", "id": 46, "min": 1, "max": 5},  # banknote
            ],
        },
        "rare": {
            "chance": 5,
            "rewards": [
                {"chance": 95, "type": "scrap_metal", "min": 5_000, "max": 8_000},
                {"chance": 5, "type": "copper", "min": 1, "max": 3},
            ],
        },
    }

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def dig(self, interaction: BossInteraction):
        """Dig in the ground and find some buried treasure."""
        await self._handle_grind_cmd(
            interaction,
            self.DIG_LOOT,
            fail_messages=[
                "With that little stick of yours, you shouldn't really expect to find anything.",
                "You found nothing! What a waste of time.",
                "After you saw a spider climbing in the dirt, you gave it up as a bad job.",
                "Wait... what's that? Aww, it's just another worm.",
            ],
            success_message="You dug in the ground and unearthed {reward}!",
            mission_id=1,
        )

    MINE_LOOT = {
        "fail": {"chance": 40},
        "common": {"chance": 35, "rewards": [{"type": "item", "id": 33, "min": 1, "max": 10}]},  # stone
        "uncommon": {
            "chance": 20,
            "rewards": [
                {"type": "item", "id": 45, "min": 1, "max": 3},  # emerald ore
                {"type": "item", "id": 44, "min": 1, "max": 5},  # iron ore
            ],
        },
        "rare": {"chance": 5, "rewards": [{"type": "item", "id": 34, "min": 1, "max": 1}]},  # diamond ore
    }

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def mine(self, interaction: BossInteraction):
        """Go mining in the caves!"""
        await self._handle_grind_cmd(
            interaction,
            self.MINE_LOOT,
            fail_messages=[
                "The cave was too dark. You ran away in a hurry.",
                "Well, you certainly know how to find the empty spots in a cave.",
                "What were you doing in your garage for the past 5 hours? You didn't mistake it as a cave... did you?",
                "You've managed to mine nothing but air. Your pickaxe must be thrilled.",
                "You mine and you mine, but all you find are rocks.",
                "Looks like you struck out. Maybe next time you'll get lucky and find a diamond... or not.",
                "Breaking rocks all day, yet nothing to show for it. You're a real master at mining for disappointment.",
            ],
            success_message="You went to the quarries and mined out {reward}!",
            mission_id=3,
        )

    SCAVENGE_LOOT = {
        "fail": {"chance": 30},
        "common": {"chance": 50, "rewards": [{"type": "scrap_metal", "min": 500, "max": 1000}]},
        "uncommon": {"chance": 18, "rewards": [{"type": "scrap_metal", "min": 1500, "max": 5000}]},
        "rare": {
            "chance": 2,
            "rewards": [
                {"type": "copper", "min": 1, "max": 2},
                {"type": "item", "id": 46, "min": 1, "max": 3},  # banknotes
            ],
        },
    }

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def scavenge(self, interaction: BossInteraction):
        """Scavenge for resources in post-apocalyptic world, maybe you'll actually found something!"""
        await self._handle_grind_cmd(
            interaction,
            self.SCAVENGE_LOOT,
            fail_messages=[
                "Looks like you didn't find anything. Better luck next time, champ.",
                "You searched high and low, but came up empty-handed. Maybe try wearing your glasses next time?",
                "Unfortunately, you didn't find anything useful. At least you got some exercise, right?",
                "Welp, that was a waste of time. Maybe try looking for items that aren't invisible next time.",
                "Sorry, no luck this time. Maybe try scaring the items out of hiding with a louder noise next time?",
            ],
            success_message="You searched absolutely everywhere and finally got {reward}!",
            mission_id=4,
        )

    SCOUT_LOOT = [
        {
            "name": "junkyard",
            "nothing": {
                "chance": 20,
                "msg": "You found nothing! Maybe next time you'll finally get something useful in the giant pile of trash.",
            },
            "fail": {
                "chance": 10,
                "msg": "You accidentally cut yourself on some sharp metal.",
                "punishment": {"type": "health", "min": 3, "max": 8},
            },
            "success": {
                "chance": 70,
                "msg": "You rummaged through the piles of discarded items and come across {reward}.",
                "money": {"type": "scrap_metal", "min": 800, "max": 1200},
                "item": {"chance": 8, "id": 50},  # iron ingots
            },
        },
        {
            "name": "power plant",
            "nothing": {
                "chance": 20,
                "msg": "Looks like the power's out and the lights are off. You couldn't find anything in the dark.",
            },
            "fail": {
                "chance": 30,
                "msg": "You set off a radiation alarm while searching the power plant, forcing you to quickly leave.",
                "punishment": {"type": "health", "min": 5, "max": 7},
            },
            "success": {
                "chance": 50,
                "msg": "You successfully navigated through the hazardous power plant and found {reward}.",
                "money": {"type": "scrap_metal", "min": 1000, "max": 1800},
            },
        },
        {
            "name": "underground sewer",
            "nothing": {
                "chance": 30,
                "msg": "You tried to search the underground sewer but gave up since it was too smelly.",
            },
            "fail": {
                "chance": 20,
                "msg": "You accidentally stumbled into a patch of toxic sludge!",
                "punishment": {"type": "health", "min": 2, "max": 10},
            },
            "success": {
                "chance": 50,
                "msg": "You swam in the twisting tunnels of the sewer and located {reward}.",
                "money": {"type": "scrap_metal", "min": 600, "max": 1000},
            },
        },
        {
            "name": "swamp",
            "nothing": {
                "chance": 50,
                "msg": "Looks like the area had nothing of value. That's definitely bad luck, not skill issues. Definitely.",
            },
            "fail": {
                "chance": 10,
                "msg": "You ended up getting lost in the dense fog for a while, and stepped into some quicksand.",
                "punishment": {"type": "hunger", "min": 3, "max": 8},
            },
            "success": {
                "chance": 40,
                "msg": "Your exploration of the swamp pays off and you brought home {reward}.",
                "money": {"type": "scrap_metal", "min": 600, "max": 1000},
            },
        },
        {
            "name": "mine",
            "nothing": {
                "chance": 30,
                "msg": "The mine seemed to be empty. Better luck next time.",
            },
            "fail": {
                "chance": 10,
                "msg": "You triggered a cave-in, and spent hours escaping the falling debris.",
                "punishment": {"type": "hunger", "min": 5, "max": 15},
            },
            "success": {
                "chance": 60,
                "msg": "After carefully exploring the dangerous mine, you stumbled upon {reward}.",
                "money": {"type": "scrap_metal", "min": 700, "max": 1200},
            },
        },
        {
            "name": "forest",
            "nothing": {
                "chance": 10,
                "msg": "You found the forest with thick branches everywhere difficult to navigate, and gave up.",
            },
            "fail": {
                "chance": 10,
                "msg": "You saw a dragon and decided to fight, but caught fire almost immediately.",
                "punishment": {"type": "health", "min": 5, "max": 12},
            },
            "success": {
                "chance": 80,
                "msg": "You found a money bag on the ground! After checking that no one was around, you emptied its contents and obtained {reward}.",
                "money": {"type": "scrap_metal", "min": 500, "max": 1800},
            },
        },
        {
            "name": "ocean",
            "nothing": {
                "chance": 20,
                "msg": "You swam in the polluted ocean and got a cramp.",
            },
            "fail": {
                "chance": 10,
                "msg": "You accidentally got caught in a dangerous current and struggled to keep afloat.",
                "punishment": {"type": "hunger", "min": 3, "max": 10},
            },
            "success": {
                "chance": 70,
                "msg": "You brave the treacherous waters and found {reward} floating above the ocean.",
                "money": {"type": "scrap_metal", "min": 300, "max": 700},
            },
        },
        {
            "name": "radioactive lake",
            "nothing": {
                "chance": 30,
                "msg": "You swam in the lake and developed a stitch. You left shamefully.",
            },
            "fail": {
                "chance": 30,
                "msg": "You ingested some radioactive material, now all you got to do is wait for cancer to arrive.",
                "punishment": {"type": "health", "min": 15, "max": 30},
            },
            "success": {
                "chance": 40,
                "msg": "You found {reward} next to a suspicious piece of machine. A label on it says 'radioactive'??? Uh oh.",
                "money": {"type": "scrap_metal", "min": 1500, "max": 2000},
            },
        },
        {
            "name": "school",
            "nothing": {
                "chance": 10,
                "msg": "Your exploration of the abandoned school didn't uncover any valuable resources.",
            },
            "fail": {
                "chance": 30,
                "msg": "You accidentally tripped over a loose piece of flooring.",
                "punishment": {"type": "health", "min": 2, "max": 6},
            },
            "success": {
                "chance": 60,
                "msg": "You explore the abandoned school and discover a hidden stash of supplies, containing {reward}.",
                "money": {"type": "scrap_metal", "min": 480, "max": 800},
            },
        },
        {
            "name": "dumpsite",
            "nothing": {
                "chance": 10,
                "msg": "The dumpsite didn't have anything useful, or so it seemed.",
            },
            "fail": {
                "chance": 10,
                "msg": "You forgot your gas mask and got poisoned.",
                "punishment": {"type": "health", "min": 3, "max": 8},
            },
            "success": {
                "chance": 80,
                "msg": "After searching for hours in the smelly and potentially poisonous dumpsite, you found {reward}.",
                "money": {"type": "scrap_metal", "min": 500, "max": 700},
            },
        },
        {
            "name": "factory",
            "nothing": {
                "chance": 10,
                "msg": "The entrance was locked, and of course you didn't have the brainpower to break in through the windows.",
            },
            "fail": {
                "chance": 30,
                "msg": "You accidentally turned on old alarm system and attracted the attention of nearby scavengers. They attacked you.",
                "punishment": {"type": "health", "min": 5, "max": 8},
            },
            "success": {
                "chance": 60,
                "msg": "There were metals everywhere! You got everything you could and brought home {reward}.",
                "money": {"type": "scrap_metal", "min": 3500, "max": 4800},
            },
        },
    ]

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def scout(self, interaction: BossInteraction):
        """Explore the wasteland and uncover hidden resources to add to your currency stash."""
        view = await ScoutView.send(interaction, self.SCOUT_LOOT)

        def check(interaction: BossInteraction):
            if not interaction.message:
                return False  # a slash command is invoked, so we ignore the interaction
            return interaction.message.id == view.msg.id

        # halt the execution, so that `after_invoke` is performed after the user has finished scouting
        with suppress(asyncio.TimeoutError):
            await self.bot.wait_for("interaction", check=check, timeout=view.timeout)
        # the timeout should be equal to the timeout of the view, so that even when the user does nothing it will time out

    MISSION_TYPES = [
        {
            "description": "Successfully </hunt:1079601533215330415> for {quantity} times",
            "min": 20,
            "max": 30,
            "rewards": [
                {"type": "item", "id": 18, "max": 15, "min": 10},
                {"type": "item", "id": 20, "max": 5, "min": 3},
                {"type": "scrap_metal", "max": 1200, "min": 800},
            ],
        },
        {
            "description": "Successfully </dig:1079644728921948230> for {quantity} times",
            "min": 20,
            "max": 30,
            "rewards": [
                {"type": "item", "id": 27, "max": 10, "min": 5},
                {"type": "item", "id": 46, "max": 15, "min": 10},
                {"type": "scrap_metal", "max": 1200, "min": 800},
            ],
        },
        {
            "description": "</trade:1102561137893056563> with villages for {quantity} times",
            "min": 30,
            "max": 50,
            "rewards": [{"type": "copper", "max": 8, "min": 6}],
        },
        {
            "description": "Successfully </mine:1102561135988838410> for {quantity} times",
            "min": 20,
            "max": 30,
            "rewards": [
                {"type": "scrap_metal", "max": 1200, "min": 800},
            ],
        },
    ]

    async def claim_missions(self, user: nextcord.User):
        new_missions = []
        for index, mission in random.sample(list(enumerate(self.MISSION_TYPES)), 3):
            reward: dict = random.choice(mission["rewards"]).copy()
            reward["amount"] = random.randint(reward["min"], reward["max"])
            # append the mission to the list of new_missions
            new_missions.append(
                (
                    user.id,
                    index,
                    random.randint(mission["min"], mission["max"]),
                    json.dumps(reward),
                )
            )

        db: Database = self.bot.db
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute("DELETE FROM players.missions WHERE player_id = $1", user.id)
                # insert the missions into the database table
                await conn.executemany(
                    """
                    INSERT INTO players.missions (player_id, mission_id, total_amount, reward)
                    VALUES ($1, $2, $3, $4)
                    """,
                    new_missions,
                )

    async def fetch_missions(self, user: nextcord.User):
        """Fetch the player's missions, and claim if they haven't already."""
        return await self.bot.db.fetch(
            """
            SELECT mission_id, date, finished_amount, total_amount, reward, finished
            FROM players.missions
            WHERE player_id = $1
            ORDER BY finished DESC, mission_id ASC
            """,
            user.id,
        )

    @nextcord.slash_command(description="Check your missions and complete them for some rewards!")
    async def missions(self, interaction: BossInteraction):
        db: Database = self.bot.db

        async def get_embed():
            missions = await self.fetch_missions(interaction.user)
            # if the date of missions are not equal to today (daily missions --> update every day),
            # update the list of missions
            # check only the first mission since they should all be updated at the same time
            now = datetime.datetime.now(tz=pytz.utc)
            if not missions or missions[0]["date"] != now.date:
                await self.claim_missions(interaction.user)
                missions = await self.fetch_missions(interaction.user)
            # Show the time when missions reset (the start of the next day)
            start_of_next_day = (now + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            timestamp = int(start_of_next_day.timestamp())

            embed = interaction.Embed(title=f"{interaction.user.name}'s Daily Missions")
            embed.description = f"Resets at <t:{timestamp}:t> (<t:{timestamp}:R>)\n\n"
            for i in missions:
                mission = self.MISSION_TYPES[i["mission_id"]]
                embed.description += "✅" if i["finished"] else "❎"
                embed.description += f" **{mission['description'].format(quantity=i['total_amount'])}**\n"

                # generate the "reward" string
                reward = json.loads(i["reward"])
                if reward["type"] == "item":
                    item = BossItem(reward["id"], reward["amount"])
                    embed.description += f"<:ReplyCont:1124521050655440916> Reward: {reward['amount']}x {await item.get_emoji(db)} {await item.get_name(db)}\n"
                else:
                    # reward["type"] will be "scrap_metal" or "copper"
                    embed.description += f"<:ReplyCont:1124521050655440916> Reward: {CURRENCY_EMOJIS[reward['type']]} {reward['amount']}\n"

                # generate the progress bar
                finished = i["finished_amount"]
                total = i["total_amount"]
                done_percent = round(finished / total * 100)
                embed.description += f"<:reply:1117458829869858917> {helpers.create_pb(done_percent)} ` {done_percent}% ` ` {finished} / {total} `\n\n"
            return embed

        # create a view to let users reload the embed
        view = BaseView(interaction, timeout=300)  # timeout is 5 minutes
        button = Button(emoji="🔄")

        async def reload_missions(btn_inter: BossInteraction):
            await btn_inter.response.edit_message(embed=await get_embed())

        button.callback = reload_missions
        view.add_item(button)

        await interaction.send(embed=await get_embed(), view=view)


def setup(bot: commands.Bot):
    bot.add_cog(Survival(bot))

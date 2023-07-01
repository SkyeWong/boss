# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Interaction, Embed, SlashOption
from nextcord.ui import Button

# slash command cooldowns
import cooldowns
from cooldowns import SlashBucket

# database
from utils.postgres_db import Database

# my modules and constants
from utils import constants, helpers
from utils.constants import CURRENCY_EMOJIS, EmbedColour
from utils.helpers import TextEmbed, check_if_not_dev_guild, BossItem, BossCurrency
from utils.player import Player
from utils.template_views import ConfirmView, BaseView

# maze
from modules.maze.maze import Maze

# default modules
import random
import asyncio
import json
import datetime


class Survival(commands.Cog, name="Apocalyptic Adventures"):
    """Missions, quests, exploration, and events"""

    COG_EMOJI = "🗺️"

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.HUNT_LOOT = {
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
        self.DIG_LOOT = {
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
        self.MINE_LOOT = {
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
        self.SCAVENGE_LOOT = {
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

    async def cog_application_command_before_invoke(self, interaction: Interaction) -> None:
        await super().cog_application_command_before_invoke(interaction)
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
            await interaction.send(
                embed=TextEmbed(
                    "You are too hungry! Consume some food before running commands again.\nContinuing after 3 seconds...",
                    EmbedColour.WARNING,
                )
            )
            await asyncio.sleep(3)

    async def cog_application_command_after_invoke(self, interaction: Interaction) -> None:
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
            random.randint(0, 2),
            interaction.user.id,
        )
        if old_hunger >= 30 and new_hunger < 30:
            await interaction.user.send(
                embed=TextEmbed(
                    "Your hunger is smaller than 30! Commands running from now on will have a slight delay.\nConsume some food before continuing.",
                    EmbedColour.WARNING,
                )
            )

    async def _handle_grind_cmd(
        self,
        interaction: Interaction,
        loot_table: dict,
        fail_messages: list[str],
        success_message: str,
        mission_id: int = None,
    ):
        """Handles a grind command, which accepts no parameters and choose a random reward for the user.

        Args:
            interaction (Interaction): The interaction of the slash command
            loot_table (dict): The loot table, which should be initalised in `Survival.__init__()`
            fail_messages (list[str]): A list of messages to show the user when they get nothing, then a random one will be chosen to shown
            success_message (str): The message to show when they succeed. It must include "{reward}", which will be used to format the reward item
            mission_id (int): The id of the mission type.
        """
        db: Database = self.bot.db
        reward_category = random.choices(list(loot_table.keys()), [i["chance"] for i in loot_table.values()])[0]

        if reward_category == "fail":
            await interaction.send(embed=TextEmbed(random.choice(fail_messages)))
            return

        player = Player(db, interaction.user)
        rewards = loot_table[reward_category]["rewards"]
        reward = random.choices(
            rewards,
            [
                i["chance"] if i.get("chance") else 1 / len(rewards) for i in rewards
            ],  # select the chance of the reward if it exists, or make the chance same for all of them
        )[0]
        if reward["type"] == "item":
            quantity = random.randint(reward["min"], reward["max"])
            await player.add_item(reward["id"], quantity)
            item = BossItem(reward["id"], quantity)
            embed = TextEmbed(
                success_message.format(reward=f"{quantity} **{await item.get_name(db)}** {await item.get_emoji(db)}")
            )
        else:
            # reward["type"] will be "scrap_metal" or "copper"
            value = random.randint(reward["min"], reward["max"])
            await player.modify_currency(reward["type"], value)
            embed = TextEmbed(success_message.format(reward=f"{CURRENCY_EMOJIS[reward['type']]} **{value}**"))
        await interaction.send(embed=embed)

        # if the user has a mission of the type of the command, update its progress
        if mission_id:
            await player.update_missions(interaction, mission_id)

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def hunt(self, interaction: Interaction):
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
            mission_id=2,
        )

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def dig(self, interaction: Interaction):
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
            mission_id=3,
        )

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def mine(self, interaction: Interaction):
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
        )

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def scavenge(self, interaction: Interaction):
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

    async def adventure_pyramid(self, button, interaction: Interaction):
        maze_size = (random.randint(15, 20), random.randint(15, 20))
        view = Maze(interaction, maze_size)
        await view.send()

    async def adventure_scrap_metal(self, button, interaction: Interaction):
        player = Player(self.bot.db, interaction.user)
        if random.randint(1, 5) > 2:
            scrap_metal = random.randint(1000, 8000)
            await player.modify_currency("scrap_metal", scrap_metal)
            await interaction.send(
                embed=TextEmbed(
                    f"Lucky you, you got home safely without injuries, but with {CURRENCY_EMOJIS['scrap_metal']} {scrap_metal}"
                ),
                ephemeral=True,
            )
        else:
            await interaction.send(
                embed=TextEmbed("Someone was lurking around! You got attacked..."),
                ephemeral=True,
            )

    async def adventure_slave(self, button, interaction: Interaction):
        player = Player(self.bot.db, interaction.user)
        if random.randint(1, 5) > 2:
            await player.add_item(32)
            await interaction.send(
                embed=TextEmbed("Wow, you found yourself a slave! However, what he is able to do, I don't know."),
                ephemeral=True,
            )
        else:
            player_scrap = await self.bot.db.fetchval(
                """
                SELECT scrap_metal
                FROM players.players
                WHERE player_id = $1
                """,
                interaction.user.id,
            )
            # use min() with user's scrap_metal so the scrap_metal will not be negative
            lost_scrap = min(player_scrap, random.randint(120, 800))
            await player.modify_currency("scrap_metal", -lost_scrap)
            await interaction.send(
                embed=TextEmbed(
                    f"Shame on you, he was a bandit. He attacked you and you lost {CURRENCY_EMOJIS['scrap_metal']} {lost_scrap}",
                ),
                ephemeral=True,
            )

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 30, SlashBucket.author, cooldown_id="adventure_fail", check=check_if_not_dev_guild)
    @cooldowns.cooldown(1, 3 * 60, SlashBucket.author, cooldown_id="adventure_success", check=check_if_not_dev_guild)
    async def adventure(
        self,
        interaction: Interaction,
    ):
        """Go explore, discover some structures and obtain some treasure!"""
        if random.randint(1, 10) > 4:
            # 60% to have an adventure
            outcomes = {
                10: (
                    "You found a creepy pyramid that goes DEEP down! Do you want to continue?",
                    self.adventure_pyramid,
                ),
                10: (
                    "Wait what? You found... a random slave! Adopt him, he'd like to.",
                    self.adventure_slave,
                ),
                50: (
                    "A bag of scrap metals was lying on the ground. You saw no one around you. Have you finally decided on whether to snatch it yet?",
                    self.adventure_scrap_metal,
                ),
            }
            # choose a random outcome
            outcome = random.choices(list(outcomes.values()), list(outcomes.keys()))[0]

            embed = Embed(title="Adventure time!", description=outcome[0])

            # if the user confirms the adventure, reset the "fail" cooldown --> only the "success" cooldown remains
            async def confirm_func(button, interaction):
                cooldowns.reset_cooldown("adventure_fail")
                await outcome[1](button, interaction)

            view = ConfirmView(
                slash_interaction=interaction,
                confirm_func=confirm_func,
                # if the user cancels the adventure, reset the "success" cooldown --> only the "fail" cooldown remains
                cancel_func=lambda button, interaction: cooldowns.reset_cooldown("adventure_success"),
                embed=embed,
            )
            await interaction.send(embed=view.embed, view=view)
        else:
            # 40% fail
            msg = (
                "You don't see anything in sight, so you just went home.",
                "It's getting dark. Feeling scared, you rushed back to your little hut and slept with a cute little plushie.",
                "You found out that you actually don't have enough courage to explore on your own.",
                "After getting scared by a rock that seems to [move by itself](https://www.youtube.com/watch?v=iu8vnVz5cYQ), you fled towards your shack.",
                "What's happening? You wanted to move, but your body just doesn't seem to obey your mind.",
            )
            await interaction.send(embed=TextEmbed(random.choice(msg)))
            # if the user does not get an adventure, reset the "success" cooldown --> only the "fail" cooldown remains
            cooldowns.reset_cooldown("adventure_success")

    async def claim_missions(self, user: nextcord.User):
        db: Database = self.bot.db

        mission_types = await db.fetch("SELECT * FROM utility.mission_types ORDER BY random() LIMIT 3")

        new_missions = []
        for i in mission_types:
            rewards = json.loads(i["rewards"])
            reward: dict = random.choice(rewards)
            # choose a random amount of the reward, update the reward and remove "min" and "max" items
            reward.update(amount=random.randint(reward["min"], reward["max"]))
            reward.pop("min")
            reward.pop("max")

            # append the mission to the list of new_missions
            new_missions.append(
                (
                    user.id,
                    i["id"],
                    0,
                    random.randint(i["min_amount"], i["max_amount"]),
                    json.dumps(reward),
                )
            )

        # delete any "old" missions
        await db.execute("DELETE FROM players.missions WHERE player_id = $1", user.id)
        # insert the missions into the database table
        await db.executemany(
            """
            INSERT INTO players.missions (player_id, mission_type_id, finished_amount, total_amount, reward)
            VALUES ($1, $2, $3, $4, $5)
            """,
            new_missions,
        )

    @nextcord.slash_command(description="Check your missions and complete them for some rewards!")
    @helpers.work_in_progress(dev_guild_only=True)
    async def missions(self, interaction: Interaction):
        db: Database = self.bot.db
        missions = await db.fetch(
            """
                SELECT t.description, m.finished_amount, m.total_amount, m.reward, m.finished, m.date
                    FROM players.missions AS m
                    INNER JOIN utility.mission_types AS t
                    ON m.mission_type_id = t.id
                WHERE m.player_id = $1
                ORDER BY m.finished DESC
            """,
            interaction.user.id,
        )
        # if the user does not have any missions previously, or the date of them are not equal to today (daily missions --> update every day)
        if not missions or any(i["date"] != datetime.date.today() for i in missions):
            await self.claim_missions(interaction.user)

        embed = Embed(
            description=f"### {helpers.upper(interaction.user.name)}'s Daily Missions\n", colour=EmbedColour.DEFAULT
        )
        for i in missions:
            embed.description += "✅" if i["finished"] else "❎"
            embed.description += f" **{i['description'].format(quantity=i['total_amount'])}**\n"

            # generate the "reward" string
            reward = json.loads(i["reward"])
            if reward["type"] == "item":
                item = BossItem(reward["id"], reward["amount"])
                embed.description += f"<:ReplyCont:1124521050655440916> Reward: {reward['amount']}x {await item.get_emoji(db)} {await item.get_name(db)}\n"
            else:
                # reward["type"] will be "scrap_metal" or "copper"
                embed.description += (
                    f"<:ReplyCont:1124521050655440916> Reward: {CURRENCY_EMOJIS[reward['type']]} {reward['amount']}\n"
                )

            # generate the progress bar
            finished = i["finished_amount"]
            total = i["total_amount"]
            done_percent = round(finished / total * 100)
            embed.description += f"<:reply:1117458829869858917> {helpers.create_pb(done_percent)} ` {done_percent}% ` ` {finished} / {total} `\n\n"

        await interaction.send(embed=embed)


def setup(bot: commands.Bot):
    bot.add_cog(Survival(bot))

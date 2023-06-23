# nextcord
import nextcord
from nextcord.ext import commands
from nextcord import Interaction, Embed, SlashOption

# slash command cooldowns
import cooldowns
from cooldowns import SlashBucket

# database
from utils.postgres_db import Database

# my modules and constants
from utils import constants, helpers
from utils.constants import CURRENCY_EMOJIS, EmbedColour
from utils.helpers import TextEmbed, check_if_not_dev_guild, BossItem, BossPrice
from utils.player import Player
from utils.template_views import ConfirmView

# maze
from modules.maze.maze import Maze

# default modules
import random
import asyncio


class Survival(commands.Cog, name="Apocalyptic Adventures"):
    """Missions, quests, exploration, and events"""

    COG_EMOJI = "🗺️"

    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
            random.randint(1, 3),
            interaction.user.id,
        )
        if old_hunger >= 30 and new_hunger < 30:
            await interaction.user.send(
                embed=TextEmbed(
                    "Your hunger is smaller than 30! Commands running from now on will have a slight delay.\nConsume some food before continuing.",
                    EmbedColour.WARNING,
                )
            )

    # `% getting one of them`: `list of animals`
    HUNT_LOOT = [
        [20, [None]],  # --fail--
        [
            40,
            (
                # --common--
                BossItem(23),  # duck
                BossItem(24),  # rabbit
                BossItem(26),  # skunk
            ),
        ],
        [
            30,
            (
                # --uncommon--
                BossItem(18),  # deer
                BossItem(22),  # cow
                BossItem(25),  # sheep
            ),
        ],
        [7, (BossItem(21),)],  # --rare--  # boar
        [3, (BossItem(20),)],  # --downright impossible--  # dragon
    ]

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def hunt(self, interaction: Interaction):
        """Go hunting and bring back some animals if you are lucky!"""
        db: Database = self.bot.db
        player = Player(db, interaction.user)
        animal_category = random.choices([i[1] for i in self.HUNT_LOOT], [i[0] for i in self.HUNT_LOOT])[0]
        item = random.choice(animal_category)

        if item is None:
            await interaction.send(embed=TextEmbed("You went hunting but found nothing... No dinner tonight ig"))
            return

        item: BossItem
        await player.add_item(item.item_id)
        embed = TextEmbed(f"You went hunting and found a **{await item.get_name(db)}** {await item.get_emoji(db)}!")
        await interaction.send(embed=embed)

    # `% getting one of them`: `list of rewards`
    DIG_LOOT = [
        [
            90,
            (
                # --fail--
                None,  # nothing
                BossItem(31, random.randint(1, 5)),  # dirt
            ),
        ],
        [
            10,
            (
                # --common--
                BossItem(27),  # Anicient Coin
            ),
        ],
    ]

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def dig(self, interaction: Interaction):
        """Dig in the ground and find some buried treasure."""
        db: Database = self.bot.db
        player = Player(db, interaction.user)
        item_category = random.choices([i[1] for i in self.DIG_LOOT], [i[0] for i in self.DIG_LOOT])[0]
        item = random.choice(item_category)

        if item is None:
            fail_msgs = [
                "With that little stick of yours, you shouldn't really expect to find anything.",
                "You found nothing! What a waste of time.",
                "After you saw a spider climbing in the dirt, you gave it up as a bad job.",
                "Wait... what's that? Aww, it's just another worm.",
            ]
            await interaction.send(embed=TextEmbed(random.choice(fail_msgs)))
            return

        item: BossItem
        await player.add_item(item.item_id, item.quantity)
        await interaction.send(
            embed=TextEmbed(
                f"You dug in the ground and unearthed **{item.quantity} {await item.get_name(db)}** {await item.get_emoji(db)}!"
            )
        )

    # `% getting one of them`: `list of rewards`
    MINE_LOOT = [
        [50, [None]],  # --fail--
        [25, (BossItem(44),)],  # --common--  # Iron ore
        [20, (BossItem(45),)],  # --rare--  # Emerald ore
        [5, (BossItem(34),)],  # --epic--  # Diamond ore
    ]

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def mine(self, interaction: Interaction):
        """Go mining in the caves!"""
        db: Database = self.bot.db
        player = Player(db, interaction.user)
        item_category = random.choices([i[1] for i in self.MINE_LOOT], [i[0] for i in self.MINE_LOOT])[0]
        item = random.choice(item_category)

        if item is None:
            fail_msgs = [
                "The cave was too dark. You ran away in a hurry.",
                "Well, you certainly know how to find the empty spots in a cave.",
                "What were you doing in your garage for the past 5 hours? You didn't mistake it as a cave... did you?",
                "You've managed to mine nothing but air. Your pickaxe must be thrilled.",
                "You mine and you mine, but all you find are rocks.",
                "Looks like you struck out. Maybe next time you'll get lucky and find a diamond... or not.",
                "Breaking rocks all day, yet nothing to show for it. You're a real master at mining for disappointment.",
            ]
            await interaction.send(embed=TextEmbed(random.choice(fail_msgs)))
            return

        item: BossItem
        item.quantity = random.randint(1, 3)
        await player.add_item(item.item_id, item.quantity)
        if item == 33:  # only stone
            await interaction.send(
                embed=TextEmbed(
                    f"Looks like you found a... **{await item.get_name(db)}** {await item.get_emoji(db)}. How exciting. Maybe try a little deeper next time?"
                )
            )
            return

        embed = TextEmbed(
            f"You went to the quarries and mined out **{await item.get_name(db)}** {await item.get_emoji(db)}"
        )
        await interaction.send(embed=embed)

    # `% getting one of them`: `list of rewards`
    SCAVENGE_LOOT = [
        [60, [None]],  # --fail--
        [
            25,
            (
                # --common--
                BossPrice.from_range(500, 1000),  # 500 - 1000 scrap metal
            ),
        ],
        [
            13.5,
            (
                # --rare--
                BossPrice.from_range(1500, 5000),  # 1500 - 5000 scrap metal
            ),
        ],
        [
            1.5,
            (
                # --epic--
                BossPrice(1, "copper"),  # 1 copper
                BossItem(46, random.randint(1, 3)),  # 1 - 3 banknote
            ),
        ],
    ]

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def scavenge(self, interaction: Interaction):
        """Scavenge for resources in post-apocalyptic world, maybe you'll actually found something!"""
        db: Database = self.bot.db
        player = Player(db, interaction.user)
        reward_category = random.choices([i[1] for i in self.SCAVENGE_LOOT], [i[0] for i in self.SCAVENGE_LOOT])[0]
        reward = random.choice(reward_category)

        if reward is None:
            fail_msgs = [
                "Looks like you didn't find anything. Better luck next time, champ.",
                "You searched high and low, but came up empty-handed. Maybe try wearing your glasses next time?",
                "Unfortunately, you didn't find anything useful. At least you got some exercise, right?",
                "Welp, that was a waste of time. Maybe try looking for items that aren't invisible next time.",
                "Sorry, no luck this time. Maybe try scaring the items out of hiding with a louder noise next time?",
            ]
            await interaction.send(embed=TextEmbed(random.choice(fail_msgs)))
            return

        msg = "You searched absolutely everywhere and finally got {reward}"
        if isinstance(reward, BossPrice):
            await player.modify_currency(reward.currency_type, reward.price)
            msg = msg.format(reward=f"**{CURRENCY_EMOJIS[reward.currency_type]} {reward.price}**")
        elif isinstance(reward, BossItem):
            await player.add_item(reward.item_id, reward.quantity)
            msg = msg.format(reward=f"**{reward.quantity} {await reward.get_name(db)}** {await reward.get_emoji(db)}")
        await interaction.send(embed=TextEmbed(msg))

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

    @nextcord.slash_command()
    @helpers.work_in_progress(dev_guild_only=True)
    async def missions(self, interaction: Interaction):
        pass


def setup(bot: commands.Bot):
    bot.add_cog(Survival(bot))

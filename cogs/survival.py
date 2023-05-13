# nextcord
import nextcord
from nextcord.ext import commands, tasks
from nextcord import Interaction, Embed, SlashOption

# slash command cooldowns
import cooldowns
from cooldowns import SlashBucket

import aiohttp

# database
from utils.postgres_db import Database
import asyncpg

# my modules and constants
from utils import constants
from utils.constants import CURRENCY_EMOJIS
from utils.functions import TextEmbed, check_if_not_dev_guild, BossItem, BossPrice
from utils.player import Player
from views.template_views import ConfirmView

# maze
from maze.maze import Maze

# trade
from village.village import TradeView
from village.villagers import Villager, TradeItem

# default modules
import random
import datetime
import pytz


class Survival(commands.Cog, name="Wasteland Wandering"):
    COG_EMOJI = "🗺️"

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_villagers.start()
        self.update_villagers.add_exception_type(
            asyncpg.PostgresConnectionError,
            asyncpg.exceptions.InterfaceError,
        )

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def hunt(self, interaction: Interaction):
        """Go hunting and bring back some animals if you are lucky!"""
        db: Database = self.bot.db
        player = Player(db, interaction.user)
        # `% getting one of them`: `list of animals`
        animals = [
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
        animal_category = random.choices([i[1] for i in animals], [i[0] for i in animals])[0]
        item = random.choice(animal_category)

        if item is None:
            await interaction.send(TextEmbed("You went hunting but found nothing... No dinner tonight ig"))
            return

        item: BossItem
        await player.add_item(item.item_id)
        embed = TextEmbed(f"You went hunting and found a **{await item.get_name(db)}** {await item.get_emoji(db)}!")
        await interaction.send(embed=embed)

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def dig(self, interaction: Interaction):
        """Dig in the ground and find some buried treasure."""
        db: Database = self.bot.db
        player = Player(db, interaction.user)
        # `% getting one of them`: `list of rewards`
        items = [
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
        item_category = random.choices([i[1] for i in items], [i[0] for i in items])[0]
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
        await player.add_item(item.item_id)
        await interaction.send(
            embed=TextEmbed(
                f"You went bonkers and finally found a **{await item.get_name(db)}** {await item.get_emoji(db)} after hours of work!"
            )
        )

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def mine(self, interaction: Interaction):
        """Go mining in the caves!"""
        db: Database = self.bot.db
        player = Player(db, interaction.user)
        # `% getting one of them`: `list of rewards`
        items = [
            [30, [None]],  # --fail--
            [40, (BossItem(44),)],  # --common--  # Iron ore
            [25, (BossItem(45),)],  # --rare--  # Emerald ore
            [5, (BossItem(34),)],  # --epic--  # Diamond ore
        ]
        item_category = random.choices([i[1] for i in items], [i[0] for i in items])[0]
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

        success_msgs = [
            "Wow, you actually found a {item}. I suppose even a blind squirrel finds a nut every once in a while.",
            "You hit the jackpot and obtained a {item}! Just kidding, you got lucky.",
            "You found a {item}! It's almost like you knew what you were doing... or maybe you just got lucky.",
            "Well, looks like you're not as useless as I thought. You found a {item}.",
            "You found a {item}! It's almost like you have a sixth sense for mining... or maybe you just stumbled upon it.",
        ]
        embed = TextEmbed(
            random.choice(success_msgs).format(item=f"**{await item.get_name(db)}** {await item.get_emoji(db)}")
        )
        await interaction.send(embed=embed)

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def scavenge(self, interaction: Interaction):
        """Scavenge for resources in post-apocalyptic world, maybe you'll actually found something!"""
        db: Database = self.bot.db
        player = Player(db, interaction.user)
        # `% getting one of them`: `list of rewards`
        rewards = [
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
        reward_category = random.choices([i[1] for i in rewards], [i[0] for i in rewards])[0]
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

        success_msgs = [
            "Wow, you managed to scavenge {reward}. You're basically a survival expert now, I suppose.",
            "Congrats, you found {reward}. You're one step closer to taking down the apocalypse.",
            "Oh wow, it's another {reward}. Just what you needed.",
            "You found {reward}. Too bad it's not worth anything in this world.",
            "You found {reward}. It's not much, but at least it's something.",
            "You found {reward}. Just don't expect anyone to be impressed by it.",
            "Great work, you found {reward}. Maybe you can use it to decorate your trash heap.",
            "Excellent, you found {reward}. It's almost like finding a penny on the ground - not really worth much, but hey, you still found something.",
            "You have successfully scavenged {reward}. I bet you're thrilled to add it to your pile of junk.",
        ]
        if isinstance(reward, BossPrice):
            await player.modify_currency(reward.currency_type, reward.price)
            msg = random.choice(success_msgs).format(
                reward=f"**{CURRENCY_EMOJIS[reward.currency_type]} {reward.price}**"
            )
        elif isinstance(reward, BossItem):
            await player.add_item(reward.item_id, reward.quantity)
            msg = random.choice(success_msgs).format(
                reward=f"{reward.quantity} **{await reward.get_name(db)}** {await reward.get_emoji(db)}"
            )
        await interaction.send(embed=TextEmbed(msg))

    async def adventure_pyramid(self, button, interaction: Interaction):
        maze_size = (random.randint(15, 20), random.randint(15, 20))
        view = Maze(interaction, maze_size)
        embed = view.get_embed()
        view.message = await interaction.send(embed=embed, view=view)

    async def adventure_village(self, button, interaction: Interaction):
        if random.randint(1, 5) > 2:
            await interaction.send(
                embed=TextEmbed("OH GOD they are **FOES**! They chased you for 10 km, luckily you outran them."),
                ephemeral=True,
            )
        else:
            db: Database = self.bot.db
            villages = await db.fetch(
                """
                SELECT structure_id, name
                FROM utility.structures
                WHERE structure_type_id = 1
                """
            )
            village = random.choice(villages)

            # add village to player's discovered structures list
            await db.execute(
                """
                INSERT INTO players.discovered_structures (player_id, structure_id)
                VALUES ($1, $2)
                """,
                interaction.user.id,
                village["structure_id"],
            )
            await interaction.send(
                embed=TextEmbed(
                    f"It turns out you came across the lovely village, **{village['name']}**.\n"
                    "The villagers are very willing to meet you and trade with you!\n"
                    "Use </visit:1081863670189006868> to visit the village."
                ),
                ephemeral=True,
            )

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
                    f"Shame on you, he was a bandits. He attacked you and you lost {CURRENCY_EMOJIS['scrap_metal']} {lost_scrap}",
                ),
                ephemeral=True,
            )

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 60, SlashBucket.author, cooldown_id="adventure", check=check_if_not_dev_guild)
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
                30: (
                    "While you were wandering in the woods, you saw some smoke rising in the sky. You walked forward and saw civilisation! Wanna meet the people?",
                    self.adventure_village,
                ),
                50: (
                    "A bag of scrap metals was lying on the ground. You saw no one around you. Have you finally decided on whether to snatch it yet?",
                    self.adventure_scrap_metal,
                ),
            }
            outcome = random.choices(list(outcomes.values()), list(outcomes.keys()))[0]

            embed = Embed(title="Adventure time!", description=outcome[0])

            view = ConfirmView(
                slash_interaction=interaction,
                confirm_func=outcome[1],
                cancel_func=lambda button, interaction: cooldowns.reset_cooldown("adventure"),
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
            cooldowns.reset_cooldown("adventure")

    async def choose_structure_autocomplete(self, interaction: Interaction, data: str):
        """Returns a list of autocompleted choices of a user's discovered structures."""
        db: Database = self.bot.db
        structures = await db.fetch(
            """
            SELECT INITCAP(CONCAT(st.name, ' - ', s.name))
                FROM players.discovered_structures As ds

                INNER JOIN utility.structures As s
                ON ds.structure_id = s.structure_id
                
                INNER JOIN utility.structure_types As st
                ON s.structure_type_id = st.structure_type_id
            WHERE ds.player_id = $1
            """,
            interaction.user.id,
        )
        if not data:
            # return full list
            return sorted([structure[0] for structure in structures])
        # send a list of nearest matches from the list of item
        near_structures = sorted(
            [structure[0] for structure in structures if structure[0].lower().startswith(data.lower())]
        )
        return near_structures

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 60, SlashBucket.author, check=check_if_not_dev_guild)
    async def visit(
        self,
        interaction: Interaction,
        structure_name: str = SlashOption(
            name="structure",
            description="The structure to visit",
            required=True,
            autocomplete_callback=choose_structure_autocomplete,
        ),
    ):
        """Visit a structure that you have unlocked!"""
        structure_type, structure_name = structure_name.split(" - ")
        await interaction.send(f"You visited a {structure_type} called {structure_name}")

    @nextcord.slash_command()
    @cooldowns.cooldown(1, 15, SlashBucket.author, check=check_if_not_dev_guild)
    async def trade(self, interaction: Interaction):
        """Trade with villagers for valuable and possibly unique items!"""
        view = TradeView(interaction)
        await view.send()

    @tasks.loop(hours=1)
    async def update_villagers(self):
        # get a list of names
        params = {"nameType": "firstname", "quantity": random.randint(10, 18)}
        headers = {"X-Api-Key": "2a4f04bc0708472d9791240ca7d39476"}
        async with aiohttp.ClientSession() as session:
            async with session.get("https://randommer.io/api/Name", params=params, headers=headers) as response:
                names = await response.json()

        # generate the villagers
        villagers: list[Villager] = []
        for name in names:
            job_type = random.choice(Villager.__subclasses__())
            villagers.append(job_type(name, self.bot.db))

        # update villagers to database
        db: Database = self.bot.db
        if db.pool is None:
            return

        await db.connect()
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    """
                    TRUNCATE table trades.villagers;
                    TRUNCATE table trades.villager_remaining_trades;
                """
                )
                # insert the villagers and their trades
                await conn.executemany(
                    """
                    INSERT INTO trades.villagers (id, name, job_title, demands, supplies, num_trades)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """,
                    [
                        (
                            i + 1,
                            villager.name,
                            villager.job_title,
                            [
                                (item.item_id, item.quantity, None, None)
                                if isinstance(item, TradeItem)
                                else (None, None, item.price, item.currency_type)
                                for item in villager.demand
                            ],
                            [
                                (item.item_id, item.quantity, None, None)
                                if isinstance(item, TradeItem)
                                else (None, None, item.price, item.currency_type)
                                for item in villager.supply
                            ],
                            villager.remaining_trades,
                        )
                        for i, villager in enumerate(villagers)
                    ],
                )
        utc = pytz.timezone("UTC")
        now = datetime.datetime.now(tz=utc).strftime("%y-%#m-%#d %#H:%#M %Z")
        print(f"\033[1;30mUpdated villagers at {now}.\033[0m")
        await db.execute(f"COMMENT ON TABLE trades.villagers IS '{now}'")
        await self.bot.get_guild(919223073054539858).get_channel(988046548309016586).send(
            embed=TextEmbed(f"villagers updated at {now}")
        )

    @update_villagers.before_loop
    async def before_update_villagers(self):
        now = datetime.datetime.now()
        # Wait until the start of the next hour before starting the task loop
        start_of_next_hour = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        await nextcord.utils.sleep_until(start_of_next_hour)

    @nextcord.slash_command(name="reload-villagers", guild_ids=[constants.DEVS_SERVER_ID])
    async def reload_villagers(self, interaction: Interaction):
        """Reload the villagers used in /trade."""
        await self.update_villagers.__call__()
        await interaction.send(embed=TextEmbed("Reloaded villagers."))


def setup(bot: commands.Bot):
    bot.add_cog(Survival(bot))

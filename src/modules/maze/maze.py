# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle, SelectOption
from nextcord.ui import View, Button, button, Select, select, Modal

# default modules
import random
import math
from datetime import datetime
import asyncio

# my modules and constants
from utils.template_views import BaseView
from utils import constants
from utils.player import Player as BossPlayer
from utils.helpers import BossItem, BossCurrency, TextEmbed
from .maze_player import MazePlayer
from .maze_enemies import MazeEnemy
from .maze_utils import ITEMS, MazeItem

# mazelib
from mazelib import Maze as Mazelib
from mazelib.generate.Prims import Prims


class MazeButton(Button["Maze"]):
    """Defines a custom button to control the player in Maze."""

    def __init__(self, player: MazePlayer, btn_func: int, x: int, y: int):
        if btn_func is not None:
            if btn_func >= 0 and btn_func <= 3:  # direction
                super().__init__(
                    style=ButtonStyle.blurple,
                    emoji=constants.MAZE_DIRECTIONS[btn_func],
                    row=y,
                    custom_id=f"walk {btn_func}",
                )
            elif btn_func == 4:  # run button
                super().__init__(style=ButtonStyle.blurple, emoji="🏃", row=y, custom_id="run")
            elif btn_func == 5:  # punch button
                super().__init__(style=ButtonStyle.blurple, emoji="👊", row=y, custom_id="punch")
            elif btn_func == 6:  # inventory
                super().__init__(
                    style=ButtonStyle.blurple,
                    emoji="🎒",
                    row=y,
                    custom_id="inventory",
                )
            elif btn_func == 7:  # compass, always disabled
                super().__init__(
                    style=ButtonStyle.grey,
                    emoji="<:CH_N:1091550941733462047>",  # north compass emoji
                    row=y,
                    custom_id="compass",
                )
        else:
            super().__init__(
                style=ButtonStyle.grey,
                label="\u200b",  # zero-width space bcs label is required
                row=y,
                disabled=True,
            )
        self.player = player
        self.btn_func = btn_func

    async def callback(self, interaction: Interaction):
        if self.disabled == True:
            return

        await interaction.response.defer()

        assert self.view is not None
        view: Maze = self.view

        player = self.player

        # MAZE_DIRECTIONS = ["⬆️", "⬅️", "⬇️", "➡️"]

        embed = None

        if "walk" in self.custom_id:
            if abs(self.btn_func - player.direction) == 2:  # opposite direcitons:
                player.direction = self.btn_func
            else:
                player.walking = True

                player.direction = self.btn_func
                player.move()
                update = await view.perform_event_results(interaction)

                player.walking = False
                if update:
                    embed = view.get_embed()
                    await view.update_msg(force_update=True, embed=embed)

        elif "run" in self.custom_id:  # run
            if await self.check_in_cooldown(interaction, "run", "running"):
                return
            if player.hunger < 30:  # stop running if hunger is too low
                await interaction.send(
                    embed=TextEmbed("I'm too tired to run! Find some food before sprinting again."),
                    ephemeral=True,
                )
                return
            if not player.walking:  # let user run
                # change button style to green,
                # and disable the direction buttons
                self.style = ButtonStyle.green
                for item in view.children:
                    if "walk" in item.custom_id:
                        item.disabled = True

                old_x = None
                old_y = None
                player.walking = True
                while player.walking == True:  # if player walked, continue to do so
                    if player.hunger < 30:  # stop running if hunger is too low
                        await interaction.send(
                            embed=TextEmbed("I'm too tired to run! Find some food before sprinting again."),
                            ephemeral=True,
                        )
                        break
                    old_x, old_y = player.x, player.y
                    player.move()
                    player.hunger -= random.randint(1, 3)

                    if (old_x, old_y) == (player.x, player.y):
                        break

                    update = await view.perform_event_results(interaction)

                    if update:
                        embed = view.get_embed()
                        await view.update_msg(force_update=True, embed=embed)
                    await asyncio.sleep(0.5)

                player.walking = False

                # player stopped walking
                # 1. revert style back to original and enable the direction buttons again
                for item in view.children:
                    if "walk" in item.custom_id:
                        item.disabled = False

                await self.start_cooldown(interaction, "run")
            else:  # user should stop
                player.walking = False
        elif "punch" in self.custom_id:
            if await self.check_in_cooldown(interaction, "punch", "punching"):
                return
            punch_distance = 2
            cam, x_start_index, y_start_index = view.get_camera()

            for i in range(punch_distance + 1):
                x, y = player.get_new_position(i)

                if player.check_postion_valid(x, y):
                    cam[y - y_start_index][x - x_start_index] = "💥"
                    for enemy in view.enemies:
                        if enemy.x == x and enemy.y == y:
                            enemy.move.stop()
                            view.enemies.remove(enemy)
                            view.spawn_enemy()
                else:
                    break

            self.style = ButtonStyle.green
            embed = view.get_embed((cam, x_start_index, y_start_index))
            await view.update_msg(force_update=True, embed=embed)

            await asyncio.sleep(1)

            # punching finished, update button style
            await self.start_cooldown(interaction, "punch")
        elif "inventory" in self.custom_id:
            if not player.inventory:
                await interaction.send(embed=TextEmbed("Empty"), ephemeral=True)
                return

            embed = Embed()
            embed.set_author(name="Inventory")
            embed.add_field(name="Item", value="`not selected`")
            inv_view = InvView(view)
            inv_view.msg = await interaction.send(embed=embed, view=inv_view, ephemeral=True)
        elif "compass" in self.custom_id:
            embed = Embed()
            embed.set_image(self.emoji.url)
            embed.set_footer(text="Deleting in 3 seconds...")
            await interaction.send(embed=embed, ephemeral=True, delete_after=3)

    def get_cooldown_embed(self, seconds: float, action: str = "Ability"):
        embed = Embed()
        embed.title = f"{action} in cooldown"
        embed.description = f"wait for `{round(seconds, 1)}` seconds!"
        embed.colour = random.choice(constants.EMBED_COLOURS)
        return embed

    async def check_in_cooldown(self, interaction: Interaction, action: str, action_gerund: str = None):
        player = self.player
        cd = (datetime.now() - player.cooldowns[action][0]).total_seconds()
        if cd < player.cooldowns[action][1]:
            embed = self.get_cooldown_embed(
                player.cooldowns[action][1] - cd,
                action_gerund.title() if action_gerund is not None else f"`{action.title()}`",
            )
            await interaction.send(embed=embed, ephemeral=True)
            return True
        return False

    async def start_cooldown(self, interaction: Interaction, action: str):
        self.style = ButtonStyle.red
        player = self.player
        view: Maze = self.view

        # 2. update last_ran and timeout
        player.cooldowns[action][0] = datetime.now()

        await view.update_msg(interaction)

        # wait for cooldown and change button style back to blurple again
        await asyncio.sleep(player.cooldowns[action][1])
        self.style = ButtonStyle.blurple
        await view.update_msg(interaction)


class Maze(BaseView):
    """Shows buttons to control a player in Maze."""

    def __init__(self, interaction, size: tuple[int] = (12, 12), rewards: list[BossItem | BossCurrency] = None):
        """
        `1.` Initalise the player, enemies and the view.

        `2.` Adds buttons as the controller.

        `3.` Make traps and spawn items/enemies in the maze.

        `4.` Controls the logic for the maze, includes functions to decide whether the player wins the game.
        """

        super().__init__(interaction=interaction, timeout=90)

        # set up the map
        # **MAPS**
        # ----------
        # 0 --> ⬜ --> walkable space
        # 1 --> 🟦 --> walls
        # 2 --> 🟨 --> destination
        # 3 --> 🔺 --> trap

        m = Mazelib()
        m.generator = Prims(*size)
        m.generate()
        m.generate_entrances(end_outer=False)

        self.start = m.start
        self.end = m.end

        self.maze_map = [list(i) for i in list(m.grid)]
        for y_i, y in enumerate(self.maze_map):
            for x_i, x in enumerate(y):
                if random.randint(1, 25) == 1 and not x:
                    self.maze_map[y_i][x_i] = 3

        self.maze_map[m.end[0]][m.end[1]] = 2

        # initalise the player
        self.player = MazePlayer(self, self.start[1], self.start[0])

        # initalise enemies
        self.enemies = []
        MAX_NUM_OF_ENEMIES = 12

        self.items = []
        MAX_NUM_OF_ITEMS = 25

        for i in range(MAX_NUM_OF_ITEMS):
            self.spawn_item()

        for i in range(MAX_NUM_OF_ENEMIES):
            self.spawn_enemy()

        self.cam_width = 10

        self.updating = False

        # set up the controller and add buttons
        # MAZE_DIRECTIONS = ["⬆️", "⬅️", "⬇️", "➡️"]
        self.controller = [
            [5, 0, 6],
            [1, 4, 3],
            [7, 2, None],
        ]

        for y, row in enumerate(self.controller):
            for x, btn in enumerate(row):
                btn_func = self.controller[y][x]
                self.add_item(MazeButton(self.player, btn_func, x, y))

        self.update_compass()

        self.rewards = rewards

    async def send(self):
        embed = self.get_embed()
        self.message = await self.interaction.send(embed=embed, view=self)

    def spawn_enemy(self):
        enemy = MazeEnemy(self, 0, 0)
        while True:
            enemy.x = random.randint(1, len(self.maze_map[0])) - 1
            enemy.y = random.randint(1, len(self.maze_map)) - 1
            distance_with_player = math.sqrt((self.player.x - enemy.x) ** 2 + (self.player.y - enemy.y) ** 2)
            if (self.maze_map[enemy.y][enemy.x] not in enemy.unwalkable_cells) and (distance_with_player > 5):
                break
        enemy.move.start()
        self.enemies.append(enemy)

    def spawn_item(self):
        item = random.choices(list(ITEMS.values()), [item.spawn_chance for item in ITEMS.values()])[0]
        while True:
            x = random.randint(1, len(self.maze_map[0])) - 1
            y = random.randint(1, len(self.maze_map)) - 1
            distance_with_player = math.sqrt((self.player.x - x) ** 2 + (self.player.y - y) ** 2)
            if (
                (self.maze_map[y][x] != 3)
                and (self.maze_map[y][x] not in self.player.unwalkable_cells)
                and (distance_with_player > 5)
                and not [item for item in self.items if x == item.x and y == item.y]
            ):
                break
        self.items.append(item(self, x, y))

    def end_maze(self):
        self.clear_items()
        for enemy in self.enemies:
            enemy.move.stop()
        self.enemies = []
        self.player.walking = False

    def update_compass(self):
        compass = [i for i in self.children if "compass" in i.custom_id]
        if not compass:
            return

        compass = compass[0]
        x_delta = self.end[1] - self.player.x
        y_delta = self.end[0] - self.player.y

        degrees = math.atan2(x_delta, y_delta) / math.pi * 180

        if degrees < 0:
            degrees += 360

        dir_emojis = [
            "<:CH_S:1091550953376858182>",  # south
            "<:CH_SE:1091550956363206676>",  # south east
            "<:CH_E:1091550939908943882>",  # east
            "<:CH_NE:1091550945478987836>",  # north east
            "<:CH_N:1091550941733462047>",  # north
            "<:CH_NW:1091550949761351710>",  # north west
            "<:CH_W:1091550936079544321>",  # west
            "<:CH_SW:1091550959555063909>",  # south west
            "<:CH_S:1091550953376858182>",  # south
        ]
        lookup = round(degrees / 45)

        compass.emoji = dir_emojis[lookup]

    async def perform_event_results(self, interaction: Interaction):
        self.update_compass()

        player = self.player

        if self.maze_map[player.y][player.x] == 3:  # trap
            player.hp -= random.randint(10, 15)

        if player.hp <= 0:  # die
            player.emoji = "💀"
            self.end_maze()
            await interaction.send(embed=TextEmbed("You died!"), ephemeral=True)

        if self.maze_map[player.y][player.x] == 2:  # win
            player.emoji = "🤴🏻"
            self.end_maze()
            db = self.interaction.client.db
            # add the list of rewards to the player's inventory, if any
            reward_msg = ""
            if self.rewards:
                for i in self.rewards:
                    boss_player = BossPlayer(db, self.interaction.user)
                    if isinstance(i, BossItem):
                        await boss_player.add_item(i.item_id, i.quantity)
                        reward_msg += f"\n- ` {i.quantity}x ` {await i.get_emoji(db)} {await i.get_name(db)}"
                    else:
                        await boss_player.modify_currency(i.currency_type, i.price)
                        reward_msg += f"\n- {constants.CURRENCY_EMOJIS[i.currency_type]} {i.price:,}"

            await interaction.send(
                embed=TextEmbed("### Congrats, you won! 🎉🎉🎉" + f"\nYou also got:{reward_msg}" if reward_msg else ""),
                ephemeral=True,
            )

        if item := [item for item in self.items if player.x == item.x and player.y == item.y]:  # picked up item
            item: MazeItem = item[0]
            self.items.remove(item)

            if not self.player.inventory.get(item.name):
                self.player.inventory[item.name] = [item]
            else:
                self.player.inventory[item.name].append(item)

            inv_btn = [i for i in self.children if i.custom_id == "inventory"][0]
            inv_btn.style = ButtonStyle.green

            embed = self.get_embed()
            await self.update_msg(force_update=True, embed=embed)
            await asyncio.sleep(1)
            inv_btn.style = ButtonStyle.blurple
            embed = self.get_embed()
            await self.update_msg(embed=embed)
            return False

        return True

    def get_camera(self, cam_width=None):
        # make the camera view and return it
        if cam_width is None:
            cam_width = self.cam_width
        y_start_index = self.player.y - math.floor(cam_width / 2)

        if y_start_index < 0:
            y_start_index = 0
        y_end_index = y_start_index + cam_width
        if y_end_index >= len(self.maze_map):
            y_end_index = len(self.maze_map)
            y_start_index = y_end_index - cam_width

        x_start_index = self.player.x - math.floor(cam_width / 2)

        if x_start_index < 0:
            x_start_index = 0
        x_end_index = x_start_index + cam_width
        if x_end_index >= len(self.maze_map[0]):
            x_end_index = len(self.maze_map[0])
            x_start_index = x_end_index - cam_width

        cam = [i[x_start_index:x_end_index] for i in self.maze_map[y_start_index:y_end_index]]
        return cam, x_start_index, y_start_index

    def draw_camera(self, camera, x_start_index, y_start_index):
        camera_str = "<:frame1:1073794639758364844>"
        camera_str += "<:frame3:1073794645508763749>" * (self.cam_width)
        camera_str += "<:frame1:1073794639758364844>\n"

        # set the embed description - map
        for y in range(self.cam_width):  # 0-8
            camera_str += "<:frame2:1073794643411619931>"
            for x in range(self.cam_width):  # 0-8
                if x + x_start_index == self.player.x and y + y_start_index == self.player.y:
                    camera_str += self.player.emoji

                elif isinstance(camera[y][x], str):  # specified text
                    camera_str += camera[y][x]

                elif item := [
                    item for item in self.items if x + x_start_index == item.x and y + y_start_index == item.y
                ]:
                    camera_str += item[0].emoji

                elif enemy := [
                    enemy for enemy in self.enemies if x + x_start_index == enemy.x and y + y_start_index == enemy.y
                ]:
                    camera_str += enemy[0].emoji

                elif camera[y][x] == 0:  # walkable space
                    camera_str += "<:empty:1008231456650301450>"  # empty emoji

                elif camera[y][x] == 1:  # wall
                    camera_str += "<:wall:1071645318845837404>"

                elif camera[y][x] == 2:  # destination
                    camera_str += "🟨"

                elif camera[y][x] == 3:  # trap
                    camera_str += "<:trap:1028648275634573343>"  # 25% opacity empty emoji

            camera_str += "<:frame2:1073794643411619931>\n"

        camera_str += "<:frame1:1073794639758364844>"
        camera_str += "<:frame3:1073794645508763749>" * (self.cam_width)
        camera_str += "<:frame1:1073794639758364844>"
        return camera_str

    def get_embed(self, set_cam: tuple = None):  # cam: (cam, x_start_index, y_start_index)
        embed = Embed()

        if set_cam is not None:
            cam, x_start_index, y_start_index = set_cam
        else:
            cam, x_start_index, y_start_index = self.get_camera()

        embed.description = self.draw_camera(cam, x_start_index, y_start_index)

        prefixes = {}

        # add player HP field
        if self.player.hp > self.player.old_hp:
            prefixes["hp"] = "+"
        elif self.player.hp < self.player.old_hp:
            prefixes["hp"] = "-"

        if self.player.hunger < 30:
            prefixes["hunger"] = "-"

        embed.add_field(
            name=" ",
            value=f"```diff\n"
            f"{prefixes.get('hp', '*')} HP: {self.player.hp}\n"
            f"{prefixes.get('hunger', '*')} Hunger: {self.player.hunger}\n"
            f"```",
            inline=True,
        )
        self.player.old_hp = self.player.hp

        return embed

    async def update_msg(self, force_update=False, **kwargs):
        if kwargs.get("embed"):
            if force_update or self.updating == False:
                self.updating = True
                try:
                    await self.message.edit(view=self, **kwargs)
                except:
                    self.on_timeout()
                    return
                else:
                    await asyncio.sleep(0.4)
                    self.updating = False
        else:
            await self.message.edit(view=self)

    async def on_timeout(self) -> None:
        if self.children:
            embed = self.get_embed()
            embed.set_author(name="You have been idle for too long!")
            self.end_maze()
            await self.message.edit(embed=embed, view=self)


class InvView(View):
    def __init__(self, maze: Maze):
        super().__init__()
        self.maze = maze
        self.inventory = maze.player.inventory
        self.item: MazeItem = None

        item_select = [i for i in self.children if i.custom_id == "choose_item"][0]
        options = []
        for item_name, items in self.inventory.items():
            item = ITEMS[item_name]
            options.append(
                SelectOption(
                    label=f"{item.name.capitalize()} - {len(items)}",
                    value=item.name,
                    description=item.description,
                    emoji=item.emoji,
                )
            )
        item_select.options = options

        self.msg: nextcord.PartialInteractionMessage | nextcord.WebhookMessage = None

    @select(
        placeholder="Choose an item...",
        options=[],
        min_values=1,
        max_values=1,
        custom_id="choose_item",
    )
    async def select_item(self, select: Select, interaction: Interaction):
        await interaction.response.defer()

        items = [items for name, items in self.inventory.items() if name == select.values[0]][0]
        self.item: MazeItem = items[-1]

        use_1 = [i for i in self.children if i.custom_id == "use_1"][0]
        use_1.disabled = False

        use_max = [i for i in self.children if i.custom_id == "use_max"][0]
        use_max.disabled = False

        inv_quantity = len(items)
        self.max_quantity = inv_quantity if inv_quantity < self.item.max_use else self.item.max_use
        use_max.label = f"Use max ({self.max_quantity})"

        embed = self.msg.embeds[0]
        embed.set_field_at(
            0,
            name=f"{self.item.emoji} {self.item.name.capitalize()} - {inv_quantity}",
            value=f"> {self.item.description}",
        )

        for option in select.options:
            option.default = False
            if option.label in select.values:
                option.default = True
        await self.msg.edit(embed=embed, view=self)

    @button(label="Use 1", style=ButtonStyle.blurple, disabled=True, custom_id="use_1")
    async def use_1_item(self, button: Button, interaction: Interaction):
        items = self.inventory[self.item.name]
        if len(items) < 1:
            await interaction.send(
                embed=TextEmbed(f"You don't have enough {self.item.emoji} {self.item.name}!"),
                ephemeral=True,
            )
            return

        res = await self.item.use(view=self.maze, interaction=interaction)
        # item.use() will return `True` if the item should be consumed and `False` if not
        if res:
            if len(items) == 1:
                self.inventory.pop(self.item.name)
            else:
                self.inventory[self.item.name] = items[:-1]

        await self.msg.delete()

    @button(label="Use max", style=ButtonStyle.blurple, disabled=True, custom_id="use_max")
    async def use_max_item(self, button: Button, interaction: Interaction):
        items = self.inventory[self.item.name]
        if len(items) < self.max_quantity:
            await interaction.send(
                embed=TextEmbed(f"You don't have enough {self.item.emoji} {self.item.name}!"),
                ephemeral=True,
            )
            return

        if len(items) == self.max_quantity:
            self.inventory.pop(self.item.name)
        else:
            self.inventory[self.item.name] = items[: -self.max_quantity]

        await self.item.use(view=self.maze, interaction=interaction, quantity=self.max_quantity)
        await self.msg.delete()

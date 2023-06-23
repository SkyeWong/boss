# default modules
from datetime import datetime
from .maze_utils import ITEMS


class MazePlayer:
    """Represents a player in the maze."""

    PLAYER_EMOJIS = [
        "<:WarriorBack:1121746585747988521>",
        "<:WarriorLeft:1121746591712284704>",
        "<:WarriorFront:1121746589195702292>",
        "<:WarriorRight:1121746580756779141>",
    ]

    def __init__(self, view, x, y):
        self._hp = 100
        self.old_hp = self._hp
        self.hunger = 100
        INITIAL_INVENTORY = {"food": 15, "pill": 15, "drill": 1}

        self.inventory = {"food": [], "pill": [], "drill": []}

        for name, items in self.inventory.items():
            items.extend([ITEMS[name](view, 0, 0) for i in range(INITIAL_INVENTORY[name])])

        self.direction = 2

        self.x = x
        self.y = y
        self.walking = False
        self.unwalkable_cells = [1]

        self.view = view
        self.cooldowns = {  # "action": [last_did_at, cooldown(seconds)]
            "run": [datetime(2000, 1, 1), 5],
            "punch": [datetime(2000, 1, 1), 2],
        }
        self._emoji = self.PLAYER_EMOJIS[2]
        self._specific_emoji = False

    @property
    def emoji(self):
        if not self._specific_emoji:
            self._emoji = self.PLAYER_EMOJIS[self.direction]
        return self._emoji

    @emoji.setter
    def emoji(self, new_emoji):
        self._emoji = new_emoji
        self._specific_emoji = True
        return self._emoji

    @property
    def hp(self):
        return self._hp

    @hp.setter
    def hp(self, new_hp):
        self._hp = new_hp
        if self._hp <= 0:
            self.death()

    def death(self):
        self.emoji = "💀"
        self.view.end_maze()

    def get_new_position(self, num_of_cells: int = 1):
        x = self.x
        y = self.y

        # MAZE_DIRECTIONS = ["⬆️", "⬅️", "⬇️", "➡️"]

        if self.direction == 0:  # up
            y -= num_of_cells
        elif self.direction == 1:  # left
            x -= num_of_cells
        elif self.direction == 2:  # down
            y += num_of_cells
        elif self.direction == 3:  # right
            x += num_of_cells
        return x, y

    def check_postion_valid(self, x=None, y=None):
        x = self.x if x is None else x
        y = self.y if y is None else y

        maze_map = self.view.maze_map
        if y < len(maze_map) and y > 0 and x < len(maze_map[0]) and x > 0:
            pos = maze_map[y][x]
            return pos not in self.unwalkable_cells
        return False

    def move(self):
        # MAZE_DIRECTIONS = ["⬆️", "⬅️", "⬇️", "➡️"]
        x, y = self.get_new_position()
        if self.check_postion_valid(x, y):
            self.x = x
            self.y = y

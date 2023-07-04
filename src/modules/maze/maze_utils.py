# nextcord
from nextcord import Interaction, Embed

# default modules
import itertools
import random


class Cell:
    """Represents a cell in the maze."""

    id_iter = itertools.count()  # function to get the next cell ID

    def __init__(self, x: int, y: int, *, counter: int, parent_id: int):
        self.id = next(self.id_iter)
        self.x = x
        self.y = y
        self.counter = counter  # counter is cells away from target (player) in a route
        self.parent_id = parent_id
        self.added_adjacent_cells = False


class MazeItem:
    """
    ### `MAZE ITEM`: (item template)
    Represents an item in the maze.
    """

    name = ""
    description = ""
    emoji = ""
    max_use = 0
    spawn_chance = 0

    def __init__(self, view, x, y) -> None:
        self.view = view
        self.x = x
        self.y = y

    async def use(self, *, view, interaction: Interaction, quantity: int = 1):
        """Function that runs when player uses the item."""
        pass


class Food(MazeItem):
    """
    ### `MAZE ITEM`: food
    Restores a player's hunger when used.
    """

    name = "food"
    description = "Restores 30 points of hunger."
    emoji = "🍗"
    max_use = 2
    spawn_chance = 70

    def __init__(self, view, x, y) -> None:
        super().__init__(view, x, y)

    async def use(self, *, view, interaction: Interaction, quantity: int = 1):
        player = view.player
        player.hunger += 30 * quantity
        player.hunger = 100 if player.hunger > 100 else player.hunger
        embed = view.get_embed()
        await view.update_msg(embed=embed)
        return True


class Pill(MazeItem):
    """
    ### `MAZE ITEM`: pill
    Restores a player's health when used.
    """

    name = "pill"
    description = "Restores 12-20 points of health."
    emoji = "💊"
    max_use = 3
    spawn_chance = 25

    def __init__(self, view, x, y) -> None:
        super().__init__(view, x, y)

    async def use(self, *, view, interaction: Interaction, quantity: int = 1):
        player = view.player
        player.hp += sum(random.randint(12 * quantity, 20 * quantity))
        player.hp = 100 if player.hp > 100 else player.hp
        embed = view.get_embed()
        await view.update_msg(embed=embed)
        return True


class Drill(MazeItem):
    """
    ### `MAZE ITEM`: drill
    Blasts through a wall and recieve 50 damage
    """

    name = "drill"
    description = "Feeling stuck? Use me to blast through the wall! (side effect: receive 50 points of damage)"
    emoji = "<:drill:1081581989427167342>"
    max_use = 1
    spawn_chance = 5

    def __init__(self, view, x, y) -> None:
        super().__init__(view, x, y)

    async def use(self, *, view, interaction: Interaction, quantity: int = 1):
        player = view.player
        x, y = player.get_new_position()
        if player.hp <= 50:
            await interaction.send(
                embed=Embed(description="You sure you gonna drill through the wall? You seem a bit low dude"),
                ephemeral=True,
                delete_after=3,
            )
            return False

        if view.maze_map[y][x] == 1:
            view.maze_map[y][x] = 0
            player.hp -= 50
        else:
            await interaction.send(embed=Embed(description="That's not a wall bruh."), ephemeral=True, delete_after=3)
            return False

        embed = view.get_embed()
        await view.update_msg(embed=embed)
        return True


ITEMS = {item.name: item for item in MazeItem.__subclasses__()}

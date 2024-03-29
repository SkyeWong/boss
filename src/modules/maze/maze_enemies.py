# default modules
import random
import asyncio

# nextcord
from nextcord.ext import tasks


# my modules and constants
from utils.helpers import TextEmbed
from .maze_utils import Cell


class MazeEnemy:
    """Represents an enemy in the maze. Could be zombies, and other stuffs that i havent thought of."""

    def __init__(self, view, x: int, y: int):
        self.x = x
        self.y = y
        self.view = view
        self.unwalkable_cells = [1]
        self.emoji = random.choice(
            [
                "<:keith_kissing:1005866421303124089>",
                "<:hoho:1005497840316977252>",
                "<:karson:1004400450117836850>",
            ]
        )

    def get_all_possible_routes(self):
        player = self.view.player
        cells = [Cell(player.x, player.y, counter=0, parent_id=None)]
        while True:
            for cell in cells:
                if not cell.added_adjacent_cells:
                    new_cells = self.get_adjacent_cells(cell)
                    new_cells = self.remove_unwalkable_cells(new_cells)
                    new_cells = self.remove_repeated_cells(new_cells, cells)
                    cell.added_adjacent_cells = True
                    cells.extend(new_cells)
            if [
                cell for cell in cells if cell.x == self.x and cell.y == self.y
            ]:  # check if enemy current cell is in the list of possible routes. End the loop if it is.
                break
        return cells

    def get_adjacent_cells(self, cell: Cell):
        counter = cell.counter + 1
        adjacent_cells = [
            Cell(cell.x, cell.y - 1, counter=counter, parent_id=cell.id),  # upwards
            Cell(cell.x + 1, cell.y, counter=counter, parent_id=cell.id),  # rightwards
            Cell(cell.x, cell.y + 1, counter=counter, parent_id=cell.id),  # downwards
            Cell(cell.x - 1, cell.y, counter=counter, parent_id=cell.id),  # leftwards
        ]
        return adjacent_cells

    def remove_unwalkable_cells(self, cells: list[Cell]):
        maze_map = self.view.maze_map

        filtered_cells = []

        for cell in cells:
            if cell.y < len(maze_map) and cell.x < len(maze_map[0]):
                pos = maze_map[cell.y][cell.x]
                if pos not in self.unwalkable_cells:
                    # if cell.y is not player.y and cell.x is not player.x:
                    filtered_cells.append(cell)
        return filtered_cells

    def remove_repeated_cells(self, cells: list[Cell], all_cells: list[Cell]):
        filtered_cells = []

        for cell in cells:
            repeated_cells = [i for i in all_cells if i.x == cell.x and i.y == cell.y]
            if not repeated_cells:
                filtered_cells.append(cell)
        return filtered_cells

    def get_target_cell(self):
        cells = self.get_all_possible_routes()
        current_cell = [cell for cell in cells if cell.x == self.x and cell.y == self.y][0]
        target_cell = [cell for cell in cells if cell.id == current_cell.parent_id]
        return target_cell[0] if target_cell else current_cell

    @tasks.loop(seconds=3)
    async def move(self):
        view = self.view
        # check if enemy is in a certain area before moving
        _, x_start_index, y_start_index = view.get_camera(12)
        if self.x > x_start_index and self.x < x_start_index + 15:
            if self.y > y_start_index and self.y < y_start_index + 15:
                player = view.player
                # find the target cell and move there, if the new distance with player is larger than 0
                target_cell: Cell = self.get_target_cell()
                if target_cell.x != view.player and target_cell.y != view.player:
                    self.x = target_cell.x
                    self.y = target_cell.y

                # if player is within 1 block of distance, deal 12 points of damage
                if (self.x == player.x and abs(self.y - player.y) == 1) or (
                    self.y == player.y and abs(self.x - player.x) == 1
                ):
                    player.hp -= random.randint(7, 12)

                view = self.view
                if player.hp <= 0:  # die
                    player.emoji = "💀"
                    self.end_maze()
                    await view.interaction.send(embed=TextEmbed("You died!"), ephemeral=True)
                # get the embed and edit the message
                embed = view.get_embed()
                await view.update_msg(embed=embed)

    @move.before_loop
    async def wait_before_moving(self):
        await asyncio.sleep(3)  # wait 3 seconds before starting to move

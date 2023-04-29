from PIL import Image, ImageDraw
import random
import sys

# Create the background image
background = Image.open("resources/village_bg.png")

# Define the size of the background image and the size of each grid cell
width, height = background.size
cell_width, cell_height = 110, 80

# Define the starting position of the grids
start_x, start_y = 70, 60

# Define the ending position of the grids
end_x, end_y = width - 60, height - 20

# Calculate the number of rows and columns in the grid
num_rows = (end_y - start_y) // cell_height
num_cols = (end_x - start_x) // cell_width

# Define the list of house images
house_images = [
    Image.open("resources/house1.png"),
    Image.open("resources/house2.png"),
]
for i in house_images:
    i.thumbnail((100, 100))

# Define the list of used grid cells
used_cells = []

# Define the list of houses
houses = []

# Generate a random village map
for i in range(num_cols * num_rows - random.randint(1, 5)):
    # Find a random unused grid cell
    while True:
        if len(used_cells) == num_cols * num_rows:
            print("There are more houses than the grids! They could not be generated.")
            sys.exit(0)

        row = random.randint(0, num_rows - 1)
        col = random.randint(0, num_cols - 1)
        if (row, col) not in used_cells:
            used_cells.append((row, col))
            break

    # Choose a random house image
    house_image = random.choice(house_images)

    # Calculate the coordinates to paste the house image with an offset based on the starting position
    offset_x = cell_width / 10
    offset_y = cell_height / 10
    x = start_x + col * cell_width + random.randint(-offset_x, offset_x)
    y = start_y + row * cell_height + random.randint(-offset_y, offset_y)

    # Check if the house is within the allowed bounds
    if x > end_x - house_image.width or y > end_y - house_image.height:
        continue

    # Add the house to the list of houses
    houses.append({"image": house_image, "x": x, "y": y})

# Sort the houses by their y coordinate to ensure they are displayed in the correct order
houses = sorted(houses, key=lambda h: h["y"])

# Draw the grid lines onto the background
draw = ImageDraw.Draw(background)
for row in range(num_rows + 1):
    y = start_y + row * cell_height
    for col in range(num_cols + 1):
        x = start_x + col * cell_width
        draw.rectangle((x, y, x + cell_width, y + cell_height), outline=(255, 0, 0))

# Paste the house images onto the background
for house in houses:
    # Paste the house image onto the background
    background.paste(house["image"], (house["x"], house["y"]), house["image"])

# Save the final image
background.save("village_map.png")
input()

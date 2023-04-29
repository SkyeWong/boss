import random
from PIL import Image, ImageDraw

# set the background image
background_image = Image.open("resources/village_bg.png")

# calculate the grid size based on the size of the image
grid_size = min(background_image.width, background_image.height) // 10
house_size = int(grid_size * 0.8)

# calculate the number of houses that can fit in the grid
num_houses_w = int(background_image.width / grid_size)
num_houses_h = int(background_image.height / grid_size)
num_houses = num_houses_w * num_houses_h

# load the house image
house_image = Image.open("resources/house.png")

# create a list of house positions
house_positions = []
for y in range(num_houses_h):
    for x in range(num_houses_w):
        offset_x = random.randint(-20, 20)
        offset_y = random.randint(-20, 20)
        house_x = x * grid_size + offset_x
        house_y = y * grid_size + offset_y
        house_positions.append((house_x, house_y))

# check for overlapping houses
for i in range(num_houses):
    for j in range(i + 1, num_houses):
        x1, y1 = house_positions[i]
        x2, y2 = house_positions[j]
        if abs(x1 - x2) < house_size and abs(y1 - y2) < house_size:
            offset_x = random.randint(-20, 20)
            offset_y = random.randint(-20, 20)
            house_positions[j] = (x2 + offset_x, y2 + offset_y)

# create a drawing context
draw = ImageDraw.Draw(background_image)

# draw the houses on the image
for pos in house_positions:
    x, y = pos
    x -= house_size // 2
    y -= house_size // 2
    background_image.paste(house_image, (x, y), house_image)

# create a list of paths
paths = []
for i in range(num_houses):
    for j in range(i + 1, num_houses):
        x1, y1 = house_positions[i]
        x2, y2 = house_positions[j]
        dx = x2 - x1
        dy = y2 - y1
        if dx != 0 and dy != 0:
            continue
        path = [(x1, y1)]
        if dx != 0:
            x3 = x2
            y3 = y1
        else:
            x3 = x1
            y3 = y2
        path.append((x3, y3))
        path.append((x2, y2))
        paths.append(path)

# draw the paths on the image
for path in paths:
    draw.line(path, fill="black", width=3)

# save the image
background_image.show()

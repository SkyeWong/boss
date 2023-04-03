# nextcord
import nextcord
from nextcord import Embed, Interaction, ButtonStyle, SelectOption
from nextcord.ui import View, Button, button, Select, select, Modal

# default modules
import random
import math
from datetime import datetime
import asyncio

# database
from mysql.connector import Error
from database import boss_pool

# my modules and constants
from views.template_views import BaseView
from utils import constants


class Village(BaseView):
    def __init__(self, slash_interaction: Interaction, *, timeout=None):
        super().__init__(slash_interaction, timeout=60)

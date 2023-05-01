#nextcord
import nextcord
from nextcord.ext import tasks

# database
from utils.postgres_db import Database

import aiohttp

# my modules
from utils import functions, constants
from utils.constants import SCRAP_METAL, COPPER

# default modules
import random
import datetime
from typing import Union, Literal


class TradeItem:
    def __init__(self, item_id: int, quantity: int) -> None:
        self.item_id = item_id
        self.quantity = quantity
        self._name = None
        self._emoji = None

    async def get_name(self, db: Database):
        if self._name is None:
            self._name = await db.fetchval(
                """
                SELECT name
                FROM utility.items
                WHERE item_id = $1
                """,
                self.item_id,
            )
        return self._name

    async def get_emoji(self, db: Database):
        if self._emoji is None:
            self._emoji = await db.fetchval(
                """
                SELECT CONCAT('<:', emoji_name, ':', emoji_id, '>') AS emoji
                FROM utility.items
                WHERE item_id = $1
                """,
                self.item_id,
            )
        return self._emoji


class TradePrice:
    def __init__(self, price: Union[int, str], type: Literal["scrap_metal", "copper"] = "scrap_metal") -> None:
        if type not in ("scrap_metal", "copper"):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")
        self.type = type
        
        if isinstance(price, str):
            self.price = functions.text_to_num(price)
        elif isinstance(price, int):
            self.price = price
        
    @classmethod
    def from_range(cls, min_price: Union[int, str], max_price: Union[int, str], type: Literal["scrap_metal", "copper"] = "scrap_metal") -> None:
        if type not in ("scrap_metal", "copper"):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")
        
        if isinstance(min_price, str):
            min_price = functions.text_to_num(min_price)
        if isinstance(max_price, str):
            max_price = functions.text_to_num(max_price)
            
        return cls(random.randint(min_price, max_price), type)


class Villager:
    """
    Represents a villager that the user can trade with.
    # Parameters
    `name`: villager's name
    `job_type`: villager's job_type,
    `demands` and `supply`: list of item_ids/ scrap metals that are required/provided
    """

    def __init__(
        self,
        villager_id: int,
        name: str,
        job_title: str,
        demand: list[TradeItem | TradePrice],
        supply: list[TradeItem | TradePrice],
        num_trades: int,
        db: Database,
    ) -> None:
        self.villager_id = villager_id
        self.name = name
        self.job_title = job_title
        self.demand = demand
        self.supply = supply
        self.remaining_trades = num_trades
        self.db = db

    async def format_trade(self):
        msgs = ["", ""]
        for index, value in enumerate((self.demand, self.supply)):
            for i in value:
                if isinstance(i, TradePrice):
                    msgs[index] += f"\n{constants.CURRENCY_EMOJIS[i.type]} ` {i.price:,} `"
                elif isinstance(i, TradeItem):
                    msgs[index] += f"\n` {i.quantity}x ` {await i.get_emoji(self.db)} {await i.get_name(self.db)}"
        return msgs[0], msgs[1]


class Hunter(Villager):
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        trades = (
            [  # price is `TradePrice(random * max_quantity * unit price[min], random * max_quantity * unit price[max])`
                {
                    "demand": [TradeItem(26, round(rand * 8))],  # skunk
                    "supply": [TradePrice.from_range(round(rand * 8 * 10_000), round(rand * 8 * 15_000))],
                },
                {"demand": [TradeItem(23, round(rand * 8))], "supply": [TradePrice.from_range("50k", "120k")]},  # duck
                {"demand": [TradeItem(25, round(rand * 8))], "supply": [TradePrice.from_range("210k", "300k")]},  # sheep
                {"demand": [TradeItem(18, 1)], "supply": [TradePrice.from_range("40k", "70k")]},  # deer
            ]
        )
        trade = random.choice(trades)
        super().__init__(
            name=name,
            job_title=__class__.__name__,
            demand=trade["demand"],
            supply=trade["supply"],
            num_trades=trade.get("trades", 8),
            villager_id=None,
            db=db,
        )


class Mason(Villager):
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        trades = [  # price is `random * quantity * unit price[min AND max]`
            {
                "demand": [TradeItem(31, round(rand * 10))],  # dirt
                "supply": [TradePrice.from_range(round(rand * 10 * 5), round(rand * 10 * 10))],
            },
            {
                "demand": [TradeItem(33, round(rand * 10))],  # stone
                "supply": [TradePrice.from_range(round(rand * 10 * 2_800), round(rand * 10 * 3_000))],
            },
        ]
        trade = random.choice(trades)
        super().__init__(
            name=name,
            job_title=__class__.__name__,
            demand=trade["demand"],
            supply=trade["supply"],
            num_trades=trade.get("trades", 100),
            villager_id=None,
            db=db,
        )


class Armourer(Villager):
    def __init__(self, name: str, db: Database) -> None:
        trades = [{"demand": [TradePrice.from_range("420m", "999m")], "supply": [TradeItem(4, 1)]}]  # aqua defender
        trade = random.choice(trades)
        super().__init__(
            name=name,
            job_title=__class__.__name__,
            demand=trade["demand"],
            supply=trade["supply"],
            num_trades=trade.get("trades", 3),
            villager_id=None,
            db=db,
        )


class Archaeologist(Villager):
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        trades = [  # price is `random * quantity * unit price[min AND max]`
            {
                "demand": [TradeItem(27, round(rand * 2))],  # ancient coin
                "supply": [TradePrice.from_range(round(rand * 2 * 4_000_000), round(rand * 2 * 8_000_000))],
                "trades": 3,
            },
            {
                "demand": [TradeItem(46, round(rand * 5))],  # banknote
                "supply": [TradePrice.from_range(round(rand * 5 * 150_000), round(rand * 5 * 210_000))],
                "trades": 10,
            },
        ]
        trade = random.choice(trades)
        super().__init__(
            name=name,
            job_title=__class__.__name__,
            demand=trade["demand"],
            supply=trade["supply"],
            num_trades=trade.get("trades", 100),
            villager_id=None,
            db=db,
        )


class Farmer(Villager):
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        trades = [  # price is `random * quantity * unit price[min AND max]`
            {"demand": [TradeItem(29, round(rand * 5))], "supply": [TradeItem(48, 1)], "trades": 8},  # wheat  # bread
            {
                "demand": [TradeItem(29, round(rand * 5))],  # wheat
                "supply": [TradePrice.from_range(round(rand * 5 * 20_000), round(rand * 5 * 40_000))],
            },
            {
                "demand": [TradeItem(30, round(rand * 5))],  # cabbage
                "supply": [TradePrice.from_range(round(rand * 5 * 40_000), round(rand * 5 * 60_000))],
            },
            {
                "demand": [TradeItem(30, round(rand * 5))],  # carrot
                "supply": [TradePrice.from_range(round(rand * 5 * 25_000), round(rand * 5 * 35_000))],
            },
        ]
        trade = random.choice(trades)
        super().__init__(
            name=name,
            job_title=__class__.__name__,
            demand=trade["demand"],
            supply=trade["supply"],
            num_trades=trade.get("trades", 15),
            villager_id=None,
            db=db,
        )
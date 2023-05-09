# nextcord
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
from typing import Union, Literal, Optional


class TradeItem:
    def __init__(
        self,
        item_id: int,
        quantity: int,
        name: Optional[str] = None,
        emoji: Optional[str] = None,
    ) -> None:
        self.item_id = item_id
        self.quantity = quantity
        self._name = name
        self._emoji = emoji

    async def get_name(self, db: Database):
        """Retrieves the name of the item from the database, if not already cached."""
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
        """Retrieves the emoji representation of the item from the database, if not already cached."""
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

    def __mul__(self, other):
        """
        Multiply the quantity of this `TradeItem` by a scalar value.

        Args:
            other (int or float): The scalar value to multiply the quantity by.

        Raises:
            NotImplementedError: If the `other` argument is not an instance of
                either the int or float classes.

        Returns:
            TradeItem: A new TradeItem instance with a quantity equal to the current quantity multiplied by the scalar value.
        """
        if not isinstance(other, (int, float)):
            raise NotImplementedError(
                f"`other` must be type int or float, not {other.__class__}"
            )
        return self.__class__(
            self.item_id, round(self.quantity * other), self._name, self._emoji
        )

    def __repr__(self):
        return f"TradeItem(item_id={self.item_id}, quantity={self.quantity}, name={self._name!r}, emoji={self._emoji!r})"


class TradePrice:
    def __init__(
        self,
        price: Union[int, str],
        currency_type: Literal["scrap_metal", "copper"] = "scrap_metal",
    ) -> None:
        if currency_type not in ("scrap_metal", "copper"):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")
        self.currency_type = currency_type

        if isinstance(price, str):
            self.price = functions.text_to_num(price)
        elif isinstance(price, int):
            self.price = price

    @classmethod
    def from_range(
        cls,
        min_price: Union[int, str],
        max_price: Union[int, str],
        currency_type: Literal["scrap_metal", "copper"] = "scrap_metal",
    ) -> "TradePrice":
        """Creates a new TradePrice instance with a random price value within a range.

        Args:
            min_price (int or str): The minimum price value, either as an integer or a string.
            max_price (int or str): The maximum price value, either as an integer or a string.
            type (str, optional): The type of currency, either "scrap_metal" or "copper". Defaults to "scrap_metal".

        Raises:
            ValueError: If the `type` argument is not "scrap_metal" or "copper".

        Returns:
            TradePrice: A new TradePrice instance with a price value randomly chosen within the specified range.
        """
        if currency_type not in ("scrap_metal", "copper"):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")

        if isinstance(min_price, str):
            min_price = functions.text_to_num(min_price)
        if isinstance(max_price, str):
            max_price = functions.text_to_num(max_price)

        return cls(random.randint(min_price, max_price), currency_type)

    @classmethod
    def from_unit_price(
        cls,
        unit_price: int,
        quantity: int,
        rand_factor: float,
        currency_type: Literal["scrap_metal", "copper"] = "scrap_metal",
    ) -> "TradePrice":
        """
        Create a new TradePrice instance based on a unit price, quantity, and random factor.

        Args:
            unit_price (int): The unit price of the item.
            quantity (int): The quantity of items being traded.
            rand_factor (float): A random factor between 0.8 and 1.2 to adjust the price.

        Returns:
            TradePrice: A new TradePrice instance with a price range based on the unit price,
            quantity, and random factor.
        """
        if currency_type not in ("scrap_metal", "copper"):
            raise ValueError("Currency must be either `scrap_metal` or `copper`.")
        rand_price = round(rand_factor * quantity * unit_price)
        price_min = int(rand_price * 1.2)
        price_max = int(rand_price * 0.8)
        return cls.from_range(price_min, price_max, currency_type)

    def __mul__(self, other):
        """Multiplies the price of this TradePrice by a scalar value.

        Args:
            other (int or float): The scalar value to multiply the price by.

        Returns:
            TradePrice: A new TradePrice instance with a price value equal to the current price multiplied by the scalar value.
        """
        return self.__class__(self.price * other, self.currency_type)

    def __repr__(self):
        return f"TradePrice(price={self.price}, type='{self.currency_type}')"


class Villager:
    """
    # Represents a villager that the user can trade with.

    Args:
        `villager_id` (int): The ID of the villager.
        `name` (str): The name of the villager.
        `job_title` (str): The job title of the villager.
        `demand` (list[TradeItem | TradePrice]): A list of items or prices that the villager demands.
        `supply` (list[TradeItem | TradePrice]): A list of items or prices that the villager supplies.
        `num_trades` (int): The number of trades remaining with the villager.
        `db` (Database): The database object to use for accessing item information.
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
                    msgs[
                        index
                    ] += f"\n{constants.CURRENCY_EMOJIS[i.currency_type]} ` {i.price:,} `"
                elif isinstance(i, TradeItem):
                    msgs[
                        index
                    ] += f"\n` {i.quantity}x ` {await i.get_emoji(self.db)} {await i.get_name(self.db)}"
        return msgs[0], msgs[1]


class Hunter(Villager):
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        # fmt: off
        # price is `TradePrice(random * max_quantity * unit price[min], random * max_quantity * unit price[max])`
        buy_trades = [
            {
                "demand": [TradeItem(26, round(rand * 8))],  # skunk
                "supply": [TradePrice.from_unit_price(12_000, 8, rand)],
            },
            {
                "demand": [TradeItem(23, round(rand * 8))],  # duck
                "supply": [TradePrice.from_unit_price(20_000, 8, rand)],
            },  
            {
                "demand": [TradeItem(25, round(rand * 8))],  # sheep
                "supply": [TradePrice.from_unit_price(35_000, 8, rand)],
            },  
            {
                "demand": [TradeItem(24, round(rand * 8))],  # rabbit
                "supply": [TradePrice.from_unit_price(38_000, 8, rand)],
            },  
            {
                "demand": [TradeItem(22, round(rand * 8))],  # cow
                "supply": [TradePrice.from_unit_price(40_000, 8, rand)],
            },  
            {
                "demand": [TradeItem(18, round(rand * 8))],  # deer
                "supply": [TradePrice.from_unit_price(55_000, 8, rand)],
            },  
            {
                "demand": [TradeItem(21, round(rand * 8))],  # boar
                "supply": [TradePrice.from_unit_price(82_000, 8, rand)],
            },  
            {
                "demand": [TradeItem(20, round(rand * 8))],  # dragon
                "supply": [TradePrice.from_unit_price(850_000, 8, rand)],
            },  
        ]
        
        trades = []
        # flip the trades so that hunters sell animals as well. 
        # decrease the amount of animals supplied,
        # but increase the price.
        for i in buy_trades:
            trades.append(i)
            trades.append({
                "demand": [j * 0.8 for j in i["supply"]], 
                "supply": [k * 1.2 for k in i["demand"]]
            })
            
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
        # fmt: on


class Mason(Villager):
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        # fmt: off
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
        # fmt: on


class Armourer(Villager):
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        # fmt: off
        trades = [  # price is `random * quantity * unit price[min AND max]`
            {
                "demand": [
                    TradePrice.from_range("420m", "999m"),
                    TradeItem(34, round(rand * 5)),  # diamond ore
                ],
                "supply": [TradeItem(4, 1)]  # aqua defender
            },
            {
                "demand": [
                    TradePrice.from_range("8m", "20m"),
                    TradeItem(44, round(rand * 5)),  # iron ore
                ],
                "supply": [TradeItem(49, 1)]  # iron sword
            }
        ]
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
        # fmt: on


class Archaeologist(Villager):
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        # fmt: off
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
        # fmt: on


class Farmer(Villager):
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        # fmt: off
        trades = [  # price is `random * quantity * unit price[min AND max]`
            {"demand": [TradeItem(29, round(rand * 5))], "supply": [TradeItem(48, 1)], "trades": 8},  # wheat  # bread
            {
                "demand": [TradeItem(29, round(rand * 5))],  # wheat
                "supply": [TradePrice.from_range(round(rand * 5 * 20_000), round(rand * 5 * 40_000))],
            },
            {
                "demand": [TradePrice.from_range(round(rand * 5 * 30_000), round(rand * 5 * 45_000))],
                "supply": [TradeItem(29, round(rand * 5))],  # wheat
            },
            {
                "demand": [TradeItem(30, round(rand * 5))],  # cabbage
                "supply": [TradePrice.from_range(round(rand * 5 * 40_000), round(rand * 5 * 60_000))],
            },
            {
                "supply": [TradePrice.from_range(round(rand * 5 * 50_000), round(rand * 5 * 65_000))],
                "demand": [TradeItem(30, round(rand * 5))],  # cabbage
            },
            {
                "demand": [TradeItem(47, round(rand * 5))],  # carrot
                "supply": [TradePrice.from_range(round(rand * 5 * 25_000), round(rand * 5 * 35_000))],
            },
            {
                "supply": [TradePrice.from_range(round(rand * 5 * 35_000), round(rand * 5 * 40_000))],
                "demand": [TradeItem(47, round(rand * 5))],  # carrot
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
        # fmt: on

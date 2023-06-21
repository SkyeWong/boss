# database
from utils.postgres_db import Database

# my modules
from utils import constants
from utils.helpers import BossItem, BossPrice

# default modules
import random
from typing import Optional


class Villager:
    """
    # Represents a villager that the user can trade with.

    Args:
        `villager_id` (int): The ID of the villager.
        `name` (str): The name of the villager.
        `job_title` (str): The job title of the villager.
        `demand` (list[BossItem | BossPrice]): A list of items or prices that the villager demands.
        `supply` (list[BossItem | BossPrice]): A list of items or prices that the villager supplies.
        `num_trades` (int): The number of trades remaining with the villager.
        `db` (Database): The database object to use for accessing item information.
    """

    def __init__(
        self,
        villager_id: int,
        name: str,
        job_title: str,
        demand: list[BossItem | BossPrice],
        supply: list[BossItem | BossPrice],
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

    async def format_trade(self, trade_quantity: Optional[int] = 1):
        msgs = ["", ""]
        for index, value in enumerate((self.demand, self.supply)):
            for i in value:
                if isinstance(i, BossPrice):
                    msgs[index] += f"\n{constants.CURRENCY_EMOJIS[i.currency_type]} ` {i.price * trade_quantity:,} `"
                elif isinstance(i, BossItem):
                    msgs[index] += f"\n` {i.quantity * trade_quantity}x ` {await i.get_emoji(self.db)} {await i.get_name(self.db)}"  # fmt: skip
        return msgs[0], msgs[1]


class Hunter(Villager):
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        # fmt: off
        # price is `BossPrice(random * max_quantity * unit price[min], random * max_quantity * unit price[max])`
        buy_trades = [
            {
                "demand": [BossItem(26, round(rand * 8))],  # skunk
                "supply": [BossPrice.from_unit_price(12_000, 8, rand)],
            },
            {
                "demand": [BossItem(23, round(rand * 8))],  # duck
                "supply": [BossPrice.from_unit_price(20_000, 8, rand)],
            },  
            {
                "demand": [BossItem(25, round(rand * 8))],  # sheep
                "supply": [BossPrice.from_unit_price(35_000, 8, rand)],
            },  
            {
                "demand": [BossItem(24, round(rand * 8))],  # rabbit
                "supply": [BossPrice.from_unit_price(38_000, 8, rand)],
            },  
            {
                "demand": [BossItem(22, round(rand * 8))],  # cow
                "supply": [BossPrice.from_unit_price(40_000, 8, rand)],
            },  
            {
                "demand": [BossItem(18, round(rand * 8))],  # deer
                "supply": [BossPrice.from_unit_price(55_000, 8, rand)],
            },  
            {
                "demand": [BossItem(21, round(rand * 8))],  # boar
                "supply": [BossPrice.from_unit_price(82_000, 8, rand)],
            },  
            {
                "demand": [BossItem(20, round(rand * 8))],  # dragon
                "supply": [BossPrice.from_unit_price(850_000, 8, rand)],
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
                "demand": [BossItem(31, round(rand * 10))],  # dirt
                "supply": [BossPrice.from_range(round(rand * 10 * 5), round(rand * 10 * 10))],
            },
            {
                "demand": [BossItem(33, round(rand * 10))],  # stone
                "supply": [BossPrice.from_range(round(rand * 10 * 2_800), round(rand * 10 * 3_000))],
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
                    BossPrice.from_range("500m", "999m"),
                    BossItem(34, round(rand * 5)),  # diamond ore
                ],
                "supply": [BossItem(4, 1)]  # aqua defender
            },
            {
                "demand": [
                    BossPrice.from_range("8m", "20m"),
                    BossItem(44, round(rand * 5)),  # iron ore
                ],
                "supply": [BossItem(49, 1)]  # iron sword
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
                "demand": [BossItem(27, round(rand * 2))],  # ancient coin
                "supply": [BossPrice.from_range(round(rand * 2 * 4_000_000), round(rand * 2 * 8_000_000))],
                "trades": 3,
            },
            {
                "demand": [BossPrice.from_range(round(rand * 2 * 6_000_000), round(rand * 2 * 10_000_000))],
                "supply": [BossItem(27, round(rand * 2))],  # ancient coin
                "trades": 3,
            },
            {
                "demand": [BossPrice.from_range(round(rand * 5 * 150_000), round(rand * 5 * 210_000))],
                "supply": [BossItem(46, round(rand * 5))],  # banknote
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
            {"demand": [BossItem(29, round(rand * 5))], "supply": [BossItem(48, 1)], "trades": 8},  # wheat  # bread
            {
                "demand": [BossItem(29, round(rand * 5))],  # wheat
                "supply": [BossPrice.from_range(round(rand * 5 * 20_000), round(rand * 5 * 40_000))],
            },
            {
                "demand": [BossPrice.from_range(round(rand * 5 * 30_000), round(rand * 5 * 45_000))],
                "supply": [BossItem(29, round(rand * 5))],  # wheat
            },
            {
                "demand": [BossItem(30, round(rand * 5))],  # cabbage
                "supply": [BossPrice.from_range(round(rand * 5 * 40_000), round(rand * 5 * 60_000))],
            },
            {
                "supply": [BossPrice.from_range(round(rand * 5 * 50_000), round(rand * 5 * 65_000))],
                "demand": [BossItem(30, round(rand * 5))],  # cabbage
            },
            {
                "demand": [BossItem(47, round(rand * 5))],  # carrot
                "supply": [BossPrice.from_range(round(rand * 5 * 25_000), round(rand * 5 * 35_000))],
            },
            {
                "supply": [BossPrice.from_range(round(rand * 5 * 35_000), round(rand * 5 * 40_000))],
                "demand": [BossItem(47, round(rand * 5))],  # carrot
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

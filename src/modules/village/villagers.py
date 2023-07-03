# database
from utils.postgres_db import Database

# my modules
from utils import constants
from utils.helpers import BossItem, BossCurrency

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
        `demand` (list[BossItem | BossCurrency]): A list of items or prices that the villager demands.
        `supply` (list[BossItem | BossCurrency]): A list of items or prices that the villager supplies.
        `num_trades` (int): The number of trades remaining with the villager.
        `db` (Database): The database object to use for accessing item information.
    """

    def __init__(
        self,
        villager_id: int,
        name: str,
        job_title: str,
        demand: list[BossItem | BossCurrency],
        supply: list[BossItem | BossCurrency],
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
                if isinstance(i, BossCurrency):
                    msgs[index] += f"\n{constants.CURRENCY_EMOJIS[i.currency_type]} ` {i.price * trade_quantity:,} `"
                elif isinstance(i, BossItem):
                    msgs[index] += f"\n` {i.quantity * trade_quantity}x ` {await i.get_emoji(self.db)} {await i.get_name(self.db)}"  # fmt: skip
        return msgs[0], msgs[1]


class Hunter(Villager):
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        # fmt: off
        # price is `BossCurrency(random * max_quantity * unit price[min], random * max_quantity * unit price[max])`
        buy_trades = [
            {
                "demand": [BossItem(26, round(rand * 8))],  # skunk
                "supply": [BossCurrency.from_unit_value(12_000, 8, rand)],
            },
            {
                "demand": [BossItem(23, round(rand * 8))],  # duck
                "supply": [BossCurrency.from_unit_value(20_000, 8, rand)],
            },  
            {
                "demand": [BossItem(25, round(rand * 8))],  # sheep
                "supply": [BossCurrency.from_unit_value(35_000, 8, rand)],
            },  
            {
                "demand": [BossItem(24, round(rand * 8))],  # rabbit
                "supply": [BossCurrency.from_unit_value(38_000, 8, rand)],
            },  
            {
                "demand": [BossItem(22, round(rand * 8))],  # cow
                "supply": [BossCurrency.from_unit_value(40_000, 8, rand)],
            },  
            {
                "demand": [BossItem(18, round(rand * 8))],  # deer
                "supply": [BossCurrency.from_unit_value(55_000, 8, rand)],
            },  
            {
                "demand": [BossItem(21, round(rand * 8))],  # boar
                "supply": [BossCurrency.from_unit_value(82_000, 8, rand)],
            },  
            {
                "demand": [BossItem(20, round(rand * 8))],  # dragon
                "supply": [BossCurrency.from_unit_value(850_000, 8, rand)],
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
        # fmt: on
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
        # fmt: off
        trades = [  # price is `random * quantity * unit price[min AND max]`
            {
                "demand": [BossItem(31, round(rand * 10))],  # dirt
                "supply": [BossCurrency.from_range(round(rand * 10 * 5), round(rand * 10 * 10))],
            },
            {
                "demand": [BossItem(33, round(rand * 10))],  # stone
                "supply": [BossCurrency.from_range(round(rand * 10 * 2_800), round(rand * 10 * 3_000))],
            },
        ]
        trade = random.choice(trades)
        # fmt: on
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
        rand = random.uniform(0.8, 1)
        # fmt: off
        trades = [  # price is `random * quantity * unit price[min AND max]`
            {
                "demand": [
                    BossCurrency.from_range("500m", "999m"),
                    BossItem(34, round(rand * 5)),  # diamond ore
                ],
                "supply": [BossItem(4, 1)]  # aqua defender
            },
            {
                "demand": [
                    BossCurrency.from_range("8m", "20m"),
                    BossItem(44, round(rand * 5)),  # iron ore
                ],
                "supply": [BossItem(49, 1)]  # iron sword
            }
        ]
        trade = random.choice(trades)
        # fmt: on
        super().__init__(
            name=name,
            job_title=__class__.__name__,
            demand=trade["demand"],
            supply=trade["supply"],
            num_trades=trade.get("trades", 3),
            villager_id=None,
            db=db,
        )


class Cartographer(Villager):
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        # fmt: off
        trades = [  # price is `random * quantity * unit price[min AND max]`
            {
                "demand": [
                    BossCurrency.from_range("10", "20", "copper"),
                ],
                "supply": [BossItem(57, 1)]  # jungle explorer map
            },
        ]
        trade = random.choice(trades)
        # fmt: on
        super().__init__(
            name=name,
            job_title=__class__.__name__,
            demand=trade["demand"],
            supply=trade["supply"],
            num_trades=trade.get("trades", 1),
            villager_id=None,
            db=db,
        )


class Archaeologist(Villager):
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        # fmt: off
        trades = [  # price is `random * quantity * unit price[min AND max]`
            {
                "demand": [BossItem(27, round(rand * 2))],  # ancient coin
                "supply": [BossCurrency.from_range(round(rand * 2 * 4_000_000), round(rand * 2 * 8_000_000))],
                "trades": 3,
            },
            {
                "demand": [BossCurrency.from_range(round(rand * 2 * 6_000_000), round(rand * 2 * 10_000_000))],
                "supply": [BossItem(27, round(rand * 2))],  # ancient coin
                "trades": 3,
            },
            {
                "demand": [BossCurrency.from_range(round(rand * 5 * 150_000), round(rand * 5 * 210_000))],
                "supply": [BossItem(46, round(rand * 5))],  # banknote
                "trades": 10,
            },
        ]
        trade = random.choice(trades)
        # fmt: on
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
        # fmt: off
        trades = [  # price is `random * quantity * unit price[min AND max]`
            {"demand": [BossItem(29, round(rand * 5))], "supply": [BossItem(48, 1)], "trades": 8},  # wheat  # bread
            {
                "demand": [BossItem(29, round(rand * 5))],  # wheat
                "supply": [BossCurrency.from_range(round(rand * 5 * 20_000), round(rand * 5 * 40_000))],
            },
            {
                "demand": [BossCurrency.from_range(round(rand * 5 * 30_000), round(rand * 5 * 45_000))],
                "supply": [BossItem(29, round(rand * 5))],  # wheat
            },
            {
                "demand": [BossItem(30, round(rand * 5))],  # cabbage
                "supply": [BossCurrency.from_range(round(rand * 5 * 40_000), round(rand * 5 * 60_000))],
            },
            {
                "supply": [BossCurrency.from_range(round(rand * 5 * 50_000), round(rand * 5 * 65_000))],
                "demand": [BossItem(30, round(rand * 5))],  # cabbage
            },
            {
                "demand": [BossItem(47, round(rand * 5))],  # carrot
                "supply": [BossCurrency.from_range(round(rand * 5 * 25_000), round(rand * 5 * 35_000))],
            },
            {
                "supply": [BossCurrency.from_range(round(rand * 5 * 35_000), round(rand * 5 * 40_000))],
                "demand": [BossItem(47, round(rand * 5))],  # carrot
            },
        ]
        trade = random.choice(trades)
        # fmt: on
        super().__init__(
            name=name,
            job_title=__class__.__name__,
            demand=trade["demand"],
            supply=trade["supply"],
            num_trades=trade.get("trades", 15),
            villager_id=None,
            db=db,
        )


class Cleric(Villager):
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        # fmt: off
        trades = [  # price is `random * quantity * unit price[min AND max]`
            {
                "demand": [
                    BossCurrency.from_range(round(rand * 5 * 2_000), round(rand * 5 * 4_000))
                ],
                "supply": [BossItem(61, round(rand * 5))]  # health potion
            },
        ]
        trade = random.choice(trades)
        # fmt: on
        super().__init__(
            name=name,
            job_title=__class__.__name__,
            demand=trade["demand"],
            supply=trade["supply"],
            num_trades=trade.get("trades", 1),
            villager_id=None,
            db=db,
        )

# database
from utils.postgres_db import Database

# my modules
from utils import functions

# default modules
import random
from typing import Union


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
    def __init__(self, min_price: Union[int, str], max_price: Union[int, str]) -> None:
        if isinstance(min_price, str):
            self.min_price = functions.text_to_num(min_price)
        elif isinstance(min_price, int):
            self.min_price = min_price
            
        if isinstance(max_price, str):
            self.max_price = functions.text_to_num(max_price)
        elif isinstance(max_price, int):
            self.max_price = max_price
        self.price = random.randint(self.min_price, self.max_price)
        
        
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
        name: str, 
        job_type: str,
        demand: list[TradeItem | TradePrice],
        supply: list[TradeItem | TradePrice],
        num_trades: int,
        db: Database
    ) -> None:
        self.name = name
        self.job_type = job_type
        self.demand = demand
        self.supply = supply
        self.remaining_trades = num_trades
        self.db = db
        
    async def format_trade(self):
        msgs = ["", ""]
        for index, value in enumerate((self.demand, self.supply)):
            for i in value:
                if isinstance(i, TradePrice):
                    msgs[index] += f"\n`◎ {i.price:,}`"
                elif isinstance(i, TradeItem):
                    msgs[index] += f"\n` {i.quantity}x ` {await i.get_emoji(self.db)} {await i.get_name(self.db)}"
        return msgs[0], msgs[1]


class Hunter(Villager):
    
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        trades = [  # price is `TradePrice(random * max_quantity * unit price[min], random * max_quantity * unit price[max])`
            {
                "demand": [TradeItem(26, round(rand * 8))],  # skunk
                "supply": [TradePrice(round(rand * 8 * 10_000), round(rand * 8 * 15_000))],
            },
            {
                "demand": [TradeItem(23, round(rand * 8))],  # duck
                "supply": [TradePrice("50k", "120k")]
            },
            {
                "demand": [TradeItem(25, round(rand * 8))],  # sheep
                "supply": [TradePrice("210k", "300k")]
            },
            {
                "demand": [TradeItem(18, 1)],  # deer
                "supply": [TradePrice("40k", "70k")]
            },
        ]
        trade = random.choice(trades)
        super().__init__(
            name=name, 
            job_type=__class__.__name__, 
            demand=trade["demand"], 
            supply=trade["supply"], 
            num_trades=trade.get("trades", 8),
            db=db
        )
        
        
class Mason(Villager):
    
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        trades = [  # price is `random * quantity * unit price[min AND max]`
            {
                "demand": [TradeItem(31, round(rand * 10))],  # dirt
                "supply": [TradePrice(round(rand * 10 * 5), round(rand * 10 * 10))],
            },
            {
                "demand": [TradeItem(33, round(rand * 10))],  # stone
                "supply": [TradePrice(round(rand * 10 * 2_800), round(rand * 10 * 3_000))]
            }
        ]
        trade = random.choice(trades)
        super().__init__(
            name=name, 
            job_type=__class__.__name__, 
            demand=trade["demand"], 
            supply=trade["supply"], 
            num_trades=trade.get("trades", 100),
            db=db
        )
        
        
class Armourer(Villager):    
    def __init__(self, name: str, db: Database) -> None:
        trades = [
            {
                "demand": [TradePrice("420m", "999m")],
                "supply": [TradeItem(4, 1)]  # aqua defender
            }
        ]
        trade = random.choice(trades)
        super().__init__(
            name=name, 
            job_type=__class__.__name__, 
            demand=trade["demand"], 
            supply=trade["supply"], 
            num_trades=3,
            db=db
        )
     
        
class Archaeologist(Villager):
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        trades = [  # price is `random * quantity * unit price[min AND max]`
            {
                "demand": [TradeItem(27, round(rand * 2))],  # ancient coin
                "supply": [TradePrice(round(rand * 2 * 4_000_000), round(rand * 2 * 8_000_000))],
                "trades": 3
            },
            {
                "demand": [TradeItem(46, round(rand * 5))],  # banknote
                "supply": [TradePrice(round(rand * 5 * 150_000), round(rand * 5 * 210_000))],
                "trades": 10
            }
        ]
        trade = random.choice(trades)
        super().__init__(
            name=name, 
            job_type=__class__.__name__, 
            demand=trade["demand"], 
            supply=trade["supply"], 
            num_trades=trade.get("trades", 100),
            db=db
        )
        
        
class Farmer(Villager):    
    def __init__(self, name: str, db: Database) -> None:
        rand = random.uniform(0.8, 1)
        trades = [  # price is `random * quantity * unit price[min AND max]`
            {
                "demand": [TradeItem(29, round(rand * 5))],  # wheat
                "supply": [TradeItem(48, 1)],  # bread
                "trades": 8
            },
            {
                "demand": [TradeItem(29, round(rand * 5))],  # wheat
                "supply": [TradePrice(round(rand * 5 * 20_000), round(rand * 5 * 40_000))],
            },
            {
                "demand": [TradeItem(30, round(rand * 5))],  # cabbage
                "supply": [TradePrice(round(rand * 5 * 40_000), round(rand * 5 * 60_000))]
            },
            {
                "demand": [TradeItem(30, round(rand * 5))],  # carrot
                "supply": [TradePrice(round(rand * 5 * 25_000), round(rand * 5 * 35_000))]
            },
        ]
        trade = random.choice(trades)
        super().__init__(
            name=name, 
            job_type=__class__.__name__, 
            demand=trade["demand"], 
            supply=trade["supply"], 
            num_trades=trade.get("trades", 15),
            db=db
        )
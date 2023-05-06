import asyncio, os

import asyncpg
from asyncpg import Pool

POSTGRES_PW = os.getenv("POSTGRES_PW")

DSN = "postgres://{user}:{password}@{host}:{port}"
DSN_DB = DSN + "/{name}"

db = None


class Database:
    """A connection pool to access data in BOSS neon.tech database."""

    def __init__(self, **kwargs):
        self.params = {
            "user": "SkyeWong",
            "host": "ep-wandering-resonance-874972.ap-southeast-1.aws.neon.tech",
            "port": 5432,
            "name": "neondb",
            "password": POSTGRES_PW,
        }
        self.params.update(kwargs)
        self.pool: Pool = None
        self.listeners = []
        self.reconnecting = False

    @property
    def connected(self) -> bool:
        if not self.pool:
            return False

        if self.pool.get_size() == 0:
            return False
        return True

    async def connect(self) -> Pool:
        """Connect to the database and return the connection."""
        if not self.reconnecting and not self.connected:
            print(f"\033[1;34mConnecting to the database...\033[0m")
            self.reconnecting = True
            try:
                self.pool = await asyncpg.create_pool(DSN_DB.format(**self.params))
            finally:
                self.reconnecting = False
            print(
                f"\033[1;36m{self.params['user']}\033[0m has connected to the \033[0;34mneon.db database!\033[0m"
            )
        return self.pool

    async def disconnect(self):
        """Disconnect to the database."""
        if self.pool:
            releases = [self.pool.release(conn) for conn in self.listeners] + [
                self.pool.close()
            ]
            await asyncio.gather(*releases, return_exceptions=True)

    async def fetch(self, sql, *args):
        try:
            return await self.pool.fetch(sql, *args)
        except (asyncpg.exceptions.InterfaceError, AttributeError):
            await self.connect()
            return await self.pool.fetch(sql, *args)

    async def fetchrow(self, sql, *args):
        try:
            return await self.pool.fetchrow(sql, *args)
        except (asyncpg.exceptions.InterfaceError, AttributeError):
            await self.connect()
            return await self.pool.fetchrow(sql, *args)

    async def fetchval(self, sql, *args):
        try:
            return await self.pool.fetchval(sql, *args)
        except (asyncpg.exceptions.InterfaceError, AttributeError):
            await self.connect()
            return await self.pool.fetchval(sql, *args)

    async def execute(self, sql, *args):
        try:
            return await self.pool.execute(sql, *args)
        except (asyncpg.exceptions.InterfaceError, AttributeError):
            await self.connect()
            return await self.pool.execute(sql, *args)

    async def executemany(self, sql, *args):
        try:
            return await self.pool.executemany(sql, *args)
        except (asyncpg.exceptions.InterfaceError, AttributeError):
            await self.connect()
            return await self.pool.executemany(sql, *args)

    async def acquire(self):
        try:
            return await self.pool.acquire()
        except (asyncpg.exceptions.InterfaceError, AttributeError):
            await self.connect()
            return await self.pool.acquire()

    async def __aenter__(self) -> Pool:
        return await self.connect()

    async def __aexit__(self, *exc):
        await self.disconnect()

    async def add_listener(self, channel, callback):
        conn: asyncpg.Connection = await self.pool.acquire()
        await conn.add_listener(channel, callback)
        self.listeners.append(conn)

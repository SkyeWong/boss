"""
## IMPORTANT!
This is a legacy database system that is going to be switched to a new postgresql database.
"""
import os
import mysql.connector.pooling

MYSQL_PW = os.getenv("MYSQL_PW")

dbconfig = {
    "host": "bsuvufmpxye5uuutqete-mysql.services.clever-cloud.com",
    "port": "3306",
    "user": "umjpzdqlwm5z2ht6",
    "password": MYSQL_PW,
    "database": "bsuvufmpxye5uuutqete",
}


class MySQLPool(object):
    """
    Create a pool when connect mysql, which will decrease the time spent in
    request connection, create connection and close connection.
    """

    def __init__(
        self,
        host="bsuvufmpxye5uuutqete-mysql.services.clever-cloud.com",
        port="3306",
        user="umjpzdqlwm5z2ht6",
        password=MYSQL_PW,
        database="bsuvufmpxye5uuutqete",
        pool_name="boss_pool",
        pool_size=1,
    ):
        res = {}
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database

        res["host"] = self._host
        res["port"] = self._port
        res["user"] = self._user
        res["password"] = self._password
        res["database"] = self._database
        self.dbconfig = res
        self.pool = self.create_pool(pool_name=pool_name, pool_size=pool_size)

    def create_pool(self, pool_name="boss_pool", pool_size=3):
        """
        Create a connection pool, after created, the request of connecting
        MySQL could get a connection from this pool instead of request to
        create a connection.

        Parameters
        ----------
        `pool_name`: the name of pool, default is "boss_pool"
        `param pool_size`: the size of pool, default is 3

        Returns
        -------
        connection pool
        """
        pool = mysql.connector.pooling.MySQLConnectionPool(
            pool_name=pool_name, pool_size=pool_size, pool_reset_session=True, **self.dbconfig
        )
        return pool

    def close(self, conn, cursor):
        """
        A method used to close connection of mysql.

        Parameters
        ----------
        `conn`: databse connection
        `cursor`

        Returns
        -------
        None
        """
        cursor.close()
        conn.close()

    def execute(self, sql, args=None, commit=False, dict=False):
        """
        Execute a sql, it could be with args and with out args. The usage is
        similar with execute() function in module pymysql.

        Parameters
        ----------
        `sql`: sql clause
        `args`: args needed by sql clause
        `commit`: whether to commit
        `dict`: whether to return result as list[dictionary] else list[tuple]

        Returns
        -------
        if commit, return None, else, return result
        """
        # get connection form connection pool instead of create one.
        # use context manager `with` to close it
        with self.pool.get_connection() as conn:
            if dict:
                cursor = conn.cursor(dictionary=True)
            else:
                cursor = conn.cursor()
            if args:
                cursor.execute(sql, args)
            else:
                cursor.execute(sql)
            if commit is True:
                conn.commit()
                return None
            else:
                res = cursor.fetchall()
                return res

    def executemany(self, sql, args, commit=False, dict=False):
        """
        Execute with many args. Similar with executemany() function in pymysql.
        args should be a sequence.

        Parameters
        ----------
        `sql`: sql clause
        `args`: args need by sql clause
        `commit`: whether to commit
        `dict`: whether to return result as list[dictionary] else list[tuple]

        Returns
        -------
        if commit, return None, else, return result
        """
        # get connection form connection pool instead of create one.
        with self.pool.get_connection() as conn:
            if dict:
                cursor = conn.cursor(dictionary=True)
            else:
                cursor = conn.cursor()
            if args:
                cursor.executemany(sql, args)
            else:
                cursor.executemany(sql)
            if commit is True:
                conn.commit()
                return None
            else:
                res = cursor.fetchall()
                return res


boss_pool = MySQLPool()

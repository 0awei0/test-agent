import pymysql
from loguru import logger
from config.settings import settings


class DBClient:
    def __init__(self):
        self.connection = None

    def connect(self):
        if self.connection is None or not self.connection.open:
            self.connection = pymysql.connect(
                host=settings.MYSQL_HOST,
                port=settings.MYSQL_PORT,
                user=settings.MYSQL_USER,
                password=settings.MYSQL_PASSWORD,
                database=settings.MYSQL_DATABASE,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
            )
            logger.info("[DB] Connected to MySQL")

    def close(self):
        if self.connection and self.connection.open:
            self.connection.close()
            self.connection = None
            logger.info("[DB] Connection closed")

    def execute(self, sql: str, params=None) -> list:
        self.connect()
        with self.connection.cursor() as cursor:
            logger.debug(f"[DB] SQL: {sql}")
            cursor.execute(sql, params)
            if sql.strip().upper().startswith("SELECT"):
                result = cursor.fetchall()
                logger.debug(f"[DB] Result: {result}")
                return result
            else:
                self.connection.commit()
                affected = cursor.rowcount
                logger.debug(f"[DB] Affected rows: {affected}")
                return [{"affected_rows": affected}]

    def fetchone(self, sql: str, params=None) -> dict:
        self.connect()
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchone()

    def fetchall(self, sql: str, params=None) -> list:
        self.connect()
        with self.connection.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

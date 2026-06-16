"""Cliente MySQL basado en pymysql con context manager."""

import pymysql
from pymysql.cursors import DictCursor

from xrom_scripts.config import Settings
from xrom_scripts.logger import setup_logger


class MySQLClient:
    """Conexion a MySQL reutilizable."""

    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        settings: Settings | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self._connection: pymysql.Connection | None = None
        self._logger = setup_logger(level=settings.log_level if settings else "INFO")

    def __enter__(self) -> "MySQLClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()

    def connect(self) -> None:
        self._logger.info("Conectando a MySQL %s:%d...", self.host, self.port)
        try:
            self._connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset="utf8mb4",
                cursorclass=DictCursor,
                connect_timeout=10,
                read_timeout=60,
                write_timeout=60,
                autocommit=True,
            )
            self._logger.info(
                "Conexion MySQL establecida (base de datos: %s).", self.database
            )
        except pymysql.MySQLError as exc:
            self._logger.error("Fallo al conectar a MySQL: %s", exc)
            raise

    def disconnect(self) -> None:
        if self._connection:
            try:
                self._connection.close()
                self._logger.info("Conexion MySQL cerrada.")
            except Exception as exc:
                self._logger.warning("Error al cerrar MySQL: %s", exc)
            finally:
                self._connection = None

    def healthcheck(self, table: str, limit: int = 3) -> list[dict]:
        """Ejecuta un SELECT limitado para validar conectividad."""
        if self._connection is None:
            raise RuntimeError("La conexion MySQL no esta activa.")

        self._logger.info(
            "Ejecutando healthcheck: SELECT * FROM `%s` LIMIT %d...", table, limit
        )
        try:
            with self._connection.cursor() as cursor:
                cursor.execute(f"SELECT * FROM `{table}` LIMIT %s", (limit,))
                rows = cursor.fetchall()
            self._logger.info("Healthcheck OK: %d filas obtenidas de `%s`.", len(rows), table)
            return rows
        except pymysql.MySQLError as exc:
            self._logger.error("Fallo en healthcheck MySQL: %s", exc)
            raise

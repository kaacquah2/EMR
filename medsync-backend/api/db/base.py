"""
PostgreSQL database engine with connection retry on failure (resilience).
- get_new_connection: retries initial connection (network blips at startup).
- Cursor execute/executemany: retry once on connection loss (e.g. idle timeout).
Use ENGINE = "api.db" in DATABASES to enable.
"""
import time
import logging
from django.db.backends.postgresql.base import DatabaseWrapper as PostgresDatabaseWrapper
from django.db.utils import OperationalError, InterfaceError

logger = logging.getLogger(__name__)
CONN_RETRY_ATTEMPTS = 3
CONN_RETRY_DELAY_SEC = 1.0
QUERY_RETRY_ONCE = (OperationalError, InterfaceError)


class RetryCursor:
    """Wraps the real cursor and retries execute/executemany once on connection loss."""

    def __init__(self, wrapper, cursor):
        self._wrapper = wrapper
        self._cursor = cursor

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def _reconnect_and_get_cursor(self):
        self._wrapper.close()
        self._wrapper.ensure_connection()
        self._cursor = PostgresDatabaseWrapper.create_cursor(self._wrapper, name=None)

    def execute(self, sql, params=None):
        try:
            return self._cursor.execute(sql, params)
        except QUERY_RETRY_ONCE as e:
            logger.warning("Database query failed (connection lost?), reconnecting and retrying once: %s", e)
            self._reconnect_and_get_cursor()
            return self._cursor.execute(sql, params)

    def executemany(self, sql, params_list):
        try:
            return self._cursor.executemany(sql, params_list)
        except QUERY_RETRY_ONCE as e:
            logger.warning("Database executemany failed (connection lost?), reconnecting and retrying once: %s", e)
            self._reconnect_and_get_cursor()
            return self._cursor.executemany(sql, params_list)


class DatabaseWrapper(PostgresDatabaseWrapper):
    def get_new_connection(self, conn_params):
        last_error = None
        for attempt in range(1, CONN_RETRY_ATTEMPTS + 1):
            try:
                return super().get_new_connection(conn_params)
            except (OperationalError, OSError) as e:
                last_error = e
                if attempt < CONN_RETRY_ATTEMPTS:
                    logger.warning(
                        "Database connection attempt %s/%s failed: %s. Retrying in %.1fs.",
                        attempt, CONN_RETRY_ATTEMPTS, e, CONN_RETRY_DELAY_SEC,
                    )
                    time.sleep(CONN_RETRY_DELAY_SEC)
        raise last_error

    def create_cursor(self, name=None):
        cursor = super().create_cursor(name=name)
        return RetryCursor(self, cursor)

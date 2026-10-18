"""FalkorDB access layer.

Every graph-dependent capability goes through `GraphClient`. When FalkorDB cannot be reached we raise
`GraphUnavailable`, which the API maps to HTTP 503 — there is deliberately no fallback to PostgreSQL.
"""

import logging
import threading
import time
from typing import Any

from falkordb import FalkorDB
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from redis.exceptions import TimeoutError as RedisTimeoutError

from app.core.config import get_settings

log = logging.getLogger("citypulse.graph")


class GraphUnavailable(RuntimeError):
    """FalkorDB is not reachable; graph-powered features must not pretend otherwise."""


class GraphQueryError(RuntimeError):
    pass


class GraphClient:
    def __init__(self, host: str, port: int, graph_name: str):
        self.host, self.port, self.graph_name = host, port, graph_name
        self._db: FalkorDB | None = None
        self._lock = threading.Lock()

    def _graph(self):
        with self._lock:
            if self._db is None:
                self._db = FalkorDB(host=self.host, port=self.port, socket_timeout=10, socket_connect_timeout=3)
            return self._db.select_graph(self.graph_name)

    def query(self, cypher: str, params: dict[str, Any] | None = None, *, readonly: bool = False) -> list[dict]:
        """Run a parameterised Cypher query and return rows as dicts keyed by column name."""
        started = time.perf_counter()
        try:
            g = self._graph()
            res = g.ro_query(cypher, params or {}) if readonly else g.query(cypher, params or {})
        except (RedisConnectionError, RedisTimeoutError, ConnectionRefusedError, OSError) as exc:
            with self._lock:
                self._db = None
            raise GraphUnavailable(f"FalkorDB unreachable at {self.host}:{self.port}") from exc
        except ResponseError as exc:
            if "already indexed" not in str(exc).lower():
                log.warning("cypher error: %s", exc)
            raise GraphQueryError(str(exc)) from exc
        cols = [h[1] for h in res.header] if res.header else []
        rows = [dict(zip(cols, row)) for row in res.result_set]
        log.debug("cypher %.1fms rows=%d", (time.perf_counter() - started) * 1000, len(rows))
        return rows

    def one(self, cypher: str, params: dict[str, Any] | None = None, *, readonly: bool = False) -> dict | None:
        rows = self.query(cypher, params, readonly=readonly)
        return rows[0] if rows else None

    def ping(self) -> bool:
        try:
            self.query("RETURN 1 AS ok", readonly=True)
            return True
        except GraphQueryError:  # e.g. graph key not created yet — the server itself is reachable
            return True
        except GraphUnavailable:
            return False

    def drop(self) -> None:
        try:
            self._graph().delete()
        except ResponseError:
            pass


_client: GraphClient | None = None


def get_graph() -> GraphClient:
    global _client
    if _client is None:
        s = get_settings()
        _client = GraphClient(s.falkordb_host, s.falkordb_port, s.falkordb_graph)
    return _client


def set_graph(client: GraphClient | None) -> None:
    """Used by tests to point the app at an isolated graph."""
    global _client
    _client = client

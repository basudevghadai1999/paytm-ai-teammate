from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from app.core.config import settings

# hide_parameters: a failed statement is logged without its values (merchant names, messages)
engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=10, hide_parameters=True)


class Db:
    """Thin wrapper over a transaction-scoped connection."""

    def __init__(self, conn: Connection):
        self.conn = conn

    def all(self, sql: str, **params: Any) -> list[dict]:
        return [dict(r._mapping) for r in self.conn.execute(text(sql), params)]

    def one(self, sql: str, **params: Any) -> dict | None:
        r = self.conn.execute(text(sql), params).first()
        return dict(r._mapping) if r else None

    def run(self, sql: str, **params: Any) -> int:
        return self.conn.execute(text(sql), params).rowcount


@contextmanager
def db() -> Iterator[Db]:
    with engine.begin() as conn:
        yield Db(conn)

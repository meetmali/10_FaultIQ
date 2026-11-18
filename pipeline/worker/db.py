"""Database access for the worker.

ADR 0007: the .NET API owns the schema through EF Core migrations. The worker only reads and
writes tables defined there. Explicit table definitions arrive in Phase 6, along with a
contract test against the migrated schema.
"""

from sqlalchemy import Engine, create_engine, text


def make_engine(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 3})


def check_database(engine: Engine) -> bool:
    """Return True if the database answers a trivial query."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return False
    return True

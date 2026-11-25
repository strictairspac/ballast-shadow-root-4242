from sqlalchemy import inspect, text

from src.models import audit, cases, reviews, runs, users  # Register the tables.
from src.models.base import metadata

# 对已存在的旧库做幂等加列；全新库由 metadata.create_all 直接建出完整结构。
ADDITIVE_COLUMNS = {
    "runs": {
        "payload": "JSON",
        "revoked_at": "BIGINT",
        "revoke_reason": "VARCHAR(300)",
    },
}


def ensure_columns(connection):
    inspector = inspect(connection)
    existing_tables = set(inspector.get_table_names())
    for table, columns in ADDITIVE_COLUMNS.items():
        if table not in existing_tables:
            continue
        present = {column["name"] for column in inspector.get_columns(table)}
        for name, column_type in columns.items():
            if name not in present:
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {column_type}"))


def upgrade(connection):
    # Version 1 is additive and fully declarative.
    metadata.create_all(connection)
    ensure_columns(connection)

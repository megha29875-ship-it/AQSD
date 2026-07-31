"""
AQSD
Database Engine

Module : DB-001
Version: 1.0.0

Description
-----------
Reusable SQLite database engine for AQSD.

Responsibilities
----------------
✓ Open database
✓ Initialize schema
✓ Execute SQL
✓ Transactions
✓ Query helpers

Every AQSD database will use this module.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class AQSDDatabase:
    """
    Generic SQLite database wrapper.
    """

    def __init__(
        self,
        database_file: Path,
        schema_file: Path | None = None,
    ) -> None:

        self.database_file = database_file
        self.schema_file = schema_file

        self.database_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.connection = sqlite3.connect(
            self.database_file
        )

        self.connection.row_factory = sqlite3.Row

        if self.schema_file is not None:
            self.initialize_schema()

    # ======================================================
    # SCHEMA
    # ======================================================

    def initialize_schema(self) -> None:
        """
        Execute schema.sql.
        """

        sql = self.schema_file.read_text(
            encoding="utf-8"
        )

        self.connection.executescript(sql)

        self.connection.commit()

    # ======================================================
    # EXECUTE
    # ======================================================

    def execute(
        self,
        sql: str,
        parameters: tuple = (),
    ) -> sqlite3.Cursor:

        cursor = self.connection.execute(
            sql,
            parameters,
        )

        self.connection.commit()

        return cursor

    # ======================================================
    # QUERY
    # ======================================================

    def query(
        self,
        sql: str,
        parameters: tuple = (),
    ) -> list[sqlite3.Row]:

        cursor = self.connection.execute(
            sql,
            parameters,
        )

        return cursor.fetchall()

    # ======================================================
    # SINGLE ROW
    # ======================================================

    def query_one(
        self,
        sql: str,
        parameters: tuple = (),
    ) -> sqlite3.Row | None:

        cursor = self.connection.execute(
            sql,
            parameters,
        )

        return cursor.fetchone()

    # ======================================================
    # TRANSACTION
    # ======================================================

    def commit(self) -> None:

        self.connection.commit()

    # ======================================================
    # CLOSE
    # ======================================================

    def close(self) -> None:

        self.connection.close()

    # ======================================================
    # CONTEXT MANAGER
    # ======================================================

    def __enter__(self):

        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):

        self.close()
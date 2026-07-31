"""
AQSD
Participant Database Engine

Module : APD-002 Participant Repository
Version: 1.0.0

Description
-----------
Provides database operations for participant-position records.

Responsibilities
----------------
- Insert one participant position.
- Insert multiple positions.
- Prevent duplicate records.
- Read records by trading date.
- Read records by participant.
- Find the latest available trading date.

This module contains database logic only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Final

from Scripts.aqsd_database.database import AQSDDatabase


# ==========================================================
# PROJECT PATHS
# ==========================================================

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[3]

APD_DATABASE_FILE: Final[Path] = (
    BASE_DIR
    / "Databases"
    / "APD"
    / "participant_database.db"
)

APD_SCHEMA_FILE: Final[Path] = (
    BASE_DIR
    / "Databases"
    / "APD"
    / "schema.sql"
)


# ==========================================================
# DATA MODEL
# ==========================================================

@dataclass(frozen=True)
class ParticipantPosition:
    """
    Standard AQSD participant-position record.
    """

    trade_date: date
    participant: str
    segment: str
    position_side: str
    value: float
    source_file: str


# ==========================================================
# REPOSITORY
# ==========================================================

class ParticipantRepository:
    """
    Repository for participant-position records.
    """

    def __init__(
        self,
        database_file: Path = APD_DATABASE_FILE,
        schema_file: Path = APD_SCHEMA_FILE,
    ) -> None:
        self.database = AQSDDatabase(
            database_file=database_file,
            schema_file=schema_file,
        )

    # ======================================================
    # NORMALIZATION
    # ======================================================

    @staticmethod
    def normalize_text(value: str) -> str:
        """
        Normalize database text values.
        """

        return " ".join(
            value.strip().upper().split()
        )

    # ======================================================
    # DUPLICATE CHECK
    # ======================================================

    def exists(
        self,
        position: ParticipantPosition,
    ) -> bool:
        """
        Return True when the same logical record already exists.
        """

        row = self.database.query_one(
            """
            SELECT id
            FROM participant_positions
            WHERE trade_date = ?
              AND participant = ?
              AND segment = ?
              AND position_side = ?
              AND source_file = ?
            LIMIT 1
            """,
            (
                position.trade_date.isoformat(),
                self.normalize_text(position.participant),
                self.normalize_text(position.segment),
                self.normalize_text(position.position_side),
                position.source_file,
            ),
        )

        return row is not None

    # ======================================================
    # INSERT ONE
    # ======================================================

    def insert_position(
        self,
        position: ParticipantPosition,
    ) -> int:
        """
        Insert one position.

        Returns:
            New database ID.

            Returns 0 when the record already exists.
        """

        if self.exists(position):
            return 0

        cursor = self.database.execute(
            """
            INSERT INTO participant_positions
            (
                trade_date,
                participant,
                segment,
                position_side,
                value,
                source_file,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                position.trade_date.isoformat(),
                self.normalize_text(position.participant),
                self.normalize_text(position.segment),
                self.normalize_text(position.position_side),
                float(position.value),
                position.source_file,
                datetime.now()
                .astimezone()
                .isoformat(timespec="seconds"),
            ),
        )

        return int(cursor.lastrowid or 0)

    # ======================================================
    # INSERT MANY
    # ======================================================

    def insert_many(
        self,
        positions: Iterable[ParticipantPosition],
    ) -> tuple[int, int]:
        """
        Insert multiple positions.

        Returns:
            inserted_count
            skipped_count
        """

        inserted_count = 0
        skipped_count = 0

        for position in positions:
            record_id = self.insert_position(position)

            if record_id == 0:
                skipped_count += 1
            else:
                inserted_count += 1

        return inserted_count, skipped_count

    # ======================================================
    # READ BY DATE
    # ======================================================

    def get_by_trade_date(
        self,
        trade_date: date,
    ) -> list[dict]:
        """
        Return all participant records for one trading date.
        """

        rows = self.database.query(
            """
            SELECT
                id,
                trade_date,
                participant,
                segment,
                position_side,
                value,
                source_file,
                created_at
            FROM participant_positions
            WHERE trade_date = ?
            ORDER BY participant, segment, position_side
            """,
            (
                trade_date.isoformat(),
            ),
        )

        return [
            dict(row)
            for row in rows
        ]

    # ======================================================
    # READ BY PARTICIPANT
    # ======================================================

    def get_by_participant(
        self,
        participant: str,
        limit: int | None = None,
    ) -> list[dict]:
        """
        Return historical records for one participant.
        """

        normalized_participant = self.normalize_text(
            participant
        )

        sql = """
            SELECT
                id,
                trade_date,
                participant,
                segment,
                position_side,
                value,
                source_file,
                created_at
            FROM participant_positions
            WHERE participant = ?
            ORDER BY trade_date DESC, segment, position_side
        """

        parameters: tuple = (
            normalized_participant,
        )

        if limit is not None:
            sql += " LIMIT ?"
            parameters = (
                normalized_participant,
                int(limit),
            )

        rows = self.database.query(
            sql,
            parameters,
        )

        return [
            dict(row)
            for row in rows
        ]

    # ======================================================
    # LATEST DATE
    # ======================================================

    def get_latest_trade_date(
        self,
    ) -> date | None:
        """
        Return the latest trading date stored in APD.
        """

        row = self.database.query_one(
            """
            SELECT MAX(trade_date) AS latest_trade_date
            FROM participant_positions
            """
        )

        if row is None:
            return None

        value = row["latest_trade_date"]

        if value is None:
            return None

        return date.fromisoformat(value)

    # ======================================================
    # COUNT
    # ======================================================

    def count_records(self) -> int:
        """
        Return the total number of records.
        """

        row = self.database.query_one(
            """
            SELECT COUNT(*) AS record_count
            FROM participant_positions
            """
        )

        if row is None:
            return 0

        return int(row["record_count"])

    # ======================================================
    # CLOSE
    # ======================================================

    def close(self) -> None:
        """
        Close the database connection.
        """

        self.database.close()

    def __enter__(self) -> ParticipantRepository:
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        self.close()
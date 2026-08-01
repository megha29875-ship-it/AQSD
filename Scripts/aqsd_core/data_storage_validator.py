"""
AQSD
Primary Data Storage Validator

Module : PATH-003
Version: 1.0.0
Author : AQSD

Purpose
-------
Validate the migrated NSE F&O historical database stored on D:.

Validation includes:
1. Database existence
2. SQLite integrity
3. Database tables
4. Total row counts
5. Trading-session coverage
6. Futures / options coverage where identifiable
7. Comparison against expected 60-session build

Safety
------
READ ONLY.
No database modification.
No source deletion.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from Scripts.aqsd_core.paths import (
    DATA_ROOT,
    NSE_FNO_HISTORICAL_DB,
)


MODULE_ID = "PATH-003"
VERSION = "1.0.0"

EXPECTED_SESSIONS = 60


# ==========================================================
# HELPERS
# ==========================================================

def separator() -> None:
    print("-" * 100)


def heading(text: str) -> None:
    print()
    print("=" * 100)
    print(text)
    print("=" * 100)


def human_size(size: int) -> str:

    value = float(size)

    for unit in (
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ):
        if value < 1024:
            return f"{value:,.2f} {unit}"

        value /= 1024

    return f"{value:,.2f} PB"


def get_tables(
    connection: sqlite3.Connection,
) -> list[str]:

    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()

    return [
        str(row[0])
        for row in rows
    ]


def get_columns(
    connection: sqlite3.Connection,
    table: str,
) -> list[str]:

    rows = connection.execute(
        f'PRAGMA table_info("{table}")'
    ).fetchall()

    return [
        str(row[1])
        for row in rows
    ]


def row_count(
    connection: sqlite3.Connection,
    table: str,
) -> int:

    result = connection.execute(
        f'SELECT COUNT(*) FROM "{table}"'
    ).fetchone()

    return int(result[0])


def find_column(
    columns: list[str],
    candidates: tuple[str, ...],
) -> str | None:

    lookup = {
        column.lower(): column
        for column in columns
    }

    for candidate in candidates:

        match = lookup.get(
            candidate.lower()
        )

        if match:
            return match

    return None


# ==========================================================
# VALIDATION
# ==========================================================

def validate_database() -> bool:

    heading(
        "AQSD PRIMARY DATA STORAGE VALIDATION"
    )

    print(
        f"Module                  : {MODULE_ID}"
    )

    print(
        f"Version                 : {VERSION}"
    )

    print(
        f"Primary Data Root       : {DATA_ROOT}"
    )

    print(
        f"Historical Database     : "
        f"{NSE_FNO_HISTORICAL_DB}"
    )

    separator()

    # ------------------------------------------------------
    # DATABASE EXISTS
    # ------------------------------------------------------

    if not NSE_FNO_HISTORICAL_DB.exists():

        print(
            "Database Exists         : NO"
        )

        print(
            "STATUS                  : FAILED"
        )

        return False

    print(
        "Database Exists         : YES"
    )

    print(
        f"Database Size           : "
        f"{human_size(NSE_FNO_HISTORICAL_DB.stat().st_size)}"
    )

    # ------------------------------------------------------
    # OPEN READ ONLY
    # ------------------------------------------------------

    database_uri = (
        NSE_FNO_HISTORICAL_DB
        .resolve()
        .as_uri()
        + "?mode=ro"
    )

    try:

        connection = sqlite3.connect(
            database_uri,
            uri=True,
        )

    except sqlite3.Error as exc:

        print(
            f"Database Open           : FAILED"
        )

        print(
            f"Error                   : {exc}"
        )

        return False

    try:

        # --------------------------------------------------
        # SQLITE INTEGRITY
        # --------------------------------------------------

        separator()

        print(
            "Running SQLite integrity check..."
        )

        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()

        integrity_result = (
            str(integrity[0])
            if integrity
            else "UNKNOWN"
        )

        integrity_pass = (
            integrity_result.lower()
            == "ok"
        )

        print(
            f"SQLite Integrity        : "
            f"{'PASS' if integrity_pass else 'FAIL'}"
        )

        print(
            f"Integrity Result        : "
            f"{integrity_result}"
        )

        # --------------------------------------------------
        # TABLE DISCOVERY
        # --------------------------------------------------

        separator()

        tables = get_tables(
            connection
        )

        print(
            f"Tables Found            : "
            f"{len(tables)}"
        )

        if not tables:

            print(
                "No database tables found."
            )

            return False

        print()

        total_rows = 0

        table_information = []

        for table in tables:

            count = row_count(
                connection,
                table,
            )

            columns = get_columns(
                connection,
                table,
            )

            total_rows += count

            table_information.append(
                (
                    table,
                    count,
                    columns,
                )
            )

            print(
                f"{table:<40} "
                f"{count:>15,} rows"
            )

        # --------------------------------------------------
        # FIND MAIN HISTORICAL TABLE
        # --------------------------------------------------

        separator()

        historical_candidates = []

        for (
            table,
            count,
            columns,
        ) in table_information:

            date_column = find_column(
                columns,
                (
                    "trade_date",
                    "TradDt",
                    "trade_dt",
                    "date",
                    "BizDt",
                ),
            )

            if (
                date_column
                and count > 0
            ):
                historical_candidates.append(
                    (
                        table,
                        count,
                        columns,
                        date_column,
                    )
                )

        if not historical_candidates:

            print(
                "Historical Table        : NOT IDENTIFIED"
            )

            print(
                "STATUS                  : FAILED"
            )

            return False

        historical_candidates.sort(
            key=lambda item: item[1],
            reverse=True,
        )

        (
            historical_table,
            historical_rows,
            historical_columns,
            date_column,
        ) = historical_candidates[0]

        print(
            f"Historical Table        : "
            f"{historical_table}"
        )

        print(
            f"Historical Rows         : "
            f"{historical_rows:,}"
        )

        print(
            f"Date Column             : "
            f"{date_column}"
        )

        # --------------------------------------------------
        # SESSION COUNT
        # --------------------------------------------------

        query = (
            f'SELECT COUNT(DISTINCT "{date_column}") '
            f'FROM "{historical_table}" '
            f'WHERE "{date_column}" IS NOT NULL'
        )

        session_result = (
            connection.execute(
                query
            ).fetchone()
        )

        session_count = int(
            session_result[0]
        )

        session_pass = (
            session_count
            == EXPECTED_SESSIONS
        )

        print(
            f"Stored Sessions         : "
            f"{session_count}"
        )

        print(
            f"Expected Sessions       : "
            f"{EXPECTED_SESSIONS}"
        )

        print(
            f"Session Validation      : "
            f"{'PASS' if session_pass else 'FAIL'}"
        )

        # --------------------------------------------------
        # FIRST / LAST DATE
        # --------------------------------------------------

        date_query = (
            f'SELECT '
            f'MIN("{date_column}"), '
            f'MAX("{date_column}") '
            f'FROM "{historical_table}" '
            f'WHERE "{date_column}" IS NOT NULL'
        )

        first_date, last_date = (
            connection.execute(
                date_query
            ).fetchone()
        )

        print(
            f"First Session           : "
            f"{first_date}"
        )

        print(
            f"Last Session            : "
            f"{last_date}"
        )

        # --------------------------------------------------
        # CONTRACT TYPE COVERAGE
        # --------------------------------------------------

        instrument_column = find_column(
            historical_columns,
            (
                "instrument",
                "instrument_type",
                "FinInstrmTp",
                "contract_type",
                "instrument_name",
            ),
        )

        if instrument_column:

            separator()

            print(
                "INSTRUMENT COVERAGE"
            )

            rows = connection.execute(
                f'''
                SELECT
                    "{instrument_column}",
                    COUNT(*)
                FROM "{historical_table}"
                GROUP BY "{instrument_column}"
                ORDER BY COUNT(*) DESC
                '''
            ).fetchall()

            for value, count in rows:

                print(
                    f"{str(value):<30} "
                    f"{int(count):>15,}"
                )

        # --------------------------------------------------
        # FINAL RESULT
        # --------------------------------------------------

        heading(
            "AQSD STORAGE VALIDATION SUMMARY"
        )

        print(
            f"Database Integrity      : "
            f"{'PASS' if integrity_pass else 'FAIL'}"
        )

        print(
            f"60 Session Coverage     : "
            f"{'PASS' if session_pass else 'FAIL'}"
        )

        print(
            f"Historical Rows         : "
            f"{historical_rows:,}"
        )

        print(
            f"All Table Rows          : "
            f"{total_rows:,}"
        )

        separator()

        overall_pass = (
            integrity_pass
            and session_pass
            and historical_rows > 0
        )

        print(
            f"VALIDATION STATUS       : "
            f"{'SUCCESS' if overall_pass else 'FAILED'}"
        )

        if overall_pass:

            print()
            print(
                "D: IS NOW A VALID AQSD PRIMARY "
                "HISTORICAL DATA STORE."
            )

            print(
                "C: SOURCE DATA REMAINS UNCHANGED."
            )

        return overall_pass

    finally:

        connection.close()


# ==========================================================
# MAIN
# ==========================================================

if __name__ == "__main__":

    validate_database()
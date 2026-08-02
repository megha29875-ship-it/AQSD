"""
AQSD
NSE Security Master Builder

Module : SMD-001
Version: 1.0.0
Author : AQSD

Purpose
-------
Create the AQSD Security Master from the frozen NSE F&O historical
contract database.

Principles
----------
- Historical database remains READ ONLY.
- No historical rows are changed or deleted.
- One row represents one underlying/security.
- Security Master is independent of daily derivative contracts.
- Designed for later expansion beyond F&O securities.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Final


MODULE_ID: Final[str] = "SMD-001"
MODULE_VERSION: Final[str] = "1.0.0"


# ==========================================================
# PATHS
# ==========================================================

AQSD_ROOT: Final[Path] = Path(__file__).resolve().parents[2]

DATABASE_FILE: Final[Path] = (
    Path(r"D:\AQSD_DATA\Databases\NSE_FNO_Historical.db")
)

OUTPUT_DIR: Final[Path] = AQSD_ROOT / "Output"

SECURITY_MASTER_CSV: Final[Path] = (
    OUTPUT_DIR / "AQSD_Security_Master.csv"
)

SECURITY_MASTER_JSON: Final[Path] = (
    OUTPUT_DIR / "AQSD_Security_Master.json"
)

SUMMARY_JSON: Final[Path] = (
    OUTPUT_DIR / "AQSD_Security_Master_Summary.json"
)


# ==========================================================
# COLUMN CANDIDATES
# ==========================================================

UNDERLYING_CANDIDATES = (
    "aqsd_underlying",
    "underlying",
    "underlying_symbol",
    "symbol",
)

SYMBOL_CANDIDATES = (
    "symbol",
    "aqsd_underlying",
    "underlying",
)

NAME_CANDIDATES = (
    "security_name",
    "company_name",
    "name",
    "underlying_name",
)


# ==========================================================
# HELPERS
# ==========================================================

def ensure_output_directory() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def connect_database() -> sqlite3.Connection:
    if not DATABASE_FILE.exists():
        raise FileNotFoundError(
            f"Historical database not found: {DATABASE_FILE}"
        )

    connection = sqlite3.connect(
        f"file:{DATABASE_FILE.as_posix()}?mode=ro",
        uri=True,
    )

    connection.row_factory = sqlite3.Row

    return connection


def table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()

    return row is not None


def get_columns(
    connection: sqlite3.Connection,
    table_name: str,
) -> list[str]:
    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return [
        str(row["name"])
        for row in rows
    ]


def choose_column(
    available_columns: list[str],
    candidates: tuple[str, ...],
) -> str | None:
    lookup = {
        column.lower(): column
        for column in available_columns
    }

    for candidate in candidates:
        actual = lookup.get(
            candidate.lower()
        )

        if actual:
            return actual

    return None


# ==========================================================
# SECURITY MASTER
# ==========================================================

def build_security_master(
    connection: sqlite3.Connection,
) -> list[dict[str, object]]:

    if not table_exists(
        connection,
        "contract_master",
    ):
        raise RuntimeError(
            "contract_master table not found."
        )

    columns = get_columns(
        connection,
        "contract_master",
    )

    underlying_column = choose_column(
        columns,
        UNDERLYING_CANDIDATES,
    )

    if underlying_column is None:
        raise RuntimeError(
            "Could not identify underlying column in contract_master.\n"
            f"Available columns: {columns}"
        )

    symbol_column = choose_column(
        columns,
        SYMBOL_CANDIDATES,
    )

    name_column = choose_column(
        columns,
        NAME_CANDIDATES,
    )

    select_parts = [
        f'"{underlying_column}" AS underlying'
    ]

    if symbol_column:
        select_parts.append(
            f'"{symbol_column}" AS symbol'
        )
    else:
        select_parts.append(
            f'"{underlying_column}" AS symbol'
        )

    if name_column:
        select_parts.append(
            f'"{name_column}" AS security_name'
        )
    else:
        select_parts.append(
            "NULL AS security_name"
        )

    query = f"""
        SELECT
            {", ".join(select_parts)}
        FROM contract_master
        WHERE "{underlying_column}" IS NOT NULL
          AND TRIM("{underlying_column}") <> ''
    """

    source_rows = connection.execute(
        query
    ).fetchall()

    securities: dict[str, dict[str, object]] = {}

    for row in source_rows:
        underlying = str(
            row["underlying"]
        ).strip().upper()

        if not underlying:
            continue

        symbol = str(
            row["symbol"]
            if row["symbol"] is not None
            else underlying
        ).strip().upper()

        security_name = (
            str(row["security_name"]).strip()
            if row["security_name"] is not None
            else ""
        )

        if underlying not in securities:
            securities[underlying] = {
                "security_id": "",
                "symbol": symbol,
                "name": security_name,
                "sector": "",
                "industry": "",
                "exchange": "NSE",
                "segment": "FNO",
                "fno_flag": "YES",
                "active_flag": "YES",
                "lot_size": "",
                "tick_size": "",
                "isin": "",
                "fyers_symbol": "",
                "nse_token": "",
                "source": "NSE_FNO_CONTRACT_MASTER",
            }

    ordered_underlyings = sorted(
        securities.keys()
    )

    output: list[dict[str, object]] = []

    for number, underlying in enumerate(
        ordered_underlyings,
        start=1,
    ):
        record = securities[
            underlying
        ]

        record["security_id"] = (
            f"SMD-{number:04d}"
        )

        record["symbol"] = underlying

        output.append(
            record
        )

    return output


# ==========================================================
# OUTPUT
# ==========================================================

def write_csv(
    rows: list[dict[str, object]],
) -> None:

    if not rows:
        raise RuntimeError(
            "Security Master contains no rows."
        )

    fieldnames = list(
        rows[0].keys()
    )

    with SECURITY_MASTER_CSV.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(
            rows
        )


def write_json(
    rows: list[dict[str, object]],
) -> None:

    SECURITY_MASTER_JSON.write_text(
        json.dumps(
            rows,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def write_summary(
    rows: list[dict[str, object]],
) -> None:

    summary = {
        "module_id": MODULE_ID,
        "module_version": MODULE_VERSION,
        "generated_at": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
        "source_database": str(
            DATABASE_FILE
        ),
        "source_table": "contract_master",
        "security_count": len(
            rows
        ),
        "exchange": "NSE",
        "fno_securities": len(
            rows
        ),
        "historical_database_modified": False,
        "status": "SUCCESS",
        "csv_output": str(
            SECURITY_MASTER_CSV
        ),
        "json_output": str(
            SECURITY_MASTER_JSON
        ),
    }

    SUMMARY_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
        ),
        encoding="utf-8",
    )


# ==========================================================
# MAIN
# ==========================================================

def main() -> None:

    print()
    print("=" * 78)
    print("AQSD SECURITY MASTER BUILDER")
    print("=" * 78)

    print(
        f"Module              : "
        f"{MODULE_ID}"
    )

    print(
        f"Version             : "
        f"{MODULE_VERSION}"
    )

    print(
        "Historical Database : READ ONLY"
    )

    ensure_output_directory()

    connection = connect_database()

    try:
        rows = build_security_master(
            connection
        )

    finally:
        connection.close()

    write_csv(
        rows
    )

    write_json(
        rows
    )

    write_summary(
        rows
    )

    print(
        f"Security Master Rows: "
        f"{len(rows):,}"
    )

    print(
        f"CSV                 : "
        f"{SECURITY_MASTER_CSV}"
    )

    print(
        f"JSON                : "
        f"{SECURITY_MASTER_JSON}"
    )

    print(
        "Historical Changes  : NONE"
    )

    print(
        "Status              : SUCCESS"
    )

    print("=" * 78)


if __name__ == "__main__":
    main()
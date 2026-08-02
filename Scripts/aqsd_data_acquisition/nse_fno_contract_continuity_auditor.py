"""
AQSD
NSE F&O Contract Continuity Auditor

Module: nse_fno_contract_continuity_auditor.py
Module ID: DCI-001
Version: 1.0.0

Purpose:
Perform a read-only continuity audit of the AQSD NSE F&O historical SQLite
database after FDB-001 has completed successfully.

Interpretation:
A continuity gap is evidence for review, not automatic corruption.
AQSD records the evidence and never modifies historical data.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final, Iterator


MODULE_ID: Final[str] = "DCI-001"
MODULE_VERSION: Final[str] = "1.0.0"

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]
DATABASE_FILE: Final[Path] = Path(r"D:\AQSD_DATA\Databases\NSE_FNO_Historical.db")
TRADING_CALENDAR_FILE: Final[Path] = BASE_DIR / "Data" / "NSE_Trading_Calendar.csv"
OUTPUT_DIR: Final[Path] = BASE_DIR / "Output"

AUDIT_CSV: Final[Path] = OUTPUT_DIR / "NSE_FNO_Contract_Continuity_Audit.csv"
GAPS_CSV: Final[Path] = OUTPUT_DIR / "NSE_FNO_Contract_Continuity_Gaps.csv"
SUMMARY_JSON: Final[Path] = OUTPUT_DIR / "NSE_FNO_Contract_Continuity_Summary.json"


@dataclass(frozen=True)
class ContractAudit:
    contract_type: str
    symbol: str
    expiry: str
    strike: float | None
    option_type: str
    first_seen: str
    last_seen: str
    observed_sessions: int
    expected_sessions: int
    missing_sessions: int
    continuity_status: str


@dataclass(frozen=True)
class GapAudit:
    contract_type: str
    symbol: str
    expiry: str
    strike: float | None
    option_type: str
    previous_trade_date: str
    next_trade_date: str
    missing_sessions: int


def load_trading_calendar() -> dict[str, int]:
    if not TRADING_CALENDAR_FILE.exists():
        raise FileNotFoundError(f"Trading calendar not found: {TRADING_CALENDAR_FILE}")

    dates: list[str] = []

    with TRADING_CALENDAR_FILE.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames is None:
            raise RuntimeError("Trading calendar has no header.")

        date_column = None
        for candidate in ("trade_date", "date", "Trade_Date", "Date"):
            if candidate in reader.fieldnames:
                date_column = candidate
                break

        if date_column is None:
            raise RuntimeError("Trading calendar has no recognised date column.")

        for row in reader:
            raw = str(row.get(date_column, "")).strip()
            if not raw:
                continue
            dates.append(date.fromisoformat(raw).isoformat())

    dates = sorted(set(dates))

    if not dates:
        raise RuntimeError("Trading calendar contains no dates.")

    return {trade_date: index for index, trade_date in enumerate(dates)}


def connect_read_only() -> sqlite3.Connection:
    if not DATABASE_FILE.exists():
        raise FileNotFoundError(f"Database not found: {DATABASE_FILE}")

    uri = DATABASE_FILE.resolve().as_uri() + "?mode=ro"
    connection = sqlite3.connect(uri, uri=True)
    connection.execute("PRAGMA query_only = ON")
    return connection


def table_count(connection: sqlite3.Connection, table_name: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def expected_sessions_between(first_seen: str, last_seen: str, sequence: dict[str, int]) -> int:
    if first_seen not in sequence or last_seen not in sequence:
        raise RuntimeError(
            f"Contract date missing from AQSD trading calendar: {first_seen} -> {last_seen}"
        )
    return sequence[last_seen] - sequence[first_seen] + 1


def missing_between(previous_date: str, next_date: str, sequence: dict[str, int]) -> int:
    if previous_date not in sequence or next_date not in sequence:
        raise RuntimeError(
            f"Contract date missing from AQSD trading calendar: {previous_date} -> {next_date}"
        )
    return max(0, sequence[next_date] - sequence[previous_date] - 1)


def iter_futures_rows(connection: sqlite3.Connection) -> Iterator[tuple[str, str, str]]:
    cursor = connection.execute(
        """
        SELECT symbol, expiry, trade_date
        FROM futures_history
        ORDER BY symbol, expiry, trade_date
        """
    )
    for row in cursor:
        yield str(row[0]), str(row[1]), str(row[2])


def iter_options_rows(
    connection: sqlite3.Connection,
) -> Iterator[tuple[str, str, float, str, str]]:
    cursor = connection.execute(
        """
        SELECT symbol, expiry, strike, option_type, trade_date
        FROM options_history
        ORDER BY symbol, expiry, strike, option_type, trade_date
        """
    )
    for row in cursor:
        yield str(row[0]), str(row[1]), float(row[2]), str(row[3]), str(row[4])


def audit_futures(
    connection: sqlite3.Connection,
    sequence: dict[str, int],
) -> tuple[list[ContractAudit], list[GapAudit]]:
    audits: list[ContractAudit] = []
    gaps: list[GapAudit] = []

    current_key: tuple[str, str] | None = None
    first_seen = ""
    last_seen = ""
    previous_date = ""
    observed_sessions = 0
    missing_sessions = 0

    def finalize() -> None:
        nonlocal current_key, first_seen, last_seen, observed_sessions, missing_sessions

        if current_key is None:
            return

        expected = expected_sessions_between(first_seen, last_seen, sequence)

        audits.append(
            ContractAudit(
                contract_type="FUTURE",
                symbol=current_key[0],
                expiry=current_key[1],
                strike=None,
                option_type="",
                first_seen=first_seen,
                last_seen=last_seen,
                observed_sessions=observed_sessions,
                expected_sessions=expected,
                missing_sessions=missing_sessions,
                continuity_status="CONTINUOUS" if missing_sessions == 0 else "GAP_FOUND",
            )
        )

    for symbol, expiry, trade_date in iter_futures_rows(connection):
        key = (symbol, expiry)

        if key != current_key:
            finalize()
            current_key = key
            first_seen = trade_date
            last_seen = trade_date
            previous_date = trade_date
            observed_sessions = 1
            missing_sessions = 0
            continue

        gap_count = missing_between(previous_date, trade_date, sequence)

        if gap_count > 0:
            gaps.append(
                GapAudit(
                    contract_type="FUTURE",
                    symbol=symbol,
                    expiry=expiry,
                    strike=None,
                    option_type="",
                    previous_trade_date=previous_date,
                    next_trade_date=trade_date,
                    missing_sessions=gap_count,
                )
            )
            missing_sessions += gap_count

        observed_sessions += 1
        last_seen = trade_date
        previous_date = trade_date

    finalize()
    return audits, gaps


def audit_options(
    connection: sqlite3.Connection,
    sequence: dict[str, int],
) -> tuple[list[ContractAudit], list[GapAudit]]:
    audits: list[ContractAudit] = []
    gaps: list[GapAudit] = []

    current_key: tuple[str, str, float, str] | None = None
    first_seen = ""
    last_seen = ""
    previous_date = ""
    observed_sessions = 0
    missing_sessions = 0

    def finalize() -> None:
        nonlocal current_key, first_seen, last_seen, observed_sessions, missing_sessions

        if current_key is None:
            return

        expected = expected_sessions_between(first_seen, last_seen, sequence)

        audits.append(
            ContractAudit(
                contract_type="OPTION",
                symbol=current_key[0],
                expiry=current_key[1],
                strike=current_key[2],
                option_type=current_key[3],
                first_seen=first_seen,
                last_seen=last_seen,
                observed_sessions=observed_sessions,
                expected_sessions=expected,
                missing_sessions=missing_sessions,
                continuity_status="CONTINUOUS" if missing_sessions == 0 else "GAP_FOUND",
            )
        )

    for symbol, expiry, strike, option_type, trade_date in iter_options_rows(connection):
        key = (symbol, expiry, strike, option_type)

        if key != current_key:
            finalize()
            current_key = key
            first_seen = trade_date
            last_seen = trade_date
            previous_date = trade_date
            observed_sessions = 1
            missing_sessions = 0
            continue

        gap_count = missing_between(previous_date, trade_date, sequence)

        if gap_count > 0:
            gaps.append(
                GapAudit(
                    contract_type="OPTION",
                    symbol=symbol,
                    expiry=expiry,
                    strike=strike,
                    option_type=option_type,
                    previous_trade_date=previous_date,
                    next_trade_date=trade_date,
                    missing_sessions=gap_count,
                )
            )
            missing_sessions += gap_count

        observed_sessions += 1
        last_seen = trade_date
        previous_date = trade_date

    finalize()
    return audits, gaps


def write_csv(path: Path, rows: list[ContractAudit] | list[GapAudit]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames = list(asdict(rows[0]).keys())

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def display_summary(summary: dict[str, object]) -> None:
    print()
    print("=" * 76)
    print("AQSD NSE F&O CONTRACT CONTINUITY AUDITOR")
    print("=" * 76)
    print(f"Module                     : {MODULE_ID}")
    print(f"Version                    : {MODULE_VERSION}")
    print("-" * 76)
    print(f"Futures History Rows       : {summary['futures_history_rows']:,}")
    print(f"Options History Rows       : {summary['options_history_rows']:,}")
    print(f"Total Historical Rows      : {summary['total_history_rows']:,}")
    print("-" * 76)
    print(f"Futures Contracts          : {summary['futures_contracts']:,}")
    print(f"Options Contracts          : {summary['options_contracts']:,}")
    print(f"Total Contracts            : {summary['total_contracts']:,}")
    print("-" * 76)
    print(f"Continuous Contracts       : {summary['continuous_contracts']:,}")
    print(f"Contracts With Gaps        : {summary['contracts_with_gaps']:,}")
    print(f"Gap Events                 : {summary['gap_events']:,}")
    print(f"Missing Trading Sessions   : {summary['missing_trading_sessions']:,}")
    print("-" * 76)
    print(f"Audit CSV                  : {AUDIT_CSV}")
    print(f"Gaps CSV                   : {GAPS_CSV}")
    print(f"Summary JSON               : {SUMMARY_JSON}")
    print("-" * 76)
    print("Database Mutation          : NONE")
    print("Historical Fabrication     : PROHIBITED")
    print("Audit Mode                 : READ ONLY")
    print("-" * 76)
    print(f"Status                     : {summary['status']}")
    print("=" * 76)


def run_audit() -> dict[str, object]:
    sequence = load_trading_calendar()
    connection = connect_read_only()

    try:
        futures_history_rows = table_count(connection, "futures_history")
        options_history_rows = table_count(connection, "options_history")

        print()
        print("Auditing FUTURES contract continuity...")
        futures_audits, futures_gaps = audit_futures(connection, sequence)
        print(f"FUTURES contracts audited : {len(futures_audits):,}")

        print()
        print("Auditing OPTIONS contract continuity...")
        options_audits, options_gaps = audit_options(connection, sequence)
        print(f"OPTIONS contracts audited : {len(options_audits):,}")

    finally:
        connection.close()

    audits = futures_audits + options_audits
    gaps = futures_gaps + options_gaps

    contracts_with_gaps = sum(
        1 for row in audits if row.continuity_status == "GAP_FOUND"
    )

    continuous_contracts = len(audits) - contracts_with_gaps
    missing_trading_sessions = sum(row.missing_sessions for row in audits)

    write_csv(AUDIT_CSV, audits)
    write_csv(GAPS_CSV, gaps)

    summary: dict[str, object] = {
        "module": MODULE_ID,
        "version": MODULE_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "database_file": str(DATABASE_FILE),
        "trading_calendar": str(TRADING_CALENDAR_FILE),
        "futures_history_rows": futures_history_rows,
        "options_history_rows": options_history_rows,
        "total_history_rows": futures_history_rows + options_history_rows,
        "futures_contracts": len(futures_audits),
        "options_contracts": len(options_audits),
        "total_contracts": len(audits),
        "continuous_contracts": continuous_contracts,
        "contracts_with_gaps": contracts_with_gaps,
        "gap_events": len(gaps),
        "missing_trading_sessions": missing_trading_sessions,
        "audit_csv": str(AUDIT_CSV),
        "gaps_csv": str(GAPS_CSV),
        "database_mutation": "NONE",
        "historical_fabrication": "PROHIBITED",
        "audit_mode": "READ ONLY",
        "status": "SUCCESS",
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    display_summary(summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AQSD NSE F&O contract continuity auditor."
    )
    parser.parse_args()
    run_audit()


if __name__ == "__main__":
    main()

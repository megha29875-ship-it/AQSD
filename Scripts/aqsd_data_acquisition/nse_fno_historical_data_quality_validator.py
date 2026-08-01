"""
AQSD
NSE F&O Historical Data Quality Validator

Module : NDQ-001
Version: 1.0.3
Author : AQSD

Purpose
-------
Validate the QUALITY of processed NSE F&O historical data after
raw validation and processed-layer reconciliation.

This module reads ONLY the master processed file for each session:

    D:/AQSD_DATA/Processed/NSE/Derivatives/YYYY-MM-DD/fno_contracts.csv

It does not modify, delete, rewrite, repair, infer or fabricate data.

Critical checks
---------------
1. Resolve requested sessions only from AQSD NSE trading calendar.
2. Confirm every requested processed session folder/master CSV exists.
3. Confirm required canonical columns exist.
4. trade_date agrees with the session folder.
5. contract_type is FUTURE or OPTION.
6. Contract-aware OHLC logical consistency (FUTURE vs OPTION).
7. Prices, volume and open interest cannot be negative.
8. Expiry cannot be before trade date.
9. OPTION rows require valid option_type and positive strike.
10. FUTURE rows must not carry an option type.
11. Duplicate canonical rows are detected within each session.
12. Empty symbol / underlying values are detected.

Warnings
--------
Zero volume, zero OI and FUTURE rows with non-zero strike are reported
as warnings rather than fabricated corrections.

Historical fabrication is prohibited.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

from Scripts.aqsd_core.paths import (
    NSE_DERIVATIVES_PROCESSED_DIR,
    OUTPUT_DIR,
    PROJECT_ROOT,
)

MODULE_ID: Final[str] = "NDQ-001"
MODULE_VERSION: Final[str] = "1.0.3"
DEFAULT_SESSIONS: Final[int] = 250

TRADING_CALENDAR_FILE: Final[Path] = (
    PROJECT_ROOT / "Data" / "NSE_Trading_Calendar.csv"
)
PROCESSED_ROOT: Final[Path] = NSE_DERIVATIVES_PROCESSED_DIR
AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR / "NSE_FNO_Historical_Data_Quality_Audit.csv"
)
SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR / "NSE_FNO_Historical_Data_Quality_Summary.json"
)
ISSUES_FILE: Final[Path] = (
    OUTPUT_DIR / "NSE_FNO_Historical_Data_Quality_Issues.csv"
)
MASTER_FILE_NAME: Final[str] = "fno_contracts.csv"

REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "trade_date",
    "symbol",
    "expiry",
    "strike",
    "option_type",
    "open",
    "high",
    "low",
    "close",
    "last_price",
    "settle_price",
    "volume",
    "turnover",
    "open_interest",
    "change_in_oi",
    "contract_type",
    "aqsd_underlying",
)

OPTION_TYPES: Final[set[str]] = {"CALL", "PUT", "CE", "PE"}
CONTRACT_TYPES: Final[set[str]] = {"FUTURE", "OPTION"}
MAX_ISSUE_ROWS_TO_SAVE: Final[int] = 50_000


@dataclass(frozen=True)
class SessionAudit:
    trade_date: str
    status: str
    rows: int
    futures_rows: int
    options_rows: int
    duplicate_rows: int
    critical_issues: int
    warnings: int
    missing_required_columns: int
    invalid_trade_date: int
    invalid_contract_type: int
    missing_symbol: int
    missing_underlying: int
    invalid_ohlc: int
    negative_price: int
    negative_volume: int
    negative_open_interest: int
    invalid_change_in_oi: int
    expiry_before_trade_date: int
    invalid_option_type: int
    invalid_option_strike: int
    future_with_option_type: int
    zero_volume_warning: int
    zero_oi_warning: int
    future_nonzero_strike_warning: int
    message: str


@dataclass(frozen=True)
class IssueRow:
    trade_date: str
    source_row_number: int
    severity: str
    issue_code: str
    symbol: str
    aqsd_underlying: str
    contract_type: str
    expiry: str
    strike: str
    option_type: str
    message: str


def norm(value: object) -> str:
    return str(value if value is not None else "").strip()


def upper(value: object) -> str:
    return norm(value).upper()


def parse_iso_date(value: object) -> date | None:
    text = norm(value)
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def to_float(value: object) -> float | None:
    text = norm(value)
    if text == "":
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def separator(character: str = "-") -> None:
    print(character * 104)


def heading(text: str) -> None:
    print()
    separator("=")
    print(text)
    separator("=")


def load_trading_calendar() -> list[date]:
    if not TRADING_CALENDAR_FILE.exists():
        raise FileNotFoundError(
            f"AQSD NSE trading calendar not found: {TRADING_CALENDAR_FILE}"
        )

    sessions: list[date] = []

    with TRADING_CALENDAR_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise RuntimeError("Trading calendar has no header.")

        fields = {
            str(name).strip().lower(): name
            for name in reader.fieldnames
            if name is not None
        }

        date_column = fields.get("trade_date") or fields.get("date")
        if date_column is None:
            raise RuntimeError("Trading calendar requires trade_date.")

        trading_flag_column = fields.get("is_trading_day")

        for row in reader:
            parsed = parse_iso_date(row.get(date_column, ""))
            if parsed is None:
                continue

            if trading_flag_column is not None:
                flag = upper(row.get(trading_flag_column, ""))
                if flag in {
                    "FALSE",
                    "0",
                    "NO",
                    "N",
                    "CLOSED",
                    "HOLIDAY",
                }:
                    continue

            sessions.append(parsed)

    sessions = sorted(set(sessions))
    if not sessions:
        raise RuntimeError("No valid trading sessions in AQSD calendar.")
    return sessions


def resolve_sessions(
    sessions: int,
    end_date: date | None,
) -> list[date]:
    if sessions <= 0:
        raise ValueError("--sessions must be greater than zero.")

    values = load_trading_calendar()

    if end_date is not None:
        values = [value for value in values if value <= end_date]

    if len(values) < sessions:
        raise RuntimeError(
            f"Not enough trading sessions. Requested={sessions}, "
            f"Available={len(values)}."
        )

    return values[-sessions:]


def append_issue(
    issues: list[IssueRow],
    session_date: date,
    source_row_number: int,
    severity: str,
    issue_code: str,
    row: dict[str, str],
    message: str,
) -> None:
    """
    Append validation issue.

    WARN rows are capped.
    FAIL rows are always preserved.
    """

    if severity == "WARN":
        if len(issues) >= MAX_ISSUE_ROWS_TO_SAVE:
            return

    issues.append(
        IssueRow(
            trade_date=session_date.isoformat(),
            source_row_number=source_row_number,
            severity=severity,
            issue_code=issue_code,
            symbol=norm(row.get("symbol", "")),
            aqsd_underlying=norm(row.get("aqsd_underlying", "")),
            contract_type=norm(row.get("contract_type", "")),
            expiry=norm(row.get("expiry", "")),
            strike=norm(row.get("strike", "")),
            option_type=norm(row.get("option_type", "")),
            message=message,
        )
    )

def empty_audit(
    session_date: date,
    status: str,
    critical_issues: int,
    message: str,
    missing_required_columns: int = 0,
) -> SessionAudit:
    return SessionAudit(
        trade_date=session_date.isoformat(),
        status=status,
        rows=0,
        futures_rows=0,
        options_rows=0,
        duplicate_rows=0,
        critical_issues=critical_issues,
        warnings=0,
        missing_required_columns=missing_required_columns,
        invalid_trade_date=0,
        invalid_contract_type=0,
        missing_symbol=0,
        missing_underlying=0,
        invalid_ohlc=0,
        negative_price=0,
        negative_volume=0,
        negative_open_interest=0,
        invalid_change_in_oi=0,
        expiry_before_trade_date=0,
        invalid_option_type=0,
        invalid_option_strike=0,
        future_with_option_type=0,
        zero_volume_warning=0,
        zero_oi_warning=0,
        future_nonzero_strike_warning=0,
        message=message,
    )


def validate_session(
    session_date: date,
    issues: list[IssueRow],
) -> SessionAudit:
    folder = PROCESSED_ROOT / session_date.isoformat()
    master_file = folder / MASTER_FILE_NAME

    if not folder.is_dir():
        return empty_audit(
            session_date,
            "MISSING",
            1,
            "Processed session folder not found.",
        )

    if not master_file.is_file():
        return empty_audit(
            session_date,
            "FAILED",
            1,
            "fno_contracts.csv not found.",
            missing_required_columns=1,
        )

    counters = {
        "rows": 0,
        "futures_rows": 0,
        "options_rows": 0,
        "duplicate_rows": 0,
        "critical_issues": 0,
        "warnings": 0,
        "missing_required_columns": 0,
        "invalid_trade_date": 0,
        "invalid_contract_type": 0,
        "missing_symbol": 0,
        "missing_underlying": 0,
        "invalid_ohlc": 0,
        "negative_price": 0,
        "negative_volume": 0,
        "negative_open_interest": 0,
        "invalid_change_in_oi": 0,
        "expiry_before_trade_date": 0,
        "invalid_option_type": 0,
        "invalid_option_strike": 0,
        "future_with_option_type": 0,
        "zero_volume_warning": 0,
        "zero_oi_warning": 0,
        "future_nonzero_strike_warning": 0,
    }

    duplicate_keys: set[tuple[str, ...]] = set()

    with master_file.open(
        "r",
        encoding="utf-8-sig",
        newline="",
        errors="replace",
    ) as handle:
        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise RuntimeError(f"No CSV header: {master_file}")

        actual_columns = {
            str(name).strip()
            for name in reader.fieldnames
            if name is not None
        }

        missing_columns = [
            column
            for column in REQUIRED_COLUMNS
            if column not in actual_columns
        ]

        if missing_columns:
            return empty_audit(
                session_date,
                "FAILED",
                len(missing_columns),
                "Missing required columns: " + ", ".join(missing_columns),
                missing_required_columns=len(missing_columns),
            )

        for source_row_number, row in enumerate(reader, start=2):
            counters["rows"] += 1

            contract_type = upper(row.get("contract_type", ""))
            symbol = norm(row.get("symbol", ""))
            underlying = norm(row.get("aqsd_underlying", ""))
            row_trade_date = parse_iso_date(row.get("trade_date", ""))
            expiry = parse_iso_date(row.get("expiry", ""))
            option_type = upper(row.get("option_type", ""))
            strike = to_float(row.get("strike", ""))

            open_price = to_float(row.get("open", ""))
            high_price = to_float(row.get("high", ""))
            low_price = to_float(row.get("low", ""))
            close_price = to_float(row.get("close", ""))
            last_price = to_float(row.get("last_price", ""))
            settle_price = to_float(row.get("settle_price", ""))
            volume = to_float(row.get("volume", ""))
            open_interest = to_float(row.get("open_interest", ""))

            change_in_oi_text = norm(row.get("change_in_oi", ""))
            change_in_oi = to_float(change_in_oi_text)

            if row_trade_date is None or row_trade_date != session_date:
                counters["invalid_trade_date"] += 1
                counters["critical_issues"] += 1
                append_issue(
                    issues,
                    session_date,
                    source_row_number,
                    "FAIL",
                    "INVALID_TRADE_DATE",
                    row,
                    "Row trade_date does not match session folder.",
                )

            if contract_type not in CONTRACT_TYPES:
                counters["invalid_contract_type"] += 1
                counters["critical_issues"] += 1
                append_issue(
                    issues,
                    session_date,
                    source_row_number,
                    "FAIL",
                    "INVALID_CONTRACT_TYPE",
                    row,
                    f"contract_type={contract_type!r}",
                )
            elif contract_type == "FUTURE":
                counters["futures_rows"] += 1
            else:
                counters["options_rows"] += 1

            if not symbol:
                counters["missing_symbol"] += 1
                counters["critical_issues"] += 1
                append_issue(
                    issues,
                    session_date,
                    source_row_number,
                    "FAIL",
                    "MISSING_SYMBOL",
                    row,
                    "symbol is blank.",
                )

            if not underlying:
                counters["missing_underlying"] += 1
                counters["critical_issues"] += 1
                append_issue(
                    issues,
                    session_date,
                    source_row_number,
                    "FAIL",
                    "MISSING_UNDERLYING",
                    row,
                    "aqsd_underlying is blank.",
                )

            duplicate_key = (
                session_date.isoformat(),
                contract_type,
                symbol,
                norm(row.get("expiry", "")),
                norm(row.get("strike", "")),
                option_type,
            )

            if duplicate_key in duplicate_keys:
                counters["duplicate_rows"] += 1
                counters["critical_issues"] += 1
                append_issue(
                    issues,
                    session_date,
                    source_row_number,
                    "FAIL",
                    "DUPLICATE_CONTRACT_ROW",
                    row,
                    "Duplicate canonical contract row.",
                )
            else:
                duplicate_keys.add(duplicate_key)

            prices = {
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "last_price": last_price,
                "settle_price": settle_price,
            }

            negative_fields = [
                name
                for name, value in prices.items()
                if value is not None and value < 0
            ]

            if negative_fields:
                counters["negative_price"] += 1
                counters["critical_issues"] += 1
                append_issue(
                    issues,
                    session_date,
                    source_row_number,
                    "FAIL",
                    "NEGATIVE_PRICE",
                    row,
                    "Negative price field(s): " + ", ".join(negative_fields),
                )

            if all(
                value is not None
                for value in (
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                )
            ):
                zero_ohl = (
                    open_price == 0
                    and high_price == 0
                    and low_price == 0
                )

                if zero_ohl and volume == 0:
                    counters["warnings"] += 1

                    append_issue(
                        issues,
                        session_date,
                        source_row_number,
                        "WARN",
                        "OHLC_UNAVAILABLE_NO_TRADE",
                        row,
                        (
                            f"O={open_price}, H={high_price}, "
                            f"L={low_price}, C={close_price}, "
                            f"Last={last_price}, Settle={settle_price}, "
                            f"Volume={volume}"
                        ),
                    )

                elif contract_type == "FUTURE":
                    # NSE futures may carry settlement-based Close values
                    # outside the traded High/Low range. Validate futures
                    # using traded fields: Open, High, Low and Last Price.
                    # Do not force Close/Settle inside the traded range.

                    if zero_ohl:
                        usable_reference_price = any(
                            value is not None and value > 0
                            for value in (
                                close_price,
                                last_price,
                                settle_price,
                            )
                        )

                        if (
                            volume is not None
                            and volume > 0
                            and usable_reference_price
                        ):
                            counters["warnings"] += 1

                            append_issue(
                                issues,
                                session_date,
                                source_row_number,
                                "WARN",
                                "ZERO_OHLC_WITH_VOLUME",
                                row,
                                (
                                    f"O={open_price}, H={high_price}, "
                                    f"L={low_price}, C={close_price}, "
                                    f"Last={last_price}, Settle={settle_price}, "
                                    f"Volume={volume}"
                                ),
                            )

                        else:
                            counters["invalid_ohlc"] += 1
                            counters["critical_issues"] += 1

                            append_issue(
                                issues,
                                session_date,
                                source_row_number,
                                "FAIL",
                                "INVALID_OHLC",
                                row,
                                (
                                    f"O={open_price}, H={high_price}, "
                                    f"L={low_price}, C={close_price}, "
                                    f"Last={last_price}, Settle={settle_price}, "
                                    f"Volume={volume}"
                                ),
                            )

                    else:
                        future_ohlc_ok = True

                        if high_price < low_price:
                            future_ohlc_ok = False

                        if not (low_price <= open_price <= high_price):
                            future_ohlc_ok = False

                        if (
                            last_price is not None
                            and last_price > 0
                            and not (low_price <= last_price <= high_price)
                        ):
                            future_ohlc_ok = False

                        if not future_ohlc_ok:
                            counters["invalid_ohlc"] += 1
                            counters["critical_issues"] += 1

                            append_issue(
                                issues,
                                session_date,
                                source_row_number,
                                "FAIL",
                                "INVALID_OHLC",
                                row,
                                (
                                    f"O={open_price}, H={high_price}, "
                                    f"L={low_price}, C={close_price}, "
                                    f"Last={last_price}, Settle={settle_price}, "
                                    f"Volume={volume}"
                                ),
                            )

                else:
                    # OPTION rows retain conventional OHLC consistency.
                    ohlc_ok = (
                        high_price >= open_price
                        and high_price >= low_price
                        and high_price >= close_price
                        and low_price <= open_price
                        and low_price <= close_price
                    )

                    if not ohlc_ok:
                        counters["invalid_ohlc"] += 1
                        counters["critical_issues"] += 1

                        append_issue(
                            issues,
                            session_date,
                            source_row_number,
                            "FAIL",
                            "INVALID_OHLC",
                            row,
                            (
                                f"O={open_price}, H={high_price}, "
                                f"L={low_price}, C={close_price}, "
                                f"Last={last_price}, Settle={settle_price}, "
                                f"Volume={volume}"
                            ),
                        )

            if volume is not None:
                if volume < 0:
                    counters["negative_volume"] += 1
                    counters["critical_issues"] += 1
                    append_issue(
                        issues,
                        session_date,
                        source_row_number,
                        "FAIL",
                        "NEGATIVE_VOLUME",
                        row,
                        f"volume={volume}",
                    )
                elif volume == 0:
                    counters["zero_volume_warning"] += 1
                    counters["warnings"] += 1

            if open_interest is not None:
                if open_interest < 0:
                    counters["negative_open_interest"] += 1
                    counters["critical_issues"] += 1
                    append_issue(
                        issues,
                        session_date,
                        source_row_number,
                        "FAIL",
                        "NEGATIVE_OPEN_INTEREST",
                        row,
                        f"open_interest={open_interest}",
                    )
                elif open_interest == 0:
                    counters["zero_oi_warning"] += 1
                    counters["warnings"] += 1

            if change_in_oi_text and change_in_oi is None:
                counters["invalid_change_in_oi"] += 1
                counters["critical_issues"] += 1
                append_issue(
                    issues,
                    session_date,
                    source_row_number,
                    "FAIL",
                    "INVALID_CHANGE_IN_OI",
                    row,
                    f"change_in_oi={change_in_oi_text!r}",
                )

            if expiry is not None and expiry < session_date:
                counters["expiry_before_trade_date"] += 1
                counters["critical_issues"] += 1
                append_issue(
                    issues,
                    session_date,
                    source_row_number,
                    "FAIL",
                    "EXPIRY_BEFORE_TRADE_DATE",
                    row,
                    f"expiry={expiry}, trade_date={session_date}",
                )

            if contract_type == "OPTION":
                if option_type not in OPTION_TYPES:
                    counters["invalid_option_type"] += 1
                    counters["critical_issues"] += 1
                    append_issue(
                        issues,
                        session_date,
                        source_row_number,
                        "FAIL",
                        "INVALID_OPTION_TYPE",
                        row,
                        f"option_type={option_type!r}",
                    )

                if strike is None or strike <= 0:
                    counters["invalid_option_strike"] += 1
                    counters["critical_issues"] += 1
                    append_issue(
                        issues,
                        session_date,
                        source_row_number,
                        "FAIL",
                        "INVALID_OPTION_STRIKE",
                        row,
                        f"strike={norm(row.get('strike', ''))!r}",
                    )

            if contract_type == "FUTURE":
                if option_type:
                    counters["future_with_option_type"] += 1
                    counters["critical_issues"] += 1
                    append_issue(
                        issues,
                        session_date,
                        source_row_number,
                        "FAIL",
                        "FUTURE_WITH_OPTION_TYPE",
                        row,
                        f"option_type={option_type!r}",
                    )

                if strike is not None and strike != 0:
                    counters["future_nonzero_strike_warning"] += 1
                    counters["warnings"] += 1

    status = "PASS" if counters["critical_issues"] == 0 else "FAILED"

    return SessionAudit(
        trade_date=session_date.isoformat(),
        status=status,
        rows=counters["rows"],
        futures_rows=counters["futures_rows"],
        options_rows=counters["options_rows"],
        duplicate_rows=counters["duplicate_rows"],
        critical_issues=counters["critical_issues"],
        warnings=counters["warnings"],
        missing_required_columns=counters["missing_required_columns"],
        invalid_trade_date=counters["invalid_trade_date"],
        invalid_contract_type=counters["invalid_contract_type"],
        missing_symbol=counters["missing_symbol"],
        missing_underlying=counters["missing_underlying"],
        invalid_ohlc=counters["invalid_ohlc"],
        negative_price=counters["negative_price"],
        negative_volume=counters["negative_volume"],
        negative_open_interest=counters["negative_open_interest"],
        invalid_change_in_oi=counters["invalid_change_in_oi"],
        expiry_before_trade_date=counters["expiry_before_trade_date"],
        invalid_option_type=counters["invalid_option_type"],
        invalid_option_strike=counters["invalid_option_strike"],
        future_with_option_type=counters["future_with_option_type"],
        zero_volume_warning=counters["zero_volume_warning"],
        zero_oi_warning=counters["zero_oi_warning"],
        future_nonzero_strike_warning=counters[
            "future_nonzero_strike_warning"
        ],
        message="OK" if status == "PASS" else "Data-quality violations detected.",
    )


def write_dataclass_csv(path: Path, rows: list[object]) -> None:
    if not rows:
        return

    dictionaries = [asdict(row) for row in rows]

    with path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(dictionaries[0].keys()),
        )
        writer.writeheader()
        writer.writerows(dictionaries)


def save_outputs(
    audits: list[SessionAudit],
    issues: list[IssueRow],
    summary: dict,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    write_dataclass_csv(AUDIT_FILE, audits)

    if issues:
        write_dataclass_csv(ISSUES_FILE, issues)
    else:
        ISSUES_FILE.write_text(
            "trade_date,source_row_number,severity,issue_code,"
            "symbol,aqsd_underlying,contract_type,expiry,strike,"
            "option_type,message\n",
            encoding="utf-8-sig",
        )

    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )


def display_summary(summary: dict) -> None:
    heading("AQSD NSE F&O HISTORICAL DATA QUALITY SUMMARY")

    print(f"Module                     : {MODULE_ID}")
    print(f"Version                    : {MODULE_VERSION}")
    print(f"Requested Sessions         : {summary['requested_sessions']}")
    print(f"Resolved Sessions          : {summary['resolved_sessions']}")
    print(f"Passed Sessions            : {summary['passed_sessions']}")
    print(f"Failed Sessions            : {summary['failed_sessions']}")
    print(f"Missing Sessions           : {summary['missing_sessions']}")
    separator()
    print(f"Master Rows                : {summary['rows']:,}")
    print(f"Futures Rows               : {summary['futures_rows']:,}")
    print(f"Options Rows               : {summary['options_rows']:,}")
    print(f"Duplicate Rows             : {summary['duplicate_rows']:,}")
    separator()
    print(f"Critical Issues            : {summary['critical_issues']:,}")
    print(f"Warnings                   : {summary['warnings']:,}")
    print(f"Invalid OHLC               : {summary['invalid_ohlc']:,}")
    print(f"Negative Price             : {summary['negative_price']:,}")
    print(f"Negative Volume            : {summary['negative_volume']:,}")
    print(
        f"Negative Open Interest     : "
        f"{summary['negative_open_interest']:,}"
    )
    print(
        f"Expiry Before Trade Date   : "
        f"{summary['expiry_before_trade_date']:,}"
    )
    print(
        f"Invalid Option Type        : "
        f"{summary['invalid_option_type']:,}"
    )
    print(
        f"Invalid Option Strike      : "
        f"{summary['invalid_option_strike']:,}"
    )
    separator()
    print(f"Trading Calendar           : {TRADING_CALENDAR_FILE}")
    print(f"Processed Root             : {PROCESSED_ROOT}")
    print(f"Audit CSV                  : {AUDIT_FILE}")
    print(f"Issues CSV                 : {ISSUES_FILE}")
    print(f"Summary JSON               : {SUMMARY_FILE}")
    separator()
    print("Processed Files            : UNCHANGED")
    print("Historical Fabrication     : PROHIBITED")
    print("Deletion                   : NONE")
    print("Validation Mode            : READ ONLY / STREAMING")
    separator()
    print(f"Status                     : {summary['status']}")
    separator("=")


def run_validation(
    sessions: int,
    end_date: date | None,
) -> dict:
    resolved = resolve_sessions(sessions, end_date)
    audits: list[SessionAudit] = []
    issues: list[IssueRow] = []

    heading("AQSD NSE F&O HISTORICAL DATA QUALITY VALIDATOR")
    print(f"Module                     : {MODULE_ID}")
    print(f"Version                    : {MODULE_VERSION}")
    print(f"Resolved Sessions          : {len(resolved)}")
    print(f"First Session              : {resolved[0]}")
    print(f"Last Session               : {resolved[-1]}")
    print("Mode                       : READ ONLY / STREAMING")
    separator()

    for index, session_date in enumerate(resolved, start=1):
        result = validate_session(session_date, issues)
        audits.append(result)

        print(
            f"[{index:03d}/{len(resolved):03d}] "
            f"{session_date} {result.status} "
            f"| Rows={result.rows:,} "
            f"| Critical={result.critical_issues:,} "
            f"| Warnings={result.warnings:,}"
        )

    def total(field: str) -> int:
        return sum(int(getattr(row, field)) for row in audits)

    passed_sessions = sum(row.status == "PASS" for row in audits)
    failed_sessions = sum(row.status == "FAILED" for row in audits)
    missing_sessions = sum(row.status == "MISSING" for row in audits)

    status = (
        "SUCCESS"
        if failed_sessions == 0
        and missing_sessions == 0
        and total("critical_issues") == 0
        else "FAILED"
    )

    summary = {
        "module": MODULE_ID,
        "version": MODULE_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "requested_sessions": sessions,
        "resolved_sessions": len(resolved),
        "first_session": resolved[0].isoformat(),
        "last_session": resolved[-1].isoformat(),
        "passed_sessions": passed_sessions,
        "failed_sessions": failed_sessions,
        "missing_sessions": missing_sessions,
        "rows": total("rows"),
        "futures_rows": total("futures_rows"),
        "options_rows": total("options_rows"),
        "duplicate_rows": total("duplicate_rows"),
        "critical_issues": total("critical_issues"),
        "warnings": total("warnings"),
        "missing_required_columns": total("missing_required_columns"),
        "invalid_trade_date": total("invalid_trade_date"),
        "invalid_contract_type": total("invalid_contract_type"),
        "missing_symbol": total("missing_symbol"),
        "missing_underlying": total("missing_underlying"),
        "invalid_ohlc": total("invalid_ohlc"),
        "negative_price": total("negative_price"),
        "negative_volume": total("negative_volume"),
        "negative_open_interest": total("negative_open_interest"),
        "invalid_change_in_oi": total("invalid_change_in_oi"),
        "expiry_before_trade_date": total("expiry_before_trade_date"),
        "invalid_option_type": total("invalid_option_type"),
        "invalid_option_strike": total("invalid_option_strike"),
        "future_with_option_type": total("future_with_option_type"),
        "zero_volume_warning": total("zero_volume_warning"),
        "zero_oi_warning": total("zero_oi_warning"),
        "future_nonzero_strike_warning": total(
            "future_nonzero_strike_warning"
        ),
        "issue_rows_saved": len(issues),
        "issue_row_save_limit": MAX_ISSUE_ROWS_TO_SAVE,
        "status": status,
    }

    save_outputs(audits, issues, summary)
    display_summary(summary)
    return summary


def show_status() -> None:
    heading("AQSD NSE F&O HISTORICAL DATA QUALITY VALIDATOR STATUS")
    print(f"Module                     : {MODULE_ID}")
    print(f"Version                    : {MODULE_VERSION}")
    print(f"Trading Calendar           : {TRADING_CALENDAR_FILE}")
    print(
        f"Calendar Exists            : "
        f"{'YES' if TRADING_CALENDAR_FILE.exists() else 'NO'}"
    )
    print(f"Processed Root             : {PROCESSED_ROOT}")
    print(
        f"Processed Root Exists      : "
        f"{'YES' if PROCESSED_ROOT.exists() else 'NO'}"
    )
    print(f"Default Sessions           : {DEFAULT_SESSIONS}")
    print("Validation Mode            : READ ONLY / STREAMING")
    separator("=")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate AQSD NSE F&O historical data quality."
    )
    parser.add_argument("--sessions", type=int, default=DEFAULT_SESSIONS)
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--status", action="store_true")
    return parser


def main() -> None:
    args = build_argument_parser().parse_args()

    if args.status:
        show_status()
        return

    end_date = parse_iso_date(args.end_date) if args.end_date else None

    if args.end_date and end_date is None:
        raise ValueError("--end-date must use YYYY-MM-DD.")

    summary = run_validation(args.sessions, end_date)

    if summary["status"] != "SUCCESS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

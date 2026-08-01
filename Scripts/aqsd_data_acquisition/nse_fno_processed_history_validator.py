"""
AQSD
NSE F&O Processed History Validator

Module : NPV-001
Version: 1.1.0
Author : AQSD

Validates processed NSE F&O history without modifying any data.

Accounting model
----------------
fno_contracts.csv = master universe
futures.csv       = FUTURE subset
options.csv       = OPTION subset

The three CSV files are NOT added together.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

from Scripts.aqsd_core.paths import (
    NSE_DERIVATIVES_PROCESSED_DIR,
    OUTPUT_DIR,
    PROJECT_ROOT,
)

MODULE_ID: Final[str] = "NPV-001"
MODULE_VERSION: Final[str] = "1.1.0"
DEFAULT_SESSIONS: Final[int] = 250

TRADING_CALENDAR_FILE: Final[Path] = (
    PROJECT_ROOT / "Data" / "NSE_Trading_Calendar.csv"
)
PROCESSED_ROOT: Final[Path] = NSE_DERIVATIVES_PROCESSED_DIR
AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR / "NSE_FNO_Processed_History_Validation_Audit.csv"
)
SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR / "NSE_FNO_Processed_History_Validation_Summary.json"
)

MASTER_NAME: Final[str] = "fno_contracts.csv"
FUTURES_NAME: Final[str] = "futures.csv"
OPTIONS_NAME: Final[str] = "options.csv"
MANIFEST_NAME: Final[str] = "parser_manifest.json"


@dataclass(frozen=True)
class Result:
    trade_date: str
    status: str
    master_rows: int
    master_futures: int
    master_options: int
    master_other: int
    futures_rows: int
    options_rows: int
    futures_type_errors: int
    options_type_errors: int
    manifest_ok: bool
    message: str


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def norm(value: object) -> str:
    return str(value if value is not None else "").strip().upper()


def load_calendar() -> list[date]:
    if not TRADING_CALENDAR_FILE.exists():
        raise FileNotFoundError(
            f"Trading calendar not found: {TRADING_CALENDAR_FILE}"
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

        date_col = fields.get("trade_date") or fields.get("date")
        flag_col = fields.get("is_trading_day")

        if date_col is None:
            raise RuntimeError(
                "Trading calendar requires trade_date column."
            )

        for row in reader:
            raw = str(row.get(date_col, "")).strip()

            if not raw:
                continue

            try:
                trading_date = parse_date(raw[:10])
            except ValueError:
                continue

            if flag_col is not None:
                flag = norm(row.get(flag_col, ""))

                if flag in {
                    "FALSE",
                    "0",
                    "NO",
                    "N",
                    "CLOSED",
                    "HOLIDAY",
                }:
                    continue

            sessions.append(trading_date)

    sessions = sorted(set(sessions))

    if not sessions:
        raise RuntimeError("No valid trading sessions in calendar.")

    return sessions


def resolve_sessions(
    sessions: int,
    end_date: date | None,
) -> list[date]:
    if sessions <= 0:
        raise ValueError("--sessions must be greater than zero.")

    values = load_calendar()

    if end_date is not None:
        values = [value for value in values if value <= end_date]

    if len(values) < sessions:
        raise RuntimeError(
            f"Not enough sessions. Requested={sessions}, "
            f"Available={len(values)}."
        )

    return values[-sessions:]


def read_contract_type_counts(
    path: Path,
) -> tuple[int, int, int, int]:
    total = 0
    futures = 0
    options = 0
    other = 0

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
        errors="replace",
    ) as handle:
        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise RuntimeError(f"No CSV header: {path}")

        fields = {
            str(name).strip().lower(): name
            for name in reader.fieldnames
            if name is not None
        }

        contract_col = fields.get("contract_type")

        if contract_col is None:
            raise RuntimeError(
                f"Missing contract_type column: {path}"
            )

        for row in reader:
            total += 1
            contract_type = norm(row.get(contract_col, ""))

            if contract_type == "FUTURE":
                futures += 1
            elif contract_type == "OPTION":
                options += 1
            else:
                other += 1

    return total, futures, options, other


def read_subset(
    path: Path,
    expected_type: str,
) -> tuple[int, int]:
    total = 0
    errors = 0

    with path.open(
        "r",
        encoding="utf-8-sig",
        newline="",
        errors="replace",
    ) as handle:
        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise RuntimeError(f"No CSV header: {path}")

        fields = {
            str(name).strip().lower(): name
            for name in reader.fieldnames
            if name is not None
        }

        contract_col = fields.get("contract_type")

        if contract_col is None:
            raise RuntimeError(
                f"Missing contract_type column: {path}"
            )

        for row in reader:
            total += 1

            if norm(row.get(contract_col, "")) != expected_type:
                errors += 1

    return total, errors


def validate_manifest(
    manifest_path: Path,
    trading_date: date,
) -> tuple[bool, str]:
    if not manifest_path.exists():
        return True, "Manifest absent; CSV validation only."

    try:
        payload = json.loads(
            manifest_path.read_text(encoding="utf-8")
        )
    except Exception as exc:
        return False, f"Manifest error: {type(exc).__name__}: {exc}"

    if not isinstance(payload, dict):
        return False, "Manifest root is not a JSON object."

    if "trade_date" in payload:
        actual = str(payload["trade_date"])[:10]
        expected = trading_date.isoformat()

        if actual and actual != expected:
            return False, (
                f"Manifest trade_date mismatch: {actual} != {expected}"
            )

    return True, "OK"


def validate_session(trading_date: date) -> Result:
    folder = PROCESSED_ROOT / trading_date.isoformat()

    master = folder / MASTER_NAME
    futures = folder / FUTURES_NAME
    options = folder / OPTIONS_NAME
    manifest = folder / MANIFEST_NAME

    if not folder.is_dir():
        return Result(
            trading_date.isoformat(),
            "MISSING",
            0, 0, 0, 0, 0, 0, 0, 0,
            False,
            "Processed session folder not found.",
        )

    missing = [
        path.name
        for path in (master, futures, options)
        if not path.is_file()
    ]

    if missing:
        return Result(
            trading_date.isoformat(),
            "FAILED",
            0, 0, 0, 0, 0, 0, 0, 0,
            False,
            "Missing required file(s): " + ", ".join(missing),
        )

    try:
        (
            master_rows,
            master_futures,
            master_options,
            master_other,
        ) = read_contract_type_counts(master)

        futures_rows, futures_errors = read_subset(
            futures,
            "FUTURE",
        )
        options_rows, options_errors = read_subset(
            options,
            "OPTION",
        )

        manifest_ok, manifest_message = validate_manifest(
            manifest,
            trading_date,
        )

        reconciliation_ok = (
            master_rows
            == master_futures + master_options + master_other
        )

        futures_match = master_futures == futures_rows
        options_match = master_options == options_rows

        ok = all(
            (
                master_rows > 0,
                futures_errors == 0,
                options_errors == 0,
                futures_match,
                options_match,
                reconciliation_ok,
                manifest_ok,
            )
        )

        messages: list[str] = []

        if futures_errors:
            messages.append(
                f"futures.csv type errors={futures_errors}"
            )
        if options_errors:
            messages.append(
                f"options.csv type errors={options_errors}"
            )
        if not futures_match:
            messages.append(
                f"FUTURE count mismatch "
                f"{master_futures}!={futures_rows}"
            )
        if not options_match:
            messages.append(
                f"OPTION count mismatch "
                f"{master_options}!={options_rows}"
            )
        if not reconciliation_ok:
            messages.append("Master reconciliation failed.")
        if not manifest_ok:
            messages.append(manifest_message)

        return Result(
            trading_date.isoformat(),
            "PASS" if ok else "FAILED",
            master_rows,
            master_futures,
            master_options,
            master_other,
            futures_rows,
            options_rows,
            futures_errors,
            options_errors,
            manifest_ok,
            "OK" if ok else " | ".join(messages),
        )

    except Exception as exc:
        return Result(
            trading_date.isoformat(),
            "FAILED",
            0, 0, 0, 0, 0, 0, 0, 0,
            False,
            f"{type(exc).__name__}: {exc}",
        )


def save_outputs(
    results: list[Result],
    summary: dict,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = [asdict(result) for result in results]

    if rows:
        with AUDIT_FILE.open(
            "w",
            encoding="utf-8-sig",
            newline="",
        ) as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=list(rows[0].keys()),
            )
            writer.writeheader()
            writer.writerows(rows)

    SUMMARY_FILE.write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )


def display(summary: dict) -> None:
    print()
    print("=" * 100)
    print("AQSD NSE F&O PROCESSED HISTORY VALIDATION")
    print("=" * 100)
    print(f"Module                    : {MODULE_ID}")
    print(f"Version                   : {MODULE_VERSION}")
    print(f"Requested Sessions        : {summary['requested_sessions']}")
    print(f"Resolved Sessions         : {summary['resolved_sessions']}")
    print(f"First Session             : {summary['first_session']}")
    print(f"Last Session              : {summary['last_session']}")
    print("-" * 100)
    print(f"Validated Sessions        : {summary['passed']}")
    print(f"Missing Sessions          : {summary['missing']}")
    print(f"Failed Sessions           : {summary['failed']}")
    print("-" * 100)
    print(f"Master Contract Rows      : {summary['master_rows']:,}")
    print(f"Master Futures Rows       : {summary['master_futures']:,}")
    print(f"Master Options Rows       : {summary['master_options']:,}")
    print(f"Master Other Rows         : {summary['master_other']:,}")
    print("-" * 100)
    print(f"Futures CSV Rows          : {summary['futures_rows']:,}")
    print(f"Options CSV Rows          : {summary['options_rows']:,}")
    print(f"Futures Type Errors       : {summary['futures_type_errors']}")
    print(f"Options Type Errors       : {summary['options_type_errors']}")
    print(f"Subset Count Mismatches   : {summary['subset_mismatches']}")
    print(f"Manifest Failures         : {summary['manifest_failures']}")
    print("-" * 100)
    print(f"Trading Calendar          : {TRADING_CALENDAR_FILE}")
    print(f"Processed Root            : {PROCESSED_ROOT}")
    print(f"Audit CSV                 : {AUDIT_FILE}")
    print(f"Summary JSON              : {SUMMARY_FILE}")
    print("-" * 100)
    print("Processed Files           : UNCHANGED")
    print("Historical Fabrication    : PROHIBITED")
    print("Deletion                  : NONE")
    print("Accounting Model          : MASTER + SUBSET VALIDATION")
    print("-" * 100)
    print(f"Status                    : {summary['status']}")
    print("=" * 100)


def run_validation(
    sessions: int,
    end_date: date | None,
) -> dict:
    resolved = resolve_sessions(sessions, end_date)
    results: list[Result] = []

    for index, trading_date in enumerate(resolved, start=1):
        result = validate_session(trading_date)
        results.append(result)

        print(
            f"[{index:03d}/{len(resolved):03d}] "
            f"{trading_date} {result.status}"
        )

    passed = sum(r.status == "PASS" for r in results)
    missing = sum(r.status == "MISSING" for r in results)
    failed = sum(r.status == "FAILED" for r in results)

    master_rows = sum(r.master_rows for r in results)
    master_futures = sum(r.master_futures for r in results)
    master_options = sum(r.master_options for r in results)
    master_other = sum(r.master_other for r in results)
    futures_rows = sum(r.futures_rows for r in results)
    options_rows = sum(r.options_rows for r in results)
    futures_type_errors = sum(r.futures_type_errors for r in results)
    options_type_errors = sum(r.options_type_errors for r in results)

    subset_mismatches = sum(
        (
            r.master_futures != r.futures_rows
            or r.master_options != r.options_rows
        )
        for r in results
    )

    manifest_failures = sum(
        not r.manifest_ok
        for r in results
        if r.status != "MISSING"
    )

    status = (
        "SUCCESS"
        if passed == len(resolved)
        and missing == 0
        and failed == 0
        and futures_type_errors == 0
        and options_type_errors == 0
        and subset_mismatches == 0
        and manifest_failures == 0
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
        "passed": passed,
        "missing": missing,
        "failed": failed,
        "master_rows": master_rows,
        "master_futures": master_futures,
        "master_options": master_options,
        "master_other": master_other,
        "futures_rows": futures_rows,
        "options_rows": options_rows,
        "futures_type_errors": futures_type_errors,
        "options_type_errors": options_type_errors,
        "subset_mismatches": subset_mismatches,
        "manifest_failures": manifest_failures,
        "status": status,
    }

    save_outputs(results, summary)
    display(summary)
    return summary


def show_status() -> None:
    print()
    print("=" * 100)
    print("AQSD NSE F&O PROCESSED HISTORY VALIDATOR STATUS")
    print("=" * 100)
    print(f"Module                    : {MODULE_ID}")
    print(f"Version                   : {MODULE_VERSION}")
    print(f"Trading Calendar          : {TRADING_CALENDAR_FILE}")
    print(
        f"Calendar Exists           : "
        f"{'YES' if TRADING_CALENDAR_FILE.exists() else 'NO'}"
    )
    print(f"Processed Root            : {PROCESSED_ROOT}")
    print(
        f"Processed Root Exists     : "
        f"{'YES' if PROCESSED_ROOT.exists() else 'NO'}"
    )
    print(f"Default Sessions          : {DEFAULT_SESSIONS}")
    print("Accounting Model          : MASTER + FUTURES/OPTIONS SUBSETS")
    print("=" * 100)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate AQSD NSE F&O processed history."
    )
    parser.add_argument(
        "--sessions",
        type=int,
        default=DEFAULT_SESSIONS,
    )
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--status",
        action="store_true",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.status:
        show_status()
        return

    end_date = parse_date(args.end_date) if args.end_date else None

    summary = run_validation(
        sessions=args.sessions,
        end_date=end_date,
    )

    if summary["status"] != "SUCCESS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

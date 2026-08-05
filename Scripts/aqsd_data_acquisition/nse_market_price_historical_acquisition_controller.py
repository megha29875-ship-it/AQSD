"""
AQSD
Market Price Historical Acquisition Controller

Module ID: MPD-007
Version: 1.1.0
Author: AQSD

Purpose
-------
Safely connect the validated MPD-006 acquisition queue to the
existing FYERS historical downloader.

Key Fixes in v1.1.0
-------------------
1. Uses downloader's ACTUAL ACQUISITION_QUEUE_FILE path.
2. Builds downloader-native queue schema:
   - security_id
   - symbol
   - acquisition_symbol
   - acquisition_ready
   - acquisition_status
3. Only MPD-006 validated securities are allowed through.
4. Original downloader queue is backed up and restored.
5. Market Price Database is not modified.
6. Frozen historical F&O database is not modified.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Final

import pandas as pd


# ============================================================
# MODULE IDENTITY
# ============================================================

MODULE_ID: Final[str] = "MPD-007"
MODULE_VERSION: Final[str] = "1.1.0"


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT: Final[Path] = (
    Path(__file__)
    .resolve()
    .parents[2]
)

OUTPUT_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Output"
)

BACKUP_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Backup"
    / "Market_Price_Queues"
)


# ============================================================
# INPUTS
# ============================================================

VALIDATED_QUEUE_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Acquisition_Queue_Validated.csv"
)

MPD006_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Acquisition_Queue_Validation_Summary.json"
)


# ============================================================
# DOWNLOADER
# ============================================================

DOWNLOADER_MODULE: Final[str] = (
    "Scripts.aqsd_data_acquisition."
    "nse_market_price_historical_downloader"
)

DOWNLOADER_SOURCE_FILE: Final[Path] = (
    PROJECT_ROOT
    / "Scripts"
    / "aqsd_data_acquisition"
    / "nse_market_price_historical_downloader.py"
)


# ============================================================
# DOWNLOADER OUTPUTS
# ============================================================

DOWNLOADER_AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Historical_Download_Audit.csv"
)

DOWNLOADER_FAILURES_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Historical_Download_Failures.csv"
)


# ============================================================
# CONTROLLER OUTPUTS
# ============================================================

CONTROLLER_AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Historical_Acquisition_Controller_Audit.csv"
)

CONTROLLER_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Historical_Acquisition_Controller_Summary.json"
)

RUNTIME_QUEUE_SNAPSHOT: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Historical_Runtime_Queue.csv"
)


# ============================================================
# HELPERS
# ============================================================

def separator() -> None:

    print("=" * 100)


def sub_separator() -> None:

    print("-" * 100)


def ensure_directories() -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def normalize_column_name(
    value: object,
) -> str:

    return (
        str(value)
        .strip()
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("/", "_")
        .replace(".", "_")
        .replace("(", "")
        .replace(")", "")
    )


def safe_text(
    value: object,
) -> str:

    if pd.isna(value):
        return ""

    return str(value).strip()


def parse_bool(
    value: object,
) -> bool:

    if pd.isna(value):
        return False

    return (
        str(value)
        .strip()
        .upper()
        in {
            "TRUE",
            "YES",
            "Y",
            "1",
        }
    )


def file_sha256(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open("rb") as handle:

        while True:

            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(
                chunk
            )

    return digest.hexdigest()


def load_json(
    path: Path,
) -> dict[str, object]:

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_inputs() -> None:

    required_files = [
        VALIDATED_QUEUE_FILE,
        MPD006_SUMMARY_FILE,
        DOWNLOADER_SOURCE_FILE,
    ]

    missing = [
        path
        for path in required_files
        if not path.exists()
    ]

    if missing:

        raise FileNotFoundError(
            "Required MPD-007 input file(s) missing: "
            + ", ".join(
                str(path)
                for path in missing
            )
        )


# ============================================================
# DISCOVER DOWNLOADER QUEUE PATH
# ============================================================

def discover_downloader_queue_file() -> Path:

    module = importlib.import_module(
        DOWNLOADER_MODULE
    )

    if not hasattr(
        module,
        "ACQUISITION_QUEUE_FILE",
    ):

        raise RuntimeError(
            "Downloader does not expose "
            "ACQUISITION_QUEUE_FILE."
        )

    raw_path = getattr(
        module,
        "ACQUISITION_QUEUE_FILE",
    )

    queue_path = Path(
        raw_path
    )

    if not queue_path.is_absolute():

        queue_path = (
            PROJECT_ROOT
            / queue_path
        )

    return queue_path.resolve()


# ============================================================
# MPD-006 GATE
# ============================================================

def validate_mpd006() -> dict[str, object]:

    summary = load_json(
        MPD006_SUMMARY_FILE
    )

    status = safe_text(
        summary.get(
            "status",
            "",
        )
    ).upper()

    critical_issues = int(
        summary.get(
            "critical_issues",
            0,
        )
    )

    rejected_rows = int(
        summary.get(
            "rejected_rows",
            0,
        )
    )

    matches_fno005 = bool(
        summary.get(
            "matches_fno005",
            False,
        )
    )

    queue_reconciles = bool(
        summary.get(
            "queue_reconciles",
            False,
        )
    )

    validated_rows = int(
        summary.get(
            "validated_rows",
            0,
        )
    )

    if status != "SUCCESS":

        raise RuntimeError(
            "MPD-006 status is not SUCCESS."
        )

    if critical_issues != 0:

        raise RuntimeError(
            "MPD-006 contains critical issues."
        )

    if rejected_rows != 0:

        raise RuntimeError(
            "MPD-006 contains rejected rows."
        )

    if not matches_fno005:

        raise RuntimeError(
            "MPD-006 does not match FNO-005."
        )

    if not queue_reconciles:

        raise RuntimeError(
            "MPD-006 queue does not reconcile."
        )

    if validated_rows <= 0:

        raise RuntimeError(
            "MPD-006 validated queue is empty."
        )

    return summary


# ============================================================
# LOAD VALIDATED QUEUE
# ============================================================

def load_validated_queue() -> pd.DataFrame:

    dataframe = pd.read_csv(
        VALIDATED_QUEUE_FILE,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(
            column
        )
        for column in dataframe.columns
    ]

    required = {
        "security_id",
        "symbol",
        "resolved_fyers_symbol",
        "validation_pass",
    }

    missing = (
        required
        - set(
            dataframe.columns
        )
    )

    if missing:

        raise RuntimeError(
            "Validated queue missing required columns: "
            + ", ".join(
                sorted(
                    missing
                )
            )
        )

    dataframe[
        "security_id"
    ] = (
        dataframe[
            "security_id"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    dataframe[
        "symbol"
    ] = (
        dataframe[
            "symbol"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe[
        "resolved_fyers_symbol"
    ] = (
        dataframe[
            "resolved_fyers_symbol"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    dataframe = dataframe[
        dataframe[
            "validation_pass"
        ].map(
            parse_bool
        )
    ].copy()

    dataframe = (
        dataframe
        .drop_duplicates(
            subset=[
                "security_id",
            ],
            keep="first",
        )
        .sort_values(
            by=[
                "symbol",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    return dataframe


# ============================================================
# BUILD DOWNLOADER-NATIVE QUEUE
# ============================================================

def build_runtime_queue(
    validated_queue: pd.DataFrame,
) -> pd.DataFrame:

    runtime = pd.DataFrame()

    runtime[
        "security_id"
    ] = validated_queue[
        "security_id"
    ]

    runtime[
        "symbol"
    ] = validated_queue[
        "symbol"
    ]

    runtime[
        "acquisition_symbol"
    ] = validated_queue[
        "resolved_fyers_symbol"
    ]

    runtime[
        "acquisition_ready"
    ] = True

    runtime[
        "acquisition_status"
    ] = "READY"

    runtime[
        "source"
    ] = "MPD-006_VALIDATED_QUEUE"

    runtime[
        "controller_module"
    ] = MODULE_ID

    runtime[
        "controller_version"
    ] = MODULE_VERSION

    runtime[
        "generated_at"
    ] = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    return runtime


# ============================================================
# VALIDATE RUNTIME QUEUE
# ============================================================

def validate_runtime_queue(
    runtime: pd.DataFrame,
    expected_rows: int,
) -> dict[str, object]:

    rows = int(
        len(
            runtime
        )
    )

    duplicate_security_ids = int(
        runtime.duplicated(
            subset=[
                "security_id",
            ],
            keep=False,
        ).sum()
    )

    duplicate_symbols = int(
        runtime.duplicated(
            subset=[
                "symbol",
            ],
            keep=False,
        ).sum()
    )

    duplicate_acquisition_symbols = int(
        runtime.duplicated(
            subset=[
                "acquisition_symbol",
            ],
            keep=False,
        ).sum()
    )

    blank_security_ids = int(
        runtime[
            "security_id"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    blank_symbols = int(
        runtime[
            "symbol"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    blank_acquisition_symbols = int(
        runtime[
            "acquisition_symbol"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    not_ready = int(
        (
            ~runtime[
                "acquisition_ready"
            ]
            .map(
                parse_bool
            )
        ).sum()
    )

    invalid_status = int(
        (
            runtime[
                "acquisition_status"
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            .ne(
                "READY"
            )
        ).sum()
    )

    row_count_matches = (
        rows
        == expected_rows
    )

    critical_issues = (
        duplicate_security_ids
        + duplicate_symbols
        + duplicate_acquisition_symbols
        + blank_security_ids
        + blank_symbols
        + blank_acquisition_symbols
        + not_ready
        + invalid_status
    )

    if not row_count_matches:

        critical_issues += 1

    return {
        "runtime_rows":
            rows,

        "expected_rows":
            expected_rows,

        "row_count_matches":
            row_count_matches,

        "duplicate_security_ids":
            duplicate_security_ids,

        "duplicate_symbols":
            duplicate_symbols,

        "duplicate_acquisition_symbols":
            duplicate_acquisition_symbols,

        "blank_security_ids":
            blank_security_ids,

        "blank_symbols":
            blank_symbols,

        "blank_acquisition_symbols":
            blank_acquisition_symbols,

        "not_ready":
            not_ready,

        "invalid_status":
            invalid_status,

        "critical_issues":
            critical_issues,
    }


# ============================================================
# BACKUP ORIGINAL DOWNLOADER QUEUE
# ============================================================

def backup_queue(
    runtime_queue_file: Path,
) -> Path | None:

    if not runtime_queue_file.exists():

        return None

    timestamp = (
        datetime.now()
        .astimezone()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    backup_file = (
        BACKUP_DIR
        / (
            runtime_queue_file.stem
            + "_PRE_MPD007_"
            + timestamp
            + runtime_queue_file.suffix
        )
    )

    shutil.copy2(
        runtime_queue_file,
        backup_file,
    )

    if (
        file_sha256(
            runtime_queue_file
        )
        != file_sha256(
            backup_file
        )
    ):

        raise RuntimeError(
            "Downloader queue backup hash mismatch."
        )

    return backup_file


# ============================================================
# INSTALL CONTROLLED QUEUE
# ============================================================

def install_runtime_queue(
    runtime: pd.DataFrame,
    runtime_queue_file: Path,
) -> None:

    runtime_queue_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    runtime.to_csv(
        RUNTIME_QUEUE_SNAPSHOT,
        index=False,
        encoding="utf-8-sig",
    )

    runtime.to_csv(
        runtime_queue_file,
        index=False,
        encoding="utf-8-sig",
    )

    installed = pd.read_csv(
        runtime_queue_file,
        low_memory=False,
    )

    installed.columns = [
        normalize_column_name(
            column
        )
        for column in installed.columns
    ]

    required = {
        "security_id",
        "symbol",
        "acquisition_symbol",
        "acquisition_ready",
        "acquisition_status",
    }

    missing = (
        required
        - set(
            installed.columns
        )
    )

    if missing:

        raise RuntimeError(
            "Installed runtime queue schema mismatch: "
            + ", ".join(
                sorted(
                    missing
                )
            )
        )

    if len(
        installed
    ) != len(
        runtime
    ):

        raise RuntimeError(
            "Installed runtime queue row count mismatch."
        )


# ============================================================
# RESTORE ORIGINAL QUEUE
# ============================================================

def restore_original_queue(
    runtime_queue_file: Path,
    backup_file: Path | None,
    queue_preexisted: bool,
) -> bool:

    if queue_preexisted:

        if backup_file is None:

            raise RuntimeError(
                "Original downloader queue existed "
                "but backup was not created."
            )

        shutil.copy2(
            backup_file,
            runtime_queue_file,
        )

        return (
            file_sha256(
                backup_file
            )
            == file_sha256(
                runtime_queue_file
            )
        )

    if runtime_queue_file.exists():

        runtime_queue_file.unlink()

    return (
        not runtime_queue_file.exists()
    )


# ============================================================
# CLEAR OLD DOWNLOADER RESULT FILES
# ============================================================

def clear_old_downloader_results() -> None:

    for path in (
        DOWNLOADER_AUDIT_FILE,
        DOWNLOADER_FAILURES_FILE,
    ):

        if path.exists():

            path.unlink()


# ============================================================
# EXECUTE DOWNLOADER
# ============================================================

def execute_downloader() -> subprocess.CompletedProcess[str]:

    command = [
        sys.executable,
        "-m",
        DOWNLOADER_MODULE,
    ]

    print()

    sub_separator()

    print(
        "STARTING CONTROLLED FYERS HISTORICAL DOWNLOAD"
    )

    sub_separator()

    print(
        f"Python Executable              : "
        f"{sys.executable}"
    )

    print(
        f"Downloader Module              : "
        f"{DOWNLOADER_MODULE}"
    )

    print()

    completed = subprocess.run(
        command,
        cwd=str(
            PROJECT_ROOT
        ),
        text=True,
        check=False,
    )

    print()

    sub_separator()

    print(
        "FYERS HISTORICAL DOWNLOAD PROCESS FINISHED"
    )

    sub_separator()

    print(
        f"Downloader Return Code         : "
        f"{completed.returncode}"
    )

    return completed


# ============================================================
# READ DOWNLOADER OUTPUT
# ============================================================

def read_downloader_results(
    expected_rows: int,
) -> dict[str, object]:

    audit_rows = 0
    success_rows = 0
    failed_rows = 0
    downloaded_rows = 0

    if DOWNLOADER_AUDIT_FILE.exists():

        try:

            audit = pd.read_csv(
                DOWNLOADER_AUDIT_FILE,
                low_memory=False,
            )

        except pd.errors.EmptyDataError:

            audit = pd.DataFrame()

        if not audit.empty:

            audit.columns = [
                normalize_column_name(
                    column
                )
                for column in audit.columns
            ]

            audit_rows = int(
                len(
                    audit
                )
            )

            if "status" in audit.columns:

                status = (
                    audit[
                        "status"
                    ]
                    .fillna("")
                    .astype(str)
                    .str.strip()
                    .str.upper()
                )

                success_rows = int(
                    status.eq(
                        "SUCCESS"
                    ).sum()
                )

                failed_rows = int(
                    status.eq(
                        "FAILED"
                    ).sum()
                )

            if "rows" in audit.columns:

                downloaded_rows = int(
                    pd.to_numeric(
                        audit[
                            "rows"
                        ],
                        errors="coerce",
                    )
                    .fillna(0)
                    .sum()
                )

    failure_file_rows = 0

    if DOWNLOADER_FAILURES_FILE.exists():

        try:

            failures = pd.read_csv(
                DOWNLOADER_FAILURES_FILE,
                low_memory=False,
            )

            failure_file_rows = int(
                len(
                    failures
                )
            )

        except pd.errors.EmptyDataError:

            failure_file_rows = 0

    if failed_rows == 0:

        failed_rows = (
            failure_file_rows
        )

    processed_symbols = audit_rows

    if processed_symbols == 0:

        processed_symbols = (
            success_rows
            + failed_rows
        )

    processing_reconciles = (
        processed_symbols
        == expected_rows
    )

    return {
        "downloader_audit_rows":
            audit_rows,

        "successful_symbols":
            success_rows,

        "failed_symbols":
            failed_rows,

        "failure_file_rows":
            failure_file_rows,

        "downloaded_price_rows":
            downloaded_rows,

        "processed_symbols":
            processed_symbols,

        "expected_symbols":
            expected_rows,

        "processing_reconciles":
            processing_reconciles,
    }


# ============================================================
# RUN CONTROLLER
# ============================================================

def run_controller() -> dict[str, object]:

    ensure_directories()

    validate_inputs()

    mpd006_summary = (
        validate_mpd006()
    )

    expected_rows = int(
        mpd006_summary[
            "validated_rows"
        ]
    )

    runtime_queue_file = (
        discover_downloader_queue_file()
    )

    validated_queue = (
        load_validated_queue()
    )

    runtime_queue = (
        build_runtime_queue(
            validated_queue
        )
    )

    runtime_validation = (
        validate_runtime_queue(
            runtime_queue,
            expected_rows,
        )
    )

    if (
        runtime_validation[
            "critical_issues"
        ]
        != 0
    ):

        raise RuntimeError(
            "Controlled runtime queue failed validation."
        )

    queue_preexisted = (
        runtime_queue_file.exists()
    )

    original_hash: str | None = None

    if queue_preexisted:

        original_hash = (
            file_sha256(
                runtime_queue_file
            )
        )

    backup_file = (
        backup_queue(
            runtime_queue_file
        )
    )

    installed_hash = ""

    downloader_return_code = -1

    downloader_results: dict[
        str,
        object,
    ] = {}

    restore_success = False

    try:

        clear_old_downloader_results()

        install_runtime_queue(
            runtime_queue,
            runtime_queue_file,
        )

        installed_hash = (
            file_sha256(
                runtime_queue_file
            )
        )

        print()

        print(
            f"Downloader Queue Path          : "
            f"{runtime_queue_file}"
        )

        print(
            f"Controlled Queue Rows          : "
            f"{len(runtime_queue):,}"
        )

        completed = (
            execute_downloader()
        )

        downloader_return_code = (
            completed.returncode
        )

        downloader_results = (
            read_downloader_results(
                expected_rows
            )
        )

    finally:

        restore_success = (
            restore_original_queue(
                runtime_queue_file,
                backup_file,
                queue_preexisted,
            )
        )

        if (
            queue_preexisted
            and original_hash is not None
        ):

            restore_success = (
                restore_success
                and file_sha256(
                    runtime_queue_file
                )
                == original_hash
            )

    if not restore_success:

        raise RuntimeError(
            "Original downloader acquisition queue "
            "was not restored."
        )

    failed_symbols = int(
        downloader_results.get(
            "failed_symbols",
            0,
        )
    )

    processing_reconciles = bool(
        downloader_results.get(
            "processing_reconciles",
            False,
        )
    )

    critical_issues = 0

    if downloader_return_code != 0:

        critical_issues += 1

    if failed_symbols != 0:

        critical_issues += (
            failed_symbols
        )

    if not processing_reconciles:

        critical_issues += 1

    status = (
        "SUCCESS"
        if critical_issues == 0
        else "PARTIAL"
    )

    summary = {
        "module_id":
            MODULE_ID,

        "module_version":
            MODULE_VERSION,

        "generated_at":
            datetime.now()
            .astimezone()
            .isoformat(
                timespec="seconds"
            ),

        "mpd006_status":
            mpd006_summary.get(
                "status"
            ),

        "validated_queue_rows":
            expected_rows,

        "downloader_queue_file":
            str(
                runtime_queue_file
            ),

        "runtime_queue_rows":
            runtime_validation[
                "runtime_rows"
            ],

        "runtime_row_count_matches":
            runtime_validation[
                "row_count_matches"
            ],

        "runtime_duplicate_security_ids":
            runtime_validation[
                "duplicate_security_ids"
            ],

        "runtime_duplicate_symbols":
            runtime_validation[
                "duplicate_symbols"
            ],

        "runtime_duplicate_acquisition_symbols":
            runtime_validation[
                "duplicate_acquisition_symbols"
            ],

        "runtime_blank_security_ids":
            runtime_validation[
                "blank_security_ids"
            ],

        "runtime_blank_symbols":
            runtime_validation[
                "blank_symbols"
            ],

        "runtime_blank_acquisition_symbols":
            runtime_validation[
                "blank_acquisition_symbols"
            ],

        "runtime_not_ready":
            runtime_validation[
                "not_ready"
            ],

        "runtime_invalid_status":
            runtime_validation[
                "invalid_status"
            ],

        "runtime_queue_backup":
            (
                str(
                    backup_file
                )
                if backup_file
                else None
            ),

        "runtime_queue_snapshot":
            str(
                RUNTIME_QUEUE_SNAPSHOT
            ),

        "runtime_queue_installed_sha256":
            installed_hash,

        "original_queue_restored":
            restore_success,

        "downloader_return_code":
            downloader_return_code,

        **downloader_results,

        "controller_critical_issues":
            critical_issues,

        "market_price_database_modified":
            False,

        "frozen_historical_database_modified":
            False,

        "historical_fabrication":
            False,

        "status":
            status,
    }

    pd.DataFrame(
        [summary]
    ).to_csv(
        CONTROLLER_AUDIT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    CONTROLLER_SUMMARY_FILE.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return summary


# ============================================================
# DISPLAY
# ============================================================

def display_summary(
    summary: dict[str, object],
) -> None:

    print()

    separator()

    print(
        "AQSD MARKET PRICE HISTORICAL ACQUISITION CONTROLLER"
    )

    separator()

    print(
        f"Module                         : "
        f"{summary['module_id']}"
    )

    print(
        f"Version                        : "
        f"{summary['module_version']}"
    )

    sub_separator()

    print(
        f"MPD-006 Status                 : "
        f"{summary['mpd006_status']}"
    )

    print(
        f"Validated Queue Rows           : "
        f"{int(summary['validated_queue_rows']):,}"
    )

    print(
        f"Downloader Queue Path          : "
        f"{summary['downloader_queue_file']}"
    )

    print(
        f"Runtime Queue Rows             : "
        f"{int(summary['runtime_queue_rows']):,}"
    )

    print(
        f"Runtime Row Count Matches      : "
        f"{summary['runtime_row_count_matches']}"
    )

    sub_separator()

    print(
        f"Runtime Duplicate IDs          : "
        f"{int(summary['runtime_duplicate_security_ids']):,}"
    )

    print(
        f"Runtime Duplicate Symbols      : "
        f"{int(summary['runtime_duplicate_symbols']):,}"
    )

    print(
        f"Runtime Duplicate Acquisition  : "
        f"{int(summary['runtime_duplicate_acquisition_symbols']):,}"
    )

    print(
        f"Runtime Blank Acquisition      : "
        f"{int(summary['runtime_blank_acquisition_symbols']):,}"
    )

    sub_separator()

    print(
        f"Downloader Return Code         : "
        f"{summary['downloader_return_code']}"
    )

    print(
        f"Expected Symbols               : "
        f"{int(summary.get('expected_symbols', 0)):,}"
    )

    print(
        f"Processed Symbols              : "
        f"{int(summary.get('processed_symbols', 0)):,}"
    )

    print(
        f"Successful Symbols             : "
        f"{int(summary.get('successful_symbols', 0)):,}"
    )

    print(
        f"Failed Symbols                 : "
        f"{int(summary.get('failed_symbols', 0)):,}"
    )

    print(
        f"Downloaded Price Rows          : "
        f"{int(summary.get('downloaded_price_rows', 0)):,}"
    )

    print(
        f"Processing Reconciles          : "
        f"{summary.get('processing_reconciles')}"
    )

    sub_separator()

    print(
        f"Original Queue Restored        : "
        f"{summary['original_queue_restored']}"
    )

    print(
        f"Controller Critical Issues     : "
        f"{int(summary['controller_critical_issues']):,}"
    )

    sub_separator()

    print(
        "Market Price Database          : NOT MODIFIED"
    )

    print(
        "Frozen Historical Database     : NOT MODIFIED"
    )

    print(
        "Historical Fabrication         : PROHIBITED"
    )

    sub_separator()

    print(
        f"Status                         : "
        f"{summary['status']}"
    )

    separator()


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    try:

        summary = run_controller()

        display_summary(
            summary
        )

    except KeyboardInterrupt:

        print()

        separator()

        print(
            "AQSD MARKET PRICE HISTORICAL ACQUISITION CONTROLLER"
        )

        separator()

        print(
            "Status                         : INTERRUPTED"
        )

        print(
            "Market Price Database          : NOT MODIFIED"
        )

        separator()

        raise SystemExit(130)

    except Exception as exc:

        print()

        separator()

        print(
            "AQSD MARKET PRICE HISTORICAL ACQUISITION CONTROLLER"
        )

        separator()

        print(
            "Status                         : FAILED"
        )

        print(
            f"Reason                         : "
            f"{type(exc).__name__}: {exc}"
        )

        print(
            "Market Price Database          : NOT MODIFIED"
        )

        print(
            "Frozen Historical Database     : NOT MODIFIED"
        )

        separator()

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
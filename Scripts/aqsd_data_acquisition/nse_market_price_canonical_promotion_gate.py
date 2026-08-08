"""
AQSD
Canonical Market Price Promotion Gate

Module ID: MPD-013
Version: 1.0.0
Author: AQSD

Purpose
-------
Safely promote the independently validated canonical Market Price
candidate into the live AQSD Market Price Database.

Promotion Safety
----------------
1. MPD-012 must be SUCCESS.
2. MPD-012 Promotion Decision must be PASS.
3. Candidate SHA256 must match MPD-012.
4. Candidate is reopened from disk.
5. Candidate row/security counts are independently rechecked.
6. Existing live database is backed up before replacement.
7. Promotion uses a temporary file.
8. Temporary file hash is verified.
9. Atomic replacement is used.
10. Promoted live file hash is verified.
11. Rollback is attempted automatically if post-promotion verification fails.
12. Security Master is never modified.
13. Raw and Processed data remain read only.
14. Historical fabrication is prohibited.

IMPORTANT
---------
This is the first MPD module allowed to modify the live Market Price Database.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Final

import pandas as pd


# ============================================================
# MODULE
# ============================================================

MODULE_ID: Final[str] = "MPD-013"
MODULE_VERSION: Final[str] = "1.0.0"


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

DATA_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Data"
)

CANDIDATE_ROOT: Final[Path] = (
    DATA_DIR
    / "Market_Price"
    / "Candidate"
)

DATABASE_ROOT: Final[Path] = (
    DATA_DIR
    / "Market_Price"
    / "Database"
)

BACKUP_ROOT: Final[Path] = (
    PROJECT_ROOT
    / "Backup"
    / "Market_Price"
)


# ============================================================
# INPUT FILES
# ============================================================

CANDIDATE_FILE: Final[Path] = (
    CANDIDATE_ROOT
    / "AQSD_Market_Price_Canonical_Candidate.csv"
)

MPD012_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Candidate_Validation_Summary.json"
)


# ============================================================
# LIVE DATABASE
# ============================================================

LIVE_DATABASE_FILE: Final[Path] = (
    DATABASE_ROOT
    / "AQSD_Market_Price_Database.csv"
)

TEMP_PROMOTION_FILE: Final[Path] = (
    DATABASE_ROOT
    / "AQSD_Market_Price_Database.__promotion_tmp__.csv"
)


# ============================================================
# OUTPUT FILES
# ============================================================

PROMOTION_AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Promotion_Audit.csv"
)

PROMOTION_SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Market_Price_Canonical_Promotion_Summary.json"
)


# ============================================================
# EXPECTED CANONICAL SCHEMA
# ============================================================

CANONICAL_COLUMNS: Final[list[str]] = [
    "trade_date",
    "security_id",
    "symbol",
    "fyers_symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "source",
    "source_file",
    "source_module",
    "validation_module",
    "processing_module",
    "processing_version",
    "canonical_builder_module",
    "canonical_builder_version",
    "canonical_candidate_generated_at",
]


# ============================================================
# DISPLAY HELPERS
# ============================================================

def separator() -> None:
    print("=" * 100)


def sub_separator() -> None:
    print("-" * 100)


# ============================================================
# GENERIC HELPERS
# ============================================================

def ensure_directories() -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    DATABASE_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    BACKUP_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )


def safe_text(
    value: object,
) -> str:

    if pd.isna(value):
        return ""

    return str(value).strip()


def normalize_column_name(
    value: object,
) -> str:

    text = (
        str(value)
        .strip()
        .lower()
    )

    text = re.sub(
        r"[^a-z0-9]+",
        "_",
        text,
    )

    return text.strip("_")


def load_json(
    path: Path,
) -> dict[str, object]:

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def file_sha256(
    path: Path,
) -> str:

    digest = hashlib.sha256()

    with path.open(
        "rb"
    ) as handle:

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


def timestamp_for_filename() -> str:

    return (
        datetime.now()
        .astimezone()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_inputs() -> None:

    required_files = [
        CANDIDATE_FILE,
        MPD012_SUMMARY_FILE,
    ]

    missing = [
        path
        for path in required_files
        if not path.exists()
    ]

    if missing:

        raise FileNotFoundError(
            "Required MPD-013 input file(s) missing: "
            + ", ".join(
                str(path)
                for path in missing
            )
        )


# ============================================================
# MPD-012 GATE
# ============================================================

def validate_mpd012() -> dict[str, object]:

    summary = load_json(
        MPD012_SUMMARY_FILE
    )

    status = safe_text(
        summary.get(
            "status",
            "",
        )
    ).upper()

    promotion_decision = safe_text(
        summary.get(
            "promotion_decision",
            "",
        )
    ).upper()

    critical_issues = int(
        summary.get(
            "critical_issues",
            0,
        )
    )

    sha256_matches = bool(
        summary.get(
            "sha256_matches",
            False,
        )
    )

    exact_column_order = bool(
        summary.get(
            "exact_column_order",
            False,
        )
    )

    candidate_rows = int(
        summary.get(
            "candidate_rows",
            0,
        )
    )

    unique_securities = int(
        summary.get(
            "unique_securities",
            0,
        )
    )

    if status != "SUCCESS":

        raise RuntimeError(
            "MPD-012 status is not SUCCESS."
        )

    if promotion_decision != "PASS":

        raise RuntimeError(
            "MPD-012 promotion decision is not PASS."
        )

    if critical_issues != 0:

        raise RuntimeError(
            "MPD-012 contains critical issues."
        )

    if not sha256_matches:

        raise RuntimeError(
            "MPD-012 candidate SHA256 validation failed."
        )

    if not exact_column_order:

        raise RuntimeError(
            "MPD-012 canonical schema/order validation failed."
        )

    if candidate_rows <= 0:

        raise RuntimeError(
            "MPD-012 candidate row count is zero."
        )

    if unique_securities <= 0:

        raise RuntimeError(
            "MPD-012 security count is zero."
        )

    return summary


# ============================================================
# LOAD AND RECHECK CANDIDATE
# ============================================================

def load_candidate() -> pd.DataFrame:

    dataframe = pd.read_csv(
        CANDIDATE_FILE,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(
            column
        )
        for column in dataframe.columns
    ]

    if list(
        dataframe.columns
    ) != CANONICAL_COLUMNS:

        raise RuntimeError(
            "Candidate schema or column order changed after MPD-012."
        )

    dataframe[
        "trade_date"
    ] = pd.to_datetime(
        dataframe[
            "trade_date"
        ],
        errors="coerce",
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

    return dataframe


# ============================================================
# FINAL PRE-PROMOTION VALIDATION
# ============================================================

def final_candidate_check(
    dataframe: pd.DataFrame,
    mpd012: dict[str, object],
) -> dict[str, object]:

    candidate_rows = int(
        len(
            dataframe
        )
    )

    expected_rows = int(
        mpd012[
            "candidate_rows"
        ]
    )

    unique_securities = int(
        dataframe[
            "security_id"
        ]
        .nunique()
    )

    expected_securities = int(
        mpd012[
            "unique_securities"
        ]
    )

    duplicate_keys = int(
        dataframe.duplicated(
            subset=[
                "trade_date",
                "security_id",
            ],
            keep=False,
        ).sum()
    )

    invalid_dates = int(
        dataframe[
            "trade_date"
        ]
        .isna()
        .sum()
    )

    blank_security_ids = int(
        dataframe[
            "security_id"
        ]
        .eq("")
        .sum()
    )

    blank_symbols = int(
        dataframe[
            "symbol"
        ]
        .eq("")
        .sum()
    )

    row_count_matches = (
        candidate_rows
        == expected_rows
    )

    security_count_matches = (
        unique_securities
        == expected_securities
    )

    critical_issues = (
        duplicate_keys
        + invalid_dates
        + blank_security_ids
        + blank_symbols
    )

    if not row_count_matches:
        critical_issues += 1

    if not security_count_matches:
        critical_issues += 1

    return {
        "candidate_rows":
            candidate_rows,

        "expected_rows":
            expected_rows,

        "unique_securities":
            unique_securities,

        "expected_securities":
            expected_securities,

        "row_count_matches":
            row_count_matches,

        "security_count_matches":
            security_count_matches,

        "duplicate_keys":
            duplicate_keys,

        "invalid_dates":
            invalid_dates,

        "blank_security_ids":
            blank_security_ids,

        "blank_symbols":
            blank_symbols,

        "critical_issues":
            critical_issues,
    }


# ============================================================
# BACKUP LIVE DATABASE
# ============================================================

def backup_live_database() -> dict[str, object]:

    if not LIVE_DATABASE_FILE.exists():

        return {
            "live_database_existed":
                False,

            "backup_created":
                False,

            "backup_file":
                "",

            "live_pre_promotion_sha256":
                "",
        }

    timestamp = (
        timestamp_for_filename()
    )

    backup_file = (
        BACKUP_ROOT
        / (
            "AQSD_Market_Price_Database_PRE_MPD013_"
            + timestamp
            + ".csv"
        )
    )

    pre_hash = (
        file_sha256(
            LIVE_DATABASE_FILE
        )
    )

    shutil.copy2(
        LIVE_DATABASE_FILE,
        backup_file,
    )

    backup_hash = (
        file_sha256(
            backup_file
        )
    )

    if backup_hash != pre_hash:

        try:
            backup_file.unlink()
        except OSError:
            pass

        raise RuntimeError(
            "Backup verification failed. "
            "Live database will not be modified."
        )

    return {
        "live_database_existed":
            True,

        "backup_created":
            True,

        "backup_file":
            str(
                backup_file
            ),

        "live_pre_promotion_sha256":
            pre_hash,
    }


# ============================================================
# WRITE TEMPORARY PROMOTION FILE
# ============================================================

def prepare_temporary_file(
    expected_candidate_hash: str,
) -> str:

    if TEMP_PROMOTION_FILE.exists():

        TEMP_PROMOTION_FILE.unlink()

    shutil.copy2(
        CANDIDATE_FILE,
        TEMP_PROMOTION_FILE,
    )

    temporary_hash = (
        file_sha256(
            TEMP_PROMOTION_FILE
        )
    )

    if (
        temporary_hash
        != expected_candidate_hash
    ):

        try:
            TEMP_PROMOTION_FILE.unlink()
        except OSError:
            pass

        raise RuntimeError(
            "Temporary promotion file SHA256 mismatch."
        )

    return temporary_hash


# ============================================================
# ROLLBACK
# ============================================================

def rollback_database(
    *,
    backup_file: str,
    live_database_existed: bool,
) -> bool:

    try:

        if live_database_existed:

            if not backup_file:

                return False

            backup_path = Path(
                backup_file
            )

            if not backup_path.exists():

                return False

            shutil.copy2(
                backup_path,
                LIVE_DATABASE_FILE,
            )

            return True

        if LIVE_DATABASE_FILE.exists():

            LIVE_DATABASE_FILE.unlink()

        return True

    except Exception:

        return False


# ============================================================
# PROMOTION
# ============================================================

def promote_candidate(
    candidate_sha256: str,
    backup: dict[str, object],
) -> dict[str, object]:

    rollback_required = False
    rollback_successful = False

    temporary_sha256 = ""

    live_post_promotion_sha256 = ""

    try:

        temporary_sha256 = (
            prepare_temporary_file(
                candidate_sha256
            )
        )

        # ----------------------------------------------------
        # Atomic replacement
        # ----------------------------------------------------

        os.replace(
            TEMP_PROMOTION_FILE,
            LIVE_DATABASE_FILE,
        )

        rollback_required = True

        # ----------------------------------------------------
        # Verify promoted live file
        # ----------------------------------------------------

        if not LIVE_DATABASE_FILE.exists():

            raise RuntimeError(
                "Live database missing after promotion."
            )

        live_post_promotion_sha256 = (
            file_sha256(
                LIVE_DATABASE_FILE
            )
        )

        if (
            live_post_promotion_sha256
            != candidate_sha256
        ):

            raise RuntimeError(
                "Post-promotion live database SHA256 mismatch."
            )

        rollback_required = False

        return {
            "promoted":
                True,

            "temporary_sha256":
                temporary_sha256,

            "live_post_promotion_sha256":
                live_post_promotion_sha256,

            "rollback_required":
                False,

            "rollback_successful":
                False,
        }

    except Exception:

        if rollback_required:

            rollback_successful = (
                rollback_database(
                    backup_file=safe_text(
                        backup.get(
                            "backup_file",
                            "",
                        )
                    ),
                    live_database_existed=bool(
                        backup.get(
                            "live_database_existed",
                            False,
                        )
                    ),
                )
            )

        raise

    finally:

        if TEMP_PROMOTION_FILE.exists():

            try:
                TEMP_PROMOTION_FILE.unlink()
            except OSError:
                pass


# ============================================================
# VERIFY PROMOTED DATABASE CONTENT
# ============================================================

def verify_promoted_database(
    mpd012: dict[str, object],
) -> dict[str, object]:

    if not LIVE_DATABASE_FILE.exists():

        raise RuntimeError(
            "Live Market Price Database does not exist "
            "after promotion."
        )

    dataframe = pd.read_csv(
        LIVE_DATABASE_FILE,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(
            column
        )
        for column in dataframe.columns
    ]

    rows = int(
        len(
            dataframe
        )
    )

    unique_securities = int(
        dataframe[
            "security_id"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .nunique()
    )

    expected_rows = int(
        mpd012[
            "candidate_rows"
        ]
    )

    expected_securities = int(
        mpd012[
            "unique_securities"
        ]
    )

    schema_matches = (
        list(
            dataframe.columns
        )
        == CANONICAL_COLUMNS
    )

    row_count_matches = (
        rows
        == expected_rows
    )

    security_count_matches = (
        unique_securities
        == expected_securities
    )

    critical_issues = 0

    if not schema_matches:
        critical_issues += 1

    if not row_count_matches:
        critical_issues += 1

    if not security_count_matches:
        critical_issues += 1

    return {
        "live_rows":
            rows,

        "expected_rows":
            expected_rows,

        "live_unique_securities":
            unique_securities,

        "expected_securities":
            expected_securities,

        "schema_matches":
            schema_matches,

        "row_count_matches":
            row_count_matches,

        "security_count_matches":
            security_count_matches,

        "critical_issues":
            critical_issues,
    }


# ============================================================
# RUN PROMOTION GATE
# ============================================================

def run_promotion_gate() -> dict[str, object]:

    ensure_directories()

    validate_inputs()

    mpd012 = (
        validate_mpd012()
    )

    candidate = (
        load_candidate()
    )

    final_check = (
        final_candidate_check(
            candidate,
            mpd012,
        )
    )

    if (
        final_check[
            "critical_issues"
        ]
        != 0
    ):

        raise RuntimeError(
            "Final pre-promotion candidate validation failed."
        )

    # --------------------------------------------------------
    # Candidate hash re-check
    # --------------------------------------------------------

    expected_candidate_hash = safe_text(
        mpd012.get(
            "actual_sha256",
            "",
        )
    )

    if not expected_candidate_hash:

        raise RuntimeError(
            "MPD-012 actual SHA256 is blank."
        )

    current_candidate_hash = (
        file_sha256(
            CANDIDATE_FILE
        )
    )

    candidate_hash_matches = (
        current_candidate_hash
        == expected_candidate_hash
    )

    if not candidate_hash_matches:

        raise RuntimeError(
            "Candidate file changed after MPD-012 validation."
        )

    print()

    separator()

    print(
        "AQSD CANONICAL MARKET PRICE PROMOTION GATE"
    )

    separator()

    print(
        f"Module                         : {MODULE_ID}"
    )

    print(
        f"Version                        : {MODULE_VERSION}"
    )

    print(
        f"MPD-012 Status                 : "
        f"{mpd012.get('status')}"
    )

    print(
        f"MPD-012 Promotion Decision     : "
        f"{mpd012.get('promotion_decision')}"
    )

    print(
        f"Candidate Hash Recheck         : "
        f"{candidate_hash_matches}"
    )

    sub_separator()

    print(
        f"Candidate Rows                 : "
        f"{final_check['candidate_rows']:,}"
    )

    print(
        f"Candidate Securities           : "
        f"{final_check['unique_securities']:,}"
    )

    print(
        f"Final Pre-Promotion Issues     : "
        f"{final_check['critical_issues']:,}"
    )

    sub_separator()

    # --------------------------------------------------------
    # Backup
    # --------------------------------------------------------

    backup = (
        backup_live_database()
    )

    print(
        f"Live Database Existed          : "
        f"{backup['live_database_existed']}"
    )

    print(
        f"Backup Created                 : "
        f"{backup['backup_created']}"
    )

    if backup[
        "backup_file"
    ]:

        print(
            f"Backup File                    : "
            f"{backup['backup_file']}"
        )

    sub_separator()

    # --------------------------------------------------------
    # Promote
    # --------------------------------------------------------

    promotion = (
        promote_candidate(
            current_candidate_hash,
            backup,
        )
    )

    # --------------------------------------------------------
    # Content verification
    # --------------------------------------------------------

    verification = (
        verify_promoted_database(
            mpd012
        )
    )

    if (
        verification[
            "critical_issues"
        ]
        != 0
    ):

        rollback_successful = (
            rollback_database(
                backup_file=safe_text(
                    backup.get(
                        "backup_file",
                        "",
                    )
                ),
                live_database_existed=bool(
                    backup.get(
                        "live_database_existed",
                        False,
                    )
                ),
            )
        )

        raise RuntimeError(
            "Post-promotion database validation failed. "
            f"Rollback successful={rollback_successful}"
        )

    live_sha256 = (
        file_sha256(
            LIVE_DATABASE_FILE
        )
    )

    hashes_match = (
        live_sha256
        == current_candidate_hash
    )

    if not hashes_match:

        rollback_successful = (
            rollback_database(
                backup_file=safe_text(
                    backup.get(
                        "backup_file",
                        "",
                    )
                ),
                live_database_existed=bool(
                    backup.get(
                        "live_database_existed",
                        False,
                    )
                ),
            )
        )

        raise RuntimeError(
            "Final promoted database SHA256 mismatch. "
            f"Rollback successful={rollback_successful}"
        )

    # --------------------------------------------------------
    # Final summary
    # --------------------------------------------------------

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

        "mpd012_status":
            mpd012.get(
                "status"
            ),

        "mpd012_promotion_decision":
            mpd012.get(
                "promotion_decision"
            ),

        "candidate_file":
            str(
                CANDIDATE_FILE
            ),

        "candidate_sha256":
            current_candidate_hash,

        "candidate_hash_matches_mpd012":
            candidate_hash_matches,

        **final_check,

        "live_database_existed_before":
            backup[
                "live_database_existed"
            ],

        "backup_created":
            backup[
                "backup_created"
            ],

        "backup_file":
            backup[
                "backup_file"
            ],

        "live_pre_promotion_sha256":
            backup[
                "live_pre_promotion_sha256"
            ],

        "temporary_sha256":
            promotion[
                "temporary_sha256"
            ],

        "live_database_file":
            str(
                LIVE_DATABASE_FILE
            ),

        "live_post_promotion_sha256":
            live_sha256,

        "promoted_hash_matches_candidate":
            hashes_match,

        "live_rows":
            verification[
                "live_rows"
            ],

        "live_unique_securities":
            verification[
                "live_unique_securities"
            ],

        "live_schema_matches":
            verification[
                "schema_matches"
            ],

        "live_row_count_matches":
            verification[
                "row_count_matches"
            ],

        "live_security_count_matches":
            verification[
                "security_count_matches"
            ],

        "rollback_required":
            False,

        "rollback_successful":
            False,

        "candidate_modified":
            False,

        "processed_dataset_modified":
            False,

        "raw_data_modified":
            False,

        "security_master_modified":
            False,

        "market_price_database_modified":
            True,

        "frozen_historical_database_modified":
            False,

        "historical_fabrication":
            False,

        "promotion_status":
            "PROMOTED",

        "status":
            "SUCCESS",
    }

    # --------------------------------------------------------
    # Audit
    # --------------------------------------------------------

    audit = pd.DataFrame(
        [
            {
                "module_id":
                    MODULE_ID,

                "module_version":
                    MODULE_VERSION,

                "candidate_rows":
                    summary[
                        "candidate_rows"
                    ],

                "candidate_securities":
                    summary[
                        "unique_securities"
                    ],

                "backup_created":
                    summary[
                        "backup_created"
                    ],

                "candidate_sha256":
                    summary[
                        "candidate_sha256"
                    ],

                "live_sha256":
                    summary[
                        "live_post_promotion_sha256"
                    ],

                "hash_match":
                    summary[
                        "promoted_hash_matches_candidate"
                    ],

                "promotion_status":
                    summary[
                        "promotion_status"
                    ],

                "status":
                    summary[
                        "status"
                    ],
            }
        ]
    )

    audit.to_csv(
        PROMOTION_AUDIT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    PROMOTION_SUMMARY_FILE.write_text(
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
        "AQSD CANONICAL MARKET PRICE PROMOTION SUMMARY"
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

    print(
        f"MPD-012 Status                 : "
        f"{summary['mpd012_status']}"
    )

    print(
        f"MPD-012 Promotion Decision     : "
        f"{summary['mpd012_promotion_decision']}"
    )

    sub_separator()

    print(
        f"Candidate Rows                 : "
        f"{int(summary['candidate_rows']):,}"
    )

    print(
        f"Candidate Securities           : "
        f"{int(summary['unique_securities']):,}"
    )

    print(
        f"Candidate Hash Matches MPD-012 : "
        f"{summary['candidate_hash_matches_mpd012']}"
    )

    sub_separator()

    print(
        f"Live Database Existed Before   : "
        f"{summary['live_database_existed_before']}"
    )

    print(
        f"Backup Created                 : "
        f"{summary['backup_created']}"
    )

    if summary[
        "backup_file"
    ]:

        print(
            f"Backup File                    : "
            f"{summary['backup_file']}"
        )

    sub_separator()

    print(
        f"Live Rows                      : "
        f"{int(summary['live_rows']):,}"
    )

    print(
        f"Live Unique Securities         : "
        f"{int(summary['live_unique_securities']):,}"
    )

    print(
        f"Live Schema Matches            : "
        f"{summary['live_schema_matches']}"
    )

    print(
        f"Live Row Count Matches         : "
        f"{summary['live_row_count_matches']}"
    )

    print(
        f"Live Security Count Matches    : "
        f"{summary['live_security_count_matches']}"
    )

    print(
        f"Promoted Hash Matches Candidate: "
        f"{summary['promoted_hash_matches_candidate']}"
    )

    sub_separator()

    print(
        f"Candidate SHA256               : "
        f"{summary['candidate_sha256']}"
    )

    print(
        f"Live SHA256                    : "
        f"{summary['live_post_promotion_sha256']}"
    )

    sub_separator()

    print(
        "Raw Data                       : READ ONLY"
    )

    print(
        "Processed Dataset              : READ ONLY"
    )

    print(
        "Canonical Candidate            : READ ONLY"
    )

    print(
        "Security Master                : NOT MODIFIED"
    )

    print(
        "Live Market Price Database     : MODIFIED"
    )

    print(
        "Frozen Historical Database     : NOT MODIFIED"
    )

    print(
        "Historical Fabrication         : PROHIBITED"
    )

    sub_separator()

    print(
        f"Promotion Status               : "
        f"{summary['promotion_status']}"
    )

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

        summary = (
            run_promotion_gate()
        )

        display_summary(
            summary
        )

    except Exception as exc:

        print()

        separator()

        print(
            "AQSD CANONICAL MARKET PRICE PROMOTION GATE"
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
            "Raw Data                       : NOT MODIFIED"
        )

        print(
            "Processed Dataset              : NOT MODIFIED"
        )

        print(
            "Security Master                : NOT MODIFIED"
        )

        print(
            "Historical Fabrication         : PROHIBITED"
        )

        separator()

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
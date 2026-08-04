"""
AQSD
F&O Security Master Promotion Executor

Module ID: FNO-004
Version: 1.0.0
Author: AQSD

Purpose
-------
Promote the validated F&O candidate Security Master to the live
AQSD Security Master only when FNO-003 explicitly returns PASS.

Promotion Rules
---------------
1. FNO-003 must be SUCCESS.
2. Promotion Decision must be PASS.
3. Candidate Security Master must exist.
4. Live Security Master must exist.
5. Candidate and live master must contain the same security identities.
6. Backup of the live master is mandatory.
7. Promotion uses atomic replacement.
8. Post-promotion validation is mandatory.
9. Historical securities are never deleted.
10. Market Price Database is not modified.

Expected Result
---------------
Live Security Master rows        : 249
Current F&O Members              : 213
Former F&O Members               : 36
Security IDs preserved           : True
Symbols preserved                : True
Historical securities preserved  : True
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Final

import pandas as pd


# ============================================================
# MODULE
# ============================================================

MODULE_ID: Final[str] = "FNO-004"
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

BACKUP_DIR: Final[Path] = (
    PROJECT_ROOT
    / "Backup"
    / "Security_Master"
)


# ============================================================
# INPUT FILES
# ============================================================

LIVE_SECURITY_MASTER: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Enriched.csv"
)

CANDIDATE_SECURITY_MASTER: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Security_Master_FNO_Promoted_Candidate.csv"
)

FNO003_SUMMARY: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_FNO_Candidate_Validation_Summary.json"
)


# ============================================================
# OUTPUT FILES
# ============================================================

PROMOTION_AUDIT_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_FNO_Live_Promotion_Audit.csv"
)

PROMOTION_SUMMARY_JSON: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_FNO_Live_Promotion_Summary.json"
)

POST_PROMOTION_CURRENT_MEMBERS: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_FNO_Live_Current_Members.csv"
)

POST_PROMOTION_FORMER_MEMBERS: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_FNO_Live_Former_Members.csv"
)


# ============================================================
# HELPERS
# ============================================================

def ensure_directories() -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    BACKUP_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def separator() -> None:

    print(
        "=" * 100
    )


def sub_separator() -> None:

    print(
        "-" * 100
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


def normalize_symbol(
    value: object,
) -> str:

    if pd.isna(value):
        return ""

    symbol = (
        str(value)
        .strip()
        .upper()
    )

    if symbol.startswith(
        "NSE:"
    ):
        symbol = symbol[4:]

    for suffix in (
        "-EQ",
        ".NS",
    ):

        if symbol.endswith(
            suffix
        ):
            symbol = symbol[
                : -len(suffix)
            ]

    aliases = {
        "NIFTY50":
            "NIFTY",

        "NIFTYBANK":
            "BANKNIFTY",

        "NIFTYNEXT50":
            "NIFTYNXT50",
    }

    return aliases.get(
        symbol,
        symbol,
    )


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


def load_json(
    path: Path,
) -> dict[str, object]:

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def load_csv(
    path: Path,
) -> pd.DataFrame:

    dataframe = pd.read_csv(
        path,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(
            column
        )
        for column in dataframe.columns
    ]

    if "security_id" in dataframe.columns:

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

    if "symbol" in dataframe.columns:

        dataframe[
            "symbol"
        ] = (
            dataframe[
                "symbol"
            ]
            .map(
                normalize_symbol
            )
        )

    return dataframe


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_input_files() -> None:

    required_files = [
        LIVE_SECURITY_MASTER,
        CANDIDATE_SECURITY_MASTER,
        FNO003_SUMMARY,
    ]

    missing = [
        path
        for path in required_files
        if not path.exists()
    ]

    if missing:

        raise FileNotFoundError(
            "Required FNO-004 files missing: "
            + ", ".join(
                str(path)
                for path in missing
            )
        )


# ============================================================
# VALIDATE FNO-003
# ============================================================

def validate_fno003() -> dict[str, object]:

    summary = load_json(
        FNO003_SUMMARY
    )

    status = str(
        summary.get(
            "status",
            "",
        )
    ).strip().upper()

    decision = str(
        summary.get(
            "promotion_decision",
            "",
        )
    ).strip().upper()

    critical_issues = int(
        summary.get(
            "critical_issues",
            0,
        )
    )

    if status != "SUCCESS":

        raise RuntimeError(
            "FNO-003 status is not SUCCESS."
        )

    if decision != "PASS":

        raise RuntimeError(
            "FNO-003 promotion decision is not PASS."
        )

    if critical_issues != 0:

        raise RuntimeError(
            "FNO-003 contains critical issues."
        )

    return summary


# ============================================================
# PRE-PROMOTION VALIDATION
# ============================================================

def validate_candidate_against_live(
    live: pd.DataFrame,
    candidate: pd.DataFrame,
) -> dict[str, object]:

    required_candidate_columns = {
        "security_id",
        "symbol",
        "current_fno_member",
        "previous_fno_member",
        "fno_membership_change",
        "fno_membership_status",
        "fno_membership_asof",
        "fno_membership_source",
        "fno_membership_module",
        "fno_membership_version",
    }

    missing_columns = (
        required_candidate_columns
        - set(
            candidate.columns
        )
    )

    live_rows = int(
        len(
            live
        )
    )

    candidate_rows = int(
        len(
            candidate
        )
    )

    row_count_preserved = (
        live_rows
        == candidate_rows
    )

    live_ids = set(
        live[
            "security_id"
        ]
    )

    candidate_ids = set(
        candidate[
            "security_id"
        ]
    )

    security_ids_preserved = (
        live_ids
        == candidate_ids
    )

    live_symbols = set(
        live[
            "symbol"
        ]
    )

    candidate_symbols = set(
        candidate[
            "symbol"
        ]
    )

    symbols_preserved = (
        live_symbols
        == candidate_symbols
    )

    duplicate_security_ids = int(
        candidate.duplicated(
            subset=[
                "security_id",
            ],
            keep=False,
        ).sum()
    )

    duplicate_symbols = int(
        candidate.duplicated(
            subset=[
                "symbol",
            ],
            keep=False,
        ).sum()
    )

    blank_security_ids = int(
        candidate[
            "security_id"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    blank_symbols = int(
        candidate[
            "symbol"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    current_fno_members = int(
        candidate[
            "current_fno_member"
        ]
        .map(
            parse_bool
        )
        .sum()
    )

    former_fno_members = int(
        candidate[
            "fno_membership_change"
        ]
        .eq(
            "EXCLUDED_FROM_CURRENT_FNO"
        )
        .sum()
    )

    critical_issues = 0

    if missing_columns:
        critical_issues += 1

    if not row_count_preserved:
        critical_issues += 1

    if not security_ids_preserved:
        critical_issues += 1

    if not symbols_preserved:
        critical_issues += 1

    critical_issues += (
        duplicate_security_ids
        + duplicate_symbols
        + blank_security_ids
        + blank_symbols
    )

    return {
        "missing_columns":
            sorted(
                missing_columns
            ),

        "live_rows":
            live_rows,

        "candidate_rows":
            candidate_rows,

        "row_count_preserved":
            row_count_preserved,

        "security_ids_preserved":
            security_ids_preserved,

        "symbols_preserved":
            symbols_preserved,

        "duplicate_security_ids":
            duplicate_security_ids,

        "duplicate_symbols":
            duplicate_symbols,

        "blank_security_ids":
            blank_security_ids,

        "blank_symbols":
            blank_symbols,

        "current_fno_members":
            current_fno_members,

        "former_fno_members":
            former_fno_members,

        "critical_issues":
            critical_issues,
    }


# ============================================================
# BACKUP
# ============================================================

def create_live_backup() -> Path:

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
            "AQSD_Security_Master_Enriched_"
            f"PRE_FNO004_{timestamp}.csv"
        )
    )

    shutil.copy2(
        LIVE_SECURITY_MASTER,
        backup_file,
    )

    if not backup_file.exists():

        raise RuntimeError(
            "Security Master backup was not created."
        )

    source_hash = file_sha256(
        LIVE_SECURITY_MASTER
    )

    backup_hash = file_sha256(
        backup_file
    )

    if source_hash != backup_hash:

        raise RuntimeError(
            "Security Master backup hash mismatch."
        )

    return backup_file


# ============================================================
# ATOMIC PROMOTION
# ============================================================

def atomic_promote_candidate() -> None:

    temp_file: Path | None = None

    try:

        with tempfile.NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=str(
                LIVE_SECURITY_MASTER.parent
            ),
            prefix="AQSD_Security_Master_PROMOTION_",
            suffix=".tmp",
        ) as handle:

            temp_file = Path(
                handle.name
            )

            with CANDIDATE_SECURITY_MASTER.open(
                "rb"
            ) as source:

                shutil.copyfileobj(
                    source,
                    handle,
                )

        candidate_hash = file_sha256(
            CANDIDATE_SECURITY_MASTER
        )

        temp_hash = file_sha256(
            temp_file
        )

        if candidate_hash != temp_hash:

            raise RuntimeError(
                "Temporary promotion file hash mismatch."
            )

        temp_file.replace(
            LIVE_SECURITY_MASTER
        )

    finally:

        if (
            temp_file is not None
            and temp_file.exists()
        ):

            temp_file.unlink(
                missing_ok=True
            )


# ============================================================
# POST PROMOTION VALIDATION
# ============================================================

def validate_promoted_live(
    candidate: pd.DataFrame,
) -> dict[str, object]:

    promoted = load_csv(
        LIVE_SECURITY_MASTER
    )

    promoted_rows = int(
        len(
            promoted
        )
    )

    candidate_rows = int(
        len(
            candidate
        )
    )

    row_count_matches = (
        promoted_rows
        == candidate_rows
    )

    promoted_ids = set(
        promoted[
            "security_id"
        ]
    )

    candidate_ids = set(
        candidate[
            "security_id"
        ]
    )

    security_ids_match = (
        promoted_ids
        == candidate_ids
    )

    promoted_symbols = set(
        promoted[
            "symbol"
        ]
    )

    candidate_symbols = set(
        candidate[
            "symbol"
        ]
    )

    symbols_match = (
        promoted_symbols
        == candidate_symbols
    )

    candidate_hash = file_sha256(
        CANDIDATE_SECURITY_MASTER
    )

    promoted_hash = file_sha256(
        LIVE_SECURITY_MASTER
    )

    file_exact_match = (
        candidate_hash
        == promoted_hash
    )

    current_fno_members = int(
        promoted[
            "current_fno_member"
        ]
        .map(
            parse_bool
        )
        .sum()
    )

    former_fno_members = int(
        promoted[
            "fno_membership_change"
        ]
        .eq(
            "EXCLUDED_FROM_CURRENT_FNO"
        )
        .sum()
    )

    duplicate_security_ids = int(
        promoted.duplicated(
            subset=[
                "security_id",
            ],
            keep=False,
        ).sum()
    )

    duplicate_symbols = int(
        promoted.duplicated(
            subset=[
                "symbol",
            ],
            keep=False,
        ).sum()
    )

    critical_issues = 0

    if not row_count_matches:
        critical_issues += 1

    if not security_ids_match:
        critical_issues += 1

    if not symbols_match:
        critical_issues += 1

    if not file_exact_match:
        critical_issues += 1

    critical_issues += (
        duplicate_security_ids
        + duplicate_symbols
    )

    return {
        "promoted_rows":
            promoted_rows,

        "row_count_matches":
            row_count_matches,

        "security_ids_match":
            security_ids_match,

        "symbols_match":
            symbols_match,

        "file_exact_match":
            file_exact_match,

        "current_fno_members":
            current_fno_members,

        "former_fno_members":
            former_fno_members,

        "duplicate_security_ids":
            duplicate_security_ids,

        "duplicate_symbols":
            duplicate_symbols,

        "critical_issues":
            critical_issues,

        "promoted_dataframe":
            promoted,
    }


# ============================================================
# ROLLBACK
# ============================================================

def rollback_from_backup(
    backup_file: Path,
) -> None:

    shutil.copy2(
        backup_file,
        LIVE_SECURITY_MASTER,
    )

    if (
        file_sha256(
            backup_file
        )
        != file_sha256(
            LIVE_SECURITY_MASTER
        )
    ):

        raise RuntimeError(
            "Rollback failed: restored master hash mismatch."
        )


# ============================================================
# WRITE OUTPUTS
# ============================================================

def write_outputs(
    promoted: pd.DataFrame,
    summary: dict[str, object],
) -> None:

    promoted[
        promoted[
            "current_fno_member"
        ]
        .map(
            parse_bool
        )
    ].to_csv(
        POST_PROMOTION_CURRENT_MEMBERS,
        index=False,
        encoding="utf-8-sig",
    )

    promoted[
        promoted[
            "fno_membership_change"
        ]
        .eq(
            "EXCLUDED_FROM_CURRENT_FNO"
        )
    ].to_csv(
        POST_PROMOTION_FORMER_MEMBERS,
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(
        [summary]
    ).to_csv(
        PROMOTION_AUDIT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    PROMOTION_SUMMARY_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ============================================================
# RUN EXECUTOR
# ============================================================

def run_executor() -> dict[str, object]:

    ensure_directories()

    validate_input_files()

    validation_summary = (
        validate_fno003()
    )

    live_before = load_csv(
        LIVE_SECURITY_MASTER
    )

    candidate = load_csv(
        CANDIDATE_SECURITY_MASTER
    )

    pre_validation = (
        validate_candidate_against_live(
            live_before,
            candidate,
        )
    )

    if (
        pre_validation[
            "critical_issues"
        ]
        != 0
    ):

        raise RuntimeError(
            "Pre-promotion candidate validation failed."
        )

    live_hash_before = file_sha256(
        LIVE_SECURITY_MASTER
    )

    candidate_hash = file_sha256(
        CANDIDATE_SECURITY_MASTER
    )

    backup_file = create_live_backup()

    promotion_started_at = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    try:

        atomic_promote_candidate()

        post_validation = (
            validate_promoted_live(
                candidate
            )
        )

        if (
            post_validation[
                "critical_issues"
            ]
            != 0
        ):

            rollback_from_backup(
                backup_file
            )

            raise RuntimeError(
                "Post-promotion validation failed. "
                "Rollback completed."
            )

    except Exception:

        if (
            file_sha256(
                LIVE_SECURITY_MASTER
            )
            != live_hash_before
        ):

            rollback_from_backup(
                backup_file
            )

        raise

    promotion_completed_at = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    live_hash_after = file_sha256(
        LIVE_SECURITY_MASTER
    )

    promoted = post_validation[
        "promoted_dataframe"
    ]

    summary = {
        "module_id":
            MODULE_ID,

        "module_version":
            MODULE_VERSION,

        "generated_at":
            promotion_completed_at,

        "fno003_status":
            validation_summary.get(
                "status"
            ),

        "fno003_promotion_decision":
            validation_summary.get(
                "promotion_decision"
            ),

        "promotion_started_at":
            promotion_started_at,

        "promotion_completed_at":
            promotion_completed_at,

        "backup_file":
            str(
                backup_file
            ),

        "live_master_sha256_before":
            live_hash_before,

        "candidate_sha256":
            candidate_hash,

        "live_master_sha256_after":
            live_hash_after,

        "live_rows_before":
            pre_validation[
                "live_rows"
            ],

        "candidate_rows":
            pre_validation[
                "candidate_rows"
            ],

        "promoted_rows":
            post_validation[
                "promoted_rows"
            ],

        "current_fno_members":
            post_validation[
                "current_fno_members"
            ],

        "former_fno_members":
            post_validation[
                "former_fno_members"
            ],

        "row_count_matches":
            post_validation[
                "row_count_matches"
            ],

        "security_ids_match":
            post_validation[
                "security_ids_match"
            ],

        "symbols_match":
            post_validation[
                "symbols_match"
            ],

        "file_exact_match":
            post_validation[
                "file_exact_match"
            ],

        "duplicate_security_ids":
            post_validation[
                "duplicate_security_ids"
            ],

        "duplicate_symbols":
            post_validation[
                "duplicate_symbols"
            ],

        "critical_issues":
            post_validation[
                "critical_issues"
            ],

        "backup_created":
            True,

        "rollback_required":
            False,

        "market_price_database_modified":
            False,

        "historical_database_modified":
            False,

        "promotion_status":
            "PROMOTED",

        "status":
            "SUCCESS",
    }

    write_outputs(
        promoted,
        summary,
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
        "AQSD F&O SECURITY MASTER PROMOTION EXECUTOR"
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
        f"FNO-003 Status                 : "
        f"{summary['fno003_status']}"
    )

    print(
        f"FNO-003 Promotion Decision     : "
        f"{summary['fno003_promotion_decision']}"
    )

    sub_separator()

    print(
        f"Live Master Rows Before        : "
        f"{int(summary['live_rows_before']):,}"
    )

    print(
        f"Candidate Rows                 : "
        f"{int(summary['candidate_rows']):,}"
    )

    print(
        f"Promoted Live Rows             : "
        f"{int(summary['promoted_rows']):,}"
    )

    sub_separator()

    print(
        f"Current F&O Members            : "
        f"{int(summary['current_fno_members']):,}"
    )

    print(
        f"Former F&O Members             : "
        f"{int(summary['former_fno_members']):,}"
    )

    sub_separator()

    print(
        f"Row Count Matches              : "
        f"{summary['row_count_matches']}"
    )

    print(
        f"Security IDs Match             : "
        f"{summary['security_ids_match']}"
    )

    print(
        f"Symbols Match                  : "
        f"{summary['symbols_match']}"
    )

    print(
        f"File Exact Match               : "
        f"{summary['file_exact_match']}"
    )

    print(
        f"Duplicate Security IDs         : "
        f"{int(summary['duplicate_security_ids']):,}"
    )

    print(
        f"Duplicate Symbols              : "
        f"{int(summary['duplicate_symbols']):,}"
    )

    print(
        f"Critical Issues                : "
        f"{int(summary['critical_issues']):,}"
    )

    sub_separator()

    print(
        f"Backup Created                 : "
        f"{summary['backup_created']}"
    )

    print(
        f"Backup File                    : "
        f"{summary['backup_file']}"
    )

    print(
        f"Rollback Required              : "
        f"{summary['rollback_required']}"
    )

    sub_separator()

    print(
        "Market Price Database          : NOT MODIFIED"
    )

    print(
        "Historical Database            : NOT MODIFIED"
    )

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

        summary = run_executor()

        display_summary(
            summary
        )

    except Exception as exc:

        print()
        separator()

        print(
            "AQSD F&O SECURITY MASTER PROMOTION EXECUTOR"
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
            "Historical Database            : NOT MODIFIED"
        )

        print(
            "Promotion Status               : NOT COMPLETED"
        )

        separator()

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
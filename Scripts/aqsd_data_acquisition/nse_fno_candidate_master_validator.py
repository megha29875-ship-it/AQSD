"""
AQSD
F&O Candidate Master Validator

Module ID: FNO-003
Version: 1.0.0
Author: AQSD

Purpose
-------
Independently validate the candidate Security Master produced by FNO-002
before any promotion is allowed.

Validation Objectives
---------------------
1. Candidate Security Master exists.
2. Source Security Master remains unchanged.
3. Candidate row count equals source row count.
4. Security IDs are preserved.
5. Symbols are preserved.
6. No duplicate Security IDs.
7. No duplicate symbols.
8. No blank Security IDs.
9. No blank symbols.
10. Current F&O membership exactly matches official FNO-001 universe.
11. Current F&O members count is correct.
12. Former F&O members are preserved.
13. No excluded security has been deleted.
14. No new current F&O symbol is missing from the candidate.
15. Candidate contains valid F&O membership metadata.
16. Promotion decision is PASS or BLOCK.

Protection
----------
Source Security Master      : READ ONLY
Candidate Security Master   : READ ONLY
Market Price Database       : NOT MODIFIED
Historical Database         : NOT MODIFIED
Automatic Promotion         : PROHIBITED
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Final

import pandas as pd


# ============================================================
# MODULE
# ============================================================

MODULE_ID: Final[str] = "FNO-003"
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


# ============================================================
# INPUT FILES
# ============================================================

SOURCE_SECURITY_MASTER: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Enriched.csv"
)

CANDIDATE_SECURITY_MASTER: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Security_Master_FNO_Promoted_Candidate.csv"
)

CURRENT_FNO_UNIVERSE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Current_NSE_FNO_Universe.csv"
)

FORMER_FNO_MEMBERS: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_FNO_Former_Members.csv"
)

FNO001_SUMMARY: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Current_NSE_FNO_Universe_Summary.json"
)

FNO002_SUMMARY: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_FNO_Promotion_Summary.json"
)


# ============================================================
# OUTPUT FILES
# ============================================================

VALIDATION_AUDIT_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_FNO_Candidate_Validation_Audit.csv"
)

VALIDATION_ISSUES_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_FNO_Candidate_Validation_Issues.csv"
)

MEMBERSHIP_MISMATCH_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_FNO_Candidate_Membership_Mismatches.csv"
)

VALIDATION_SUMMARY_JSON: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_FNO_Candidate_Validation_Summary.json"
)


# ============================================================
# HELPERS
# ============================================================

def ensure_output_directory() -> None:

    OUTPUT_DIR.mkdir(
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

    if symbol.startswith("NSE:"):
        symbol = symbol[4:]

    for suffix in (
        "-EQ",
        ".NS",
    ):

        if symbol.endswith(suffix):
            symbol = symbol[:-len(suffix)]

    aliases = {
        "NIFTY50": "NIFTY",
        "NIFTYBANK": "BANKNIFTY",
        "NIFTYNEXT50": "NIFTYNXT50",
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

    with path.open("rb") as handle:

        while True:

            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def separator() -> None:

    print("=" * 100)


def sub_separator() -> None:

    print("-" * 100)


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_input_files() -> None:

    required_files = [
        SOURCE_SECURITY_MASTER,
        CANDIDATE_SECURITY_MASTER,
        CURRENT_FNO_UNIVERSE,
        FNO001_SUMMARY,
        FNO002_SUMMARY,
    ]

    missing = [
        path
        for path in required_files
        if not path.exists()
    ]

    if missing:

        raise FileNotFoundError(
            "Missing required FNO-003 input files: "
            + ", ".join(
                str(path)
                for path in missing
            )
        )


# ============================================================
# LOADERS
# ============================================================

def load_csv(
    path: Path,
) -> pd.DataFrame:

    dataframe = pd.read_csv(
        path,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(column)
        for column in dataframe.columns
    ]

    if "symbol" in dataframe.columns:

        dataframe["symbol"] = (
            dataframe["symbol"]
            .map(
                normalize_symbol
            )
        )

    if "security_id" in dataframe.columns:

        dataframe["security_id"] = (
            dataframe["security_id"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

    return dataframe


def load_json(
    path: Path,
) -> dict[str, object]:

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


# ============================================================
# PRIOR MODULE VALIDATION
# ============================================================

def validate_prior_modules(
    fno001: dict[str, object],
    fno002: dict[str, object],
) -> None:

    if (
        str(
            fno001.get(
                "status",
                "",
            )
        ).upper()
        != "SUCCESS"
    ):

        raise RuntimeError(
            "FNO-001 is not SUCCESS."
        )

    if not bool(
        fno001.get(
            "reconciliation_ok",
            False,
        )
    ):

        raise RuntimeError(
            "FNO-001 reconciliation failed."
        )

    if int(
        fno001.get(
            "critical_issues",
            0,
        )
    ) != 0:

        raise RuntimeError(
            "FNO-001 contains critical issues."
        )

    if (
        str(
            fno002.get(
                "status",
                "",
            )
        ).upper()
        != "SUCCESS"
    ):

        raise RuntimeError(
            "FNO-002 is not SUCCESS."
        )

    if (
        str(
            fno002.get(
                "promotion_status",
                "",
            )
        ).upper()
        != "CANDIDATE_ONLY"
    ):

        raise RuntimeError(
            "FNO-002 candidate is not in CANDIDATE_ONLY state."
        )

    if int(
        fno002.get(
            "critical_issues",
            0,
        )
    ) != 0:

        raise RuntimeError(
            "FNO-002 contains critical issues."
        )


# ============================================================
# STRUCTURAL VALIDATION
# ============================================================

def validate_structure(
    source: pd.DataFrame,
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

    missing_candidate_columns = (
        required_candidate_columns
        - set(
            candidate.columns
        )
    )

    duplicate_security_ids = int(
        candidate.duplicated(
            subset=["security_id"],
            keep=False,
        ).sum()
    )

    duplicate_symbols = int(
        candidate.duplicated(
            subset=["symbol"],
            keep=False,
        ).sum()
    )

    blank_security_ids = int(
        candidate["security_id"]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    blank_symbols = int(
        candidate["symbol"]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    source_rows = int(
        len(source)
    )

    candidate_rows = int(
        len(candidate)
    )

    row_count_preserved = (
        source_rows
        == candidate_rows
    )

    source_ids = set(
        source["security_id"]
    )

    candidate_ids = set(
        candidate["security_id"]
    )

    security_ids_preserved = (
        source_ids
        == candidate_ids
    )

    source_symbols = set(
        source["symbol"]
    )

    candidate_symbols = set(
        candidate["symbol"]
    )

    symbols_preserved = (
        source_symbols
        == candidate_symbols
    )

    return {
        "missing_candidate_columns":
            sorted(
                missing_candidate_columns
            ),

        "duplicate_security_ids":
            duplicate_security_ids,

        "duplicate_symbols":
            duplicate_symbols,

        "blank_security_ids":
            blank_security_ids,

        "blank_symbols":
            blank_symbols,

        "source_rows":
            source_rows,

        "candidate_rows":
            candidate_rows,

        "row_count_preserved":
            row_count_preserved,

        "security_ids_preserved":
            security_ids_preserved,

        "symbols_preserved":
            symbols_preserved,
    }


# ============================================================
# MEMBERSHIP VALIDATION
# ============================================================

def validate_membership(
    candidate: pd.DataFrame,
    current_universe: pd.DataFrame,
) -> tuple[
    dict[str, object],
    pd.DataFrame,
]:

    official_symbols = set(
        current_universe["symbol"]
    )

    candidate_current = candidate[
        candidate[
            "current_fno_member"
        ].map(
            parse_bool
        )
    ].copy()

    candidate_current_symbols = set(
        candidate_current[
            "symbol"
        ]
    )

    missing_current_symbols = (
        official_symbols
        - candidate_current_symbols
    )

    extra_current_symbols = (
        candidate_current_symbols
        - official_symbols
    )

    mismatch_rows: list[
        dict[str, object]
    ] = []

    for symbol in sorted(
        missing_current_symbols
    ):

        mismatch_rows.append(
            {
                "symbol":
                    symbol,

                "issue_type":
                    "OFFICIAL_CURRENT_MISSING_FROM_CANDIDATE_CURRENT",
            }
        )

    for symbol in sorted(
        extra_current_symbols
    ):

        mismatch_rows.append(
            {
                "symbol":
                    symbol,

                "issue_type":
                    "CANDIDATE_CURRENT_NOT_IN_OFFICIAL_CURRENT",
            }
        )

    mismatches = pd.DataFrame(
        mismatch_rows
    )

    membership_exact_match = (
        not missing_current_symbols
        and not extra_current_symbols
    )

    return (
        {
            "official_current_members":
                int(
                    len(
                        official_symbols
                    )
                ),

            "candidate_current_members":
                int(
                    len(
                        candidate_current_symbols
                    )
                ),

            "missing_current_symbols":
                int(
                    len(
                        missing_current_symbols
                    )
                ),

            "extra_current_symbols":
                int(
                    len(
                        extra_current_symbols
                    )
                ),

            "membership_exact_match":
                membership_exact_match,
        },

        mismatches,
    )


# ============================================================
# FORMER MEMBER VALIDATION
# ============================================================

def validate_former_members(
    source: pd.DataFrame,
    candidate: pd.DataFrame,
) -> dict[str, object]:

    if "is_fno" in source.columns:

        previous_mask = (
            source["is_fno"]
            .map(
                parse_bool
            )
        )

    elif "fno_flag" in source.columns:

        previous_mask = (
            source["fno_flag"]
            .map(
                parse_bool
            )
        )

    else:

        previous_mask = pd.Series(
            False,
            index=source.index,
        )

    previous_fno_symbols = set(
        source.loc[
            previous_mask,
            "symbol",
        ]
    )

    current_mask = (
        candidate[
            "current_fno_member"
        ]
        .map(
            parse_bool
        )
    )

    current_fno_symbols = set(
        candidate.loc[
            current_mask,
            "symbol",
        ]
    )

    expected_former_symbols = (
        previous_fno_symbols
        - current_fno_symbols
    )

    actual_former_symbols = set(
        candidate.loc[
            candidate[
                "fno_membership_change"
            ].eq(
                "EXCLUDED_FROM_CURRENT_FNO"
            ),
            "symbol",
        ]
    )

    former_match = (
        expected_former_symbols
        == actual_former_symbols
    )

    all_former_preserved = (
        expected_former_symbols
        <= set(
            candidate["symbol"]
        )
    )

    return {
        "previous_fno_members":
            int(
                len(
                    previous_fno_symbols
                )
            ),

        "expected_former_members":
            int(
                len(
                    expected_former_symbols
                )
            ),

        "actual_former_members":
            int(
                len(
                    actual_former_symbols
                )
            ),

        "former_members_match":
            former_match,

        "all_former_members_preserved":
            all_former_preserved,
    }


# ============================================================
# METADATA VALIDATION
# ============================================================

def validate_metadata(
    candidate: pd.DataFrame,
) -> dict[str, int]:

    required_metadata_columns = [
        "fno_membership_status",
        "fno_membership_asof",
        "fno_membership_source",
        "fno_membership_module",
        "fno_membership_version",
    ]

    blank_metadata = 0

    for column in required_metadata_columns:

        if column not in candidate.columns:
            blank_metadata += len(
                candidate
            )
            continue

        blank_metadata += int(
            candidate[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .eq("")
            .sum()
        )

    invalid_status = int(
        (
            ~candidate[
                "fno_membership_status"
            ]
            .isin(
                {
                    "CURRENT_FNO",
                    "NOT_CURRENT_FNO",
                }
            )
        ).sum()
    )
    return {
        "blank_membership_metadata":
            blank_metadata,

        "invalid_membership_status":
            invalid_status,
    }


# ============================================================
# ISSUE BUILDER
# ============================================================

def build_issues(
    structure: dict[str, object],
    membership: dict[str, object],
    former: dict[str, object],
    metadata: dict[str, int],
    source_untouched: bool,
) -> pd.DataFrame:

    issues: list[
        dict[str, object]
    ] = []

    def add_issue(
        code: str,
        description: str,
    ) -> None:

        issues.append(
            {
                "issue_code":
                    code,

                "description":
                    description,
            }
        )

    if structure[
        "missing_candidate_columns"
    ]:

        add_issue(
            "MISSING_COLUMNS",
            str(
                structure[
                    "missing_candidate_columns"
                ]
            ),
        )

    if int(
        structure[
            "duplicate_security_ids"
        ]
    ) != 0:

        add_issue(
            "DUPLICATE_SECURITY_ID",
            str(
                structure[
                    "duplicate_security_ids"
                ]
            ),
        )

    if int(
        structure[
            "duplicate_symbols"
        ]
    ) != 0:

        add_issue(
            "DUPLICATE_SYMBOL",
            str(
                structure[
                    "duplicate_symbols"
                ]
            ),
        )

    if int(
        structure[
            "blank_security_ids"
        ]
    ) != 0:

        add_issue(
            "BLANK_SECURITY_ID",
            str(
                structure[
                    "blank_security_ids"
                ]
            ),
        )

    if int(
        structure[
            "blank_symbols"
        ]
    ) != 0:

        add_issue(
            "BLANK_SYMBOL",
            str(
                structure[
                    "blank_symbols"
                ]
            ),
        )

    if not bool(
        structure[
            "row_count_preserved"
        ]
    ):

        add_issue(
            "ROW_COUNT_CHANGED",
            "Source and candidate row counts differ.",
        )

    if not bool(
        structure[
            "security_ids_preserved"
        ]
    ):

        add_issue(
            "SECURITY_IDS_CHANGED",
            "Security IDs are not preserved.",
        )

    if not bool(
        structure[
            "symbols_preserved"
        ]
    ):

        add_issue(
            "SYMBOL_SET_CHANGED",
            "Candidate symbol set differs from source.",
        )

    if not bool(
        membership[
            "membership_exact_match"
        ]
    ):

        add_issue(
            "MEMBERSHIP_MISMATCH",
            (
                "Official current F&O membership does not "
                "exactly match candidate membership."
            ),
        )

    if not bool(
        former[
            "former_members_match"
        ]
    ):

        add_issue(
            "FORMER_MEMBER_MISMATCH",
            "Former F&O membership classification mismatch.",
        )

    if not bool(
        former[
            "all_former_members_preserved"
        ]
    ):

        add_issue(
            "FORMER_MEMBER_DELETED",
            "One or more former F&O members are missing.",
        )

    if int(
        metadata[
            "blank_membership_metadata"
        ]
    ) != 0:

        add_issue(
            "BLANK_MEMBERSHIP_METADATA",
            str(
                metadata[
                    "blank_membership_metadata"
                ]
            ),
        )

    if int(
        metadata[
            "invalid_membership_status"
        ]
    ) != 0:

        add_issue(
            "INVALID_MEMBERSHIP_STATUS",
            str(
                metadata[
                    "invalid_membership_status"
                ]
            ),
        )

    if not source_untouched:

        add_issue(
            "SOURCE_MASTER_MODIFIED",
            "Source Security Master changed during validation.",
        )

    return pd.DataFrame(
        issues
    )


# ============================================================
# RUN VALIDATOR
# ============================================================

def run_validator() -> dict[str, object]:

    ensure_output_directory()

    validate_input_files()

    source_hash_before = file_sha256(
        SOURCE_SECURITY_MASTER
    )

    candidate_hash_before = file_sha256(
        CANDIDATE_SECURITY_MASTER
    )

    fno001 = load_json(
        FNO001_SUMMARY
    )

    fno002 = load_json(
        FNO002_SUMMARY
    )

    validate_prior_modules(
        fno001,
        fno002,
    )

    source = load_csv(
        SOURCE_SECURITY_MASTER
    )

    candidate = load_csv(
        CANDIDATE_SECURITY_MASTER
    )

    current_universe = load_csv(
        CURRENT_FNO_UNIVERSE
    )

    structure = validate_structure(
        source,
        candidate,
    )

    (
        membership,
        membership_mismatches,
    ) = validate_membership(
        candidate,
        current_universe,
    )

    former = validate_former_members(
        source,
        candidate,
    )

    metadata = validate_metadata(
        candidate
    )

    source_hash_after = file_sha256(
        SOURCE_SECURITY_MASTER
    )

    candidate_hash_after = file_sha256(
        CANDIDATE_SECURITY_MASTER
    )

    source_untouched = (
        source_hash_before
        == source_hash_after
    )

    candidate_untouched = (
        candidate_hash_before
        == candidate_hash_after
    )

    issues = build_issues(
        structure,
        membership,
        former,
        metadata,
        source_untouched,
    )

    critical_issues = int(
        len(
            issues
        )
    )

    promotion_decision = (
        "PASS"
        if critical_issues == 0
        else "BLOCK"
    )

    status = (
        "SUCCESS"
        if promotion_decision == "PASS"
        else "FAILED"
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

        "source_rows":
            int(
                structure[
                    "source_rows"
                ]
            ),

        "candidate_rows":
            int(
                structure[
                    "candidate_rows"
                ]
            ),

        "row_count_preserved":
            bool(
                structure[
                    "row_count_preserved"
                ]
            ),

        "security_ids_preserved":
            bool(
                structure[
                    "security_ids_preserved"
                ]
            ),

        "symbols_preserved":
            bool(
                structure[
                    "symbols_preserved"
                ]
            ),

        "duplicate_security_ids":
            int(
                structure[
                    "duplicate_security_ids"
                ]
            ),

        "duplicate_symbols":
            int(
                structure[
                    "duplicate_symbols"
                ]
            ),

        "blank_security_ids":
            int(
                structure[
                    "blank_security_ids"
                ]
            ),

        "blank_symbols":
            int(
                structure[
                    "blank_symbols"
                ]
            ),

        "official_current_fno_members":
            int(
                membership[
                    "official_current_members"
                ]
            ),

        "candidate_current_fno_members":
            int(
                membership[
                    "candidate_current_members"
                ]
            ),

        "missing_current_symbols":
            int(
                membership[
                    "missing_current_symbols"
                ]
            ),

        "extra_current_symbols":
            int(
                membership[
                    "extra_current_symbols"
                ]
            ),

        "membership_exact_match":
            bool(
                membership[
                    "membership_exact_match"
                ]
            ),

        "previous_fno_members":
            int(
                former[
                    "previous_fno_members"
                ]
            ),

        "expected_former_members":
            int(
                former[
                    "expected_former_members"
                ]
            ),

        "actual_former_members":
            int(
                former[
                    "actual_former_members"
                ]
            ),

        "former_members_match":
            bool(
                former[
                    "former_members_match"
                ]
            ),

        "all_former_members_preserved":
            bool(
                former[
                    "all_former_members_preserved"
                ]
            ),

        "blank_membership_metadata":
            int(
                metadata[
                    "blank_membership_metadata"
                ]
            ),

        "invalid_membership_status":
            int(
                metadata[
                    "invalid_membership_status"
                ]
            ),

        "source_master_untouched":
            source_untouched,

        "candidate_master_untouched":
            candidate_untouched,

        "critical_issues":
            critical_issues,

        "promotion_decision":
            promotion_decision,

        "source_security_master_modified":
            False,

        "candidate_security_master_modified":
            False,

        "market_price_database_modified":
            False,

        "historical_database_modified":
            False,

        "automatic_promotion":
            False,

        "status":
            status,
    }

    audit = pd.DataFrame(
        [summary]
    )

    audit.to_csv(
        VALIDATION_AUDIT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    issues.to_csv(
        VALIDATION_ISSUES_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    membership_mismatches.to_csv(
        MEMBERSHIP_MISMATCH_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    VALIDATION_SUMMARY_JSON.write_text(
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
        "AQSD F&O CANDIDATE MASTER VALIDATOR"
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
        f"Source Rows                    : "
        f"{int(summary['source_rows']):,}"
    )

    print(
        f"Candidate Rows                 : "
        f"{int(summary['candidate_rows']):,}"
    )

    print(
        f"Row Count Preserved            : "
        f"{summary['row_count_preserved']}"
    )

    print(
        f"Security IDs Preserved         : "
        f"{summary['security_ids_preserved']}"
    )

    print(
        f"Symbols Preserved              : "
        f"{summary['symbols_preserved']}"
    )

    sub_separator()

    print(
        f"Official Current F&O Members   : "
        f"{int(summary['official_current_fno_members']):,}"
    )

    print(
        f"Candidate Current F&O Members  : "
        f"{int(summary['candidate_current_fno_members']):,}"
    )

    print(
        f"Missing Current Symbols        : "
        f"{int(summary['missing_current_symbols']):,}"
    )

    print(
        f"Extra Current Symbols          : "
        f"{int(summary['extra_current_symbols']):,}"
    )

    print(
        f"Membership Exact Match         : "
        f"{summary['membership_exact_match']}"
    )

    sub_separator()

    print(
        f"Previous F&O Members           : "
        f"{int(summary['previous_fno_members']):,}"
    )

    print(
        f"Expected Former Members        : "
        f"{int(summary['expected_former_members']):,}"
    )

    print(
        f"Actual Former Members          : "
        f"{int(summary['actual_former_members']):,}"
    )

    print(
        f"Former Members Match           : "
        f"{summary['former_members_match']}"
    )

    print(
        f"All Former Members Preserved   : "
        f"{summary['all_former_members_preserved']}"
    )

    sub_separator()

    print(
        f"Duplicate Security IDs         : "
        f"{int(summary['duplicate_security_ids']):,}"
    )

    print(
        f"Duplicate Symbols              : "
        f"{int(summary['duplicate_symbols']):,}"
    )

    print(
        f"Blank Security IDs             : "
        f"{int(summary['blank_security_ids']):,}"
    )

    print(
        f"Blank Symbols                  : "
        f"{int(summary['blank_symbols']):,}"
    )

    print(
        f"Blank Membership Metadata      : "
        f"{int(summary['blank_membership_metadata']):,}"
    )

    print(
        f"Invalid Membership Status      : "
        f"{int(summary['invalid_membership_status']):,}"
    )

    sub_separator()

    print(
        f"Source Master Untouched        : "
        f"{summary['source_master_untouched']}"
    )

    print(
        f"Candidate Master Untouched     : "
        f"{summary['candidate_master_untouched']}"
    )

    print(
        f"Critical Issues                : "
        f"{int(summary['critical_issues']):,}"
    )

    sub_separator()

    print(
        f"Promotion Decision             : "
        f"{summary['promotion_decision']}"
    )

    print(
        "Automatic Promotion            : PROHIBITED"
    )

    print(
        "Market Price Database          : NOT MODIFIED"
    )

    print(
        "Historical Database            : NOT MODIFIED"
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

        summary = run_validator()

        display_summary(
            summary
        )

    except Exception as exc:

        print()
        separator()

        print(
            "AQSD F&O CANDIDATE MASTER VALIDATOR"
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
            "Source Security Master         : NOT MODIFIED"
        )

        print(
            "Candidate Security Master      : NOT MODIFIED"
        )

        print(
            "Automatic Promotion            : PROHIBITED"
        )

        separator()

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
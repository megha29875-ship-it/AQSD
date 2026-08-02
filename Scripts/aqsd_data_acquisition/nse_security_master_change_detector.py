"""
AQSD
NSE Security Master Change Detector

Module : SMD-005
Version: 1.0.0
Author : AQSD

Purpose
-------
Compare the current AQSD Security Master universe with the latest
derived/enriched Security Master and identify structural changes.

This module is READ ONLY.

It detects:
- new securities
- removed securities
- symbol changes
- F&O flag changes
- security type changes
- instrument class changes
- AQSD scope changes

It does NOT:
- modify the frozen historical database
- modify the Security Master
- rebuild historical data
- fabricate missing metadata
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd


# ============================================================
# MODULE CONFIGURATION
# ============================================================

MODULE_ID = "SMD-005"
MODULE_VERSION = "1.0.0"

PROJECT_ROOT = Path(__file__).resolve().parents[2]

OUTPUT_DIR = PROJECT_ROOT / "Output"

BASELINE_CSV = (
    PROJECT_ROOT
    / "Data"
    / "Security_Master"
    / "AQSD_Security_Master_Baseline.csv"
)

CURRENT_CSV = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Enriched.csv"
)

CHANGE_REPORT_CSV = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Changes.csv"
)

CHANGE_REPORT_JSON = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Changes.json"
)

SUMMARY_JSON = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Change_Summary.json"
)


# ============================================================
# COMPARISON FIELDS
# ============================================================

COMPARISON_FIELDS = [
    "symbol",
    "fno_flag",
    "security_type",
    "instrument_class",
    "is_index",
    "is_stock",
    "is_fno",
    "aqsd_scope",
]


# ============================================================
# HELPERS
# ============================================================

def normalize_column_name(
    value: object,
) -> str:
    return str(value).strip().lower()


def normalize_text(
    value: object,
) -> str:

    if pd.isna(value):
        return ""

    return str(value).strip().upper()


def load_csv(
    path: Path,
) -> pd.DataFrame:

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found: {path}"
        )

    dataframe = pd.read_csv(
        path,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(column)
        for column in dataframe.columns
    ]

    return dataframe


def validate_required_columns(
    dataframe: pd.DataFrame,
    *,
    label: str,
) -> None:

    required = {
        "security_id",
        "symbol",
    }

    missing = sorted(
        required
        - set(dataframe.columns)
    )

    if missing:
        raise RuntimeError(
            f"{label} missing required columns: "
            + ", ".join(missing)
        )


def normalize_dataframe(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:

    normalized = dataframe.copy()

    for column in normalized.columns:
        if normalized[column].dtype == object:
            normalized[column] = (
                normalized[column]
                .fillna("")
                .astype(str)
                .str.strip()
            )

    normalized["security_id"] = (
        normalized["security_id"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    normalized["symbol"] = (
        normalized["symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    return normalized


# ============================================================
# CHANGE DETECTION
# ============================================================

def detect_changes(
    baseline: pd.DataFrame,
    current: pd.DataFrame,
) -> list[dict[str, object]]:

    baseline = normalize_dataframe(
        baseline
    )

    current = normalize_dataframe(
        current
    )

    baseline_map = {
        str(row["security_id"]): row
        for _, row in baseline.iterrows()
    }

    current_map = {
        str(row["security_id"]): row
        for _, row in current.iterrows()
    }

    baseline_ids = set(
        baseline_map.keys()
    )

    current_ids = set(
        current_map.keys()
    )

    changes: list[dict[str, object]] = []

    # --------------------------------------------------------
    # NEW SECURITIES
    # --------------------------------------------------------

    for security_id in sorted(
        current_ids - baseline_ids
    ):

        row = current_map[
            security_id
        ]

        changes.append(
            {
                "change_type": "NEW_SECURITY",
                "security_id": security_id,
                "symbol": normalize_text(
                    row.get(
                        "symbol",
                        "",
                    )
                ),
                "field": "",
                "old_value": "",
                "new_value": normalize_text(
                    row.get(
                        "symbol",
                        "",
                    )
                ),
                "severity": "INFO",
            }
        )

    # --------------------------------------------------------
    # REMOVED SECURITIES
    # --------------------------------------------------------

    for security_id in sorted(
        baseline_ids - current_ids
    ):

        row = baseline_map[
            security_id
        ]

        changes.append(
            {
                "change_type": "REMOVED_SECURITY",
                "security_id": security_id,
                "symbol": normalize_text(
                    row.get(
                        "symbol",
                        "",
                    )
                ),
                "field": "",
                "old_value": normalize_text(
                    row.get(
                        "symbol",
                        "",
                    )
                ),
                "new_value": "",
                "severity": "WARNING",
            }
        )

    # --------------------------------------------------------
    # EXISTING SECURITY CHANGES
    # --------------------------------------------------------

    common_ids = sorted(
        baseline_ids
        & current_ids
    )

    for security_id in common_ids:

        old_row = baseline_map[
            security_id
        ]

        new_row = current_map[
            security_id
        ]

        for field in COMPARISON_FIELDS:

            if (
                field not in baseline.columns
                or field not in current.columns
            ):
                continue

            old_value = normalize_text(
                old_row.get(
                    field,
                    "",
                )
            )

            new_value = normalize_text(
                new_row.get(
                    field,
                    "",
                )
            )

            if old_value == new_value:
                continue

            if field == "symbol":
                change_type = "SYMBOL_CHANGE"
                severity = "WARNING"

            elif field in {
                "fno_flag",
                "is_fno",
            }:
                change_type = "FNO_STATUS_CHANGE"
                severity = "WARNING"

            elif field == "security_type":
                change_type = "SECURITY_TYPE_CHANGE"
                severity = "WARNING"

            elif field == "instrument_class":
                change_type = "INSTRUMENT_CLASS_CHANGE"
                severity = "WARNING"

            elif field == "aqsd_scope":
                change_type = "AQSD_SCOPE_CHANGE"
                severity = "INFO"

            else:
                change_type = "FIELD_CHANGE"
                severity = "INFO"

            changes.append(
                {
                    "change_type":
                        change_type,
                    "security_id":
                        security_id,
                    "symbol":
                        normalize_text(
                            new_row.get(
                                "symbol",
                                "",
                            )
                        ),
                    "field":
                        field,
                    "old_value":
                        old_value,
                    "new_value":
                        new_value,
                    "severity":
                        severity,
                }
            )

    return changes


# ============================================================
# OUTPUT
# ============================================================

def write_change_outputs(
    changes: list[dict[str, object]],
) -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    columns = [
        "change_type",
        "security_id",
        "symbol",
        "field",
        "old_value",
        "new_value",
        "severity",
    ]

    dataframe = pd.DataFrame(
        changes,
        columns=columns,
    )

    dataframe.to_csv(
        CHANGE_REPORT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    CHANGE_REPORT_JSON.write_text(
        json.dumps(
            changes,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def build_summary(
    changes: list[dict[str, object]],
    baseline_rows: int,
    current_rows: int,
) -> dict[str, object]:

    new_count = sum(
        1
        for row in changes
        if row["change_type"]
        == "NEW_SECURITY"
    )

    removed_count = sum(
        1
        for row in changes
        if row["change_type"]
        == "REMOVED_SECURITY"
    )

    symbol_change_count = sum(
        1
        for row in changes
        if row["change_type"]
        == "SYMBOL_CHANGE"
    )

    fno_status_change_count = sum(
        1
        for row in changes
        if row["change_type"]
        == "FNO_STATUS_CHANGE"
    )

    structural_change_count = sum(
        1
        for row in changes
        if row["change_type"]
        in {
            "SECURITY_TYPE_CHANGE",
            "INSTRUMENT_CLASS_CHANGE",
        }
    )

    total_changes = len(
        changes
    )

    status = (
        "NO CHANGE"
        if total_changes == 0
        else "CHANGES DETECTED"
    )

    return {
        "module_id":
            MODULE_ID,
        "module_version":
            MODULE_VERSION,
        "generated_at":
            datetime.now().astimezone().isoformat(
                timespec="seconds"
            ),
        "baseline_file":
            str(
                BASELINE_CSV
            ),
        "current_file":
            str(
                CURRENT_CSV
            ),
        "baseline_rows":
            baseline_rows,
        "current_rows":
            current_rows,
        "new_securities":
            new_count,
        "removed_securities":
            removed_count,
        "symbol_changes":
            symbol_change_count,
        "fno_status_changes":
            fno_status_change_count,
        "structural_changes":
            structural_change_count,
        "total_changes":
            total_changes,
        "historical_database_modified":
            False,
        "security_master_modified":
            False,
        "status":
            status,
    }


def save_summary(
    summary: dict[str, object],
) -> None:

    SUMMARY_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ============================================================
# DISPLAY
# ============================================================

def display_summary(
    summary: dict[str, object],
) -> None:

    print()
    print("=" * 80)
    print("AQSD SECURITY MASTER CHANGE DETECTOR")
    print("=" * 80)

    print(
        f"Module                    : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                   : "
        f"{MODULE_VERSION}"
    )

    print("-" * 80)

    print(
        f"Baseline Rows             : "
        f"{summary['baseline_rows']:,}"
    )

    print(
        f"Current Rows              : "
        f"{summary['current_rows']:,}"
    )

    print(
        f"New Securities            : "
        f"{summary['new_securities']}"
    )

    print(
        f"Removed Securities        : "
        f"{summary['removed_securities']}"
    )

    print(
        f"Symbol Changes            : "
        f"{summary['symbol_changes']}"
    )

    print(
        f"F&O Status Changes        : "
        f"{summary['fno_status_changes']}"
    )

    print(
        f"Structural Changes        : "
        f"{summary['structural_changes']}"
    )

    print(
        f"Total Changes             : "
        f"{summary['total_changes']}"
    )

    print("-" * 80)

    print(
        "Historical Database       : READ ONLY / UNTOUCHED"
    )

    print(
        "Security Master           : READ ONLY / UNCHANGED"
    )

    print(
        f"Change CSV                : "
        f"{CHANGE_REPORT_CSV}"
    )

    print(
        f"Change JSON               : "
        f"{CHANGE_REPORT_JSON}"
    )

    print("-" * 80)

    print(
        f"Status                    : "
        f"{summary['status']}"
    )

    print("=" * 80)


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    baseline = load_csv(
        BASELINE_CSV
    )

    current = load_csv(
        CURRENT_CSV
    )

    validate_required_columns(
        baseline,
        label="Baseline Security Master",
    )

    validate_required_columns(
        current,
        label="Current Security Master",
    )

    changes = detect_changes(
        baseline,
        current,
    )

    write_change_outputs(
        changes
    )

    summary = build_summary(
        changes,
        baseline_rows=len(
            baseline
        ),
        current_rows=len(
            current
        ),
    )

    save_summary(
        summary
    )

    display_summary(
        summary
    )


if __name__ == "__main__":
    main()
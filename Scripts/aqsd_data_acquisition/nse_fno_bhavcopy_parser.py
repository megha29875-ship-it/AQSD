"""
AQSD
NSE F&O Bhavcopy Parser

Module : NFP-001
Version: 1.2.0
Author : AQSD

Purpose
-------
Parse official NSE UDiFF F&O bhavcopy ZIP files downloaded by
NHF-001 and normalize them into a clean AQSD historical
derivatives dataset.

Input
-----
D:/AQSD_DATA/Raw/NSE/Derivatives/YYYY-MM-DD/
    BhavCopy_NSE_FO_0_0_0_YYYYMMDD_F_0000.csv.zip

Output
------
D:/AQSD_DATA/Processed/NSE/Derivatives/YYYY-MM-DD/
    fno_contracts.csv
    futures.csv
    options.csv
    parser_manifest.json

Important
---------
This parser uses the ACTUAL columns present in NSE UDiFF files.

It does not assume old bhavcopy column names.

It does not modify raw NSE files.

It does not fabricate missing data.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from typing import Final

import pandas as pd

from Scripts.aqsd_core.paths import (
    NSE_DERIVATIVES_PROCESSED_DIR,
    NSE_DERIVATIVES_RAW_DIR,
    OUTPUT_DIR,
    PROJECT_ROOT,
    ensure_aqsd_directories,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "NFP-001"
MODULE_VERSION: Final[str] = "1.2.0"

RAW_ROOT: Final[Path] = (
    NSE_DERIVATIVES_RAW_DIR
)

PROCESSED_ROOT: Final[Path] = (
    NSE_DERIVATIVES_PROCESSED_DIR
)


AUDIT_FILE: Final[Path] = (
    OUTPUT_DIR
    / "NSE_FNO_Bhavcopy_Parser_Audit.csv"
)

SUMMARY_FILE: Final[Path] = (
    OUTPUT_DIR
    / "NSE_FNO_Bhavcopy_Parser_Summary.json"
)

DEFAULT_SESSIONS: Final[int] = 3

TRADING_CALENDAR_FILE: Final[Path] = (
    PROJECT_ROOT
    / "Data"
    / "NSE_Trading_Calendar.csv"
)


# ==========================================================
# GENERAL HELPERS
# ==========================================================

def parse_date(
    value: str,
) -> date:
    """
    Parse YYYY-MM-DD.
    """

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    except ValueError as exc:
        raise ValueError(
            "Invalid date format. Use YYYY-MM-DD."
        ) from exc


def ensure_directories() -> None:
    """
    Create AQSD central data/output directories.

    Storage architecture:
        C: project / code / reports
        D: primary market data
        E: backup
    """

    ensure_aqsd_directories()

    RAW_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    PROCESSED_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )


def normalize_column_name(
    value: object,
) -> str:
    """
    Convert one source column to AQSD-safe normalized form.
    """

    text = str(
        value
    ).strip()

    text = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        text,
    )

    text = re.sub(
        r"_+",
        "_",
        text,
    )

    return text.strip(
        "_"
    ).lower()


def clean_text(
    value: object,
) -> str:
    """
    Normalize source text.
    """

    if pd.isna(
        value
    ):
        return ""

    return str(
        value
    ).strip()


# ==========================================================
# RAW FILE DISCOVERY
# ==========================================================

def raw_date_directory(
    trade_date: date,
) -> Path:
    """
    Return raw NSE derivative directory.
    """

    return (
        RAW_ROOT
        / trade_date.isoformat()
    )


def processed_date_directory(
    trade_date: date,
) -> Path:
    """
    Return processed derivative directory.
    """

    return (
        PROCESSED_ROOT
        / trade_date.isoformat()
    )


def find_bhavcopy_zip(
    trade_date: date,
) -> Path:
    """
    Locate UDiFF F&O bhavcopy ZIP for one date.
    """

    directory = raw_date_directory(
        trade_date
    )

    if not directory.exists():
        raise FileNotFoundError(
            "Raw NSE directory not found:\n"
            f"{directory}"
        )

    candidates = sorted(
        directory.glob(
            "BhavCopy_NSE_FO_*.csv.zip"
        )
    )

    if not candidates:
        raise FileNotFoundError(
            "NSE F&O UDiFF bhavcopy ZIP not found for "
            f"{trade_date.isoformat()}."
        )

    if len(
        candidates
    ) > 1:
        exact_text = trade_date.strftime(
            "%Y%m%d"
        )

        exact_candidates = [
            path
            for path in candidates
            if exact_text in path.name
        ]

        if exact_candidates:
            return exact_candidates[0]

    return candidates[0]


# ==========================================================
# ZIP READER
# ==========================================================

def read_udiff_zip(
    zip_path: Path,
) -> tuple[
    pd.DataFrame,
    str,
]:
    """
    Read CSV contained inside NSE UDiFF ZIP.
    """

    if not zipfile.is_zipfile(
        zip_path
    ):
        raise RuntimeError(
            "Downloaded NSE bhavcopy is not a valid ZIP:\n"
            f"{zip_path}"
        )

    with zipfile.ZipFile(
        zip_path,
        "r",
    ) as archive:

        members = [
            name
            for name in archive.namelist()
            if name.lower().endswith(
                ".csv"
            )
        ]

        if not members:
            raise RuntimeError(
                "No CSV file found inside NSE bhavcopy ZIP."
            )

        csv_member = members[0]

        with archive.open(
            csv_member
        ) as handle:

            frame = pd.read_csv(
                handle,
                low_memory=False,
            )

    if frame.empty:
        raise RuntimeError(
            "NSE UDiFF bhavcopy CSV is empty."
        )

    return (
        frame,
        csv_member,
    )


# ==========================================================
# COLUMN DISCOVERY
# ==========================================================

def normalize_columns(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """
    Normalize actual NSE source column names.
    """

    working = frame.copy()

    working.columns = [
        normalize_column_name(
            column
        )
        for column in working.columns
    ]

    return working


def find_column(
    frame: pd.DataFrame,
    candidates: tuple[str, ...],
) -> str | None:
    """
    Find first existing column from candidate names.
    """

    available = set(
        frame.columns
    )

    for candidate in candidates:
        normalized = normalize_column_name(
            candidate
        )

        if normalized in available:
            return normalized

    return None


# ==========================================================
# CANONICAL FIELD MAP
# ==========================================================

CANONICAL_CANDIDATES: Final[
    dict[str, tuple[str, ...]]
] = {
    "trade_date": (
        "TradDt",
        "trade_date",
        "trad_dt",
        "trade_dt",
        "date",
    ),

    "segment": (
        "Sgmt",
        "segment",
        "sgmnt",
        "market_segment",
    ),

    "source": (
        "Src",
        "source",
        "src",
    ),

    "instrument": (
        "FinInstrmTp",
        "fin_instrm_tp",
        "instrument",
        "instrument_type",
        "fin_instrument_type",
    ),

    "underlying": (
        "TckrSymb",
        "ticker_symbol",
        "ticker_symb",
        "underlying",
        "underlying_symbol",
        "symbol",
    ),

    "symbol": (
        "TckrSymb",
        "ticker_symbol",
        "ticker_symb",
        "symbol",
        "security_symbol",
        "tradingsymbol",
    ),

    "expiry": (
        "XpryDt",
        "FinInstrmActlXpryDt",
        "expiry",
        "expiry_date",
    ),

    "strike": (
        "StrkPric",
        "strike",
        "strike_price",
    ),

    "option_type": (
        "OptnTp",
        "option_type",
        "opt_type",
        "option_typ",
    ),

    "open": (
        "OpnPric",
        "open",
        "open_price",
    ),

    "high": (
        "HghPric",
        "high",
        "high_price",
    ),

    "low": (
        "LwPric",
        "low",
        "low_price",
    ),

    "close": (
        "ClsPric",
        "close",
        "close_price",
    ),

    "last_price": (
        "LastPric",
        "last_price",
        "last_pric",
        "lst_pric",
    ),

    "settle_price": (
        "SttlmPric",
        "settle_price",
        "settlement_price",
    ),

    "volume": (
        "TtlTradgVol",
        "volume",
        "total_trading_volume",
        "contracts",
        "contracts_traded",
    ),

    "turnover": (
        "TtlTrfVal",
        "turnover",
        "traded_value",
        "turnover_rs_lacs",
    ),

    "open_interest": (
        "OpnIntrst",
        "open_interest",
        "open_int",
        "oi",
    ),

    "change_in_oi": (
        "ChngInOpnIntrst",
        "change_in_oi",
        "change_open_interest",
        "change_in_open_interest",
    ),
}



# ==========================================================
# CANONICALIZATION
# ==========================================================

def build_canonical_frame(
    *,
    raw_frame: pd.DataFrame,
    trade_date: date,
) -> tuple[
    pd.DataFrame,
    dict[str, str | None],
]:
    """
    Build normalized AQSD derivatives dataset from actual UDiFF columns.
    """

    frame = normalize_columns(
        raw_frame
    )

    resolved_columns: dict[
        str,
        str | None,
    ] = {}

    for (
        canonical_name,
        candidates,
    ) in CANONICAL_CANDIDATES.items():

        resolved_columns[
            canonical_name
        ] = find_column(
            frame,
            candidates,
        )

    result = pd.DataFrame(
        index=frame.index
    )

    result[
        "trade_date"
    ] = trade_date.isoformat()

    for canonical_name in (
        "segment",
        "source",
        "instrument",
        "underlying",
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
    ):

        source_column = resolved_columns.get(
            canonical_name
        )

        if source_column:
            result[
                canonical_name
            ] = frame[
                source_column
            ]

        else:
            result[
                canonical_name
            ] = pd.NA

    # ------------------------------------------------------
    # CLEAN TEXT FIELDS
    # ------------------------------------------------------

    for column in (
        "segment",
        "source",
        "instrument",
        "underlying",
        "symbol",
        "option_type",
    ):

        result[
            column
        ] = (
            result[
                column
            ]
            .map(
                clean_text
            )
            .astype(str)
            .str.strip()
        )

    # ------------------------------------------------------
    # EXPIRY
    # ------------------------------------------------------

    result[
        "expiry"
    ] = pd.to_datetime(
        result[
            "expiry"
        ],
        errors="coerce",
    )

    result[
        "expiry"
    ] = result[
        "expiry"
    ].dt.date

    # ------------------------------------------------------
    # NUMERICS
    # ------------------------------------------------------

    numeric_columns = (
        "strike",
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
    )

    for column in numeric_columns:
        result[
            column
        ] = pd.to_numeric(
            result[
                column
            ],
            errors="coerce",
        )

    # ------------------------------------------------------
    # ORIGINAL ROW IDENTIFIER
    # ------------------------------------------------------

    result[
        "source_row_number"
    ] = range(
        1,
        len(
            result
        )
        + 1,
    )

    result[
        "source_provider"
    ] = "NSE"

    result[
        "source_format"
    ] = "UDIFF F&O BHAVCOPY"

    return (
        result,
        resolved_columns,
    )


# ==========================================================
# FUTURES / OPTIONS CLASSIFICATION
# ==========================================================

def classify_contract_type(
    row: pd.Series,
) -> str:
    """
    Classify NSE UDiFF derivative row as FUTURE / OPTION / OTHER.

    NSE UDiFF instrument codes observed in the official F&O bhavcopy:

        STO = Stock Option
        IDO = Index Derivative Option
        STF = Stock Future
        IDF = Index Derivative Future

    The option-type field is retained as an additional confirmation.
    Unknown instrument codes remain OTHER.
    """

    instrument = clean_text(
        row.get(
            "instrument",
            "",
        )
    ).upper()

    option_type = clean_text(
        row.get(
            "option_type",
            "",
        )
    ).upper()

    # ------------------------------------------------------
    # NSE UDiFF EXPLICIT INSTRUMENT CODES
    # ------------------------------------------------------

    if instrument in {
        "STO",
        "IDO",
    }:
        return "OPTION"

    if instrument in {
        "STF",
        "IDF",
    }:
        return "FUTURE"

    # ------------------------------------------------------
    # TEXTUAL FALLBACKS
    # ------------------------------------------------------

    if option_type in {
        "CE",
        "PE",
        "CA",
        "PA",
        "CALL",
        "PUT",
    }:
        return "OPTION"

    if (
        "OPT" in instrument
        or "OPTION" in instrument
    ):
        return "OPTION"

    if (
        "FUT" in instrument
        or "FUTURE" in instrument
    ):
        return "FUTURE"

    return "OTHER"


def add_contract_classification(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add AQSD contract type.
    """

    working = frame.copy()

    working[
        "contract_type"
    ] = working.apply(
        classify_contract_type,
        axis=1,
    )

    return working


# ==========================================================
# UNDERLYING RESOLUTION
# ==========================================================

def resolve_underlying(
    row: pd.Series,
) -> str:
    """
    Resolve best available underlying identifier.
    """

    underlying = clean_text(
        row.get(
            "underlying",
            "",
        )
    )

    symbol = clean_text(
        row.get(
            "symbol",
            "",
        )
    )

    if underlying:
        return underlying

    return symbol


def add_underlying_key(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add standardized AQSD underlying key.
    """

    working = frame.copy()

    working[
        "aqsd_underlying"
    ] = working.apply(
        resolve_underlying,
        axis=1,
    )

    return working


# ==========================================================
# VALIDATION
# ==========================================================

def validate_canonical_frame(
    frame: pd.DataFrame,
) -> dict[str, object]:
    """
    Validate parsed derivatives dataset.
    """

    total_rows = len(
        frame
    )

    futures_rows = int(
        (
            frame[
                "contract_type"
            ]
            == "FUTURE"
        ).sum()
    )

    options_rows = int(
        (
            frame[
                "contract_type"
            ]
            == "OPTION"
        ).sum()
    )

    other_rows = int(
        (
            frame[
                "contract_type"
            ]
            == "OTHER"
        ).sum()
    )

    unique_symbols = int(
        frame[
            "symbol"
        ]
        .replace(
            "",
            pd.NA,
        )
        .dropna()
        .nunique()
    )

    unique_underlyings = int(
        frame[
            "aqsd_underlying"
        ]
        .replace(
            "",
            pd.NA,
        )
        .dropna()
        .nunique()
    )

    rows_with_oi = int(
        frame[
            "open_interest"
        ]
        .notna()
        .sum()
    )

    rows_with_volume = int(
        frame[
            "volume"
        ]
        .notna()
        .sum()
    )

    return {
        "total_rows": total_rows,
        "futures_rows": futures_rows,
        "options_rows": options_rows,
        "other_rows": other_rows,
        "unique_symbols": unique_symbols,
        "unique_underlyings": unique_underlyings,
        "rows_with_oi": rows_with_oi,
        "rows_with_volume": rows_with_volume,
    }


# ==========================================================
# STORAGE
# ==========================================================

def save_processed_outputs(
    *,
    trade_date: date,
    full_frame: pd.DataFrame,
    source_zip: Path,
    source_member: str,
    source_columns: list[str],
    resolved_columns: dict[
        str,
        str | None,
    ],
    validation: dict[str, object],
    overwrite: bool,
) -> dict[str, object]:
    """
    Save normalized all-F&O, futures and options outputs.
    """

    directory = processed_date_directory(
        trade_date
    )

    directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_file = (
        directory
        / "fno_contracts.csv"
    )

    futures_file = (
        directory
        / "futures.csv"
    )

    options_file = (
        directory
        / "options.csv"
    )

    manifest_file = (
        directory
        / "parser_manifest.json"
    )

    if (
        all_file.exists()
        and futures_file.exists()
        and options_file.exists()
        and not overwrite
    ):
        return {
            "action": (
                "SKIPPED EXISTING"
            ),
            "all_file": str(
                all_file
            ),
            "futures_file": str(
                futures_file
            ),
            "options_file": str(
                options_file
            ),
        }

    futures = full_frame.loc[
        full_frame[
            "contract_type"
        ]
        == "FUTURE"
    ].copy()

    options = full_frame.loc[
        full_frame[
            "contract_type"
        ]
        == "OPTION"
    ].copy()

    full_frame.to_csv(
        all_file,
        index=False,
        encoding="utf-8-sig",
    )

    futures.to_csv(
        futures_file,
        index=False,
        encoding="utf-8-sig",
    )

    options.to_csv(
        options_file,
        index=False,
        encoding="utf-8-sig",
    )

    manifest = {
        "module_id": MODULE_ID,
        "module_version": (
            MODULE_VERSION
        ),

        "trade_date": (
            trade_date.isoformat()
        ),

        "source_zip": str(
            source_zip
        ),

        "source_csv_member": (
            source_member
        ),

        "source_columns": (
            source_columns
        ),

        "resolved_columns": (
            resolved_columns
        ),

        "validation": (
            validation
        ),

        "created_at": (
            datetime.now()
            .isoformat(
                timespec="seconds"
            )
        ),

        "outputs": {
            "fno_contracts": str(
                all_file
            ),
            "futures": str(
                futures_file
            ),
            "options": str(
                options_file
            ),
        },

        "status": "SUCCESS",
    }

    manifest_file.write_text(
        json.dumps(
            manifest,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    return {
        "action": "CREATED",
        "all_file": str(
            all_file
        ),
        "futures_file": str(
            futures_file
        ),
        "options_file": str(
            options_file
        ),
    }


# ==========================================================
# DATE DISCOVERY
# ==========================================================

def available_raw_dates() -> list[date]:
    """
    Discover date folders that contain raw NSE data.

    This function is retained for status/diagnostics only.
    It is NOT the authoritative source for parser session
    resolution.
    """

    if not RAW_ROOT.exists():
        return []

    dates: list[date] = []

    for path in RAW_ROOT.iterdir():

        if not path.is_dir():
            continue

        try:
            parsed = datetime.strptime(
                path.name,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            continue

        dates.append(
            parsed
        )

    return sorted(
        dates
    )


def load_trading_calendar() -> pd.DataFrame:
    """
    Load the AQSD authoritative NSE F&O trading calendar.

    The parser must never infer trading sessions from raw folder
    names because raw storage can legitimately contain historical
    holiday folders or other non-session artifacts.
    """

    if not TRADING_CALENDAR_FILE.exists():
        raise FileNotFoundError(
            "AQSD NSE trading calendar not found:\n"
            f"{TRADING_CALENDAR_FILE}"
        )

    frame = pd.read_csv(
        TRADING_CALENDAR_FILE,
        low_memory=False,
    )

    if "trade_date" not in frame.columns:
        raise RuntimeError(
            "AQSD NSE trading calendar is missing "
            "required column: trade_date."
        )

    frame = frame.copy()

    frame["trade_date"] = pd.to_datetime(
        frame["trade_date"],
        errors="coerce",
    )

    frame = frame.dropna(
        subset=["trade_date"]
    )

    # NTC-001 saves only valid trading sessions, but if a future
    # calendar format includes non-trading rows we still fail safe.
    if "is_trading_day" in frame.columns:

        trading_values = (
            frame["is_trading_day"]
            .astype(str)
            .str.strip()
            .str.lower()
        )

        frame = frame.loc[
            trading_values.isin(
                {
                    "true",
                    "1",
                    "yes",
                }
            )
        ].copy()

    frame = (
        frame
        .sort_values(
            "trade_date"
        )
        .drop_duplicates(
            subset=[
                "trade_date"
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    if frame.empty:
        raise RuntimeError(
            "AQSD NSE trading calendar contains no "
            "valid trading sessions."
        )

    return frame


def resolve_dates(
    *,
    sessions: int,
    end_date: date | None,
) -> list[date]:
    """
    Resolve dates to parse from the AQSD authoritative
    NSE F&O trading calendar.

    Rules
    -----
    1. Trading calendar is the authoritative session source.
    2. Raw folders are never used to decide whether a date is a
       trading session.
    3. --end-date is applied to the authoritative calendar.
    4. The final N sessions are selected from the filtered calendar.
    5. Missing raw files for a valid session remain real failures;
       AQSD does not fabricate or silently skip them.
    """

    requested_sessions = max(
        1,
        int(
            sessions
        ),
    )

    frame = load_trading_calendar()

    if end_date is not None:

        frame = frame.loc[
            frame[
                "trade_date"
            ].dt.date
            <= end_date
        ].copy()

    if frame.empty:
        raise RuntimeError(
            "No AQSD NSE trading sessions are available "
            "for the requested end date."
        )

    if len(frame) < requested_sessions:
        raise RuntimeError(
            "AQSD NSE trading calendar does not contain "
            "enough sessions for this parser request. "
            f"Requested={requested_sessions}, "
            f"Available={len(frame)}."
        )

    selected = frame.tail(
        requested_sessions
    )

    return [
        value.date()
        for value in selected[
            "trade_date"
        ]
    ]


# ==========================================================
# ENGINE
# ==========================================================

def run_parser(
    *,
    sessions: int,
    end_date: date | None,
    overwrite: bool,
) -> dict[str, object]:
    """
    Parse available NSE UDiFF F&O bhavcopies.
    """

    ensure_directories()

    target_dates = resolve_dates(
        sessions=sessions,
        end_date=end_date,
    )

    audit_rows: list[
        dict[str, object]
    ] = []

    created = 0
    skipped = 0
    failed = 0

    total_rows = 0
    total_futures = 0
    total_options = 0

    all_underlyings: set[
        str
    ] = set()

    for trade_date in target_dates:

        try:
            zip_path = find_bhavcopy_zip(
                trade_date
            )

            (
                raw_frame,
                csv_member,
            ) = read_udiff_zip(
                zip_path
            )

            source_columns = [
                str(
                    column
                )
                for column in raw_frame.columns
            ]

            (
                canonical,
                resolved_columns,
            ) = build_canonical_frame(
                raw_frame=raw_frame,
                trade_date=trade_date,
            )

            canonical = (
                add_contract_classification(
                    canonical
                )
            )

            canonical = (
                add_underlying_key(
                    canonical
                )
            )

            validation = (
                validate_canonical_frame(
                    canonical
                )
            )

            save_result = (
                save_processed_outputs(
                    trade_date=trade_date,
                    full_frame=canonical,
                    source_zip=zip_path,
                    source_member=csv_member,
                    source_columns=source_columns,
                    resolved_columns=(
                        resolved_columns
                    ),
                    validation=validation,
                    overwrite=overwrite,
                )
            )

            action = str(
                save_result[
                    "action"
                ]
            )

            if action == "CREATED":
                created += 1
            else:
                skipped += 1

            total_rows += int(
                validation[
                    "total_rows"
                ]
            )

            total_futures += int(
                validation[
                    "futures_rows"
                ]
            )

            total_options += int(
                validation[
                    "options_rows"
                ]
            )

            underlyings = (
                canonical[
                    "aqsd_underlying"
                ]
                .replace(
                    "",
                    pd.NA,
                )
                .dropna()
                .astype(str)
                .tolist()
            )

            all_underlyings.update(
                underlyings
            )

            audit_rows.append(
                {
                    "trade_date": (
                        trade_date.isoformat()
                    ),
                    "status": "SUCCESS",
                    "action": action,
                    "source_zip": str(
                        zip_path
                    ),
                    "rows": (
                        validation[
                            "total_rows"
                        ]
                    ),
                    "futures_rows": (
                        validation[
                            "futures_rows"
                        ]
                    ),
                    "options_rows": (
                        validation[
                            "options_rows"
                        ]
                    ),
                    "unique_underlyings": (
                        validation[
                            "unique_underlyings"
                        ]
                    ),
                    "rows_with_oi": (
                        validation[
                            "rows_with_oi"
                        ]
                    ),
                    "message": (
                        "NSE UDiFF bhavcopy parsed successfully."
                    ),
                }
            )

        except Exception as exc:

            failed += 1

            audit_rows.append(
                {
                    "trade_date": (
                        trade_date.isoformat()
                    ),
                    "status": "FAILED",
                    "action": "NONE",
                    "source_zip": "",
                    "rows": 0,
                    "futures_rows": 0,
                    "options_rows": 0,
                    "unique_underlyings": 0,
                    "rows_with_oi": 0,
                    "message": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    ),
                }
            )

    audit_frame = pd.DataFrame(
        audit_rows
    )

    audit_frame.to_csv(
        AUDIT_FILE,
        index=False,
        encoding="utf-8-sig",
    )

    summary = {
        "module_id": MODULE_ID,
        "module_version": (
            MODULE_VERSION
        ),

        "requested_sessions": (
            sessions
        ),

        "resolved_sessions": len(
            target_dates
        ),

        "created": created,
        "skipped_existing": skipped,
        "failed": failed,

        "total_contract_rows": (
            total_rows
        ),

        "total_futures_rows": (
            total_futures
        ),

        "total_options_rows": (
            total_options
        ),

        "unique_underlyings_across_run": len(
            all_underlyings
        ),

        "raw_root": str(
            RAW_ROOT
        ),

        "processed_root": str(
            PROCESSED_ROOT
        ),

        "trading_calendar_file": str(
            TRADING_CALENDAR_FILE
        ),

        "session_source": (
            "AQSD NSE TRADING CALENDAR"
        ),

        "audit_file": str(
            AUDIT_FILE
        ),

        "status": (
            "SUCCESS"
            if failed == 0
            else "SUCCESS WITH FAILURES"
        ),
    }

    SUMMARY_FILE.write_text(
        json.dumps(
            summary,
            indent=2,
        ),
        encoding="utf-8",
    )

    return summary


# ==========================================================
# DISPLAY
# ==========================================================

def display_summary(
    summary: dict[str, object],
) -> None:
    """
    Display parser summary.
    """

    print()
    print("=" * 100)
    print(
        "AQSD NSE F&O BHAVCOPY PARSER"
    )
    print("=" * 100)

    print(
        f"Module                    : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                   : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Trading Calendar          : "
        f"{TRADING_CALENDAR_FILE}"
    )

    print(f"Calendar Exists          : {'YES' if TRADING_CALENDAR_FILE.exists() else 'NO'}")

    print(
        f"Calendar Trading Sessions : "
        f"{len(load_trading_calendar())}"
    )

    print(
        f"Requested Sessions        : "
        f"{summary['requested_sessions']}"
    )

    print(
        f"Resolved Sessions         : "
        f"{summary['resolved_sessions']}"
    )

    print("-" * 100)

    print("PARSER RESULTS")
    print("-" * 100)

    print(
        f"Created                   : "
        f"{summary['created']}"
    )

    print(
        f"Skipped Existing          : "
        f"{summary['skipped_existing']}"
    )

    print(
        f"Failed                    : "
        f"{summary['failed']}"
    )

    print("-" * 100)

    print("CONTRACT COVERAGE")
    print("-" * 100)

    print(
        f"Total Contract Rows       : "
        f"{summary['total_contract_rows']}"
    )

    print(
        f"Futures Rows              : "
        f"{summary['total_futures_rows']}"
    )

    print(
        f"Options Rows              : "
        f"{summary['total_options_rows']}"
    )

    print(
        f"Unique Underlyings        : "
        f"{summary['unique_underlyings_across_run']}"
    )

    print("-" * 100)

    print(
        f"Raw Root                  : "
        f"{summary['raw_root']}"
    )

    print(
        f"Processed Root            : "
        f"{summary['processed_root']}"
    )

    print(
        f"Trading Calendar          : "
        f"{summary['trading_calendar_file']}"
    )

    print(
        f"Session Source            : "
        f"{summary['session_source']}"
    )

    print(
        f"Audit CSV                 : "
        f"{summary['audit_file']}"
    )

    print(
        f"Summary JSON              : "
        f"{SUMMARY_FILE}"
    )

    print("-" * 100)

    print(
        "Raw Files                 : "
        "UNCHANGED"
    )

    print(
        "Universe                  : "
        "ALL CONTRACTS FOUND IN NSE F&O UDIFF BHAVCOPY"
    )

    print(
        "Missing Columns           : "
        "LEFT AS NULL - NOT FABRICATED"
    )

    print("-" * 100)

    print(
        f"Status                    : "
        f"{summary['status']}"
    )

    print("=" * 100)


# ==========================================================
# STATUS
# ==========================================================

def show_status() -> None:
    """
    Display parser configuration.
    """

    dates = available_raw_dates()

    calendar_exists = (
        TRADING_CALENDAR_FILE.exists()
    )

    calendar_sessions = 0

    if calendar_exists:
        try:
            calendar_sessions = len(
                load_trading_calendar()
            )
        except Exception:
            calendar_sessions = 0

    print()
    print("=" * 100)
    print(
        "AQSD NSE F&O BHAVCOPY PARSER STATUS"
    )
    print("=" * 100)

    print(
        f"Module                    : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                   : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Raw Root                  : "
        f"{RAW_ROOT}"
    )

    print(
        f"Raw Root Exists           : "
        f"{'YES' if RAW_ROOT.exists() else 'NO'}"
    )

    print(
        f"Raw Trading Dates         : "
        f"{len(dates)}"
    )

    if dates:
        print(
            f"First Raw Date            : "
            f"{dates[0]}"
        )

        print(
            f"Last Raw Date             : "
            f"{dates[-1]}"
        )

    print(
        f"Processed Root            : "
        f"{PROCESSED_ROOT}"
    )

    print("=" * 100)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Parse NSE UDiFF F&O bhavcopy raw files."
        )
    )

    parser.add_argument(
        "--sessions",
        type=int,
        default=DEFAULT_SESSIONS,
    )

    parser.add_argument(
        "--end-date",
        required=False,
        help=(
            "Last permitted AQSD NSE trading session YYYY-MM-DD."
        ),
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
    )

    parser.add_argument(
        "--status",
        action="store_true",
    )

    return parser.parse_args()


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    if arguments.status:
        show_status()
        return

    end_date = (
        parse_date(
            arguments.end_date
        )
        if arguments.end_date
        else None
    )

    try:
        summary = run_parser(
            sessions=max(
                1,
                int(
                    arguments.sessions
                ),
            ),
            end_date=end_date,
            overwrite=(
                arguments.overwrite
            ),
        )

    except Exception as exc:
        print()
        print("=" * 100)
        print(
            "AQSD NSE F&O BHAVCOPY PARSER"
        )
        print("=" * 100)

        print(
            "Status : FAILED"
        )

        print(
            f"Reason : "
            f"{type(exc).__name__}: {exc}"
        )

        print("=" * 100)

        raise SystemExit(
            1
        ) from exc

    display_summary(
        summary
    )


if __name__ == "__main__":
    main()
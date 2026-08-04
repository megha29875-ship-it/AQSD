"""
AQSD
Current NSE F&O Universe Builder

Module ID: FNO-001
Version: 2.3.0
Author: AQSD

Purpose
-------
Build the CURRENT NSE F&O underlying universe from the official
NSE F&O MII contract master.

This version explicitly supports NSE MII / ISO-style field names
and rejects NSE test/dummy contracts.

Core Responsibilities
---------------------
1. Discover latest official NSE F&O MII contract master.
2. Download and decompress the file.
3. Normalize MII / ISO-style field names.
4. Identify current F&O contracts.
5. Reject NSETEST / dummy / test symbols.
6. Derive unique current underlyings.
7. Separate INDEX and STOCK underlyings.
8. Compare with AQSD Security Master.
9. Produce genuine inclusions and exclusions.
10. Reconcile previous + inclusions - exclusions = current.
11. Never automatically modify Security Master.
12. Never modify AQSD Market Price Database.

Protection
----------
Security Master          : READ ONLY
Market Price Database    : NOT MODIFIED
Automatic Promotion      : PROHIBITED
Historical Fabrication   : PROHIBITED
"""

from __future__ import annotations

import gzip
import io
import json
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Final

import pandas as pd
import requests


# ============================================================
# MODULE IDENTITY
# ============================================================

MODULE_ID: Final[str] = "FNO-001"
MODULE_VERSION: Final[str] = "2.3.0"

PRIMARY_SOURCE: Final[str] = (
    "NSE F&O MII CONTRACT MASTER"
)


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

FNO_DATA_DIR: Final[Path] = (
    DATA_DIR
    / "FNO_Universe"
)

RAW_DIR: Final[Path] = (
    FNO_DATA_DIR
    / "Raw"
)


# ============================================================
# SECURITY MASTER
# ============================================================

SECURITY_MASTER_FILE: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Security_Master_Enriched.csv"
)


# ============================================================
# OUTPUT FILES
# ============================================================

CURRENT_UNIVERSE_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Current_NSE_FNO_Universe.csv"
)

CURRENT_STOCKS_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Current_NSE_FNO_Stocks.csv"
)

CURRENT_INDICES_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Current_NSE_FNO_Indices.csv"
)

INCLUSIONS_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Current_NSE_FNO_Inclusions.csv"
)

EXCLUSIONS_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Current_NSE_FNO_Exclusions.csv"
)

UNCHANGED_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Current_NSE_FNO_Unchanged.csv"
)

FILTERED_TEST_SYMBOLS_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Current_NSE_FNO_Filtered_Test_Symbols.csv"
)

RAW_CONTRACT_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Latest_NSE_FO_Contract_Master.csv"
)

AUDIT_CSV: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Current_NSE_FNO_Universe_Audit.csv"
)

SUMMARY_JSON: Final[Path] = (
    OUTPUT_DIR
    / "AQSD_Current_NSE_FNO_Universe_Summary.json"
)


# ============================================================
# NSE ARCHIVE POLICY
# ============================================================

NSE_FO_ARCHIVE_BASE: Final[str] = (
    "https://nsearchives.nseindia.com/content/fo"
)

LOOKBACK_CALENDAR_DAYS: Final[int] = 15

REQUEST_TIMEOUT: Final[int] = 30

REQUEST_DELAY_SECONDS: Final[float] = 0.15


# ============================================================
# INDEX ALIASES
# ============================================================

INDEX_SYMBOL_ALIASES: Final[dict[str, str]] = {
    "NIFTY": "NIFTY",
    "NIFTY50": "NIFTY",

    "BANKNIFTY": "BANKNIFTY",
    "NIFTYBANK": "BANKNIFTY",

    "FINNIFTY": "FINNIFTY",

    "MIDCPNIFTY": "MIDCPNIFTY",

    "NIFTYNXT50": "NIFTYNXT50",
    "NIFTYNEXT50": "NIFTYNXT50",
}


# ============================================================
# TEST / DUMMY SYMBOL FILTERS
# ============================================================

TEST_SYMBOL_PATTERNS: Final[tuple[str, ...]] = (
    "NSETEST",
    "TEST",
    "DUMMY",
    "MOCK",
    "SIMUL",
)

TEST_SYMBOL_EXACT: Final[set[str]] = {
    "NSETEST",
    "TEST",
    "DUMMY",
}


# ============================================================
# HTTP HEADERS
# ============================================================

HTTP_HEADERS: Final[dict[str, str]] = {
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/150.0.0.0 "
        "Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


# ============================================================
# HELPERS
# ============================================================

def ensure_directories() -> None:

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    FNO_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    RAW_DIR.mkdir(
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


def safe_text(
    value: object,
) -> str:

    if pd.isna(value):
        return ""

    return str(
        value
    ).strip()


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

    if not symbol:
        return ""

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

    symbol = INDEX_SYMBOL_ALIASES.get(
        symbol,
        symbol,
    )

    return symbol


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


def is_test_symbol(
    symbol: str,
) -> bool:

    symbol = (
        str(symbol)
        .strip()
        .upper()
    )

    if not symbol:
        return True

    if symbol in TEST_SYMBOL_EXACT:
        return True

    for pattern in TEST_SYMBOL_PATTERNS:

        if pattern in symbol:
            return True

    if re.fullmatch(
        r"\d+NSETEST",
        symbol,
    ):
        return True

    return False


# ============================================================
# HTTP SESSION
# ============================================================

def create_http_session() -> requests.Session:

    session = requests.Session()

    session.headers.update(
        HTTP_HEADERS
    )

    return session


# ============================================================
# DISCOVER LATEST NSE CONTRACT MASTER
# ============================================================

def discover_contract_file_url(
    session: requests.Session,
) -> tuple[str, str, date]:

    today = date.today()

    print()
    print(
        "Searching official NSE F&O contract master..."
    )

    for offset in range(
        LOOKBACK_CALENDAR_DAYS
    ):

        candidate_date = (
            today
            - timedelta(
                days=offset
            )
        )

        filename = (
            "NSE_FO_contract_"
            + candidate_date.strftime(
                "%d%m%Y"
            )
            + ".csv.gz"
        )

        url = (
            f"{NSE_FO_ARCHIVE_BASE}/"
            f"{filename}"
        )

        print(
            f"Checking : {filename}",
            end="",
            flush=True,
        )

        try:

            response = session.get(
                url,
                timeout=REQUEST_TIMEOUT,
            )

            content = response.content

            valid_gzip = (
                response.status_code == 200
                and len(content) > 100
                and content[:2] == b"\x1f\x8b"
            )

            if valid_gzip:

                print(
                    "  FOUND"
                )

                return (
                    url,
                    filename,
                    candidate_date,
                )

            print(
                "  unavailable"
            )

        except requests.RequestException as exc:

            print(
                f"  error "
                f"({type(exc).__name__})"
            )

        time.sleep(
            REQUEST_DELAY_SECONDS
        )

    raise RuntimeError(
        "No valid NSE F&O contract master found "
        f"within last "
        f"{LOOKBACK_CALENDAR_DAYS} calendar days."
    )


# ============================================================
# DOWNLOAD / READ CONTRACT MASTER
# ============================================================

def download_contract_master(
    session: requests.Session,
    url: str,
    filename: str,
) -> pd.DataFrame:

    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    content = response.content

    if (
        len(content) < 2
        or content[:2]
        != b"\x1f\x8b"
    ):

        raise RuntimeError(
            "Downloaded NSE file is not valid gzip."
        )

    raw_file = (
        RAW_DIR
        / filename
    )

    raw_file.write_bytes(
        content
    )

    decompressed = gzip.decompress(
        content
    )

    last_error: Exception | None = None

    dataframe = pd.DataFrame()

    for encoding in (
        "utf-8",
        "utf-8-sig",
        "latin-1",
    ):

        try:

            dataframe = pd.read_csv(
                io.BytesIO(
                    decompressed
                ),
                encoding=encoding,
                low_memory=False,
            )

            if not dataframe.empty:
                break

        except Exception as exc:

            last_error = exc

    if dataframe.empty:

        raise RuntimeError(
            "Could not parse NSE contract master. "
            f"Last error: {last_error}"
        )

    dataframe.columns = [
        normalize_column_name(
            column
        )
        for column in dataframe.columns
    ]

    return dataframe


# ============================================================
# MII FIELD DISCOVERY
# ============================================================

def find_column(
    dataframe: pd.DataFrame,
    candidates: tuple[str, ...],
) -> str | None:

    columns = set(
        dataframe.columns
    )

    for candidate in candidates:

        if candidate in columns:
            return candidate

    for candidate in candidates:

        for column in dataframe.columns:

            if candidate in column:
                return column

    return None


def discover_mii_columns(
    dataframe: pd.DataFrame,
) -> dict[str, str | None]:

    return {
        "ticker_symbol":
            find_column(
                dataframe,
                (
                    "tckrsymb",
                    "ticker_symbol",
                    "symbol",
                ),
            ),

        "financial_instrument_id":
            find_column(
                dataframe,
                (
                    "fininstrmid",
                    "instrument_id",
                ),
            ),

        "financial_instrument_type":
            find_column(
                dataframe,
                (
                    "fininstrmtp",
                    "instrument_type",
                ),
            ),

        "financial_instrument_name":
            find_column(
                dataframe,
                (
                    "fininstrmnm",
                    "instrument_name",
                ),
            ),

        "expiry_date":
            find_column(
                dataframe,
                (
                    "xprydt",
                    "expiry_date",
                    "expiry",
                ),
            ),

        "option_type":
            find_column(
                dataframe,
                (
                    "optntp",
                    "option_type",
                ),
            ),

        "strike_price":
            find_column(
                dataframe,
                (
                    "strkpric",
                    "strike_price",
                ),
            ),

        "underlying_symbol":
            find_column(
                dataframe,
                (
                    "undrlygssymb",
                    "undrlygsymb",
                    "undrlygsymbol",
                    "underlying_symbol",
                    "underlyingsymbol",
                ),
            ),

        "underlying_id":
            find_column(
                dataframe,
                (
                    "undrlygfininstrmid",
                    "underlying_instrument_id",
                ),
            ),
    }


# ============================================================
# CLASSIFICATION
# ============================================================

def classify_instrument(
    ticker_symbol: str,
    instrument_type: str,
    instrument_name: str,
) -> str:

    combined = (
        f"{ticker_symbol} "
        f"{instrument_type} "
        f"{instrument_name}"
    ).upper()

    if (
        "INDEX" in combined
        or ticker_symbol
        in INDEX_SYMBOL_ALIASES.values()
    ):

        return "INDEX"

    return "STOCK"


# ============================================================
# EXTRACT CURRENT UNDERLYINGS
# ============================================================

def extract_current_underlyings(
    contracts: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:

    columns = discover_mii_columns(
        contracts
    )

    ticker_column = columns[
        "ticker_symbol"
    ]

    underlying_column = columns[
        "underlying_symbol"
    ]

    instrument_type_column = columns[
        "financial_instrument_type"
    ]

    instrument_name_column = columns[
        "financial_instrument_name"
    ]

    if (
        ticker_column is None
        and underlying_column is None
    ):

        print()
        print(
            "Available contract-master columns:"
        )

        for column in contracts.columns:
            print(
                f"  {column}"
            )

        raise RuntimeError(
            "Could not identify ticker / underlying "
            "symbol column in NSE contract master."
        )

    if underlying_column is not None:

        symbols = (
            contracts[
                underlying_column
            ]
            .map(
                normalize_symbol
            )
        )

    else:

        symbols = (
            contracts[
                ticker_column
            ]
            .map(
                normalize_symbol
            )
        )

    working = pd.DataFrame()

    working[
        "symbol"
    ] = symbols

    if instrument_type_column:

        working[
            "instrument_type"
        ] = (
            contracts[
                instrument_type_column
            ]
            .map(
                safe_text
            )
        )

    else:

        working[
            "instrument_type"
        ] = ""

    if instrument_name_column:

        working[
            "instrument_name"
        ] = (
            contracts[
                instrument_name_column
            ]
            .map(
                safe_text
            )
        )

    else:

        working[
            "instrument_name"
        ] = ""

    working = working[
        working[
            "symbol"
        ].ne(
            ""
        )
    ].copy()

    working = working[
        ~working[
            "symbol"
        ].isin(
            {
                "NAN",
                "NONE",
                "NULL",
            }
        )
    ].copy()

    # --------------------------------------------------------
    # Explicit NSE test / dummy rejection
    # --------------------------------------------------------

    test_mask = (
        working[
            "symbol"
        ]
        .map(
            is_test_symbol
        )
    )

    filtered_tests = working[
        test_mask
    ].copy()

    if not filtered_tests.empty:

        filtered_tests[
            "filter_reason"
        ] = "TEST_OR_DUMMY_SYMBOL"

    working = working[
        ~test_mask
    ].copy()

    working[
        "underlying_type"
    ] = working.apply(
        lambda row:
            classify_instrument(
                row[
                    "symbol"
                ],
                row[
                    "instrument_type"
                ],
                row[
                    "instrument_name"
                ],
            ),
        axis=1,
    )

    current_universe = (
        working[
            [
                "symbol",
                "underlying_type",
            ]
        ]
        .drop_duplicates(
            subset=[
                "symbol",
            ],
            keep="first",
        )
        .sort_values(
            by=[
                "underlying_type",
                "symbol",
            ]
        )
        .reset_index(
            drop=True
        )
    )

    current_universe[
        "is_index"
    ] = (
        current_universe[
            "underlying_type"
        ]
        .eq(
            "INDEX"
        )
    )

    current_universe[
        "is_stock"
    ] = (
        current_universe[
            "underlying_type"
        ]
        .eq(
            "STOCK"
        )
    )

    current_universe[
        "is_fno"
    ] = True

    current_universe[
        "exchange"
    ] = "NSE"

    current_universe[
        "source"
    ] = (
        "NSE_FO_MII_CONTRACT_MASTER"
    )

    current_universe[
        "retrieved_at"
    ] = (
        datetime.now()
        .astimezone()
        .isoformat(
            timespec="seconds"
        )
    )

    return (
        current_universe,
        filtered_tests,
    )


# ============================================================
# LOAD SECURITY MASTER
# ============================================================

def load_security_master() -> pd.DataFrame:

    if not SECURITY_MASTER_FILE.exists():

        raise FileNotFoundError(
            "Security Master not found: "
            f"{SECURITY_MASTER_FILE}"
        )

    dataframe = pd.read_csv(
        SECURITY_MASTER_FILE,
        low_memory=False,
    )

    dataframe.columns = [
        normalize_column_name(
            column
        )
        for column in dataframe.columns
    ]

    if "symbol" not in dataframe.columns:

        raise RuntimeError(
            "Security Master does not contain "
            "symbol column."
        )

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

    if "is_fno" in dataframe.columns:

        dataframe = dataframe[
            dataframe[
                "is_fno"
            ].map(
                parse_bool
            )
        ].copy()

    elif "fno_flag" in dataframe.columns:

        dataframe = dataframe[
            dataframe[
                "fno_flag"
            ].map(
                parse_bool
            )
        ].copy()

    dataframe = dataframe[
        dataframe[
            "symbol"
        ].ne(
            ""
        )
    ].copy()

    dataframe = (
        dataframe
        .drop_duplicates(
            subset=[
                "symbol",
            ],
            keep="first",
        )
        .reset_index(
            drop=True
        )
    )

    return dataframe


# ============================================================
# COMPARE UNIVERSES
# ============================================================

def compare_universe(
    current_universe: pd.DataFrame,
    security_master: pd.DataFrame,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    pd.DataFrame,
]:

    current_symbols = set(
        current_universe[
            "symbol"
        ]
    )

    old_symbols = set(
        security_master[
            "symbol"
        ]
    )

    inclusion_symbols = (
        current_symbols
        - old_symbols
    )

    exclusion_symbols = (
        old_symbols
        - current_symbols
    )

    unchanged_symbols = (
        current_symbols
        & old_symbols
    )

    inclusions = current_universe[
        current_universe[
            "symbol"
        ].isin(
            inclusion_symbols
        )
    ].copy()

    inclusions[
        "change_type"
    ] = "INCLUSION"

    inclusions[
        "review_status"
    ] = "PENDING"

    inclusions[
        "promotion_status"
    ] = "NOT_PROMOTED"

    exclusions = security_master[
        security_master[
            "symbol"
        ].isin(
            exclusion_symbols
        )
    ].copy()

    exclusions[
        "change_type"
    ] = "EXCLUSION"

    exclusions[
        "review_status"
    ] = "PENDING"

    exclusions[
        "promotion_status"
    ] = "NOT_PROMOTED"

    unchanged = current_universe[
        current_universe[
            "symbol"
        ].isin(
            unchanged_symbols
        )
    ].copy()

    unchanged[
        "change_type"
    ] = "UNCHANGED"

    return (
        inclusions,
        exclusions,
        unchanged,
    )


# ============================================================
# VALIDATION
# ============================================================

def validate_universe(
    universe: pd.DataFrame,
    security_master: pd.DataFrame,
    inclusions: pd.DataFrame,
    exclusions: pd.DataFrame,
    unchanged: pd.DataFrame,
    filtered_tests: pd.DataFrame,
) -> dict[str, object]:

    duplicate_symbols = int(
        universe.duplicated(
            subset=[
                "symbol",
            ],
            keep=False,
        ).sum()
    )

    blank_symbols = int(
        universe[
            "symbol"
        ]
        .fillna("")
        .astype(str)
        .str.strip()
        .eq("")
        .sum()
    )

    index_count = int(
        universe[
            "is_index"
        ].sum()
    )

    stock_count = int(
        universe[
            "is_stock"
        ].sum()
    )

    previous_count = int(
        len(
            security_master
        )
    )

    current_count = int(
        len(
            universe
        )
    )

    inclusion_count = int(
        len(
            inclusions
        )
    )

    exclusion_count = int(
        len(
            exclusions
        )
    )

    unchanged_count = int(
        len(
            unchanged
        )
    )

    filtered_test_count = int(
        len(
            filtered_tests
        )
    )

    reconciled_current = (
        previous_count
        + inclusion_count
        - exclusion_count
    )

    reconciliation_ok = (
        reconciled_current
        == current_count
    )

    unchanged_check = (
        unchanged_count
        + inclusion_count
        == current_count
    )

    critical_issues = (
        duplicate_symbols
        + blank_symbols
    )

    if current_count < 100:
        critical_issues += 1

    if not reconciliation_ok:
        critical_issues += 1

    if not unchanged_check:
        critical_issues += 1

    return {
        "duplicate_symbols":
            duplicate_symbols,

        "blank_symbols":
            blank_symbols,

        "indices":
            index_count,

        "stocks":
            stock_count,

        "previous_count":
            previous_count,

        "current_count":
            current_count,

        "inclusions":
            inclusion_count,

        "exclusions":
            exclusion_count,

        "unchanged":
            unchanged_count,

        "filtered_test_symbols":
            filtered_test_count,

        "reconciled_current":
            reconciled_current,

        "reconciliation_ok":
            reconciliation_ok,

        "unchanged_check":
            unchanged_check,

        "critical_issues":
            critical_issues,
    }


# ============================================================
# WRITE OUTPUTS
# ============================================================

def write_outputs(
    contracts: pd.DataFrame,
    current_universe: pd.DataFrame,
    inclusions: pd.DataFrame,
    exclusions: pd.DataFrame,
    unchanged: pd.DataFrame,
    filtered_tests: pd.DataFrame,
    summary: dict[str, object],
) -> None:

    contracts.to_csv(
        RAW_CONTRACT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    current_universe.to_csv(
        CURRENT_UNIVERSE_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    current_universe[
        current_universe[
            "is_stock"
        ]
    ].to_csv(
        CURRENT_STOCKS_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    current_universe[
        current_universe[
            "is_index"
        ]
    ].to_csv(
        CURRENT_INDICES_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    inclusions.to_csv(
        INCLUSIONS_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    exclusions.to_csv(
        EXCLUSIONS_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    unchanged.to_csv(
        UNCHANGED_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    filtered_tests.to_csv(
        FILTERED_TEST_SYMBOLS_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    pd.DataFrame(
        [summary]
    ).to_csv(
        AUDIT_CSV,
        index=False,
        encoding="utf-8-sig",
    )

    SUMMARY_JSON.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ============================================================
# RUN BUILDER
# ============================================================

def run_builder() -> dict[str, object]:

    ensure_directories()

    separator()
    print(
        "AQSD CURRENT NSE F&O UNIVERSE BUILDER"
    )
    separator()

    print(
        f"Module                         : "
        f"{MODULE_ID}"
    )

    print(
        f"Version                        : "
        f"{MODULE_VERSION}"
    )

    print(
        f"Primary Source                 : "
        f"{PRIMARY_SOURCE}"
    )

    print(
        "Security Master                : READ ONLY"
    )

    print(
        "Automatic Promotion            : PROHIBITED"
    )

    sub_separator()

    session = create_http_session()

    (
        contract_url,
        contract_filename,
        contract_date,
    ) = discover_contract_file_url(
        session
    )

    print()
    print(
        f"Contract File                  : "
        f"{contract_filename}"
    )

    contracts = download_contract_master(
        session,
        contract_url,
        contract_filename,
    )

    print(
        f"Contract Rows                  : "
        f"{len(contracts):,}"
    )

    print()
    print(
        "Detected NSE MII columns:"
    )

    detected_columns = (
        discover_mii_columns(
            contracts
        )
    )

    for key, value in (
        detected_columns.items()
    ):

        print(
            f"  {key:<30}: "
            f"{value}"
        )

    print()
    print(
        "Extracting current F&O "
        "underlying universe..."
    )

    (
        current_universe,
        filtered_tests,
    ) = extract_current_underlyings(
        contracts
    )

    security_master = (
        load_security_master()
    )

    (
        inclusions,
        exclusions,
        unchanged,
    ) = compare_universe(
        current_universe,
        security_master,
    )

    validation = validate_universe(
        current_universe,
        security_master,
        inclusions,
        exclusions,
        unchanged,
        filtered_tests,
    )

    if validation[
        "critical_issues"
    ] != 0:

        raise RuntimeError(
            "Current F&O universe failed structural "
            "or reconciliation validation."
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

        "contract_file":
            contract_filename,

        "contract_date":
            contract_date.isoformat(),

        "contract_url":
            contract_url,

        "contract_rows":
            len(
                contracts
            ),

        "current_fno_universe":
            validation[
                "current_count"
            ],

        "current_fno_indices":
            validation[
                "indices"
            ],

        "current_fno_stocks":
            validation[
                "stocks"
            ],

        "previous_aqsd_fno_universe":
            validation[
                "previous_count"
            ],

        "inclusions":
            validation[
                "inclusions"
            ],

        "exclusions":
            validation[
                "exclusions"
            ],

        "unchanged":
            validation[
                "unchanged"
            ],

        "filtered_test_symbols":
            validation[
                "filtered_test_symbols"
            ],

        "reconciled_current":
            validation[
                "reconciled_current"
            ],

        "reconciliation_ok":
            validation[
                "reconciliation_ok"
            ],

        "unchanged_check":
            validation[
                "unchanged_check"
            ],

        "duplicate_symbols":
            validation[
                "duplicate_symbols"
            ],

        "blank_symbols":
            validation[
                "blank_symbols"
            ],

        "critical_issues":
            validation[
                "critical_issues"
            ],

        "security_master_modified":
            False,

        "market_price_database_modified":
            False,

        "automatic_promotion":
            False,

        "historical_fabrication":
            False,

        "status":
            "SUCCESS",
    }

    write_outputs(
        contracts,
        current_universe,
        inclusions,
        exclusions,
        unchanged,
        filtered_tests,
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
        "AQSD CURRENT NSE F&O UNIVERSE SUMMARY"
    )
    separator()

    print(
        f"Contract File                  : "
        f"{summary['contract_file']}"
    )

    print(
        f"Contract Date                  : "
        f"{summary['contract_date']}"
    )

    print(
        f"Contract Rows                  : "
        f"{int(summary['contract_rows']):,}"
    )

    sub_separator()

    print(
        f"Current F&O Universe           : "
        f"{int(summary['current_fno_universe']):,}"
    )

    print(
        f"Current F&O Indices            : "
        f"{int(summary['current_fno_indices']):,}"
    )

    print(
        f"Current F&O Stocks             : "
        f"{int(summary['current_fno_stocks']):,}"
    )

    sub_separator()

    print(
        f"Previous AQSD F&O Universe     : "
        f"{int(summary['previous_aqsd_fno_universe']):,}"
    )

    print(
        f"Current Inclusions             : "
        f"{int(summary['inclusions']):,}"
    )

    print(
        f"Current Exclusions             : "
        f"{int(summary['exclusions']):,}"
    )

    print(
        f"Unchanged                      : "
        f"{int(summary['unchanged']):,}"
    )

    print(
        f"Filtered Test Symbols          : "
        f"{int(summary['filtered_test_symbols']):,}"
    )

    sub_separator()

    print(
        f"Reconciled Current             : "
        f"{int(summary['reconciled_current']):,}"
    )

    print(
        f"Reconciliation OK              : "
        f"{summary['reconciliation_ok']}"
    )

    print(
        f"Unchanged Check                : "
        f"{summary['unchanged_check']}"
    )

    sub_separator()

    print(
        f"Duplicate Symbols              : "
        f"{int(summary['duplicate_symbols']):,}"
    )

    print(
        f"Blank Symbols                  : "
        f"{int(summary['blank_symbols']):,}"
    )

    print(
        f"Critical Issues                : "
        f"{int(summary['critical_issues']):,}"
    )

    sub_separator()

    print(
        f"Current Universe CSV           : "
        f"{CURRENT_UNIVERSE_CSV}"
    )

    print(
        f"Inclusions CSV                 : "
        f"{INCLUSIONS_CSV}"
    )

    print(
        f"Exclusions CSV                 : "
        f"{EXCLUSIONS_CSV}"
    )

    print(
        f"Unchanged CSV                  : "
        f"{UNCHANGED_CSV}"
    )

    print(
        f"Filtered Test Symbols CSV      : "
        f"{FILTERED_TEST_SYMBOLS_CSV}"
    )

    sub_separator()

    print(
        "Security Master                : NOT MODIFIED"
    )

    print(
        "Market Price Database          : NOT MODIFIED"
    )

    print(
        "Automatic Promotion            : PROHIBITED"
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

        summary = run_builder()

        display_summary(
            summary
        )

    except Exception as exc:

        print()
        separator()
        print(
            "AQSD CURRENT NSE F&O UNIVERSE BUILDER"
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
            "Security Master                : NOT MODIFIED"
        )

        print(
            "Market Price Database          : NOT MODIFIED"
        )

        print(
            "Automatic Promotion            : PROHIBITED"
        )

        separator()

        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
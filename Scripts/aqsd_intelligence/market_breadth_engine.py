"""
AQSD
Market Breadth Engine

Module : MBI-001
Version: 1.0.0
Author : AQSD

Description
-----------
Measures the internal health and participation of the broader market.

The engine analyses a prepared daily market-universe file containing
approximately 500 to 1,000 NSE stocks.

The input can be either CSV or Excel.

Required columns
----------------
Symbol
Close
Previous_Close
EMA20
EMA50
EMA200
High_52W
Low_52W

Optional columns
----------------
Sector
Market_Cap_Category
Volume
Average_Volume_20
Is_FnO

Supported analytics
-------------------
- Advances
- Declines
- Unchanged stocks
- Advance / Decline ratio
- Advance percentage
- Decline percentage
- Stocks above EMA20
- Stocks above EMA50
- Stocks above EMA200
- Stocks near 52-week high
- Stocks near 52-week low
- New 52-week highs
- New 52-week lows
- Volume participation
- Sector participation
- Large-cap breadth
- Mid-cap breadth
- Small-cap breadth
- F&O breadth
- Breadth momentum
- Breadth trend
- Breadth strength
- Breadth regime
- Risk-on / Risk-off classification
- Internal market health
- Breadth confidence
- Explainable conclusion

Important
---------
This engine performs market analysis only.

It does not generate BUY, SELL or SHORT instructions.
"""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

import pandas as pd


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "MBI-001"
MODULE_VERSION: Final[str] = "1.0.0"

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

DEFAULT_INPUT_FILE: Final[Path] = (
    BASE_DIR
    / "Data"
    / "Market_Breadth"
    / "market_breadth_snapshot.xlsx"
)

OUTPUT_DIR: Final[Path] = (
    BASE_DIR
    / "Output"
    / "Market_Breadth"
)

REQUIRED_COLUMNS: Final[tuple[str, ...]] = (
    "Symbol",
    "Close",
    "Previous_Close",
    "EMA20",
    "EMA50",
    "EMA200",
    "High_52W",
    "Low_52W",
)

OPTIONAL_COLUMNS: Final[tuple[str, ...]] = (
    "Sector",
    "Market_Cap_Category",
    "Volume",
    "Average_Volume_20",
    "Is_FnO",
)

NEAR_52W_HIGH_THRESHOLD: Final[float] = 0.95
NEAR_52W_LOW_THRESHOLD: Final[float] = 1.05


# ==========================================================
# RESULT MODELS
# ==========================================================

@dataclass(frozen=True)
class SegmentBreadth:
    """
    Breadth result for one market segment.
    """

    name: str
    total_stocks: int
    advances: int
    declines: int
    unchanged: int
    advance_percentage: float
    above_ema20_percentage: float
    above_ema50_percentage: float
    above_ema200_percentage: float
    score: int
    classification: str


@dataclass(frozen=True)
class SectorBreadth:
    """
    Breadth result for one sector.
    """

    sector: str
    total_stocks: int
    advances: int
    declines: int
    advance_percentage: float
    above_ema20_percentage: float
    above_ema50_percentage: float
    above_ema200_percentage: float
    score: int
    classification: str


@dataclass(frozen=True)
class MarketBreadthResult:
    """
    Complete market-breadth result.
    """

    requested_date: date
    analysis_date: date
    source_file: Path

    total_stocks: int
    valid_stocks: int
    invalid_rows: int

    advances: int
    declines: int
    unchanged: int

    advance_percentage: float
    decline_percentage: float
    unchanged_percentage: float
    advance_decline_ratio: float | None

    above_ema20_count: int
    above_ema50_count: int
    above_ema200_count: int

    above_ema20_percentage: float
    above_ema50_percentage: float
    above_ema200_percentage: float

    new_52w_high_count: int
    new_52w_low_count: int
    near_52w_high_count: int
    near_52w_low_count: int

    new_52w_high_percentage: float
    new_52w_low_percentage: float
    near_52w_high_percentage: float
    near_52w_low_percentage: float

    high_volume_advances: int
    high_volume_declines: int
    volume_breadth_ratio: float | None
    volume_participation: str

    bullish_sectors: int
    bearish_sectors: int
    neutral_sectors: int
    sector_participation_percentage: float

    large_cap_breadth: SegmentBreadth | None
    mid_cap_breadth: SegmentBreadth | None
    small_cap_breadth: SegmentBreadth | None
    fno_breadth: SegmentBreadth | None

    breadth_score: int
    breadth_momentum: str
    breadth_trend: str
    breadth_strength: str
    breadth_regime: str

    risk_environment: str
    internal_market_health: str
    participation_quality: str
    divergence_risk: str

    confidence: int
    expected_behaviour: str
    concise_summary: str
    explanation: str

    sectors: tuple[SectorBreadth, ...]
    warnings: tuple[str, ...]
    status: str


# ==========================================================
# COLUMN HELPERS
# ==========================================================

def normalize_header(value: object) -> str:
    """
    Convert a column heading into a consistent format.
    """

    text = str(value).strip()

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

    return text.strip("_")


def normalize_dataframe_columns(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Normalize known column-name variants.
    """

    normalized = dataframe.copy()

    normalized.columns = [
        normalize_header(column)
        for column in normalized.columns
    ]

    aliases = {
        "SYMBOL": "Symbol",
        "TICKER": "Symbol",
        "CLOSE": "Close",
        "LTP": "Close",
        "PREVIOUS_CLOSE": "Previous_Close",
        "PREV_CLOSE": "Previous_Close",
        "PREVIOUSCLOSE": "Previous_Close",
        "EMA_20": "EMA20",
        "EMA20": "EMA20",
        "EMA_50": "EMA50",
        "EMA50": "EMA50",
        "EMA_200": "EMA200",
        "EMA200": "EMA200",
        "HIGH_52W": "High_52W",
        "52W_HIGH": "High_52W",
        "52_WEEK_HIGH": "High_52W",
        "LOW_52W": "Low_52W",
        "52W_LOW": "Low_52W",
        "52_WEEK_LOW": "Low_52W",
        "SECTOR": "Sector",
        "INDUSTRY": "Sector",
        "MARKET_CAP_CATEGORY": "Market_Cap_Category",
        "MARKET_CAP": "Market_Cap_Category",
        "CAP_CATEGORY": "Market_Cap_Category",
        "VOLUME": "Volume",
        "AVERAGE_VOLUME_20": "Average_Volume_20",
        "AVG_VOLUME_20": "Average_Volume_20",
        "20D_AVG_VOLUME": "Average_Volume_20",
        "IS_FNO": "Is_FnO",
        "FNO": "Is_FnO",
        "IS_F_O": "Is_FnO",
    }

    rename_map: dict[str, str] = {}

    for column in normalized.columns:
        key = column.upper()

        if key in aliases:
            rename_map[column] = aliases[key]

    return normalized.rename(
        columns=rename_map
    )


def validate_required_columns(
    dataframe: pd.DataFrame,
) -> None:
    """
    Ensure all required breadth columns are available.
    """

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in dataframe.columns
    ]

    if missing:
        raise KeyError(
            "Market breadth input is missing required columns: "
            + ", ".join(missing)
        )


# ==========================================================
# INPUT READING
# ==========================================================

def read_market_snapshot(
    source_file: Path,
    sheet_name: str | int = 0,
) -> pd.DataFrame:
    """
    Read a CSV or Excel market-breadth snapshot.
    """

    if not source_file.exists():
        raise FileNotFoundError(
            f"Market breadth input file not found: {source_file}"
        )

    suffix = source_file.suffix.lower()

    if suffix == ".csv":
        dataframe = pd.read_csv(
            source_file
        )

    elif suffix in {
        ".xlsx",
        ".xlsm",
    }:
        dataframe = pd.read_excel(
            source_file,
            sheet_name=sheet_name,
            engine="openpyxl",
        )

    else:
        raise ValueError(
            "Supported input formats are CSV, XLSX and XLSM."
        )

    dataframe = dataframe.dropna(
        how="all"
    ).reset_index(drop=True)

    dataframe = normalize_dataframe_columns(
        dataframe
    )

    validate_required_columns(
        dataframe
    )

    return dataframe


# ==========================================================
# DATA CLEANING
# ==========================================================

def convert_numeric_columns(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Convert market-value columns into numeric data.
    """

    result = dataframe.copy()

    numeric_columns = [
        "Close",
        "Previous_Close",
        "EMA20",
        "EMA50",
        "EMA200",
        "High_52W",
        "Low_52W",
        "Volume",
        "Average_Volume_20",
    ]

    for column in numeric_columns:
        if column not in result.columns:
            continue

        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    return result


def normalize_boolean_value(
    value: object,
) -> bool:
    """
    Convert common F&O markers into Boolean values.
    """

    if isinstance(value, bool):
        return value

    if value is None:
        return False

    try:
        if pd.isna(value):
            return False
    except TypeError:
        pass

    text = str(value).strip().upper()

    return text in {
        "TRUE",
        "YES",
        "Y",
        "1",
        "FNO",
        "F&O",
    }


def prepare_market_snapshot(
    dataframe: pd.DataFrame,
) -> tuple[pd.DataFrame, int]:
    """
    Clean and validate the breadth snapshot.
    """

    prepared = convert_numeric_columns(
        dataframe
    )

    prepared["Symbol"] = (
        prepared["Symbol"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    required_numeric = [
        "Close",
        "Previous_Close",
        "EMA20",
        "EMA50",
        "EMA200",
        "High_52W",
        "Low_52W",
    ]

    valid_mask = (
        prepared["Symbol"].ne("")
        & prepared["Symbol"].ne("NAN")
    )

    for column in required_numeric:
        valid_mask &= (
            prepared[column].notna()
            & prepared[column].gt(0)
        )

    invalid_rows = int(
        (~valid_mask).sum()
    )

    prepared = prepared.loc[
        valid_mask
    ].copy()

    prepared = prepared.drop_duplicates(
        subset=["Symbol"],
        keep="last",
    )

    if "Sector" not in prepared.columns:
        prepared["Sector"] = "UNKNOWN"

    prepared["Sector"] = (
        prepared["Sector"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    if "Market_Cap_Category" not in prepared.columns:
        prepared["Market_Cap_Category"] = "UNKNOWN"

    prepared["Market_Cap_Category"] = (
        prepared["Market_Cap_Category"]
        .fillna("UNKNOWN")
        .astype(str)
        .str.strip()
        .str.upper()
    )

    if "Is_FnO" not in prepared.columns:
        prepared["Is_FnO"] = False
    else:
        prepared["Is_FnO"] = prepared["Is_FnO"].apply(
            normalize_boolean_value
        )

    return prepared, invalid_rows


# ==========================================================
# SAFE CALCULATIONS
# ==========================================================

def safe_percentage(
    numerator: float,
    denominator: float,
) -> float:
    """
    Calculate a percentage safely.
    """

    if denominator == 0:
        return 0.0

    return round(
        numerator / denominator * 100,
        2,
    )


def safe_ratio(
    numerator: float,
    denominator: float,
) -> float | None:
    """
    Calculate a ratio safely.
    """

    if denominator == 0:
        return None

    return round(
        numerator / denominator,
        2,
    )


def clamp_score(
    value: float,
) -> int:
    """
    Restrict a score to 0-100.
    """

    return max(
        0,
        min(
            round(value),
            100,
        ),
    )


# ==========================================================
# STOCK CLASSIFICATION
# ==========================================================

def add_breadth_flags(
    dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add all per-stock breadth flags.
    """

    result = dataframe.copy()

    result["Advance"] = (
        result["Close"]
        > result["Previous_Close"]
    )

    result["Decline"] = (
        result["Close"]
        < result["Previous_Close"]
    )

    result["Unchanged"] = (
        result["Close"]
        == result["Previous_Close"]
    )

    result["Above_EMA20"] = (
        result["Close"]
        > result["EMA20"]
    )

    result["Above_EMA50"] = (
        result["Close"]
        > result["EMA50"]
    )

    result["Above_EMA200"] = (
        result["Close"]
        > result["EMA200"]
    )

    result["New_52W_High"] = (
        result["Close"]
        >= result["High_52W"]
    )

    result["New_52W_Low"] = (
        result["Close"]
        <= result["Low_52W"]
    )

    result["Near_52W_High"] = (
        result["Close"]
        >= result["High_52W"]
        * NEAR_52W_HIGH_THRESHOLD
    )

    result["Near_52W_Low"] = (
        result["Close"]
        <= result["Low_52W"]
        * NEAR_52W_LOW_THRESHOLD
    )

    if {
        "Volume",
        "Average_Volume_20",
    }.issubset(result.columns):
        result["High_Volume"] = (
            result["Volume"].notna()
            & result["Average_Volume_20"].notna()
            & result["Average_Volume_20"].gt(0)
            & (
                result["Volume"]
                >= result["Average_Volume_20"]
            )
        )
    else:
        result["High_Volume"] = False

    return result


# ==========================================================
# SEGMENT BREADTH
# ==========================================================

def classify_segment_score(
    score: int,
) -> str:
    """
    Convert a segment score into a classification.
    """

    if score >= 70:
        return "STRONG BULLISH"

    if score >= 58:
        return "BULLISH"

    if score <= 30:
        return "STRONG BEARISH"

    if score <= 42:
        return "BEARISH"

    return "NEUTRAL"


def calculate_segment_score(
    *,
    advance_percentage: float,
    ema20_percentage: float,
    ema50_percentage: float,
    ema200_percentage: float,
) -> int:
    """
    Calculate one market-segment breadth score.
    """

    return clamp_score(
        advance_percentage * 0.35
        + ema20_percentage * 0.25
        + ema50_percentage * 0.20
        + ema200_percentage * 0.20
    )


def analyse_segment(
    dataframe: pd.DataFrame,
    name: str,
) -> SegmentBreadth | None:
    """
    Analyse one subset of the market.
    """

    if dataframe.empty:
        return None

    total = len(dataframe)

    advances = int(
        dataframe["Advance"].sum()
    )

    declines = int(
        dataframe["Decline"].sum()
    )

    unchanged = int(
        dataframe["Unchanged"].sum()
    )

    advance_percentage = safe_percentage(
        advances,
        total,
    )

    ema20_percentage = safe_percentage(
        int(dataframe["Above_EMA20"].sum()),
        total,
    )

    ema50_percentage = safe_percentage(
        int(dataframe["Above_EMA50"].sum()),
        total,
    )

    ema200_percentage = safe_percentage(
        int(dataframe["Above_EMA200"].sum()),
        total,
    )

    score = calculate_segment_score(
        advance_percentage=advance_percentage,
        ema20_percentage=ema20_percentage,
        ema50_percentage=ema50_percentage,
        ema200_percentage=ema200_percentage,
    )

    return SegmentBreadth(
        name=name,
        total_stocks=total,
        advances=advances,
        declines=declines,
        unchanged=unchanged,
        advance_percentage=advance_percentage,
        above_ema20_percentage=ema20_percentage,
        above_ema50_percentage=ema50_percentage,
        above_ema200_percentage=ema200_percentage,
        score=score,
        classification=classify_segment_score(
            score
        ),
    )


def get_market_cap_segment(
    dataframe: pd.DataFrame,
    accepted_names: set[str],
) -> pd.DataFrame:
    """
    Return stocks matching the requested market-cap aliases.
    """

    normalized = (
        dataframe["Market_Cap_Category"]
        .astype(str)
        .str.upper()
        .str.replace(
            r"[^A-Z0-9]+",
            "",
            regex=True,
        )
    )

    normalized_aliases = {
        re.sub(
            r"[^A-Z0-9]+",
            "",
            name.upper(),
        )
        for name in accepted_names
    }

    return dataframe.loc[
        normalized.isin(
            normalized_aliases
        )
    ]


# ==========================================================
# SECTOR BREADTH
# ==========================================================

def analyse_sectors(
    dataframe: pd.DataFrame,
) -> tuple[SectorBreadth, ...]:
    """
    Calculate breadth for every available sector.
    """

    results: list[SectorBreadth] = []

    grouped = dataframe.groupby(
        "Sector",
        dropna=False,
    )

    for sector, group in grouped:
        total = len(group)

        if total == 0:
            continue

        advances = int(
            group["Advance"].sum()
        )

        declines = int(
            group["Decline"].sum()
        )

        advance_percentage = safe_percentage(
            advances,
            total,
        )

        ema20_percentage = safe_percentage(
            int(group["Above_EMA20"].sum()),
            total,
        )

        ema50_percentage = safe_percentage(
            int(group["Above_EMA50"].sum()),
            total,
        )

        ema200_percentage = safe_percentage(
            int(group["Above_EMA200"].sum()),
            total,
        )

        score = calculate_segment_score(
            advance_percentage=advance_percentage,
            ema20_percentage=ema20_percentage,
            ema50_percentage=ema50_percentage,
            ema200_percentage=ema200_percentage,
        )

        results.append(
            SectorBreadth(
                sector=str(sector),
                total_stocks=total,
                advances=advances,
                declines=declines,
                advance_percentage=advance_percentage,
                above_ema20_percentage=ema20_percentage,
                above_ema50_percentage=ema50_percentage,
                above_ema200_percentage=ema200_percentage,
                score=score,
                classification=classify_segment_score(
                    score
                ),
            )
        )

    return tuple(
        sorted(
            results,
            key=lambda item: item.score,
            reverse=True,
        )
    )


# ==========================================================
# BREADTH SCORE
# ==========================================================

def calculate_breadth_score(
    *,
    advance_percentage: float,
    ema20_percentage: float,
    ema50_percentage: float,
    ema200_percentage: float,
    near_high_percentage: float,
    near_low_percentage: float,
    sector_participation_percentage: float,
    volume_ratio: float | None,
) -> int:
    """
    Calculate the overall market-breadth score.
    """

    score = (
        advance_percentage * 0.25
        + ema20_percentage * 0.20
        + ema50_percentage * 0.17
        + ema200_percentage * 0.15
        + near_high_percentage * 0.08
        + sector_participation_percentage * 0.15
    )

    score -= min(
        near_low_percentage * 0.12,
        12,
    )

    if volume_ratio is not None:
        if volume_ratio >= 2:
            score += 6

        elif volume_ratio >= 1.2:
            score += 3

        elif volume_ratio <= 0.5:
            score -= 6

        elif volume_ratio <= 0.8:
            score -= 3

    return clamp_score(score)


# ==========================================================
# CLASSIFICATION ENGINES
# ==========================================================

def determine_breadth_momentum(
    *,
    advance_percentage: float,
    ema20_percentage: float,
    ema50_percentage: float,
) -> str:
    """
    Determine near-term breadth momentum.
    """

    if (
        advance_percentage >= 65
        and ema20_percentage >= 65
        and ema50_percentage >= 55
    ):
        return "STRONGLY IMPROVING"

    if (
        advance_percentage >= 55
        and ema20_percentage >= 55
    ):
        return "IMPROVING"

    if (
        advance_percentage <= 35
        and ema20_percentage <= 35
        and ema50_percentage <= 45
    ):
        return "STRONGLY DETERIORATING"

    if (
        advance_percentage <= 45
        and ema20_percentage <= 45
    ):
        return "DETERIORATING"

    return "MIXED"


def determine_breadth_trend(
    *,
    ema20_percentage: float,
    ema50_percentage: float,
    ema200_percentage: float,
) -> str:
    """
    Determine the structural breadth trend.
    """

    if (
        ema20_percentage >= 60
        and ema50_percentage >= 60
        and ema200_percentage >= 55
    ):
        return "BULLISH"

    if (
        ema20_percentage <= 40
        and ema50_percentage <= 40
        and ema200_percentage <= 45
    ):
        return "BEARISH"

    if (
        ema20_percentage > ema50_percentage
        > ema200_percentage
    ):
        return "IMPROVING BULLISH"

    if (
        ema20_percentage < ema50_percentage
        < ema200_percentage
    ):
        return "DETERIORATING BEARISH"

    return "NEUTRAL TO MIXED"


def determine_breadth_strength(
    score: int,
) -> str:
    """
    Convert breadth score into strength.
    """

    if score >= 75:
        return "VERY STRONG"

    if score >= 62:
        return "STRONG"

    if score >= 52:
        return "MODERATE"

    if score >= 40:
        return "WEAK"

    return "VERY WEAK"


def determine_breadth_regime(
    *,
    score: int,
    trend: str,
    momentum: str,
) -> str:
    """
    Determine the overall breadth regime.
    """

    if (
        score >= 65
        and "BULLISH" in trend
        and "IMPROVING" in momentum
    ):
        return "BROAD-BASED BULLISH PARTICIPATION"

    if (
        score <= 35
        and "BEARISH" in trend
        and "DETERIORATING" in momentum
    ):
        return "BROAD-BASED BEARISH PARTICIPATION"

    if (
        "BULLISH" in trend
        and "DETERIORATING" in momentum
    ):
        return "BULLISH STRUCTURE WITH NARROWING PARTICIPATION"

    if (
        "BEARISH" in trend
        and "IMPROVING" in momentum
    ):
        return "BEARISH STRUCTURE WITH RECOVERY"

    if score >= 55:
        return "SELECTIVE BULLISH PARTICIPATION"

    if score <= 45:
        return "SELECTIVE BEARISH PARTICIPATION"

    return "MIXED PARTICIPATION"


def determine_risk_environment(
    *,
    score: int,
    advance_percentage: float,
    sector_participation_percentage: float,
) -> str:
    """
    Classify the internal risk-on or risk-off environment.
    """

    if (
        score >= 65
        and advance_percentage >= 60
        and sector_participation_percentage >= 60
    ):
        return "RISK ON"

    if (
        score <= 35
        and advance_percentage <= 40
        and sector_participation_percentage <= 40
    ):
        return "RISK OFF"

    if score >= 55:
        return "SELECTIVE RISK ON"

    if score <= 45:
        return "SELECTIVE RISK OFF"

    return "NEUTRAL / TRANSITION"


def determine_internal_market_health(
    *,
    ema50_percentage: float,
    ema200_percentage: float,
    advance_percentage: float,
) -> str:
    """
    Determine the internal health of the market.
    """

    if (
        ema50_percentage >= 65
        and ema200_percentage >= 60
        and advance_percentage >= 55
    ):
        return "VERY HEALTHY"

    if (
        ema50_percentage >= 55
        and ema200_percentage >= 50
    ):
        return "HEALTHY"

    if (
        ema50_percentage <= 35
        and ema200_percentage <= 40
    ):
        return "UNHEALTHY"

    if (
        ema50_percentage <= 45
        or ema200_percentage <= 45
    ):
        return "FRAGILE"

    return "MIXED"


def determine_participation_quality(
    *,
    advance_percentage: float,
    sector_participation_percentage: float,
    fno_breadth: SegmentBreadth | None,
) -> str:
    """
    Determine whether participation is broad or narrow.
    """

    fno_advance_percentage = (
        fno_breadth.advance_percentage
        if fno_breadth is not None
        else advance_percentage
    )

    if (
        advance_percentage >= 60
        and sector_participation_percentage >= 60
        and fno_advance_percentage >= 55
    ):
        return "BROAD BASED"

    if (
        advance_percentage <= 40
        and sector_participation_percentage <= 40
    ):
        return "BROAD BASED WEAKNESS"

    if (
        abs(
            advance_percentage
            - fno_advance_percentage
        )
        >= 15
    ):
        return "NARROW / UNEVEN"

    return "SELECTIVE"


def determine_divergence_risk(
    *,
    advance_percentage: float,
    ema20_percentage: float,
    ema200_percentage: float,
    sector_participation_percentage: float,
) -> str:
    """
    Detect conflicts between short-term and long-term breadth.
    """

    if (
        advance_percentage >= 60
        and ema20_percentage >= 60
        and ema200_percentage <= 40
    ):
        return "HIGH — SHORT-TERM RECOVERY WITH WEAK LONG-TERM BREADTH"

    if (
        advance_percentage <= 40
        and ema20_percentage <= 40
        and ema200_percentage >= 60
    ):
        return "MODERATE — SHORT-TERM WEAKNESS WITH HEALTHY LONG-TERM BREADTH"

    if (
        sector_participation_percentage < 40
        and advance_percentage >= 55
    ):
        return "HIGH — INDEX OR STOCK-SPECIFIC ADVANCE"

    return "LOW TO MODERATE"


# ==========================================================
# CONFIDENCE
# ==========================================================

def calculate_confidence(
    *,
    valid_stocks: int,
    invalid_rows: int,
    sector_count: int,
    has_volume_data: bool,
    has_market_cap_data: bool,
    has_fno_data: bool,
) -> int:
    """
    Calculate breadth confidence from data completeness.
    """

    score = 55.0

    if valid_stocks >= 500:
        score += 18

    elif valid_stocks >= 300:
        score += 12

    elif valid_stocks >= 150:
        score += 6

    else:
        score -= 12

    total_rows = valid_stocks + invalid_rows

    if total_rows > 0:
        invalid_percentage = (
            invalid_rows
            / total_rows
            * 100
        )

        score -= min(
            invalid_percentage * 0.8,
            20,
        )

    if sector_count >= 15:
        score += 8

    elif sector_count >= 8:
        score += 4

    else:
        score -= 5

    if has_volume_data:
        score += 6

    if has_market_cap_data:
        score += 5

    if has_fno_data:
        score += 5

    return clamp_score(score)


# ==========================================================
# BEHAVIOUR AND EXPLANATION
# ==========================================================

def determine_expected_behaviour(
    *,
    breadth_regime: str,
    risk_environment: str,
    divergence_risk: str,
) -> str:
    """
    Describe likely behaviour from breadth conditions.
    """

    if breadth_regime == "BROAD-BASED BULLISH PARTICIPATION":
        return (
            "BROAD MARKET PARTICIPATION MAY SUPPORT CONTINUATION, "
            "WITH PULLBACKS MORE LIKELY TO ATTRACT PARTICIPATION"
        )

    if breadth_regime == "BROAD-BASED BEARISH PARTICIPATION":
        return (
            "WIDESPREAD WEAKNESS MAY CONTINUE, WITH RECOVERIES "
            "REMAINING VULNERABLE UNTIL PARTICIPATION IMPROVES"
        )

    if breadth_regime == "BEARISH STRUCTURE WITH RECOVERY":
        return (
            "A RECOVERY MAY CONTINUE, BUT LONG-TERM INTERNAL "
            "MARKET HEALTH REMAINS WEAK"
        )

    if breadth_regime == "BULLISH STRUCTURE WITH NARROWING PARTICIPATION":
        return (
            "THE MARKET MAY REMAIN POSITIVE, BUT NARROWING "
            "PARTICIPATION INCREASES CORRECTION RISK"
        )

    if "HIGH" in divergence_risk:
        return (
            "INDEX MOVEMENT MAY NOT REPRESENT THE BROADER MARKET; "
            "FALSE BREAKOUTS OR RAPID REVERSALS ARE POSSIBLE"
        )

    if risk_environment == "NEUTRAL / TRANSITION":
        return (
            "RANGE-BOUND OR ROTATIONAL BEHAVIOUR MAY CONTINUE "
            "WITHOUT CLEAR BROAD-MARKET CONTROL"
        )

    return (
        "PARTICIPATION IS SELECTIVE AND MARKET BEHAVIOUR MAY "
        "REMAIN STOCK-SPECIFIC OR SECTOR-SPECIFIC"
    )


def build_concise_summary(
    *,
    breadth_score: int,
    breadth_trend: str,
    breadth_strength: str,
    breadth_regime: str,
    risk_environment: str,
    internal_health: str,
    confidence: int,
) -> str:
    """
    Build a dashboard-ready summary.
    """

    return (
        f"BREADTH {breadth_score}% | "
        f"{breadth_trend} TREND | "
        f"{breadth_strength} STRENGTH | "
        f"{breadth_regime} | "
        f"{risk_environment} | "
        f"{internal_health} INTERNAL HEALTH | "
        f"{confidence}% CONFIDENCE"
    )


def build_explanation(
    *,
    total_stocks: int,
    advances: int,
    declines: int,
    advance_percentage: float,
    ema20_percentage: float,
    ema50_percentage: float,
    ema200_percentage: float,
    bullish_sectors: int,
    sector_count: int,
    breadth_score: int,
    breadth_regime: str,
    risk_environment: str,
    internal_health: str,
    participation_quality: str,
    divergence_risk: str,
) -> str:
    """
    Build the final market-breadth explanation.
    """

    return (
        f"The breadth universe contains {total_stocks:,} valid stocks. "
        f"{advances:,} stocks advanced and {declines:,} declined, "
        f"producing an advance rate of {advance_percentage:.2f}%. "
        f"{ema20_percentage:.2f}% of stocks are above EMA20, "
        f"{ema50_percentage:.2f}% are above EMA50 and "
        f"{ema200_percentage:.2f}% are above EMA200. "
        f"{bullish_sectors} of {sector_count} analysed sectors are "
        f"classified as bullish. The overall breadth score is "
        f"{breadth_score}%, creating a "
        f"{breadth_regime.lower()} regime. "
        f"The market environment is {risk_environment.lower()}, "
        f"internal market health is {internal_health.lower()}, and "
        f"participation quality is {participation_quality.lower()}. "
        f"Divergence risk is classified as {divergence_risk.lower()}."
    )


# ==========================================================
# WARNINGS
# ==========================================================

def build_warnings(
    *,
    valid_stocks: int,
    invalid_rows: int,
    sector_count: int,
    volume_data_available: bool,
    market_cap_data_available: bool,
    fno_data_available: bool,
    divergence_risk: str,
    breadth_regime: str,
) -> tuple[str, ...]:
    """
    Build breadth warnings.
    """

    warnings: list[str] = []

    if valid_stocks < 300:
        warnings.append(
            "The breadth universe contains fewer than 300 valid stocks."
        )

    if invalid_rows > 0:
        warnings.append(
            f"{invalid_rows} input rows were excluded due to missing "
            "or invalid values."
        )

    if sector_count < 8:
        warnings.append(
            "Sector coverage is limited."
        )

    if not volume_data_available:
        warnings.append(
            "Volume breadth is unavailable because volume columns "
            "were not supplied."
        )

    if not market_cap_data_available:
        warnings.append(
            "Large-cap, mid-cap and small-cap breadth may be unavailable."
        )

    if not fno_data_available:
        warnings.append(
            "F&O breadth is unavailable because Is_FnO was not supplied."
        )

    if "HIGH" in divergence_risk:
        warnings.append(
            divergence_risk
        )

    if "NARROWING" in breadth_regime:
        warnings.append(
            "Bullish structure is being supported by narrowing participation."
        )

    if not warnings:
        warnings.append(
            "No major market-breadth warning is active."
        )

    return tuple(
        dict.fromkeys(warnings)
    )


# ==========================================================
# OUTPUT EXPORT
# ==========================================================

def export_result(
    *,
    result: MarketBreadthResult,
) -> tuple[Path, Path]:
    """
    Export the market-breadth result to Excel and CSV.
    """

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    date_text = result.analysis_date.strftime(
        "%Y%m%d"
    )

    summary_file = (
        OUTPUT_DIR
        / f"market_breadth_summary_{date_text}.csv"
    )

    excel_file = (
        OUTPUT_DIR
        / f"market_breadth_report_{date_text}.xlsx"
    )

    summary_data = {
        "Analysis_Date": result.analysis_date,
        "Total_Stocks": result.total_stocks,
        "Advances": result.advances,
        "Declines": result.declines,
        "Unchanged": result.unchanged,
        "Advance_Percentage": result.advance_percentage,
        "Decline_Percentage": result.decline_percentage,
        "Advance_Decline_Ratio": result.advance_decline_ratio,
        "Above_EMA20_Percentage": result.above_ema20_percentage,
        "Above_EMA50_Percentage": result.above_ema50_percentage,
        "Above_EMA200_Percentage": result.above_ema200_percentage,
        "New_52W_Highs": result.new_52w_high_count,
        "New_52W_Lows": result.new_52w_low_count,
        "Bullish_Sectors": result.bullish_sectors,
        "Bearish_Sectors": result.bearish_sectors,
        "Sector_Participation_Percentage": (
            result.sector_participation_percentage
        ),
        "Breadth_Score": result.breadth_score,
        "Breadth_Momentum": result.breadth_momentum,
        "Breadth_Trend": result.breadth_trend,
        "Breadth_Strength": result.breadth_strength,
        "Breadth_Regime": result.breadth_regime,
        "Risk_Environment": result.risk_environment,
        "Internal_Market_Health": result.internal_market_health,
        "Participation_Quality": result.participation_quality,
        "Divergence_Risk": result.divergence_risk,
        "Confidence": result.confidence,
        "Expected_Behaviour": result.expected_behaviour,
        "Concise_Summary": result.concise_summary,
        "Status": result.status,
    }

    summary_dataframe = pd.DataFrame(
        [summary_data]
    )

    summary_dataframe.to_csv(
        summary_file,
        index=False,
    )

    sector_dataframe = pd.DataFrame(
        [
            {
                "Sector": sector.sector,
                "Total_Stocks": sector.total_stocks,
                "Advances": sector.advances,
                "Declines": sector.declines,
                "Advance_Percentage": sector.advance_percentage,
                "Above_EMA20_Percentage": (
                    sector.above_ema20_percentage
                ),
                "Above_EMA50_Percentage": (
                    sector.above_ema50_percentage
                ),
                "Above_EMA200_Percentage": (
                    sector.above_ema200_percentage
                ),
                "Score": sector.score,
                "Classification": sector.classification,
            }
            for sector in result.sectors
        ]
    )

    segment_rows: list[dict[str, object]] = []

    for segment in (
        result.large_cap_breadth,
        result.mid_cap_breadth,
        result.small_cap_breadth,
        result.fno_breadth,
    ):
        if segment is None:
            continue

        segment_rows.append(
            {
                "Segment": segment.name,
                "Total_Stocks": segment.total_stocks,
                "Advances": segment.advances,
                "Declines": segment.declines,
                "Unchanged": segment.unchanged,
                "Advance_Percentage": segment.advance_percentage,
                "Above_EMA20_Percentage": (
                    segment.above_ema20_percentage
                ),
                "Above_EMA50_Percentage": (
                    segment.above_ema50_percentage
                ),
                "Above_EMA200_Percentage": (
                    segment.above_ema200_percentage
                ),
                "Score": segment.score,
                "Classification": segment.classification,
            }
        )

    segment_dataframe = pd.DataFrame(
        segment_rows
    )

    warnings_dataframe = pd.DataFrame(
        {
            "Warning": list(
                result.warnings
            )
        }
    )

    with pd.ExcelWriter(
        excel_file,
        engine="openpyxl",
    ) as writer:
        summary_dataframe.to_excel(
            writer,
            sheet_name="Summary",
            index=False,
        )

        sector_dataframe.to_excel(
            writer,
            sheet_name="Sectors",
            index=False,
        )

        segment_dataframe.to_excel(
            writer,
            sheet_name="Segments",
            index=False,
        )

        warnings_dataframe.to_excel(
            writer,
            sheet_name="Warnings",
            index=False,
        )

    return summary_file, excel_file


# ==========================================================
# MAIN ENGINE
# ==========================================================

def run_market_breadth_engine(
    *,
    requested_date: date,
    source_file: Path,
    sheet_name: str | int = 0,
    export: bool = True,
) -> MarketBreadthResult:
    """
    Run the complete AQSD Market Breadth Engine.
    """

    raw_dataframe = read_market_snapshot(
        source_file=source_file,
        sheet_name=sheet_name,
    )

    total_input_rows = len(
        raw_dataframe
    )

    prepared_dataframe, invalid_rows = (
        prepare_market_snapshot(
            raw_dataframe
        )
    )

    breadth_dataframe = add_breadth_flags(
        prepared_dataframe
    )

    total_stocks = len(
        breadth_dataframe
    )

    if total_stocks == 0:
        raise RuntimeError(
            "No valid stocks remain after breadth-data validation."
        )

    advances = int(
        breadth_dataframe["Advance"].sum()
    )

    declines = int(
        breadth_dataframe["Decline"].sum()
    )

    unchanged = int(
        breadth_dataframe["Unchanged"].sum()
    )

    advance_percentage = safe_percentage(
        advances,
        total_stocks,
    )

    decline_percentage = safe_percentage(
        declines,
        total_stocks,
    )

    unchanged_percentage = safe_percentage(
        unchanged,
        total_stocks,
    )

    advance_decline_ratio = safe_ratio(
        advances,
        declines,
    )

    above_ema20_count = int(
        breadth_dataframe["Above_EMA20"].sum()
    )

    above_ema50_count = int(
        breadth_dataframe["Above_EMA50"].sum()
    )

    above_ema200_count = int(
        breadth_dataframe["Above_EMA200"].sum()
    )

    above_ema20_percentage = safe_percentage(
        above_ema20_count,
        total_stocks,
    )

    above_ema50_percentage = safe_percentage(
        above_ema50_count,
        total_stocks,
    )

    above_ema200_percentage = safe_percentage(
        above_ema200_count,
        total_stocks,
    )

    new_52w_high_count = int(
        breadth_dataframe["New_52W_High"].sum()
    )

    new_52w_low_count = int(
        breadth_dataframe["New_52W_Low"].sum()
    )

    near_52w_high_count = int(
        breadth_dataframe["Near_52W_High"].sum()
    )

    near_52w_low_count = int(
        breadth_dataframe["Near_52W_Low"].sum()
    )

    new_52w_high_percentage = safe_percentage(
        new_52w_high_count,
        total_stocks,
    )

    new_52w_low_percentage = safe_percentage(
        new_52w_low_count,
        total_stocks,
    )

    near_52w_high_percentage = safe_percentage(
        near_52w_high_count,
        total_stocks,
    )

    near_52w_low_percentage = safe_percentage(
        near_52w_low_count,
        total_stocks,
    )

    high_volume_advances = int(
        (
            breadth_dataframe["High_Volume"]
            & breadth_dataframe["Advance"]
        ).sum()
    )

    high_volume_declines = int(
        (
            breadth_dataframe["High_Volume"]
            & breadth_dataframe["Decline"]
        ).sum()
    )

    volume_breadth_ratio = safe_ratio(
        high_volume_advances,
        high_volume_declines,
    )

    if volume_breadth_ratio is None:
        volume_participation = "INSUFFICIENT VOLUME DATA"

    elif volume_breadth_ratio >= 1.5:
        volume_participation = "BULLISH VOLUME PARTICIPATION"

    elif volume_breadth_ratio <= 0.67:
        volume_participation = "BEARISH VOLUME PARTICIPATION"

    else:
        volume_participation = "BALANCED VOLUME PARTICIPATION"

    sectors = analyse_sectors(
        breadth_dataframe
    )

    bullish_sectors = sum(
        "BULLISH" in sector.classification
        for sector in sectors
    )

    bearish_sectors = sum(
        "BEARISH" in sector.classification
        for sector in sectors
    )

    neutral_sectors = (
        len(sectors)
        - bullish_sectors
        - bearish_sectors
    )

    sector_participation_percentage = safe_percentage(
        bullish_sectors,
        len(sectors),
    )

    large_cap_dataframe = get_market_cap_segment(
        breadth_dataframe,
        {
            "LARGE CAP",
            "LARGECAP",
            "LARGE",
        },
    )

    mid_cap_dataframe = get_market_cap_segment(
        breadth_dataframe,
        {
            "MID CAP",
            "MIDCAP",
            "MID",
        },
    )

    small_cap_dataframe = get_market_cap_segment(
        breadth_dataframe,
        {
            "SMALL CAP",
            "SMALLCAP",
            "SMALL",
        },
    )

    fno_dataframe = breadth_dataframe.loc[
        breadth_dataframe["Is_FnO"]
    ]

    large_cap_breadth = analyse_segment(
        large_cap_dataframe,
        "LARGE CAP",
    )

    mid_cap_breadth = analyse_segment(
        mid_cap_dataframe,
        "MID CAP",
    )

    small_cap_breadth = analyse_segment(
        small_cap_dataframe,
        "SMALL CAP",
    )

    fno_breadth = analyse_segment(
        fno_dataframe,
        "F&O",
    )

    breadth_score = calculate_breadth_score(
        advance_percentage=advance_percentage,
        ema20_percentage=above_ema20_percentage,
        ema50_percentage=above_ema50_percentage,
        ema200_percentage=above_ema200_percentage,
        near_high_percentage=near_52w_high_percentage,
        near_low_percentage=near_52w_low_percentage,
        sector_participation_percentage=(
            sector_participation_percentage
        ),
        volume_ratio=volume_breadth_ratio,
    )

    breadth_momentum = determine_breadth_momentum(
        advance_percentage=advance_percentage,
        ema20_percentage=above_ema20_percentage,
        ema50_percentage=above_ema50_percentage,
    )

    breadth_trend = determine_breadth_trend(
        ema20_percentage=above_ema20_percentage,
        ema50_percentage=above_ema50_percentage,
        ema200_percentage=above_ema200_percentage,
    )

    breadth_strength = determine_breadth_strength(
        breadth_score
    )

    breadth_regime = determine_breadth_regime(
        score=breadth_score,
        trend=breadth_trend,
        momentum=breadth_momentum,
    )

    risk_environment = determine_risk_environment(
        score=breadth_score,
        advance_percentage=advance_percentage,
        sector_participation_percentage=(
            sector_participation_percentage
        ),
    )

    internal_market_health = (
        determine_internal_market_health(
            ema50_percentage=above_ema50_percentage,
            ema200_percentage=above_ema200_percentage,
            advance_percentage=advance_percentage,
        )
    )

    participation_quality = (
        determine_participation_quality(
            advance_percentage=advance_percentage,
            sector_participation_percentage=(
                sector_participation_percentage
            ),
            fno_breadth=fno_breadth,
        )
    )

    divergence_risk = determine_divergence_risk(
        advance_percentage=advance_percentage,
        ema20_percentage=above_ema20_percentage,
        ema200_percentage=above_ema200_percentage,
        sector_participation_percentage=(
            sector_participation_percentage
        ),
    )

    volume_data_available = (
        "Volume" in raw_dataframe.columns
        and "Average_Volume_20" in raw_dataframe.columns
    )

    market_cap_data_available = (
        "Market_Cap_Category"
        in raw_dataframe.columns
    )

    fno_data_available = (
        "Is_FnO"
        in raw_dataframe.columns
    )

    confidence = calculate_confidence(
        valid_stocks=total_stocks,
        invalid_rows=invalid_rows,
        sector_count=len(sectors),
        has_volume_data=volume_data_available,
        has_market_cap_data=market_cap_data_available,
        has_fno_data=fno_data_available,
    )

    expected_behaviour = determine_expected_behaviour(
        breadth_regime=breadth_regime,
        risk_environment=risk_environment,
        divergence_risk=divergence_risk,
    )

    concise_summary = build_concise_summary(
        breadth_score=breadth_score,
        breadth_trend=breadth_trend,
        breadth_strength=breadth_strength,
        breadth_regime=breadth_regime,
        risk_environment=risk_environment,
        internal_health=internal_market_health,
        confidence=confidence,
    )

    explanation = build_explanation(
        total_stocks=total_stocks,
        advances=advances,
        declines=declines,
        advance_percentage=advance_percentage,
        ema20_percentage=above_ema20_percentage,
        ema50_percentage=above_ema50_percentage,
        ema200_percentage=above_ema200_percentage,
        bullish_sectors=bullish_sectors,
        sector_count=len(sectors),
        breadth_score=breadth_score,
        breadth_regime=breadth_regime,
        risk_environment=risk_environment,
        internal_health=internal_market_health,
        participation_quality=participation_quality,
        divergence_risk=divergence_risk,
    )

    warnings = build_warnings(
        valid_stocks=total_stocks,
        invalid_rows=invalid_rows,
        sector_count=len(sectors),
        volume_data_available=volume_data_available,
        market_cap_data_available=market_cap_data_available,
        fno_data_available=fno_data_available,
        divergence_risk=divergence_risk,
        breadth_regime=breadth_regime,
    )

    result = MarketBreadthResult(
        requested_date=requested_date,
        analysis_date=requested_date,
        source_file=source_file,
        total_stocks=total_input_rows,
        valid_stocks=total_stocks,
        invalid_rows=invalid_rows,
        advances=advances,
        declines=declines,
        unchanged=unchanged,
        advance_percentage=advance_percentage,
        decline_percentage=decline_percentage,
        unchanged_percentage=unchanged_percentage,
        advance_decline_ratio=advance_decline_ratio,
        above_ema20_count=above_ema20_count,
        above_ema50_count=above_ema50_count,
        above_ema200_count=above_ema200_count,
        above_ema20_percentage=above_ema20_percentage,
        above_ema50_percentage=above_ema50_percentage,
        above_ema200_percentage=above_ema200_percentage,
        new_52w_high_count=new_52w_high_count,
        new_52w_low_count=new_52w_low_count,
        near_52w_high_count=near_52w_high_count,
        near_52w_low_count=near_52w_low_count,
        new_52w_high_percentage=new_52w_high_percentage,
        new_52w_low_percentage=new_52w_low_percentage,
        near_52w_high_percentage=near_52w_high_percentage,
        near_52w_low_percentage=near_52w_low_percentage,
        high_volume_advances=high_volume_advances,
        high_volume_declines=high_volume_declines,
        volume_breadth_ratio=volume_breadth_ratio,
        volume_participation=volume_participation,
        bullish_sectors=bullish_sectors,
        bearish_sectors=bearish_sectors,
        neutral_sectors=neutral_sectors,
        sector_participation_percentage=(
            sector_participation_percentage
        ),
        large_cap_breadth=large_cap_breadth,
        mid_cap_breadth=mid_cap_breadth,
        small_cap_breadth=small_cap_breadth,
        fno_breadth=fno_breadth,
        breadth_score=breadth_score,
        breadth_momentum=breadth_momentum,
        breadth_trend=breadth_trend,
        breadth_strength=breadth_strength,
        breadth_regime=breadth_regime,
        risk_environment=risk_environment,
        internal_market_health=internal_market_health,
        participation_quality=participation_quality,
        divergence_risk=divergence_risk,
        confidence=confidence,
        expected_behaviour=expected_behaviour,
        concise_summary=concise_summary,
        explanation=explanation,
        sectors=sectors,
        warnings=warnings,
        status="SUCCESS",
    )

    if export:
        export_result(
            result=result
        )

    return result


# ==========================================================
# DISPLAY HELPERS
# ==========================================================

def format_optional_ratio(
    value: float | None,
) -> str:
    """
    Format an optional ratio.
    """

    if value is None:
        return "NOT AVAILABLE"

    return f"{value:.2f}"


def display_segment(
    segment: SegmentBreadth | None,
) -> None:
    """
    Display one segment breadth result.
    """

    if segment is None:
        return

    print(
        f"{segment.name:<20}: "
        f"{segment.classification} | "
        f"Score {segment.score}% | "
        f"Advances {segment.advance_percentage:.2f}% | "
        f"Above EMA200 {segment.above_ema200_percentage:.2f}%"
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: MarketBreadthResult,
) -> None:
    """
    Display the market-breadth terminal report.
    """

    print()
    print("=" * 104)
    print("AQSD MARKET BREADTH ENGINE")
    print("=" * 104)
    print(f"Module                           : {MODULE_ID}")
    print(f"Version                          : {MODULE_VERSION}")
    print(f"Requested Date                   : {result.requested_date}")
    print(f"Analysis Date                    : {result.analysis_date}")
    print(f"Source File                      : {result.source_file}")
    print("-" * 104)

    print("UNIVERSE")
    print("-" * 104)
    print(
        f"Input Rows                        : "
        f"{result.total_stocks:,}"
    )
    print(
        f"Valid Stocks                      : "
        f"{result.valid_stocks:,}"
    )
    print(
        f"Invalid Rows                      : "
        f"{result.invalid_rows:,}"
    )
    print("-" * 104)

    print("ADVANCE / DECLINE")
    print("-" * 104)
    print(
        f"Advances                          : "
        f"{result.advances:,} "
        f"({result.advance_percentage:.2f}%)"
    )
    print(
        f"Declines                          : "
        f"{result.declines:,} "
        f"({result.decline_percentage:.2f}%)"
    )
    print(
        f"Unchanged                         : "
        f"{result.unchanged:,} "
        f"({result.unchanged_percentage:.2f}%)"
    )
    print(
        f"Advance / Decline Ratio           : "
        f"{format_optional_ratio(result.advance_decline_ratio)}"
    )
    print("-" * 104)

    print("MOVING-AVERAGE BREADTH")
    print("-" * 104)
    print(
        f"Above EMA20                       : "
        f"{result.above_ema20_count:,} "
        f"({result.above_ema20_percentage:.2f}%)"
    )
    print(
        f"Above EMA50                       : "
        f"{result.above_ema50_count:,} "
        f"({result.above_ema50_percentage:.2f}%)"
    )
    print(
        f"Above EMA200                      : "
        f"{result.above_ema200_count:,} "
        f"({result.above_ema200_percentage:.2f}%)"
    )
    print("-" * 104)

    print("52-WEEK BREADTH")
    print("-" * 104)
    print(
        f"New 52-Week Highs                 : "
        f"{result.new_52w_high_count:,} "
        f"({result.new_52w_high_percentage:.2f}%)"
    )
    print(
        f"New 52-Week Lows                  : "
        f"{result.new_52w_low_count:,} "
        f"({result.new_52w_low_percentage:.2f}%)"
    )
    print(
        f"Near 52-Week High                 : "
        f"{result.near_52w_high_count:,} "
        f"({result.near_52w_high_percentage:.2f}%)"
    )
    print(
        f"Near 52-Week Low                  : "
        f"{result.near_52w_low_count:,} "
        f"({result.near_52w_low_percentage:.2f}%)"
    )
    print("-" * 104)

    print("VOLUME BREADTH")
    print("-" * 104)
    print(
        f"High-Volume Advances              : "
        f"{result.high_volume_advances:,}"
    )
    print(
        f"High-Volume Declines              : "
        f"{result.high_volume_declines:,}"
    )
    print(
        f"Volume Breadth Ratio              : "
        f"{format_optional_ratio(result.volume_breadth_ratio)}"
    )
    print(
        f"Volume Participation              : "
        f"{result.volume_participation}"
    )
    print("-" * 104)

    print("SECTOR PARTICIPATION")
    print("-" * 104)
    print(
        f"Bullish Sectors                   : "
        f"{result.bullish_sectors}"
    )
    print(
        f"Bearish Sectors                   : "
        f"{result.bearish_sectors}"
    )
    print(
        f"Neutral Sectors                   : "
        f"{result.neutral_sectors}"
    )
    print(
        f"Bullish Sector Participation      : "
        f"{result.sector_participation_percentage:.2f}%"
    )
    print("-" * 104)

    print("MARKET SEGMENTS")
    print("-" * 104)
    display_segment(
        result.large_cap_breadth
    )
    display_segment(
        result.mid_cap_breadth
    )
    display_segment(
        result.small_cap_breadth
    )
    display_segment(
        result.fno_breadth
    )
    print("-" * 104)

    print("BREADTH CLASSIFICATION")
    print("-" * 104)
    print(
        f"Breadth Score                     : "
        f"{result.breadth_score}%"
    )
    print(
        f"Breadth Momentum                  : "
        f"{result.breadth_momentum}"
    )
    print(
        f"Breadth Trend                     : "
        f"{result.breadth_trend}"
    )
    print(
        f"Breadth Strength                  : "
        f"{result.breadth_strength}"
    )
    print(
        f"Breadth Regime                    : "
        f"{result.breadth_regime}"
    )
    print(
        f"Risk Environment                  : "
        f"{result.risk_environment}"
    )
    print(
        f"Internal Market Health            : "
        f"{result.internal_market_health}"
    )
    print(
        f"Participation Quality             : "
        f"{result.participation_quality}"
    )
    print(
        f"Divergence Risk                   : "
        f"{result.divergence_risk}"
    )
    print(
        f"Confidence                        : "
        f"{result.confidence}%"
    )
    print("-" * 104)

    print("EXPECTED BEHAVIOUR")
    print("-" * 104)
    print(result.expected_behaviour)
    print("-" * 104)

    print("CONCISE SUMMARY")
    print("-" * 104)
    print(result.concise_summary)
    print("-" * 104)

    print("TOP BULLISH SECTORS")
    print("-" * 104)

    for sector in result.sectors[:5]:
        print(
            f"{sector.sector:<30}: "
            f"{sector.classification} | "
            f"Score {sector.score}%"
        )

    print("-" * 104)
    print("WEAKEST SECTORS")
    print("-" * 104)

    for sector in result.sectors[-5:]:
        print(
            f"{sector.sector:<30}: "
            f"{sector.classification} | "
            f"Score {sector.score}%"
        )

    print("-" * 104)
    print("WARNINGS")
    print("-" * 104)

    for number, warning in enumerate(
        result.warnings,
        start=1,
    ):
        print(f"{number}. {warning}")

    print("-" * 104)
    print("EXPLANATION")
    print("-" * 104)
    print(result.explanation)
    print("-" * 104)
    print(
        "Method                           : "
        "RULE-BASED MARKET BREADTH ANALYSIS"
    )
    print(
        f"Status                           : "
        f"{result.status}"
    )
    print("=" * 104)


# ==========================================================
# COMMAND LINE
# ==========================================================

def normalize_sheet_argument(
    value: object,
) -> str | int:
    """
    Convert a numeric sheet argument into an integer.
    """

    text = str(value).strip()

    if text.isdigit():
        return int(text)

    return text


def parse_date(
    value: str,
) -> date:
    """
    Convert YYYY-MM-DD text into a date.
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


def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Analyse NSE market breadth using a prepared "
            "CSV or Excel market-universe snapshot."
        )
    )

    parser.add_argument(
        "--date",
        required=True,
        help="Analysis date in YYYY-MM-DD format.",
    )

    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help=(
            "Path to the market-breadth CSV or Excel file. "
            f"Default: {DEFAULT_INPUT_FILE}"
        ),
    )

    parser.add_argument(
        "--sheet",
        default=0,
        help=(
            "Excel worksheet name or zero-based worksheet number. "
            "Default: first worksheet."
        ),
    )

    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Do not create CSV and Excel output files.",
    )

    return parser.parse_args()


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    try:
        result = run_market_breadth_engine(
            requested_date=parse_date(
                arguments.date
            ),
            source_file=(
                arguments.input
                .expanduser()
                .resolve()
            ),
            sheet_name=normalize_sheet_argument(
                arguments.sheet
            ),
            export=not arguments.no_export,
        )

    except Exception as exc:
        print()
        print("=" * 104)
        print("AQSD MARKET BREADTH ENGINE")
        print("=" * 104)
        print("Status : FAILED")
        print(f"Reason : {exc}")
        print("=" * 104)

        raise SystemExit(1) from exc

    display_result(
        result
    )


if __name__ == "__main__":
    main()
"""
AQSD
Market History Trend / Persistence Engine

Module : MHT-001
Version: 1.0.0
Author : AQSD

Purpose
-------
Analyse multi-session trends and persistence in AQSD's stored
Market Intelligence history.

Reads:
Output/Market_History/market_intelligence_history.csv

Measures:
- 5-session and 10-session bullish probability trend
- 5-session and 10-session bearish probability trend
- 5-session and 10-session neutral probability trend
- Confidence trend
- Bias persistence
- Regime persistence
- Risk persistence
- Directional consistency
- Regime stability
- Historical maturity

This engine does NOT:
- Call FYERS
- Download market data
- Re-run Market Master Decision
- Generate BUY / SELL / SHORT orders
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import pandas as pd


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "MHT-001"
MODULE_VERSION: Final[str] = "1.0.0"

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

HISTORY_FILE: Final[Path] = (
    BASE_DIR
    / "Output"
    / "Market_History"
    / "market_intelligence_history.csv"
)

SHORT_WINDOW: Final[int] = 5
MEDIUM_WINDOW: Final[int] = 10


# ==========================================================
# RESULT MODEL
# ==========================================================

@dataclass(frozen=True)
class MarketHistoryTrendResult:
    available: bool

    latest_date: str
    total_sessions: int

    current_bias: str
    current_regime: str
    current_risk: str

    bullish_5d_trend: str
    bearish_5d_trend: str
    neutral_5d_trend: str
    confidence_5d_trend: str

    bullish_10d_trend: str
    bearish_10d_trend: str
    neutral_10d_trend: str
    confidence_10d_trend: str

    bias_persistence_sessions: int
    regime_persistence_sessions: int
    risk_persistence_sessions: int

    bias_stability: str
    regime_stability: str
    directional_consistency: str

    historical_maturity: str
    trend_quality: str

    summary: str
    explanation: str
    status: str


# ==========================================================
# HELPERS
# ==========================================================

def clean_text(
    value: object,
) -> str:
    if value is None:
        return ""

    return str(
        value
    ).strip().upper()


def safe_float(
    value: object,
) -> float:
    try:
        number = float(
            value
        )

        if pd.isna(
            number
        ):
            return 0.0

        return number

    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def load_history(
    history_file: Path,
) -> pd.DataFrame:
    """
    Load and validate Market Intelligence history.
    """

    if not history_file.exists():
        raise FileNotFoundError(
            "Market Intelligence history file not found:\n"
            f"{history_file}"
        )

    frame = pd.read_csv(
        history_file,
        low_memory=False,
    )

    required = {
        "analysis_date",
        "final_market_bias",
        "primary_regime",
        "risk_level",
        "bullish_probability",
        "bearish_probability",
        "neutral_probability",
        "confidence",
    }

    missing = required - set(
        frame.columns
    )

    if missing:
        raise RuntimeError(
            "Market History is missing required columns: "
            + ", ".join(
                sorted(
                    missing
                )
            )
        )

    frame["analysis_date"] = pd.to_datetime(
        frame["analysis_date"],
        errors="coerce",
    )

    frame = (
        frame
        .dropna(
            subset=[
                "analysis_date"
            ]
        )
        .sort_values(
            "analysis_date"
        )
        .drop_duplicates(
            subset=[
                "analysis_date"
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )

    return frame


def persistence_count(
    series: pd.Series,
) -> int:
    """
    Count consecutive matching values from latest session backwards.
    """

    cleaned = (
        series
        .astype(str)
        .str.strip()
        .str.upper()
    )

    if cleaned.empty:
        return 0

    latest = cleaned.iloc[-1]

    count = 0

    for value in reversed(
        cleaned.tolist()
    ):
        if value == latest:
            count += 1
        else:
            break

    return count


def trend_from_series(
    values: pd.Series,
) -> str:
    """
    Classify broad movement over a session window.
    """

    numeric = pd.to_numeric(
        values,
        errors="coerce",
    ).dropna()

    if len(
        numeric
    ) < 2:
        return "INSUFFICIENT HISTORY"

    first = float(
        numeric.iloc[0]
    )

    last = float(
        numeric.iloc[-1]
    )

    change = (
        last
        - first
    )

    if change >= 5:
        return "STRONGLY RISING"

    if change >= 2:
        return "RISING"

    if change <= -5:
        return "STRONGLY FALLING"

    if change <= -2:
        return "FALLING"

    return "STABLE"


def categorical_stability(
    series: pd.Series,
) -> str:
    """
    Measure stability of a categorical intelligence field.
    """

    cleaned = (
        series
        .astype(str)
        .str.strip()
        .str.upper()
    )

    if len(
        cleaned
    ) < 2:
        return "INSUFFICIENT HISTORY"

    unique_count = cleaned.nunique()

    if unique_count == 1:
        return "VERY STABLE"

    if unique_count == 2:
        return "STABLE"

    if unique_count <= 3:
        return "MIXED"

    return "UNSTABLE"


def directional_consistency(
    frame: pd.DataFrame,
) -> str:
    """
    Evaluate consistency between bullish and bearish probabilities.
    """

    if len(
        frame
    ) < 2:
        return "INSUFFICIENT HISTORY"

    bullish = pd.to_numeric(
        frame[
            "bullish_probability"
        ],
        errors="coerce",
    )

    bearish = pd.to_numeric(
        frame[
            "bearish_probability"
        ],
        errors="coerce",
    )

    valid = pd.DataFrame(
        {
            "bullish": bullish,
            "bearish": bearish,
        }
    ).dropna()

    if valid.empty:
        return "NOT AVAILABLE"

    bullish_days = (
        valid[
            "bullish"
        ]
        > valid[
            "bearish"
        ]
    ).sum()

    bearish_days = (
        valid[
            "bearish"
        ]
        > valid[
            "bullish"
        ]
    ).sum()

    total = len(
        valid
    )

    bullish_share = (
        bullish_days
        / total
        * 100
    )

    bearish_share = (
        bearish_days
        / total
        * 100
    )

    if bullish_share >= 80:
        return "CONSISTENTLY BULLISH"

    if bearish_share >= 80:
        return "CONSISTENTLY BEARISH"

    if (
        bullish_share >= 60
        and bullish_share > bearish_share
    ):
        return "BULLISH LEAN"

    if (
        bearish_share >= 60
        and bearish_share > bullish_share
    ):
        return "BEARISH LEAN"

    return "MIXED"


def classify_maturity(
    sessions: int,
) -> str:
    """
    Classify depth of historical intelligence.
    """

    if sessions < 2:
        return "STARTING"

    if sessions < 5:
        return "VERY LIMITED"

    if sessions < 10:
        return "LIMITED"

    if sessions < 20:
        return "DEVELOPING"

    if sessions < 60:
        return "MODERATE"

    return "MATURE"


def classify_quality(
    sessions: int,
) -> str:
    """
    Grade confidence in historical-trend analysis.
    """

    if sessions < 2:
        return "D"

    if sessions < 5:
        return "C"

    if sessions < 10:
        return "B"

    return "A"


# ==========================================================
# ENGINE
# ==========================================================

def run_market_history_trend_engine(
    *,
    history_file: Path = HISTORY_FILE,
) -> MarketHistoryTrendResult:
    """
    Run AQSD multi-session historical trend analysis.
    """

    history = load_history(
        history_file
    )

    total_sessions = len(
        history
    )

    if total_sessions == 0:
        return MarketHistoryTrendResult(
            available=False,
            latest_date="",
            total_sessions=0,

            current_bias="",
            current_regime="",
            current_risk="",

            bullish_5d_trend="INSUFFICIENT HISTORY",
            bearish_5d_trend="INSUFFICIENT HISTORY",
            neutral_5d_trend="INSUFFICIENT HISTORY",
            confidence_5d_trend="INSUFFICIENT HISTORY",

            bullish_10d_trend="INSUFFICIENT HISTORY",
            bearish_10d_trend="INSUFFICIENT HISTORY",
            neutral_10d_trend="INSUFFICIENT HISTORY",
            confidence_10d_trend="INSUFFICIENT HISTORY",

            bias_persistence_sessions=0,
            regime_persistence_sessions=0,
            risk_persistence_sessions=0,

            bias_stability="INSUFFICIENT HISTORY",
            regime_stability="INSUFFICIENT HISTORY",
            directional_consistency="INSUFFICIENT HISTORY",

            historical_maturity="STARTING",
            trend_quality="D",

            summary=(
                "No historical Market Intelligence sessions "
                "are currently available."
            ),

            explanation=(
                "AQSD cannot perform persistence or multi-session "
                "trend analysis until Market History contains at "
                "least one valid recorded session."
            ),

            status="INSUFFICIENT HISTORY",
        )

    latest = history.iloc[-1]

    latest_date = (
        latest[
            "analysis_date"
        ]
        .date()
        .isoformat()
    )

    current_bias = clean_text(
        latest[
            "final_market_bias"
        ]
    )

    current_regime = clean_text(
        latest[
            "primary_regime"
        ]
    )

    current_risk = clean_text(
        latest[
            "risk_level"
        ]
    )

    window_5 = history.tail(
        SHORT_WINDOW
    )

    window_10 = history.tail(
        MEDIUM_WINDOW
    )

    bullish_5d = trend_from_series(
        window_5[
            "bullish_probability"
        ]
    )

    bearish_5d = trend_from_series(
        window_5[
            "bearish_probability"
        ]
    )

    neutral_5d = trend_from_series(
        window_5[
            "neutral_probability"
        ]
    )

    confidence_5d = trend_from_series(
        window_5[
            "confidence"
        ]
    )

    bullish_10d = trend_from_series(
        window_10[
            "bullish_probability"
        ]
    )

    bearish_10d = trend_from_series(
        window_10[
            "bearish_probability"
        ]
    )

    neutral_10d = trend_from_series(
        window_10[
            "neutral_probability"
        ]
    )

    confidence_10d = trend_from_series(
        window_10[
            "confidence"
        ]
    )

    bias_persistence = persistence_count(
        history[
            "final_market_bias"
        ]
    )

    regime_persistence = persistence_count(
        history[
            "primary_regime"
        ]
    )

    risk_persistence = persistence_count(
        history[
            "risk_level"
        ]
    )

    bias_stability = categorical_stability(
        window_10[
            "final_market_bias"
        ]
    )

    regime_stability = categorical_stability(
        window_10[
            "primary_regime"
        ]
    )

    consistency = directional_consistency(
        window_10
    )

    maturity = classify_maturity(
        total_sessions
    )

    quality = classify_quality(
        total_sessions
    )

    available = (
        total_sessions >= 2
    )

    status = (
        "SUCCESS"
        if available
        else "INSUFFICIENT HISTORY"
    )

    summary = (
        f"{total_sessions} RECORDED SESSION(S) | "
        f"BIAS {current_bias} | "
        f"REGIME {current_regime} | "
        f"5D BULL {bullish_5d} | "
        f"5D BEAR {bearish_5d} | "
        f"REGIME PERSISTENCE {regime_persistence} | "
        f"MATURITY {maturity} | "
        f"QUALITY {quality}"
    )

    explanation = (
        f"AQSD currently has {total_sessions} recorded Market "
        f"Intelligence session(s). The latest market bias is "
        f"{current_bias}, while the primary regime is "
        f"{current_regime}. The current regime has persisted for "
        f"{regime_persistence} consecutive recorded session(s), "
        f"the market bias for {bias_persistence} session(s), and "
        f"the current risk classification for "
        f"{risk_persistence} session(s). "
        f"Over the most recent five available sessions, bullish "
        f"probability is {bullish_5d}, bearish probability is "
        f"{bearish_5d}, neutral probability is {neutral_5d}, and "
        f"confidence is {confidence_5d}. "
        f"Directional consistency is {consistency}. "
        f"Historical maturity is classified as {maturity}, with "
        f"trend-analysis quality grade {quality}."
    )

    return MarketHistoryTrendResult(
        available=available,

        latest_date=latest_date,
        total_sessions=total_sessions,

        current_bias=current_bias,
        current_regime=current_regime,
        current_risk=current_risk,

        bullish_5d_trend=bullish_5d,
        bearish_5d_trend=bearish_5d,
        neutral_5d_trend=neutral_5d,
        confidence_5d_trend=confidence_5d,

        bullish_10d_trend=bullish_10d,
        bearish_10d_trend=bearish_10d,
        neutral_10d_trend=neutral_10d,
        confidence_10d_trend=confidence_10d,

        bias_persistence_sessions=(
            bias_persistence
        ),

        regime_persistence_sessions=(
            regime_persistence
        ),

        risk_persistence_sessions=(
            risk_persistence
        ),

        bias_stability=bias_stability,
        regime_stability=regime_stability,

        directional_consistency=(
            consistency
        ),

        historical_maturity=maturity,
        trend_quality=quality,

        summary=summary,
        explanation=explanation,

        status=status,
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: MarketHistoryTrendResult,
) -> None:
    """
    Display multi-session historical trend analysis.
    """

    print()
    print("=" * 100)
    print("AQSD MARKET HISTORY TREND / PERSISTENCE ENGINE")
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
        f"Latest Date               : "
        f"{result.latest_date or 'NOT AVAILABLE'}"
    )

    print(
        f"Recorded Sessions         : "
        f"{result.total_sessions}"
    )

    print("-" * 100)

    print("CURRENT STATE")
    print("-" * 100)

    print(
        f"Market Bias               : "
        f"{result.current_bias or 'NOT AVAILABLE'}"
    )

    print(
        f"Primary Regime            : "
        f"{result.current_regime or 'NOT AVAILABLE'}"
    )

    print(
        f"Risk                      : "
        f"{result.current_risk or 'NOT AVAILABLE'}"
    )

    print("-" * 100)

    print("5-SESSION TREND")
    print("-" * 100)

    print(
        f"Bullish Probability       : "
        f"{result.bullish_5d_trend}"
    )

    print(
        f"Bearish Probability       : "
        f"{result.bearish_5d_trend}"
    )

    print(
        f"Neutral Probability       : "
        f"{result.neutral_5d_trend}"
    )

    print(
        f"Confidence                : "
        f"{result.confidence_5d_trend}"
    )

    print("-" * 100)

    print("10-SESSION TREND")
    print("-" * 100)

    print(
        f"Bullish Probability       : "
        f"{result.bullish_10d_trend}"
    )

    print(
        f"Bearish Probability       : "
        f"{result.bearish_10d_trend}"
    )

    print(
        f"Neutral Probability       : "
        f"{result.neutral_10d_trend}"
    )

    print(
        f"Confidence                : "
        f"{result.confidence_10d_trend}"
    )

    print("-" * 100)

    print("PERSISTENCE")
    print("-" * 100)

    print(
        f"Bias Persistence          : "
        f"{result.bias_persistence_sessions} session(s)"
    )

    print(
        f"Regime Persistence        : "
        f"{result.regime_persistence_sessions} session(s)"
    )

    print(
        f"Risk Persistence          : "
        f"{result.risk_persistence_sessions} session(s)"
    )

    print("-" * 100)

    print("STABILITY")
    print("-" * 100)

    print(
        f"Bias Stability            : "
        f"{result.bias_stability}"
    )

    print(
        f"Regime Stability          : "
        f"{result.regime_stability}"
    )

    print(
        f"Directional Consistency   : "
        f"{result.directional_consistency}"
    )

    print("-" * 100)

    print("HISTORICAL QUALITY")
    print("-" * 100)

    print(
        f"Historical Maturity       : "
        f"{result.historical_maturity}"
    )

    print(
        f"Trend Quality             : "
        f"{result.trend_quality}"
    )

    print("-" * 100)

    print("CONCISE SUMMARY")
    print("-" * 100)

    print(
        result.summary
    )

    print("-" * 100)

    print("EXPLANATION")
    print("-" * 100)

    print(
        result.explanation
    )

    print("-" * 100)

    print(
        f"Status                    : "
        f"{result.status}"
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
            "Analyse multi-session AQSD Market Intelligence "
            "trends and persistence."
        )
    )

    parser.add_argument(
        "--history",
        type=Path,
        default=HISTORY_FILE,
        help=(
            "Path to market_intelligence_history.csv"
        ),
    )

    return parser.parse_args()


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    try:
        result = run_market_history_trend_engine(
            history_file=(
                arguments.history
                .expanduser()
                .resolve()
            )
        )

    except Exception as exc:
        print()
        print("=" * 100)
        print(
            "AQSD MARKET HISTORY TREND / "
            "PERSISTENCE ENGINE"
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

    display_result(
        result
    )


if __name__ == "__main__":
    main()
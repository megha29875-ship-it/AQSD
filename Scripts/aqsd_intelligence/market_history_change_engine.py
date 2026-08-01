"""
AQSD
Market History Change Engine

Module : MHC-001
Version: 1.0.0
Author : AQSD

Purpose
-------
Analyse changes in AQSD's stored daily Market Intelligence.

This engine does NOT:
- Download market data.
- Call FYERS.
- Re-run the Market Master Decision Engine.
- Generate BUY / SELL / SHORT orders.

It reads:

Output/Market_History/market_intelligence_history.csv

and measures:

- Day-over-day probability change
- Confidence change
- Market bias transition
- Regime transition
- Risk transition
- Multi-session probability trend
- Regime persistence
- Directional persistence
- Intelligence momentum
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

MODULE_ID: Final[str] = "MHC-001"
MODULE_VERSION: Final[str] = "1.0.0"

BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]

HISTORY_FILE: Final[Path] = (
    BASE_DIR
    / "Output"
    / "Market_History"
    / "market_intelligence_history.csv"
)

DEFAULT_LOOKBACK: Final[int] = 5


# ==========================================================
# RESULT MODEL
# ==========================================================

@dataclass(frozen=True)
class MarketHistoryChangeResult:
    """
    Final AQSD historical-change assessment.
    """

    available: bool

    current_date: str
    previous_date: str

    current_bias: str
    previous_bias: str
    bias_transition: str

    current_regime: str
    previous_regime: str
    regime_transition: str

    current_risk: str
    previous_risk: str
    risk_transition: str

    bullish_probability: float
    bearish_probability: float
    neutral_probability: float

    bullish_change: float
    bearish_change: float
    neutral_change: float

    current_confidence: float
    confidence_change: float

    bullish_trend: str
    bearish_trend: str
    neutral_trend: str
    confidence_trend: str

    regime_persistence_sessions: int
    bias_persistence_sessions: int

    directional_momentum: str
    intelligence_momentum: str

    quality: str
    status: str

    explanation: str


# ==========================================================
# HELPERS
# ==========================================================

def clean_text(
    value: object,
) -> str:
    """
    Convert any value to normalized text.
    """

    if value is None:
        return ""

    return str(
        value
    ).strip().upper()


def safe_float(
    value: object,
    default: float = 0.0,
) -> float:
    """
    Convert a value to float safely.
    """

    try:
        if value is None:
            return default

        number = float(
            value
        )

        if pd.isna(
            number
        ):
            return default

        return number

    except (
        TypeError,
        ValueError,
    ):
        return default


def classify_change(
    value: float,
    *,
    positive_threshold: float = 2.0,
    negative_threshold: float = -2.0,
) -> str:
    """
    Classify a numerical change.
    """

    if value >= positive_threshold:
        return "RISING"

    if value <= negative_threshold:
        return "FALLING"

    return "STABLE"


def calculate_series_trend(
    values: pd.Series,
) -> str:
    """
    Determine broad trend over available sessions.
    """

    numeric = pd.to_numeric(
        values,
        errors="coerce",
    ).dropna()

    if len(
        numeric
    ) < 2:
        return "INSUFFICIENT HISTORY"

    first_value = float(
        numeric.iloc[0]
    )

    last_value = float(
        numeric.iloc[-1]
    )

    change = (
        last_value
        - first_value
    )

    return classify_change(
        change
    )


def persistence_count(
    values: pd.Series,
) -> int:
    """
    Count consecutive identical values backwards
    from the latest session.
    """

    cleaned = (
        values
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


# ==========================================================
# HISTORY LOADER
# ==========================================================

def load_history(
    history_file: Path = HISTORY_FILE,
) -> pd.DataFrame:
    """
    Load and validate AQSD Market Intelligence History.
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

    required_columns = {
        "analysis_date",
        "final_market_bias",
        "primary_regime",
        "risk_level",
        "bullish_probability",
        "bearish_probability",
        "neutral_probability",
        "confidence",
    }

    missing = (
        required_columns
        - set(
            frame.columns
        )
    )

    if missing:
        raise RuntimeError(
            "Market History file is missing columns: "
            + ", ".join(
                sorted(
                    missing
                )
            )
        )

    frame[
        "analysis_date"
    ] = pd.to_datetime(
        frame[
            "analysis_date"
        ],
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


# ==========================================================
# TRANSITION LOGIC
# ==========================================================

def classify_transition(
    previous: str,
    current: str,
) -> str:
    """
    Describe categorical transition.
    """

    previous = clean_text(
        previous
    )

    current = clean_text(
        current
    )

    if not previous or not current:
        return "NOT AVAILABLE"

    if previous == current:
        return "UNCHANGED"

    return (
        f"{previous} -> {current}"
    )


def classify_risk_transition(
    previous: str,
    current: str,
) -> str:
    """
    Determine whether risk is rising or falling.
    """

    risk_rank = {
        "VERY LOW": 1,
        "LOW": 2,
        "LOW TO MODERATE": 3,
        "MODERATE": 4,
        "MODERATE TO HIGH": 5,
        "HIGH": 6,
        "VERY HIGH": 7,
    }

    previous_text = clean_text(
        previous
    )

    current_text = clean_text(
        current
    )

    previous_rank = risk_rank.get(
        previous_text
    )

    current_rank = risk_rank.get(
        current_text
    )

    if (
        previous_rank is None
        or current_rank is None
    ):
        return classify_transition(
            previous_text,
            current_text,
        )

    if current_rank > previous_rank:
        return "RISK INCREASING"

    if current_rank < previous_rank:
        return "RISK DECREASING"

    return "RISK STABLE"


# ==========================================================
# MOMENTUM LOGIC
# ==========================================================

def classify_directional_momentum(
    bullish_change: float,
    bearish_change: float,
    neutral_change: float,
) -> str:
    """
    Determine whether directional pressure is improving,
    deteriorating or remaining mixed.
    """

    if (
        bullish_change >= 2.0
        and bearish_change <= 0
    ):
        return "BULLISH MOMENTUM IMPROVING"

    if (
        bearish_change >= 2.0
        and bullish_change <= 0
    ):
        return "BEARISH MOMENTUM IMPROVING"

    if neutral_change >= 3.0:
        return "NEUTRALITY INCREASING"

    if (
        bullish_change > 0
        and bearish_change > 0
    ):
        return "TWO-SIDED RISK INCREASING"

    return "MIXED / STABLE MOMENTUM"


def classify_intelligence_momentum(
    *,
    bullish_trend: str,
    bearish_trend: str,
    confidence_trend: str,
    risk_transition: str,
) -> str:
    """
    Consolidate multi-session intelligence momentum.
    """

    if (
        bullish_trend == "RISING"
        and bearish_trend != "RISING"
        and confidence_trend == "RISING"
    ):
        return "BULLISH INTELLIGENCE STRENGTHENING"

    if (
        bearish_trend == "RISING"
        and bullish_trend != "RISING"
        and confidence_trend == "RISING"
    ):
        return "BEARISH INTELLIGENCE STRENGTHENING"

    if (
        confidence_trend == "FALLING"
        or risk_transition == "RISK INCREASING"
    ):
        return "INTELLIGENCE QUALITY DETERIORATING"

    if (
        bullish_trend == "STABLE"
        and bearish_trend == "STABLE"
        and confidence_trend == "STABLE"
    ):
        return "INTELLIGENCE STABLE"

    return "INTELLIGENCE MIXED"


# ==========================================================
# QUALITY
# ==========================================================

def calculate_quality(
    history_sessions: int,
    current_confidence: float,
) -> str:
    """
    Grade historical-change analysis quality.
    """

    if history_sessions < 2:
        return "D"

    if history_sessions < 5:
        return "C"

    if (
        history_sessions >= 10
        and current_confidence >= 65
    ):
        return "A"

    if history_sessions >= 5:
        return "B"

    return "C"


# ==========================================================
# ENGINE
# ==========================================================

def run_market_history_change_engine(
    *,
    history_file: Path = HISTORY_FILE,
    lookback_sessions: int = DEFAULT_LOOKBACK,
) -> MarketHistoryChangeResult:
    """
    Run AQSD Market History Change analysis.
    """

    history = load_history(
        history_file
    )

    if len(
        history
    ) < 2:
        return MarketHistoryChangeResult(
            available=False,

            current_date=(
                history.iloc[-1][
                    "analysis_date"
                ].date().isoformat()
                if len(history)
                else ""
            ),

            previous_date="",

            current_bias=(
                clean_text(
                    history.iloc[-1][
                        "final_market_bias"
                    ]
                )
                if len(history)
                else ""
            ),

            previous_bias="",
            bias_transition="INSUFFICIENT HISTORY",

            current_regime=(
                clean_text(
                    history.iloc[-1][
                        "primary_regime"
                    ]
                )
                if len(history)
                else ""
            ),

            previous_regime="",
            regime_transition="INSUFFICIENT HISTORY",

            current_risk=(
                clean_text(
                    history.iloc[-1][
                        "risk_level"
                    ]
                )
                if len(history)
                else ""
            ),

            previous_risk="",
            risk_transition="INSUFFICIENT HISTORY",

            bullish_probability=0.0,
            bearish_probability=0.0,
            neutral_probability=0.0,

            bullish_change=0.0,
            bearish_change=0.0,
            neutral_change=0.0,

            current_confidence=0.0,
            confidence_change=0.0,

            bullish_trend="INSUFFICIENT HISTORY",
            bearish_trend="INSUFFICIENT HISTORY",
            neutral_trend="INSUFFICIENT HISTORY",
            confidence_trend="INSUFFICIENT HISTORY",

            regime_persistence_sessions=1,
            bias_persistence_sessions=1,

            directional_momentum=(
                "INSUFFICIENT HISTORY"
            ),

            intelligence_momentum=(
                "INSUFFICIENT HISTORY"
            ),

            quality="D",
            status="INSUFFICIENT HISTORY",

            explanation=(
                "AQSD requires at least two recorded "
                "Market Intelligence sessions before "
                "historical change analysis is available."
            ),
        )

    lookback_sessions = max(
        2,
        int(
            lookback_sessions
        ),
    )

    window = history.tail(
        lookback_sessions
    ).copy()

    previous = history.iloc[-2]
    current = history.iloc[-1]

    bullish_probability = safe_float(
        current[
            "bullish_probability"
        ]
    )

    bearish_probability = safe_float(
        current[
            "bearish_probability"
        ]
    )

    neutral_probability = safe_float(
        current[
            "neutral_probability"
        ]
    )

    previous_bullish = safe_float(
        previous[
            "bullish_probability"
        ]
    )

    previous_bearish = safe_float(
        previous[
            "bearish_probability"
        ]
    )

    previous_neutral = safe_float(
        previous[
            "neutral_probability"
        ]
    )

    bullish_change = round(
        bullish_probability
        - previous_bullish,
        1,
    )

    bearish_change = round(
        bearish_probability
        - previous_bearish,
        1,
    )

    neutral_change = round(
        neutral_probability
        - previous_neutral,
        1,
    )

    current_confidence = safe_float(
        current[
            "confidence"
        ]
    )

    previous_confidence = safe_float(
        previous[
            "confidence"
        ]
    )

    confidence_change = round(
        current_confidence
        - previous_confidence,
        1,
    )

    current_bias = clean_text(
        current[
            "final_market_bias"
        ]
    )

    previous_bias = clean_text(
        previous[
            "final_market_bias"
        ]
    )

    current_regime = clean_text(
        current[
            "primary_regime"
        ]
    )

    previous_regime = clean_text(
        previous[
            "primary_regime"
        ]
    )

    current_risk = clean_text(
        current[
            "risk_level"
        ]
    )

    previous_risk = clean_text(
        previous[
            "risk_level"
        ]
    )

    bullish_trend = calculate_series_trend(
        window[
            "bullish_probability"
        ]
    )

    bearish_trend = calculate_series_trend(
        window[
            "bearish_probability"
        ]
    )

    neutral_trend = calculate_series_trend(
        window[
            "neutral_probability"
        ]
    )

    confidence_trend = calculate_series_trend(
        window[
            "confidence"
        ]
    )

    regime_persistence = persistence_count(
        history[
            "primary_regime"
        ]
    )

    bias_persistence = persistence_count(
        history[
            "final_market_bias"
        ]
    )

    risk_transition = (
        classify_risk_transition(
            previous_risk,
            current_risk,
        )
    )

    directional_momentum = (
        classify_directional_momentum(
            bullish_change,
            bearish_change,
            neutral_change,
        )
    )

    intelligence_momentum = (
        classify_intelligence_momentum(
            bullish_trend=bullish_trend,
            bearish_trend=bearish_trend,
            confidence_trend=confidence_trend,
            risk_transition=risk_transition,
        )
    )

    quality = calculate_quality(
        len(
            history
        ),
        current_confidence,
    )

    explanation = (
        f"AQSD compared {previous['analysis_date'].date().isoformat()} "
        f"with {current['analysis_date'].date().isoformat()}. "
        f"Bullish probability changed by "
        f"{bullish_change:+.1f} points, bearish probability by "
        f"{bearish_change:+.1f} points and neutral probability by "
        f"{neutral_change:+.1f} points. "
        f"Confidence changed by {confidence_change:+.1f} points. "
        f"The current regime is {current_regime} and has persisted "
        f"for {regime_persistence} recorded session(s). "
        f"The current market bias is {current_bias} and has persisted "
        f"for {bias_persistence} recorded session(s). "
        f"Directional momentum is classified as "
        f"{directional_momentum}. "
        f"Overall historical intelligence momentum is "
        f"{intelligence_momentum}."
    )

    return MarketHistoryChangeResult(
        available=True,

        current_date=(
            current[
                "analysis_date"
            ].date().isoformat()
        ),

        previous_date=(
            previous[
                "analysis_date"
            ].date().isoformat()
        ),

        current_bias=current_bias,
        previous_bias=previous_bias,

        bias_transition=classify_transition(
            previous_bias,
            current_bias,
        ),

        current_regime=current_regime,
        previous_regime=previous_regime,

        regime_transition=classify_transition(
            previous_regime,
            current_regime,
        ),

        current_risk=current_risk,
        previous_risk=previous_risk,

        risk_transition=risk_transition,

        bullish_probability=(
            bullish_probability
        ),

        bearish_probability=(
            bearish_probability
        ),

        neutral_probability=(
            neutral_probability
        ),

        bullish_change=bullish_change,
        bearish_change=bearish_change,
        neutral_change=neutral_change,

        current_confidence=current_confidence,
        confidence_change=confidence_change,

        bullish_trend=bullish_trend,
        bearish_trend=bearish_trend,
        neutral_trend=neutral_trend,
        confidence_trend=confidence_trend,

        regime_persistence_sessions=(
            regime_persistence
        ),

        bias_persistence_sessions=(
            bias_persistence
        ),

        directional_momentum=(
            directional_momentum
        ),

        intelligence_momentum=(
            intelligence_momentum
        ),

        quality=quality,
        status="SUCCESS",

        explanation=explanation,
    )


# ==========================================================
# DISPLAY
# ==========================================================

def display_result(
    result: MarketHistoryChangeResult,
) -> None:
    """
    Display Market History Change analysis.
    """

    print()
    print("=" * 100)
    print("AQSD MARKET HISTORY CHANGE ENGINE")
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
        f"Current Date              : "
        f"{result.current_date}"
    )

    print(
        f"Previous Date             : "
        f"{result.previous_date or 'NOT AVAILABLE'}"
    )

    print("-" * 100)

    if not result.available:
        print(
            f"Status                    : "
            f"{result.status}"
        )

        print(
            f"Explanation               : "
            f"{result.explanation}"
        )

        print("=" * 100)
        return

    print("MARKET STATE TRANSITION")
    print("-" * 100)

    print(
        f"Bias                      : "
        f"{result.bias_transition}"
    )

    print(
        f"Regime                    : "
        f"{result.regime_transition}"
    )

    print(
        f"Risk                      : "
        f"{result.risk_transition}"
    )

    print("-" * 100)

    print("PROBABILITY CHANGE")
    print("-" * 100)

    print(
        f"Bullish Probability       : "
        f"{result.bullish_probability:.1f}% "
        f"({result.bullish_change:+.1f})"
    )

    print(
        f"Bearish Probability       : "
        f"{result.bearish_probability:.1f}% "
        f"({result.bearish_change:+.1f})"
    )

    print(
        f"Neutral Probability       : "
        f"{result.neutral_probability:.1f}% "
        f"({result.neutral_change:+.1f})"
    )

    print(
        f"Confidence                : "
        f"{result.current_confidence:.1f}% "
        f"({result.confidence_change:+.1f})"
    )

    print("-" * 100)

    print("MULTI-SESSION TREND")
    print("-" * 100)

    print(
        f"Bullish Trend             : "
        f"{result.bullish_trend}"
    )

    print(
        f"Bearish Trend             : "
        f"{result.bearish_trend}"
    )

    print(
        f"Neutral Trend             : "
        f"{result.neutral_trend}"
    )

    print(
        f"Confidence Trend          : "
        f"{result.confidence_trend}"
    )

    print("-" * 100)

    print("PERSISTENCE")
    print("-" * 100)

    print(
        f"Regime Persistence        : "
        f"{result.regime_persistence_sessions} session(s)"
    )

    print(
        f"Bias Persistence          : "
        f"{result.bias_persistence_sessions} session(s)"
    )

    print("-" * 100)

    print("INTELLIGENCE MOMENTUM")
    print("-" * 100)

    print(
        f"Directional Momentum      : "
        f"{result.directional_momentum}"
    )

    print(
        f"Intelligence Momentum     : "
        f"{result.intelligence_momentum}"
    )

    print(
        f"Quality                   : "
        f"{result.quality}"
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
            "Analyse changes in AQSD Market Intelligence History."
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

    parser.add_argument(
        "--lookback",
        type=int,
        default=DEFAULT_LOOKBACK,
        help=(
            "Number of recent sessions used for trend analysis."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    try:
        result = (
            run_market_history_change_engine(
                history_file=(
                    arguments.history
                    .expanduser()
                    .resolve()
                ),
                lookback_sessions=(
                    arguments.lookback
                ),
            )
        )

    except Exception as exc:
        print()
        print("=" * 100)
        print("AQSD MARKET HISTORY CHANGE ENGINE")
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
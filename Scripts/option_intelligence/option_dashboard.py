"""
AQSD
Option Intelligence

Module: option_dashboard.py
Version: 1.0
Author: AQSD

Description:
Runs all AQSD Option Intelligence engines and creates one integrated
terminal dashboard.

Integrated engines:
- Open Interest
- PCR
- Max Pain
- Walls
- Volatility
- Probability

Outputs:
- Compact terminal dashboard
- Dashboard summary CSV
- Dashboard detail table CSV
- Dashboard history CSV
- Excel workbook
- JSON
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from Scripts.option_intelligence.exporters import (
    EngineResult,
    ExportMetadata,
    export_results,
    print_export_report,
)

from Scripts.option_intelligence.max_pain_engine import (
    MaxPainResult,
    analyze_max_pain,
)

from Scripts.option_intelligence.oi_engine import (
    OIResult,
    analyze_open_interest,
)

from Scripts.option_intelligence.option_chain_loader import (
    OptionChainData,
    load_option_chain,
)

from Scripts.option_intelligence.pcr_engine import (
    PCRResult,
    analyze_pcr,
)

from Scripts.option_intelligence.probability_engine import (
    ProbabilityInputs,
    ProbabilityResult,
    analyze_probability,
)

from Scripts.option_intelligence.volatility_engine import (
    VolatilityResult,
    analyze_volatility,
)

from Scripts.option_intelligence.wall_engine import (
    WallResult,
    analyze_walls,
)


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "Output"

DASHBOARD_WIDTH = 108
DEFAULT_UNDERLYING = "BANKNIFTY_SAMPLE"
DEFAULT_SPOT_PRICE = 57582.25


# ============================================================
# DASHBOARD DATA MODEL
# ============================================================

@dataclass(slots=True)
class DashboardResult:
    """
    Integrated AQSD dashboard result.
    """

    underlying: str
    spot_price: float
    atm_strike: float
    timestamp: str

    directional_bias: str
    suggested_action: str
    confidence_score: float
    trade_grade: str
    trade_quality: str
    market_regime: str

    bullish_probability: float
    bearish_probability: float
    continuation_probability: float
    reversal_probability: float

    oi_pcr: float | None
    change_oi_pcr: float | None
    oi_market_bias: str
    oi_build_up_signal: str

    modified_pcr: float | None
    atm_zone_pcr: float | None
    volume_pcr: float | None
    pcr_trend: str
    pcr_bias: str
    reversal_watch: str

    max_pain_strike: float
    pinning_probability: float
    magnet_strength: str
    expiry_bias: str
    pain_shift: str

    positional_call_wall: float | None
    positional_put_wall: float | None
    fresh_call_wall: float | None
    fresh_put_wall: float | None
    expected_range_low: float | None
    expected_range_high: float | None
    combined_wall_shift: str
    breakout_watch: str
    breakdown_watch: str

    atm_iv: float | None
    historical_volatility: float | None
    iv_rank: float | None
    iv_percentile: float | None
    iv_hv_spread: float | None
    expected_move_low: float | None
    expected_move_high: float | None
    volatility_trend: str
    volatility_regime: str
    volatility_signal: str
    skew_signal: str

    dashboard_status: str
    interpretation: str


# ============================================================
# FORMAT HELPERS
# ============================================================

def format_number(
    value: float | None,
    decimals: int = 2,
    suffix: str = "",
) -> str:
    """
    Format an optional number.
    """

    if value is None:
        return "N/A"

    return f"{value:,.{decimals}f}{suffix}"


def format_ratio(
    value: float | None,
) -> str:
    """
    Format an optional ratio.
    """

    if value is None:
        return "N/A"

    return f"{value:.3f}"


def fit_text(
    value: Any,
    width: int,
) -> str:
    """
    Fit text inside a fixed terminal width.
    """

    text = str(value)

    if len(text) <= width:
        return text

    if width <= 3:
        return text[:width]

    return text[: width - 3] + "..."


def print_line(
    character: str = "=",
) -> None:
    """
    Print a dashboard separator.
    """

    print(character * DASHBOARD_WIDTH)


def print_title(
    title: str,
) -> None:
    """
    Print a centered dashboard title.
    """

    print_line("=")
    print(title.center(DASHBOARD_WIDTH))
    print_line("=")


def print_section(
    title: str,
) -> None:
    """
    Print a dashboard section header.
    """

    print()
    print_line("-")
    print(f" {title}")
    print_line("-")


def print_metric_row(
    metrics: list[tuple[str, Any]],
) -> None:
    """
    Print up to four metrics across one terminal row.
    """

    column_width = DASHBOARD_WIDTH // len(metrics)

    cells: list[str] = []

    for label, value in metrics:
        content = f"{label}: {value}"
        cells.append(
            fit_text(
                content,
                column_width - 2,
            ).ljust(column_width)
        )

    print("".join(cells))


# ============================================================
# SAMPLE DATA
# ============================================================

def create_sample_option_chain() -> pd.DataFrame:
    """
    Create integrated sample option-chain data.

    Includes:
    - OI
    - Change in OI
    - Volume
    - Implied Volatility
    """

    sample_data = {
        56500: {
            "ce_oi": 90000,
            "pe_oi": 300000,
            "ce_change": 12000,
            "pe_change": 65000,
            "ce_volume": 72000,
            "pe_volume": 128000,
            "ce_iv": 17.20,
            "pe_iv": 22.80,
        },
        57000: {
            "ce_oi": 125000,
            "pe_oi": 410000,
            "ce_change": 18000,
            "pe_change": 72000,
            "ce_volume": 82000,
            "pe_volume": 145000,
            "ce_iv": 16.80,
            "pe_iv": 21.50,
        },
        57500: {
            "ce_oi": 250000,
            "pe_oi": 350000,
            "ce_change": 46000,
            "pe_change": 52000,
            "ce_volume": 154000,
            "pe_volume": 168000,
            "ce_iv": 17.10,
            "pe_iv": 19.90,
        },
        58000: {
            "ce_oi": 520000,
            "pe_oi": 290000,
            "ce_change": 98000,
            "pe_change": 41000,
            "ce_volume": 244000,
            "pe_volume": 230000,
            "ce_iv": 18.20,
            "pe_iv": 19.10,
        },
        58500: {
            "ce_oi": 610000,
            "pe_oi": 185000,
            "ce_change": 122000,
            "pe_change": 18000,
            "ce_volume": 280000,
            "pe_volume": 125000,
            "ce_iv": 19.60,
            "pe_iv": 19.40,
        },
        59000: {
            "ce_oi": 480000,
            "pe_oi": 120000,
            "ce_change": 76000,
            "pe_change": 11000,
            "ce_volume": 220000,
            "pe_volume": 98000,
            "ce_iv": 21.30,
            "pe_iv": 20.10,
        },
    }

    rows: list[dict[str, float | str]] = []

    for strike, values in sample_data.items():
        rows.append(
            {
                "strikePrice": strike,
                "optionType": "CE",
                "OI": values["ce_oi"],
                "ChangeOI": values["ce_change"],
                "TotalVolume": values["ce_volume"],
                "IV": values["ce_iv"],
            }
        )

        rows.append(
            {
                "strikePrice": strike,
                "optionType": "PE",
                "OI": values["pe_oi"],
                "ChangeOI": values["pe_change"],
                "TotalVolume": values["pe_volume"],
                "IV": values["pe_iv"],
            }
        )

    return pd.DataFrame(rows)


def create_sample_close_prices() -> pd.Series:
    """
    Create sample daily closing prices for HV.
    """

    closes = [
        56120.00,
        56240.00,
        56080.00,
        56310.00,
        56520.00,
        56410.00,
        56680.00,
        56820.00,
        56710.00,
        56950.00,
        57120.00,
        57040.00,
        57280.00,
        57410.00,
        57330.00,
        57560.00,
        57620.00,
        57480.00,
        57710.00,
        57820.00,
        57690.00,
        DEFAULT_SPOT_PRICE,
    ]

    return pd.Series(
        closes,
        name="close",
        dtype="float64",
    )


def create_sample_iv_history() -> pd.Series:
    """
    Create sample ATM-IV history.
    """

    values = [
        14.2,
        14.8,
        15.1,
        15.6,
        16.0,
        15.4,
        16.3,
        17.1,
        17.8,
        18.4,
        19.0,
        18.6,
        17.9,
        18.8,
        19.5,
        20.1,
        21.3,
        20.5,
        19.7,
        18.9,
        18.1,
        17.6,
        18.0,
        18.4,
        18.7,
    ]

    return pd.Series(
        values,
        name="atm_iv",
        dtype="float64",
    )


# ============================================================
# PROBABILITY INPUT BUILDER
# ============================================================

def build_probability_inputs(
    oi_result: OIResult,
    pcr_result: PCRResult,
    max_pain_result: MaxPainResult,
    wall_result: WallResult,
    volatility_result: VolatilityResult,
) -> ProbabilityInputs:
    """
    Convert engine results into ProbabilityInputs.
    """

    return ProbabilityInputs(
        spot_price=oi_result.positional_call_wall
        and pcr_result.spot_price
        or pcr_result.spot_price,

        oi_pcr=oi_result.oi_pcr,
        change_oi_pcr=oi_result.change_oi_pcr,
        oi_imbalance=oi_result.oi_imbalance,
        oi_market_bias=oi_result.market_bias,
        oi_build_up_signal=oi_result.build_up_signal,

        modified_pcr=pcr_result.modified_pcr,
        atm_zone_pcr=pcr_result.atm_zone_pcr,
        pcr_trend=pcr_result.pcr_trend,
        pcr_bias=pcr_result.pcr_bias,
        reversal_watch=pcr_result.reversal_watch,

        max_pain_strike=max_pain_result.max_pain_strike,
        expiry_bias=max_pain_result.expiry_bias,
        pinning_probability=max_pain_result.pinning_probability,
        magnet_strength=max_pain_result.magnet_strength,
        pain_shift=max_pain_result.pain_shift,

        positional_call_wall=wall_result.positional_call_wall,
        positional_put_wall=wall_result.positional_put_wall,
        fresh_call_wall=wall_result.fresh_call_wall,
        fresh_put_wall=wall_result.fresh_put_wall,
        combined_wall_shift=wall_result.combined_wall_shift,
        range_bias=wall_result.range_bias,
        breakout_watch=wall_result.breakout_watch,
        breakdown_watch=wall_result.breakdown_watch,

        atm_iv=volatility_result.atm_iv,
        historical_volatility=(
            volatility_result.historical_volatility
        ),
        iv_rank=volatility_result.iv_rank,
        iv_percentile=volatility_result.iv_percentile,
        iv_hv_spread=volatility_result.iv_hv_spread,
        volatility_trend=volatility_result.volatility_trend,
        volatility_regime=volatility_result.volatility_regime,
        volatility_signal=volatility_result.volatility_signal,
        skew_signal=volatility_result.skew_signal,
    )


# ============================================================
# DASHBOARD RESULT
# ============================================================

def build_dashboard_interpretation(
    probability: ProbabilityResult,
    oi: OIResult,
    pcr: PCRResult,
    max_pain: MaxPainResult,
    walls: WallResult,
    volatility: VolatilityResult,
) -> str:
    """
    Build the integrated dashboard interpretation.
    """

    observations = [
        (
            f"The integrated model has a "
            f"{probability.directional_bias.lower()} bias."
        ),
        (
            f"Bullish probability is "
            f"{probability.bullish_probability:.1f}% and bearish "
            f"probability is {probability.bearish_probability:.1f}%."
        ),
        (
            f"OI positioning is {oi.market_bias.lower()} with "
            f"{oi.build_up_signal.lower()}."
        ),
        (
            f"Modified PCR is {format_ratio(pcr.modified_pcr)} and "
            f"PCR trend is {pcr.pcr_trend.lower()}."
        ),
        (
            f"Max Pain is {max_pain.max_pain_strike:,.0f} with "
            f"{max_pain.magnet_strength.lower()} magnet strength."
        ),
        (
            f"The OI-defined range is "
            f"{format_number(walls.expected_range_low, 0)} to "
            f"{format_number(walls.expected_range_high, 0)}."
        ),
        (
            f"The volatility regime is "
            f"{volatility.volatility_regime.lower()}."
        ),
        (
            f"Final suggested action is "
            f"{probability.suggested_action.lower()} with "
            f"{probability.confidence_score:.1f}% confidence."
        ),
    ]

    return " ".join(observations)


def build_dashboard_result(
    underlying: str,
    option_chain_data: OptionChainData,
    oi: OIResult,
    pcr: PCRResult,
    max_pain: MaxPainResult,
    walls: WallResult,
    volatility: VolatilityResult,
    probability: ProbabilityResult,
) -> DashboardResult:
    """
    Build the final integrated result object.
    """

    interpretation = build_dashboard_interpretation(
        probability=probability,
        oi=oi,
        pcr=pcr,
        max_pain=max_pain,
        walls=walls,
        volatility=volatility,
    )

    return DashboardResult(
        underlying=underlying,
        spot_price=option_chain_data.spot_price,
        atm_strike=option_chain_data.atm_strike,
        timestamp=option_chain_data.timestamp,

        directional_bias=probability.directional_bias,
        suggested_action=probability.suggested_action,
        confidence_score=probability.confidence_score,
        trade_grade=probability.trade_grade,
        trade_quality=probability.trade_quality,
        market_regime=probability.market_regime,

        bullish_probability=probability.bullish_probability,
        bearish_probability=probability.bearish_probability,
        continuation_probability=(
            probability.continuation_probability
        ),
        reversal_probability=probability.reversal_probability,

        oi_pcr=oi.oi_pcr,
        change_oi_pcr=oi.change_oi_pcr,
        oi_market_bias=oi.market_bias,
        oi_build_up_signal=oi.build_up_signal,

        modified_pcr=pcr.modified_pcr,
        atm_zone_pcr=pcr.atm_zone_pcr,
        volume_pcr=pcr.volume_pcr,
        pcr_trend=pcr.pcr_trend,
        pcr_bias=pcr.pcr_bias,
        reversal_watch=pcr.reversal_watch,

        max_pain_strike=max_pain.max_pain_strike,
        pinning_probability=max_pain.pinning_probability,
        magnet_strength=max_pain.magnet_strength,
        expiry_bias=max_pain.expiry_bias,
        pain_shift=max_pain.pain_shift,

        positional_call_wall=walls.positional_call_wall,
        positional_put_wall=walls.positional_put_wall,
        fresh_call_wall=walls.fresh_call_wall,
        fresh_put_wall=walls.fresh_put_wall,
        expected_range_low=walls.expected_range_low,
        expected_range_high=walls.expected_range_high,
        combined_wall_shift=walls.combined_wall_shift,
        breakout_watch=walls.breakout_watch,
        breakdown_watch=walls.breakdown_watch,

        atm_iv=volatility.atm_iv,
        historical_volatility=volatility.historical_volatility,
        iv_rank=volatility.iv_rank,
        iv_percentile=volatility.iv_percentile,
        iv_hv_spread=volatility.iv_hv_spread,
        expected_move_low=volatility.expected_move_low,
        expected_move_high=volatility.expected_move_high,
        volatility_trend=volatility.volatility_trend,
        volatility_regime=volatility.volatility_regime,
        volatility_signal=volatility.volatility_signal,
        skew_signal=volatility.skew_signal,

        dashboard_status="SUCCESS",
        interpretation=interpretation,
    )


# ============================================================
# DETAIL TABLES
# ============================================================

def create_dashboard_detail_table(
    oi_result: OIResult,
    pcr_result: PCRResult,
    max_pain_result: MaxPainResult,
    wall_result: WallResult,
    volatility_result: VolatilityResult,
    probability_result: ProbabilityResult,
) -> pd.DataFrame:
    """
    Build a long-form table containing all key analytics.
    """

    sections: list[
        tuple[
            str,
            dict[str, Any],
        ]
    ] = [
        (
            "OPEN INTEREST",
            asdict(oi_result),
        ),
        (
            "PCR",
            asdict(pcr_result),
        ),
        (
            "MAX PAIN",
            asdict(max_pain_result),
        ),
        (
            "WALLS",
            asdict(wall_result),
        ),
        (
            "VOLATILITY",
            asdict(volatility_result),
        ),
        (
            "PROBABILITY",
            asdict(probability_result),
        ),
    ]

    rows: list[dict[str, Any]] = []

    for section, values in sections:
        for metric, value in values.items():
            rows.append(
                {
                    "section": section,
                    "metric": metric,
                    "value": value,
                }
            )

    return pd.DataFrame(rows)


# ============================================================
# TERMINAL DASHBOARD
# ============================================================

def print_dashboard(
    result: DashboardResult,
) -> None:
    """
    Print the integrated AQSD Option Intelligence dashboard.
    """

    print()
    print_title(
        "AQSD OPTION INTELLIGENCE DASHBOARD"
    )

    print_metric_row(
        [
            ("Underlying", result.underlying),
            (
                "Spot",
                format_number(
                    result.spot_price,
                ),
            ),
            (
                "ATM",
                format_number(
                    result.atm_strike,
                    0,
                ),
            ),
            ("Status", result.dashboard_status),
        ]
    )

    print_section(
        "FINAL DECISION"
    )

    print_metric_row(
        [
            ("Action", result.suggested_action),
            ("Bias", result.directional_bias),
            (
                "Confidence",
                format_number(
                    result.confidence_score,
                    suffix="%",
                ),
            ),
            (
                "Grade",
                (
                    f"{result.trade_grade} / "
                    f"{result.trade_quality}"
                ),
            ),
        ]
    )

    print_metric_row(
        [
            (
                "Bull",
                format_number(
                    result.bullish_probability,
                    suffix="%",
                ),
            ),
            (
                "Bear",
                format_number(
                    result.bearish_probability,
                    suffix="%",
                ),
            ),
            (
                "Continuation",
                format_number(
                    result.continuation_probability,
                    suffix="%",
                ),
            ),
            (
                "Reversal",
                format_number(
                    result.reversal_probability,
                    suffix="%",
                ),
            ),
        ]
    )

    print_metric_row(
        [
            ("Market Regime", result.market_regime),
        ]
    )

    print_section(
        "OPEN INTEREST AND PCR"
    )

    print_metric_row(
        [
            ("OI PCR", format_ratio(result.oi_pcr)),
            (
                "Change-OI PCR",
                format_ratio(
                    result.change_oi_pcr
                ),
            ),
            (
                "Modified PCR",
                format_ratio(
                    result.modified_pcr
                ),
            ),
            (
                "ATM PCR",
                format_ratio(
                    result.atm_zone_pcr
                ),
            ),
        ]
    )

    print_metric_row(
        [
            ("OI Bias", result.oi_market_bias),
            ("OI Signal", result.oi_build_up_signal),
            ("PCR Trend", result.pcr_trend),
            ("PCR Bias", result.pcr_bias),
        ]
    )

    print_section(
        "MAX PAIN AND OPTION WALLS"
    )

    print_metric_row(
        [
            (
                "Max Pain",
                format_number(
                    result.max_pain_strike,
                    0,
                ),
            ),
            (
                "Pinning",
                format_number(
                    result.pinning_probability,
                    suffix="%",
                ),
            ),
            ("Magnet", result.magnet_strength),
            ("Expiry Bias", result.expiry_bias),
        ]
    )

    print_metric_row(
        [
            (
                "Call Wall",
                format_number(
                    result.positional_call_wall,
                    0,
                ),
            ),
            (
                "Put Wall",
                format_number(
                    result.positional_put_wall,
                    0,
                ),
            ),
            (
                "Fresh Call",
                format_number(
                    result.fresh_call_wall,
                    0,
                ),
            ),
            (
                "Fresh Put",
                format_number(
                    result.fresh_put_wall,
                    0,
                ),
            ),
        ]
    )

    print_metric_row(
        [
            (
                "Expected Range",
                (
                    f"{format_number(result.expected_range_low, 0)}"
                    f" - "
                    f"{format_number(result.expected_range_high, 0)}"
                ),
            ),
            ("Wall Shift", result.combined_wall_shift),
        ]
    )

    print_section(
        "VOLATILITY"
    )

    print_metric_row(
        [
            (
                "ATM IV",
                format_number(
                    result.atm_iv,
                    suffix="%",
                ),
            ),
            (
                "HV",
                format_number(
                    result.historical_volatility,
                    suffix="%",
                ),
            ),
            (
                "IV Rank",
                format_number(
                    result.iv_rank,
                    suffix="%",
                ),
            ),
            (
                "IV Percentile",
                format_number(
                    result.iv_percentile,
                    suffix="%",
                ),
            ),
        ]
    )

    print_metric_row(
        [
            (
                "IV-HV Spread",
                format_number(
                    result.iv_hv_spread,
                ),
            ),
            ("IV Trend", result.volatility_trend),
            ("IV Regime", result.volatility_regime),
            ("IV Signal", result.volatility_signal),
        ]
    )

    print_metric_row(
        [
            (
                "Expected Move",
                (
                    f"{format_number(result.expected_move_low, 0)}"
                    f" - "
                    f"{format_number(result.expected_move_high, 0)}"
                ),
            ),
            ("Skew", result.skew_signal),
        ]
    )

    print_section(
        "WATCH LEVELS"
    )

    print_metric_row(
        [
            ("Breakout", result.breakout_watch),
            ("Breakdown", result.breakdown_watch),
        ]
    )

    print_section(
        "INTEGRATED INTERPRETATION"
    )

    print(result.interpretation)

    print()
    print_line("=")
    print(
        f"Generated: {result.timestamp}"
    )
    print_line("=")
    print()


# ============================================================
# DASHBOARD ORCHESTRATOR
# ============================================================

def run_option_dashboard(
    source: pd.DataFrame,
    spot_price: float,
    underlying: str,
    close_prices: pd.Series | pd.DataFrame | None = None,
    historical_iv: pd.Series | None = None,
) -> tuple[
    DashboardResult,
    pd.DataFrame,
    pd.DataFrame,
]:
    """
    Run every Option Intelligence engine.

    Returns:
        1. DashboardResult
        2. Dashboard detail table
        3. Probability evidence table
    """

    option_chain_data = load_option_chain(
        source=source,
        spot_price=spot_price,
    )

    oi_result, _ = analyze_open_interest(
        source
    )

    pcr_result = analyze_pcr(
        option_chain_data=option_chain_data,
        atm_window_strikes_each_side=3,
    )

    max_pain_result, _ = analyze_max_pain(
        option_chain_data=option_chain_data,
    )

    wall_result, _ = analyze_walls(
        option_chain_data=option_chain_data,
    )

    volatility_result, _ = analyze_volatility(
        option_chain_data=option_chain_data,
        close_prices=close_prices,
        historical_iv=historical_iv,
        hv_lookback_days=20,
        expected_move_days=7,
    )

    probability_inputs = build_probability_inputs(
        oi_result=oi_result,
        pcr_result=pcr_result,
        max_pain_result=max_pain_result,
        wall_result=wall_result,
        volatility_result=volatility_result,
    )

    probability_result, evidence_table = (
        analyze_probability(
            inputs=probability_inputs,
            timestamp=option_chain_data.timestamp,
        )
    )

    dashboard_result = build_dashboard_result(
        underlying=underlying,
        option_chain_data=option_chain_data,
        oi=oi_result,
        pcr=pcr_result,
        max_pain=max_pain_result,
        walls=wall_result,
        volatility=volatility_result,
        probability=probability_result,
    )

    detail_table = create_dashboard_detail_table(
        oi_result=oi_result,
        pcr_result=pcr_result,
        max_pain_result=max_pain_result,
        wall_result=wall_result,
        volatility_result=volatility_result,
        probability_result=probability_result,
    )

    return (
        dashboard_result,
        detail_table,
        evidence_table,
    )


# ============================================================
# INDEPENDENT TEST
# ============================================================

def main() -> None:
    """
    Run the integrated sample dashboard.
    """

    option_chain = create_sample_option_chain()
    close_prices = create_sample_close_prices()
    historical_iv = create_sample_iv_history()

    (
        dashboard_result,
        detail_table,
        evidence_table,
    ) = run_option_dashboard(
        source=option_chain,
        spot_price=DEFAULT_SPOT_PRICE,
        underlying=DEFAULT_UNDERLYING,
        close_prices=close_prices,
        historical_iv=historical_iv,
    )

    print_dashboard(
        dashboard_result
    )

    metadata = ExportMetadata(
        engine="DASHBOARD",
        underlying=DEFAULT_UNDERLYING,
        engine_version="1.0",
        rows_processed=len(option_chain),
        status="SUCCESS",
        source="AQSD Integrated Sample Option Chain",
        notes=(
            "Integrated Option Intelligence dashboard "
            "independent test."
        ),
    )

    history_row = {
        "timestamp": dashboard_result.timestamp,
        "underlying": dashboard_result.underlying,
        "spot_price": dashboard_result.spot_price,
        "suggested_action": (
            dashboard_result.suggested_action
        ),
        "directional_bias": (
            dashboard_result.directional_bias
        ),
        "confidence_score": (
            dashboard_result.confidence_score
        ),
        "trade_grade": dashboard_result.trade_grade,
        "bullish_probability": (
            dashboard_result.bullish_probability
        ),
        "bearish_probability": (
            dashboard_result.bearish_probability
        ),
        "continuation_probability": (
            dashboard_result.continuation_probability
        ),
        "reversal_probability": (
            dashboard_result.reversal_probability
        ),
        "max_pain_strike": (
            dashboard_result.max_pain_strike
        ),
        "positional_call_wall": (
            dashboard_result.positional_call_wall
        ),
        "positional_put_wall": (
            dashboard_result.positional_put_wall
        ),
        "atm_iv": dashboard_result.atm_iv,
        "iv_rank": dashboard_result.iv_rank,
    }

    engine_result = EngineResult(
        summary=dashboard_result,
        table=detail_table,
        history=history_row,
        metadata=metadata,
        extra_tables={
            "Probability Evidence": evidence_table,
        },
    )

    export_paths = export_results(
        engine_result=engine_result,
        base_filename=(
            "BANKNIFTY_SAMPLE_OPTION_DASHBOARD"
        ),
    )

    print_export_report(
        export_paths
    )


if __name__ == "__main__":
    main()
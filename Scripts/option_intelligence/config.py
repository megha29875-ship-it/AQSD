"""
AQSD
Option Intelligence

Module: config.py
Version: 1.0

Description:
Central configuration and threshold values for all
AQSD Option Intelligence engines.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = BASE_DIR / "Scripts"
DATA_DIR = BASE_DIR / "Data"
OUTPUT_DIR = BASE_DIR / "Output"
LOGS_DIR = BASE_DIR / "Logs"

OPTION_INTELLIGENCE_DIR = (
    SCRIPTS_DIR / "option_intelligence"
)

OUTPUT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

LOGS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ============================================================
# GENERAL SETTINGS
# ============================================================

DEFAULT_UNDERLYING = "BANKNIFTY"
DEFAULT_SYMBOL = "NSE:NIFTYBANK-INDEX"

DEFAULT_STRIKE_INTERVAL = 100.0
DEFAULT_ATM_WINDOW = 3

TRADING_DAYS_PER_YEAR = 252
RISK_FREE_RATE = 0.065

HISTORY_LOOKBACK_DAYS = 252
MINIMUM_HISTORY_RECORDS = 20

ROUNDING_DECIMALS = 4


# ============================================================
# DATA VALIDATION SETTINGS
# ============================================================

REQUIRED_OPTION_COLUMNS = [
    "strike",
    "option_type",
    "open_interest",
    "change_in_oi",
    "volume",
]

OPTIONAL_OPTION_COLUMNS = [
    "ltp",
    "iv",
    "bid",
    "ask",
    "expiry",
    "underlying",
]

VALID_OPTION_TYPES = {
    "CE",
    "PE",
}

ALLOW_NEGATIVE_CHANGE_IN_OI = True
ALLOW_NEGATIVE_OPEN_INTEREST = False
ALLOW_NEGATIVE_VOLUME = False

DROP_DUPLICATE_ROWS = True
DROP_INVALID_STRIKES = True


# ============================================================
# PCR SETTINGS
# ============================================================

PCR_STRONGLY_BULLISH = 1.30
PCR_BULLISH = 1.10

PCR_NEUTRAL_LOWER = 0.80
PCR_NEUTRAL_UPPER = 1.10

PCR_BEARISH = 0.80
PCR_STRONGLY_BEARISH = 0.60

PCR_TREND_TOLERANCE = 0.03

ATM_PCR_WINDOW = 3


# ============================================================
# MODIFIED PCR WEIGHTS
# ============================================================

PCR_WEIGHT_OI = 0.35
PCR_WEIGHT_CHANGE_OI = 0.30
PCR_WEIGHT_VOLUME = 0.20
PCR_WEIGHT_ATM = 0.15

PCR_WEIGHT_TOTAL = (
    PCR_WEIGHT_OI
    + PCR_WEIGHT_CHANGE_OI
    + PCR_WEIGHT_VOLUME
    + PCR_WEIGHT_ATM
)

if round(PCR_WEIGHT_TOTAL, 6) != 1.0:
    raise ValueError(
        "Modified PCR weights must total 1.0."
    )


# ============================================================
# OI SETTINGS
# ============================================================

OI_DOMINANCE_RATIO_STRONG = 1.50
OI_DOMINANCE_RATIO_MODERATE = 1.20

OI_CHANGE_DOMINANCE_STRONG = 1.50
OI_CHANGE_DOMINANCE_MODERATE = 1.20

MINIMUM_MEANINGFUL_OI = 1.0
MINIMUM_MEANINGFUL_CHANGE_OI = 1.0


# ============================================================
# WALL SETTINGS
# ============================================================

WALL_TOP_STRIKES = 5

WALL_STRENGTH_VERY_STRONG = 1.75
WALL_STRENGTH_STRONG = 1.35
WALL_STRENGTH_MODERATE = 1.10

FRESH_WALL_MINIMUM_CHANGE_OI = 1.0

WALL_SHIFT_TOLERANCE_STRIKES = 0.0

WALL_PROXIMITY_NEAR_PERCENT = 0.50
WALL_PROXIMITY_MODERATE_PERCENT = 1.00


# ============================================================
# MAX PAIN SETTINGS
# ============================================================

MAX_PAIN_TOP_STRIKES = 5

MAX_PAIN_NEAR_PERCENT = 0.50
MAX_PAIN_MODERATE_PERCENT = 1.00
MAX_PAIN_FAR_PERCENT = 2.00

PINNING_SCORE_MINIMUM = 5.0
PINNING_SCORE_MAXIMUM = 95.0

PINNING_VERY_STRONG = 75.0
PINNING_STRONG = 60.0
PINNING_MODERATE = 40.0


# ============================================================
# VOLATILITY SETTINGS
# ============================================================

HV_LOOKBACK_SHORT = 10
HV_LOOKBACK_MEDIUM = 20
HV_LOOKBACK_LONG = 30

IV_HISTORY_LOOKBACK = 252

IV_RANK_VERY_HIGH = 80.0
IV_RANK_HIGH = 60.0
IV_RANK_NORMAL = 40.0
IV_RANK_LOW = 20.0

IV_PERCENTILE_VERY_HIGH = 80.0
IV_PERCENTILE_HIGH = 60.0
IV_PERCENTILE_NORMAL = 40.0
IV_PERCENTILE_LOW = 20.0

IV_HV_SPREAD_VERY_HIGH = 10.0
IV_HV_SPREAD_HIGH = 5.0
IV_HV_SPREAD_LOW = -5.0

IV_SKEW_STRONG = 5.0
IV_SKEW_MODERATE = 2.0


# ============================================================
# PROBABILITY AND SCORE SETTINGS
# ============================================================

PROBABILITY_MINIMUM = 5.0
PROBABILITY_MAXIMUM = 95.0

SIGNAL_SCORE_STRONG = 70.0
SIGNAL_SCORE_MODERATE = 55.0
SIGNAL_SCORE_WEAK = 40.0

BULLISH_REVERSAL_WEIGHT_PCR = 0.30
BULLISH_REVERSAL_WEIGHT_WALLS = 0.25
BULLISH_REVERSAL_WEIGHT_MAX_PAIN = 0.20
BULLISH_REVERSAL_WEIGHT_VOLATILITY = 0.15
BULLISH_REVERSAL_WEIGHT_TREND = 0.10

BEARISH_REVERSAL_WEIGHT_PCR = 0.30
BEARISH_REVERSAL_WEIGHT_WALLS = 0.25
BEARISH_REVERSAL_WEIGHT_MAX_PAIN = 0.20
BEARISH_REVERSAL_WEIGHT_VOLATILITY = 0.15
BEARISH_REVERSAL_WEIGHT_TREND = 0.10

CONTINUATION_WEIGHT_OI = 0.30
CONTINUATION_WEIGHT_PCR = 0.20
CONTINUATION_WEIGHT_WALLS = 0.20
CONTINUATION_WEIGHT_VOLATILITY = 0.15
CONTINUATION_WEIGHT_TREND = 0.15


# ============================================================
# EXPORT SETTINGS
# ============================================================

SAVE_CSV = True
SAVE_EXCEL = True
SAVE_JSON = True
SAVE_HISTORY = True

EXCEL_ENGINE = "openpyxl"

SUMMARY_SUFFIX = "Summary"
HISTORY_SUFFIX = "History"
TABLE_SUFFIX = "Table"

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
FILE_DATETIME_FORMAT = "%Y%m%d_%H%M%S"


# ============================================================
# DASHBOARD SETTINGS
# ============================================================

DASHBOARD_REFRESH_SECONDS = 60

DASHBOARD_MAX_ROWS = 20
DASHBOARD_SHOW_RAW_TABLE = True

COLOUR_BULLISH = "GREEN"
COLOUR_BEARISH = "RED"
COLOUR_NEUTRAL = "GREY"
COLOUR_WARNING = "AMBER"


# ============================================================
# DATACLASS CONFIGURATIONS
# ============================================================

@dataclass(frozen=True)
class PCRConfig:
    """
    PCR thresholds and weights.
    """

    strongly_bullish: float = PCR_STRONGLY_BULLISH
    bullish: float = PCR_BULLISH
    neutral_lower: float = PCR_NEUTRAL_LOWER
    neutral_upper: float = PCR_NEUTRAL_UPPER
    bearish: float = PCR_BEARISH
    strongly_bearish: float = PCR_STRONGLY_BEARISH

    weight_oi: float = PCR_WEIGHT_OI
    weight_change_oi: float = PCR_WEIGHT_CHANGE_OI
    weight_volume: float = PCR_WEIGHT_VOLUME
    weight_atm: float = PCR_WEIGHT_ATM


@dataclass(frozen=True)
class WallConfig:
    """
    Option wall thresholds.
    """

    top_strikes: int = WALL_TOP_STRIKES
    very_strong_ratio: float = WALL_STRENGTH_VERY_STRONG
    strong_ratio: float = WALL_STRENGTH_STRONG
    moderate_ratio: float = WALL_STRENGTH_MODERATE
    minimum_change_oi: float = FRESH_WALL_MINIMUM_CHANGE_OI


@dataclass(frozen=True)
class VolatilityConfig:
    """
    Volatility calculation settings.
    """

    hv_short: int = HV_LOOKBACK_SHORT
    hv_medium: int = HV_LOOKBACK_MEDIUM
    hv_long: int = HV_LOOKBACK_LONG
    history_lookback: int = IV_HISTORY_LOOKBACK
    trading_days: int = TRADING_DAYS_PER_YEAR
    risk_free_rate: float = RISK_FREE_RATE


@dataclass(frozen=True)
class ExportConfig:
    """
    Output file settings.
    """

    output_dir: Path = OUTPUT_DIR
    save_csv: bool = SAVE_CSV
    save_excel: bool = SAVE_EXCEL
    save_json: bool = SAVE_JSON
    save_history: bool = SAVE_HISTORY


PCR_CONFIG = PCRConfig()
WALL_CONFIG = WallConfig()
VOLATILITY_CONFIG = VolatilityConfig()
EXPORT_CONFIG = ExportConfig()


# ============================================================
# TEST
# ============================================================

def main() -> None:
    """
    Test configuration values.
    """

    print()
    print("=" * 72)
    print("AQSD OPTION INTELLIGENCE — CONFIGURATION")
    print("=" * 72)

    print(
        f"Base Directory          : {BASE_DIR}"
    )
    print(
        f"Output Directory        : {OUTPUT_DIR}"
    )
    print(
        f"Default Underlying      : {DEFAULT_UNDERLYING}"
    )
    print(
        f"ATM Window              : {DEFAULT_ATM_WINDOW}"
    )
    print(
        f"PCR Bullish Threshold   : {PCR_CONFIG.bullish}"
    )
    print(
        f"PCR Bearish Threshold   : {PCR_CONFIG.bearish}"
    )
    print(
        f"Modified PCR Weight Sum : {PCR_WEIGHT_TOTAL:.2f}"
    )
    print(
        f"Wall Top Strikes        : {WALL_CONFIG.top_strikes}"
    )
    print(
        f"HV Medium Lookback      : "
        f"{VOLATILITY_CONFIG.hv_medium}"
    )
    print(
        f"Risk-Free Rate          : "
        f"{VOLATILITY_CONFIG.risk_free_rate:.2%}"
    )
    print(
        f"Save Excel              : "
        f"{EXPORT_CONFIG.save_excel}"
    )

    print("=" * 72)
    print()


if __name__ == "__main__":
    main()
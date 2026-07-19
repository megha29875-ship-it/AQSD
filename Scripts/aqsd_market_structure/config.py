"""
AQSD
Market Structure Engine

Module: config.py
Version: 1.0
Author: AQSD
Description:
Stores all configurable values used by the
AQSD Market Structure Engine.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class MarketStructureConfig:
    """
    Configuration for the AQSD Market Structure Engine.

    All important thresholds and weights are stored here
    so that no values need to be hardcoded elsewhere.
    """

    # Indicator periods
    ema_fast_period: int = 20
    ema_medium_period: int = 50
    ema_slow_period: int = 200
    atr_period: int = 14
    volume_average_period: int = 20

    # Swing detection
    swing_window: int = 3
    minimum_required_rows: int = 220

    # Trend-strength thresholds
    strong_trend_ema_gap_percent: float = 0.50
    moderate_trend_ema_gap_percent: float = 0.20

    # ATR and volume confirmation
    atr_expansion_multiplier: float = 1.10
    volume_confirmation_multiplier: float = 1.20

    # Market Structure Score thresholds
    strong_bearish_max: float = 20.0
    bearish_max: float = 40.0
    neutral_max: float = 60.0
    bullish_max: float = 80.0

    # Evidence weights
    confidence_weights: Dict[str, float] = field(
        default_factory=lambda: {
            "higher_high": 20.0,
            "higher_low": 20.0,
            "lower_high": 20.0,
            "lower_low": 20.0,
            "price_above_ema20": 10.0,
            "price_below_ema20": 10.0,
            "ema20_above_ema50": 10.0,
            "ema20_below_ema50": 10.0,
            "ema50_above_ema200": 10.0,
            "ema50_below_ema200": 10.0,
            "atr_expansion": 10.0,
            "volume_confirmation": 10.0,
        }
    )

    def validate(self) -> None:
        """
        Validate configuration values.

        Raises:
            ValueError: If any configuration value is invalid.
        """

        integer_fields = {
            "ema_fast_period": self.ema_fast_period,
            "ema_medium_period": self.ema_medium_period,
            "ema_slow_period": self.ema_slow_period,
            "atr_period": self.atr_period,
            "volume_average_period": self.volume_average_period,
            "swing_window": self.swing_window,
            "minimum_required_rows": self.minimum_required_rows,
        }

        for name, value in integer_fields.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero.")

        if not (
            self.ema_fast_period
            < self.ema_medium_period
            < self.ema_slow_period
        ):
            raise ValueError(
                "EMA periods must follow: fast < medium < slow."
            )

        if self.strong_trend_ema_gap_percent < 0:
            raise ValueError(
                "strong_trend_ema_gap_percent cannot be negative."
            )

        if self.moderate_trend_ema_gap_percent < 0:
            raise ValueError(
                "moderate_trend_ema_gap_percent cannot be negative."
            )

        if (
            self.strong_trend_ema_gap_percent
            < self.moderate_trend_ema_gap_percent
        ):
            raise ValueError(
                "Strong trend threshold must be greater than or equal "
                "to the moderate trend threshold."
            )

        for key, weight in self.confidence_weights.items():
            if weight < 0:
                raise ValueError(
                    f"Confidence weight '{key}' cannot be negative."
                )


DEFAULT_CONFIG = MarketStructureConfig()
DEFAULT_CONFIG.validate()
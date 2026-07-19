"""
AQSD
Market Structure Engine

Module: models.py
Version: 1.0
Author: AQSD
Description:
Defines the standard data models used by the
AQSD Market Structure Engine.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional


class TrendDirection(str, Enum):
    """Supported market trend directions."""

    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"


class MarketPhase(str, Enum):
    """Supported market phases."""

    ACCUMULATION = "ACCUMULATION"
    UPTREND = "UPTREND"
    DISTRIBUTION = "DISTRIBUTION"
    DOWNTREND = "DOWNTREND"
    CAPITULATION = "CAPITULATION"
    RECOVERY = "RECOVERY"
    UNKNOWN = "UNKNOWN"


class TrendStrength(str, Enum):
    """Supported trend-strength classifications."""

    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    NEUTRAL = "NEUTRAL"


class SwingType(str, Enum):
    """Supported swing-point classifications."""

    HIGHER_HIGH = "HH"
    HIGHER_LOW = "HL"
    LOWER_HIGH = "LH"
    LOWER_LOW = "LL"
    SWING_HIGH = "SH"
    SWING_LOW = "SL"


@dataclass
class SwingPoint:
    """
    Represents one detected swing point.

    Attributes:
        index: Row position in the source DataFrame.
        timestamp: Date and time of the swing.
        price: Swing-point price.
        swing_type: Swing classification.
    """

    index: int
    timestamp: datetime
    price: float
    swing_type: SwingType


@dataclass
class TrendResult:
    """
    Stores the result produced by the Trend Detector.
    """

    direction: TrendDirection
    strength: TrendStrength
    close: float
    ema20: Optional[float] = None
    ema50: Optional[float] = None
    ema200: Optional[float] = None
    evidence: List[str] = field(default_factory=list)


@dataclass
class StructureScore:
    """
    Stores the AQSD Market Structure Score.

    The score must remain between 0 and 100.
    """

    score: float
    classification: str
    bullish_points: float = 0.0
    bearish_points: float = 0.0
    evidence: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.score = max(0.0, min(100.0, float(self.score)))


@dataclass
class ConfidenceResult:
    """
    Stores the confidence calculation.
    """

    confidence: float
    evidence_score: float
    maximum_score: float
    evidence: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(100.0, float(self.confidence)))


@dataclass
class MarketStructureResult:
    """
    Final output returned by the Market Structure Engine.
    """

    symbol: str
    structure: TrendDirection
    phase: MarketPhase
    trend_strength: TrendStrength
    confidence: float
    structure_score: float

    latest_close: float
    latest_swing_high: Optional[float] = None
    latest_swing_low: Optional[float] = None

    hh_confirmed: bool = False
    hl_confirmed: bool = False
    lh_confirmed: bool = False
    ll_confirmed: bool = False

    evidence: List[str] = field(default_factory=list)
    rule_ids: List[str] = field(default_factory=list)

    generated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self) -> None:
        self.confidence = max(0.0, min(100.0, float(self.confidence)))
        self.structure_score = max(
            0.0,
            min(100.0, float(self.structure_score)),
        )

    def to_dict(self) -> dict:
        """
        Convert the result into a dictionary suitable for
        JSON, Excel, CSV, or dashboard output.
        """

        return {
            "symbol": self.symbol,
            "structure": self.structure.value,
            "phase": self.phase.value,
            "trend_strength": self.trend_strength.value,
            "confidence": round(self.confidence, 2),
            "structure_score": round(self.structure_score, 2),
            "latest_close": self.latest_close,
            "latest_swing_high": self.latest_swing_high,
            "latest_swing_low": self.latest_swing_low,
            "hh_confirmed": self.hh_confirmed,
            "hl_confirmed": self.hl_confirmed,
            "lh_confirmed": self.lh_confirmed,
            "ll_confirmed": self.ll_confirmed,
            "evidence": self.evidence,
            "rule_ids": self.rule_ids,
            "generated_at": self.generated_at.isoformat(),
        }
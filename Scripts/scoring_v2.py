
"""
AQSD Professional
Module: Scoring Engine
Version: 2.0
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class ScoreResult:
    score: int
    confidence: int
    grade: str
    action: str
    reasons: list[str]

    def as_dict(self) -> dict:
        return {
            "Score": self.score,
            "Confidence": self.confidence,
            "Grade": self.grade,
            "Action": self.action,
            "Reasons": " | ".join(self.reasons),
        }


def _clamp(value: float, minimum: int = 0, maximum: int = 100) -> int:
    return int(max(minimum, min(maximum, round(value))))


def _grade(score: int) -> str:
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B+"
    if score >= 60:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def _option_action(score: int, direction: str) -> str:
    direction = direction.upper().strip()

    if direction != "BUY":
        return "AVOID"

    if score >= 85:
        return "STRONG BUY"
    if score >= 72:
        return "BUY"
    if score >= 58:
        return "WATCH"
    return "WAIT"


def _investment_action(score: int) -> str:
    if score >= 82:
        return "STRONG"
    if score >= 68:
        return "ACCUMULATE"
    if score >= 52:
        return "WATCH"
    return "WEAK"


def score_option_setup(
    *,
    st_direction: str,
    st_signal: str,
    ema_trend: str,
    rsi: float,
    adx: float,
    plus_di: float,
    minus_di: float,
    volume_ratio: float,
    atr_percent: float,
    st_gap_percent: float,
    breakout_20d: bool,
    ema20_cross: bool,
    rsi_cross_50: bool,
    adx_rising: bool,
    market_bias: str = "NEUTRAL",
) -> ScoreResult:
    """
    Score a 3-7 day bullish option-buying setup.

    Returns:
        ScoreResult with score, confidence, grade, action and reasons.
    """

    score = 0
    reasons: list[str] = []

    st_direction = st_direction.upper().strip()
    st_signal = st_signal.upper().strip()
    ema_trend = ema_trend.strip()
    market_bias = market_bias.upper().strip()

    # Supertrend: 25 points
    if st_direction == "BUY":
        score += 18
        reasons.append("Supertrend BUY")

    if st_signal == "FRESH BUY":
        score += 7
        reasons.append("Fresh Supertrend BUY")

    # EMA structure: 20 points
    if ema_trend == "Strong Uptrend":
        score += 20
        reasons.append("Strong EMA alignment")
    elif ema_trend == "Uptrend":
        score += 15
        reasons.append("EMA uptrend")
    elif ema_trend == "Pullback":
        score += 7
        reasons.append("Price above EMA20 pullback")

    if ema20_cross:
        score += 5
        reasons.append("Fresh EMA20 cross")

    # Momentum: 15 points
    if 55 <= rsi < 70:
        score += 12
        reasons.append("RSI in bullish zone")
    elif 50 <= rsi < 55:
        score += 6
        reasons.append("RSI above 50")
    elif rsi >= 70:
        score += 3
        reasons.append("RSI overbought")

    if rsi_cross_50:
        score += 3
        reasons.append("RSI crossed above 50")

    # Trend strength: 15 points
    if adx >= 30:
        score += 10
        reasons.append("ADX strong")
    elif adx >= 25:
        score += 8
        reasons.append("ADX supportive")
    elif adx >= 20:
        score += 4
        reasons.append("ADX developing")

    if adx_rising:
        score += 3
        reasons.append("ADX rising")

    if plus_di > minus_di:
        score += 2
        reasons.append("+DI above -DI")

    # Participation: 10 points
    if volume_ratio >= 2:
        score += 10
        reasons.append("Major volume expansion")
    elif volume_ratio >= 1.5:
        score += 8
        reasons.append("Volume breakout")
    elif volume_ratio >= 1.1:
        score += 4
        reasons.append("Volume above average")

    # Breakout: 8 points
    if breakout_20d:
        score += 8
        reasons.append("20-day breakout")

    # Volatility suitability: 7 points
    if 1.5 <= atr_percent <= 4:
        score += 5
        reasons.append("ATR suitable for option buying")
    elif 1.0 <= atr_percent < 1.5:
        score += 2
        reasons.append("Moderate ATR")
    elif atr_percent > 5:
        score -= 3
        reasons.append("ATR very high")

    # Entry quality around Supertrend: 5 points
    if st_direction == "BUY":
        if 0 <= st_gap_percent <= 3:
            score += 5
            reasons.append("Price close to Supertrend support")
        elif st_gap_percent > 8:
            score -= 4
            reasons.append("Price extended from Supertrend")

    # Market context: +/- 10 points
    if market_bias == "BULLISH":
        score += 8
        reasons.append("Market Pulse bullish")
    elif market_bias == "BEARISH":
        score -= 10
        reasons.append("Market Pulse bearish")
    else:
        reasons.append("Market Pulse neutral")

    score = _clamp(score)

    # Confidence is intentionally lower than score to avoid easy 100%.
    confidence = _clamp(
        score * 0.82
        + min(adx, 40) * 0.20
        + min(volume_ratio, 2.0) * 3
    )

    return ScoreResult(
        score=score,
        confidence=confidence,
        grade=_grade(score),
        action=_option_action(score, st_direction),
        reasons=reasons[:8],
    )


def score_investment_setup(
    *,
    close: float,
    ema50: float,
    ema200: float,
    high_52w: float,
    rsi: float,
    adx: float,
) -> ScoreResult:
    """
    Technical-only long-term score.
    Fundamental factors can be added later.
    """

    score = 0
    reasons: list[str] = []

    if close > ema200:
        score += 30
        reasons.append("Price above EMA200")

    if ema50 > ema200:
        score += 25
        reasons.append("EMA50 above EMA200")

    if close > ema50:
        score += 15
        reasons.append("Price above EMA50")

    distance_from_high = (
        ((high_52w - close) / high_52w) * 100
        if high_52w
        else 100
    )

    if distance_from_high <= 10:
        score += 15
        reasons.append("Near 52-week high")
    elif distance_from_high <= 20:
        score += 10
        reasons.append("Within 20% of 52-week high")

    if 50 <= rsi <= 70:
        score += 10
        reasons.append("Healthy RSI")

    if adx >= 20:
        score += 5
        reasons.append("Trend has strength")

    score = _clamp(score)
    confidence = _clamp(score * 0.9)

    return ScoreResult(
        score=score,
        confidence=confidence,
        grade=_grade(score),
        action=_investment_action(score),
        reasons=reasons[:8],
    )

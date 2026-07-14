
"""
AQSD Professional
Module: Bidirectional Scoring Engine
Version: 3.0

Supports both CALL and PUT setups for 3-7 day option buying.
"""

from __future__ import annotations

from dataclasses import dataclass


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


def _recommendation(score: int, direction: str) -> str:
    direction = direction.upper().strip()

    if direction == "BUY":
        if score >= 85:
            return "STRONG CALL"
        if score >= 72:
            return "CALL BUY"
        if score >= 58:
            return "CALL WATCH"
        return "WAIT"

    if direction == "SELL":
        if score >= 85:
            return "STRONG PUT"
        if score >= 72:
            return "PUT BUY"
        if score >= 58:
            return "PUT WATCH"
        return "WAIT"

    return "AVOID"


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
    Score both bullish CALL and bearish PUT setups.
    """

    direction = st_direction.upper().strip()
    signal = st_signal.upper().strip()
    bias = market_bias.upper().strip()
    trend = ema_trend.strip()

    bullish = direction == "BUY"
    bearish = direction == "SELL"

    score = 0
    reasons: list[str] = []

    # --------------------------------------------------------
    # Supertrend
    # --------------------------------------------------------
    if bullish:
        score += 18
        reasons.append("Supertrend BUY")
    elif bearish:
        score += 18
        reasons.append("Supertrend SELL")

    if signal == "FRESH BUY" and bullish:
        score += 7
        reasons.append("Fresh Supertrend BUY")

    if signal == "FRESH SELL" and bearish:
        score += 7
        reasons.append("Fresh Supertrend SELL")

    # --------------------------------------------------------
    # EMA structure
    # --------------------------------------------------------
    if bullish:
        if trend == "Strong Uptrend":
            score += 20
            reasons.append("Strong EMA uptrend")
        elif trend == "Uptrend":
            score += 15
            reasons.append("EMA uptrend")
        elif trend == "Pullback":
            score += 7
            reasons.append("Bullish pullback")

        if ema20_cross:
            score += 5
            reasons.append("Fresh EMA20 bullish cross")

    elif bearish:
        if trend == "Downtrend":
            score += 20
            reasons.append("EMA downtrend")
        elif trend == "Pullback":
            score += 7
            reasons.append("Weak pullback structure")

    # --------------------------------------------------------
    # RSI
    # --------------------------------------------------------
    if bullish:
        if 55 <= rsi < 70:
            score += 12
            reasons.append("RSI bullish")
        elif 50 <= rsi < 55:
            score += 6
            reasons.append("RSI above 50")
        elif rsi >= 70:
            score += 3
            reasons.append("RSI overbought")

        if rsi_cross_50:
            score += 3
            reasons.append("RSI crossed above 50")

    elif bearish:
        if 30 < rsi <= 45:
            score += 12
            reasons.append("RSI bearish")
        elif 45 < rsi < 50:
            score += 6
            reasons.append("RSI below 50")
        elif rsi <= 30:
            score += 3
            reasons.append("RSI oversold")

    # --------------------------------------------------------
    # ADX and directional movement
    # --------------------------------------------------------
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

    if bullish and plus_di > minus_di:
        score += 2
        reasons.append("+DI above -DI")

    if bearish and minus_di > plus_di:
        score += 2
        reasons.append("-DI above +DI")

    # --------------------------------------------------------
    # Volume
    # --------------------------------------------------------
    if volume_ratio >= 2:
        score += 10
        reasons.append("Major volume expansion")
    elif volume_ratio >= 1.5:
        score += 8
        reasons.append("Volume breakout")
    elif volume_ratio >= 1.1:
        score += 4
        reasons.append("Volume above average")

    # --------------------------------------------------------
    # Breakout / breakdown
    # --------------------------------------------------------
    if breakout_20d:
        score += 8
        reasons.append(
            "20-day breakout" if bullish else "20-day breakdown"
        )

    # --------------------------------------------------------
    # ATR suitability
    # --------------------------------------------------------
    if 1.5 <= atr_percent <= 4:
        score += 5
        reasons.append("ATR suitable for option buying")
    elif 1.0 <= atr_percent < 1.5:
        score += 2
        reasons.append("Moderate ATR")
    elif atr_percent > 5:
        score -= 3
        reasons.append("ATR very high")

    # --------------------------------------------------------
    # Supertrend distance
    # --------------------------------------------------------
    if bullish:
        if 0 <= st_gap_percent <= 3:
            score += 5
            reasons.append("Near Supertrend support")
        elif st_gap_percent > 8:
            score -= 4
            reasons.append("Extended above Supertrend")

    elif bearish:
        gap = abs(st_gap_percent)

        if 0 <= gap <= 3:
            score += 5
            reasons.append("Near Supertrend resistance")
        elif gap > 8:
            score -= 4
            reasons.append("Extended below Supertrend")

    # --------------------------------------------------------
    # Market Pulse
    # --------------------------------------------------------
    if bullish:
        if bias == "BULLISH":
            score += 8
            reasons.append("Market Pulse supports CALL")
        elif bias == "BEARISH":
            score -= 10
            reasons.append("Market Pulse against CALL")
        else:
            reasons.append("Market Pulse neutral")

    elif bearish:
        if bias == "BEARISH":
            score += 8
            reasons.append("Market Pulse supports PUT")
        elif bias == "BULLISH":
            score -= 10
            reasons.append("Market Pulse against PUT")
        else:
            reasons.append("Market Pulse neutral")

    score = _clamp(score)

    confidence = _clamp(
        score * 0.80
        + min(adx, 40) * 0.20
        + min(volume_ratio, 2.0) * 3
    )

    return ScoreResult(
        score=score,
        confidence=confidence,
        grade=_grade(score),
        action=_recommendation(score, direction),
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
    confidence = _clamp(score * 0.90)

    if score >= 82:
        action = "STRONG"
    elif score >= 68:
        action = "ACCUMULATE"
    elif score >= 52:
        action = "WATCH"
    else:
        action = "WEAK"

    return ScoreResult(
        score=score,
        confidence=confidence,
        grade=_grade(score),
        action=action,
        reasons=reasons[:8],
    )

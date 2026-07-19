"""
AQSD
Implied Volatility Calculator

Module: iv_calculator.py
Version: 1.0
Author: AQSD

Description:
Calculates option implied volatility using the Black-Scholes model
and a stable bisection search.

Analytics only. No order placement.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal


OptionType = Literal["CE", "PE"]


@dataclass(frozen=True)
class ImpliedVolatilityResult:
    """
    Result returned by the implied-volatility calculator.
    """

    implied_volatility: float | None
    implied_volatility_percent: float | None
    theoretical_price: float | None
    intrinsic_value: float
    time_value: float
    converged: bool
    iterations: int
    message: str


def normal_cdf(
    value: float,
) -> float:
    """
    Standard normal cumulative distribution function.
    """

    return 0.5 * (
        1.0
        + math.erf(
            value / math.sqrt(2.0)
        )
    )


def intrinsic_value(
    spot_price: float,
    strike_price: float,
    option_type: OptionType,
) -> float:
    """
    Calculate option intrinsic value.
    """

    normalized_type = option_type.upper()

    if normalized_type == "CE":
        return max(
            spot_price - strike_price,
            0.0,
        )

    if normalized_type == "PE":
        return max(
            strike_price - spot_price,
            0.0,
        )

    raise ValueError(
        "option_type must be CE or PE."
    )


def black_scholes_price(
    spot_price: float,
    strike_price: float,
    time_to_expiry_years: float,
    risk_free_rate: float,
    volatility: float,
    option_type: OptionType,
    dividend_yield: float = 0.0,
) -> float:
    """
    Calculate the Black-Scholes theoretical option price.

    Rates and volatility must be supplied as decimals.

    Example:
        6.5% rate = 0.065
        18% volatility = 0.18
    """

    normalized_type = option_type.upper()

    if normalized_type not in {"CE", "PE"}:
        raise ValueError(
            "option_type must be CE or PE."
        )

    if spot_price <= 0.0:
        raise ValueError(
            "spot_price must be positive."
        )

    if strike_price <= 0.0:
        raise ValueError(
            "strike_price must be positive."
        )

    if time_to_expiry_years <= 0.0:
        return intrinsic_value(
            spot_price=spot_price,
            strike_price=strike_price,
            option_type=normalized_type,
        )

    if volatility <= 0.0:
        discounted_spot = (
            spot_price
            * math.exp(
                -dividend_yield
                * time_to_expiry_years
            )
        )

        discounted_strike = (
            strike_price
            * math.exp(
                -risk_free_rate
                * time_to_expiry_years
            )
        )

        if normalized_type == "CE":
            return max(
                discounted_spot
                - discounted_strike,
                0.0,
            )

        return max(
            discounted_strike
            - discounted_spot,
            0.0,
        )

    square_root_time = math.sqrt(
        time_to_expiry_years
    )

    d1 = (
        math.log(
            spot_price / strike_price
        )
        + (
            risk_free_rate
            - dividend_yield
            + 0.5 * volatility**2
        )
        * time_to_expiry_years
    ) / (
        volatility
        * square_root_time
    )

    d2 = (
        d1
        - volatility
        * square_root_time
    )

    discounted_spot = (
        spot_price
        * math.exp(
            -dividend_yield
            * time_to_expiry_years
        )
    )

    discounted_strike = (
        strike_price
        * math.exp(
            -risk_free_rate
            * time_to_expiry_years
        )
    )

    if normalized_type == "CE":
        return (
            discounted_spot
            * normal_cdf(d1)
            - discounted_strike
            * normal_cdf(d2)
        )

    return (
        discounted_strike
        * normal_cdf(-d2)
        - discounted_spot
        * normal_cdf(-d1)
    )


def calculate_implied_volatility(
    market_price: float,
    spot_price: float,
    strike_price: float,
    time_to_expiry_years: float,
    risk_free_rate: float,
    option_type: OptionType,
    dividend_yield: float = 0.0,
    minimum_volatility: float = 0.0001,
    maximum_volatility: float = 5.0,
    tolerance: float = 0.0001,
    maximum_iterations: int = 200,
) -> ImpliedVolatilityResult:
    """
    Calculate implied volatility using bisection search.
    """

    normalized_type = option_type.upper()

    intrinsic = intrinsic_value(
        spot_price=spot_price,
        strike_price=strike_price,
        option_type=normalized_type,
    )

    time_value = max(
        market_price - intrinsic,
        0.0,
    )

    if market_price <= 0.0:
        return ImpliedVolatilityResult(
            implied_volatility=None,
            implied_volatility_percent=None,
            theoretical_price=None,
            intrinsic_value=intrinsic,
            time_value=time_value,
            converged=False,
            iterations=0,
            message="Market price must be positive.",
        )

    if time_to_expiry_years <= 0.0:
        return ImpliedVolatilityResult(
            implied_volatility=None,
            implied_volatility_percent=None,
            theoretical_price=intrinsic,
            intrinsic_value=intrinsic,
            time_value=time_value,
            converged=False,
            iterations=0,
            message="Option has expired or time to expiry is zero.",
        )

    if market_price < intrinsic:
        return ImpliedVolatilityResult(
            implied_volatility=None,
            implied_volatility_percent=None,
            theoretical_price=None,
            intrinsic_value=intrinsic,
            time_value=time_value,
            converged=False,
            iterations=0,
            message=(
                "Market price is below intrinsic value. "
                "Implied volatility cannot be calculated reliably."
            ),
        )

    low_volatility = minimum_volatility
    high_volatility = maximum_volatility

    high_price = black_scholes_price(
        spot_price=spot_price,
        strike_price=strike_price,
        time_to_expiry_years=time_to_expiry_years,
        risk_free_rate=risk_free_rate,
        volatility=high_volatility,
        option_type=normalized_type,
        dividend_yield=dividend_yield,
    )

    if market_price > high_price:
        return ImpliedVolatilityResult(
            implied_volatility=None,
            implied_volatility_percent=None,
            theoretical_price=high_price,
            intrinsic_value=intrinsic,
            time_value=time_value,
            converged=False,
            iterations=0,
            message=(
                "Market price is outside the configured "
                "volatility search range."
            ),
        )

    midpoint_volatility = 0.0
    midpoint_price = 0.0

    for iteration in range(
        1,
        maximum_iterations + 1,
    ):
        midpoint_volatility = (
            low_volatility
            + high_volatility
        ) / 2.0

        midpoint_price = black_scholes_price(
            spot_price=spot_price,
            strike_price=strike_price,
            time_to_expiry_years=time_to_expiry_years,
            risk_free_rate=risk_free_rate,
            volatility=midpoint_volatility,
            option_type=normalized_type,
            dividend_yield=dividend_yield,
        )

        price_difference = (
            midpoint_price
            - market_price
        )

        if abs(price_difference) <= tolerance:
            return ImpliedVolatilityResult(
                implied_volatility=midpoint_volatility,
                implied_volatility_percent=(
                    midpoint_volatility * 100.0
                ),
                theoretical_price=midpoint_price,
                intrinsic_value=intrinsic,
                time_value=time_value,
                converged=True,
                iterations=iteration,
                message="Implied volatility calculation converged.",
            )

        if midpoint_price > market_price:
            high_volatility = (
                midpoint_volatility
            )

        else:
            low_volatility = (
                midpoint_volatility
            )

    return ImpliedVolatilityResult(
        implied_volatility=midpoint_volatility,
        implied_volatility_percent=(
            midpoint_volatility * 100.0
        ),
        theoretical_price=midpoint_price,
        intrinsic_value=intrinsic,
        time_value=time_value,
        converged=False,
        iterations=maximum_iterations,
        message=(
            "Maximum iterations reached before full convergence."
        ),
    )


def days_to_years(
    days_to_expiry: float,
    trading_days_basis: bool = False,
) -> float:
    """
    Convert days to an annual time fraction.
    """

    denominator = (
        252.0
        if trading_days_basis
        else 365.0
    )

    return max(
        float(days_to_expiry),
        0.0,
    ) / denominator


def main() -> None:
    """
    Test the implied-volatility calculator.
    """

    spot_price = 58521.40
    strike_price = 58500.00
    market_price = 425.00
    days_to_expiry = 5.0
    risk_free_rate = 0.065

    time_to_expiry = days_to_years(
        days_to_expiry
    )

    result = calculate_implied_volatility(
        market_price=market_price,
        spot_price=spot_price,
        strike_price=strike_price,
        time_to_expiry_years=time_to_expiry,
        risk_free_rate=risk_free_rate,
        option_type="CE",
    )

    print()
    print("=" * 68)
    print("AQSD IMPLIED VOLATILITY CALCULATOR")
    print("=" * 68)
    print(f"Spot Price          : {spot_price:,.2f}")
    print(f"Strike Price        : {strike_price:,.2f}")
    print(f"Option Market Price : {market_price:,.2f}")
    print(f"Days to Expiry      : {days_to_expiry:.2f}")
    print(f"Intrinsic Value     : {result.intrinsic_value:,.2f}")
    print(f"Time Value          : {result.time_value:,.2f}")

    if result.implied_volatility_percent is None:
        print("Implied Volatility  : N/A")

    else:
        print(
            "Implied Volatility  : "
            f"{result.implied_volatility_percent:.2f}%"
        )

    if result.theoretical_price is None:
        print("Theoretical Price   : N/A")

    else:
        print(
            "Theoretical Price   : "
            f"{result.theoretical_price:,.2f}"
        )

    print(f"Converged           : {result.converged}")
    print(f"Iterations          : {result.iterations}")
    print(f"Message             : {result.message}")
    print("=" * 68)


if __name__ == "__main__":
    main()
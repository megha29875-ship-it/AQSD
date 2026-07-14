
"""
AQSD Professional
Module: Risk & Position Sizing
Version: 1.0
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor


@dataclass
class RiskPlan:
    capital: float
    risk_percent: float
    entry: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_amount: float
    risk_per_unit: float
    quantity: int
    capital_required: float
    max_loss: float
    reward_1: float
    reward_2: float
    rr_1: float
    rr_2: float

    def as_dict(self) -> dict:
        return {
            "Capital": round(self.capital, 2),
            "Risk %": round(self.risk_percent, 2),
            "Risk Amount": round(self.risk_amount, 2),
            "Entry": round(self.entry, 2),
            "Stop Loss": round(self.stop_loss, 2),
            "Target 1": round(self.target_1, 2),
            "Target 2": round(self.target_2, 2),
            "Risk / Unit": round(self.risk_per_unit, 2),
            "Quantity": self.quantity,
            "Capital Required": round(self.capital_required, 2),
            "Maximum Loss": round(self.max_loss, 2),
            "Reward 1": round(self.reward_1, 2),
            "Reward 2": round(self.reward_2, 2),
            "RR 1": round(self.rr_1, 2),
            "RR 2": round(self.rr_2, 2),
        }


def calculate_position_size(
    *,
    capital: float,
    risk_percent: float,
    entry: float,
    stop_loss: float,
    target_1: float,
    target_2: float,
    lot_size: int = 1,
    max_capital_percent: float = 100.0,
) -> RiskPlan:
    """
    Calculate position size from account risk.

    lot_size:
        Use 1 for cash-market shares.
        Use the official option/futures lot size when required.

    max_capital_percent:
        Caps capital deployed in one trade.
    """

    if capital <= 0:
        raise ValueError("Capital must be greater than zero.")

    if not 0 < risk_percent <= 10:
        raise ValueError("Risk percent must be between 0 and 10.")

    if entry <= 0 or stop_loss <= 0:
        raise ValueError("Entry and stop loss must be greater than zero.")

    if lot_size < 1:
        raise ValueError("Lot size must be at least 1.")

    risk_per_unit = abs(entry - stop_loss)

    if risk_per_unit <= 0:
        raise ValueError("Entry and stop loss cannot be equal.")

    risk_amount = capital * (risk_percent / 100)
    raw_quantity = floor(risk_amount / risk_per_unit)

    max_capital = capital * (max_capital_percent / 100)
    capital_limited_quantity = floor(max_capital / entry)

    allowed_quantity = min(raw_quantity, capital_limited_quantity)

    quantity = floor(allowed_quantity / lot_size) * lot_size

    if quantity < lot_size:
        quantity = 0

    capital_required = quantity * entry
    max_loss = quantity * risk_per_unit

    reward_1_per_unit = abs(target_1 - entry)
    reward_2_per_unit = abs(target_2 - entry)

    reward_1 = quantity * reward_1_per_unit
    reward_2 = quantity * reward_2_per_unit

    rr_1 = (
        reward_1_per_unit / risk_per_unit
        if risk_per_unit
        else 0
    )

    rr_2 = (
        reward_2_per_unit / risk_per_unit
        if risk_per_unit
        else 0
    )

    return RiskPlan(
        capital=capital,
        risk_percent=risk_percent,
        entry=entry,
        stop_loss=stop_loss,
        target_1=target_1,
        target_2=target_2,
        risk_amount=risk_amount,
        risk_per_unit=risk_per_unit,
        quantity=quantity,
        capital_required=capital_required,
        max_loss=max_loss,
        reward_1=reward_1,
        reward_2=reward_2,
        rr_1=rr_1,
        rr_2=rr_2,
    )


def main() -> None:
    print("\nAQSD RISK CALCULATOR\n")

    capital = float(input("Trading capital: "))
    risk_percent = float(input("Risk per trade (%): "))
    entry = float(input("Entry price: "))
    stop_loss = float(input("Stop loss: "))
    target_1 = float(input("Target 1: "))
    target_2 = float(input("Target 2: "))

    plan = calculate_position_size(
        capital=capital,
        risk_percent=risk_percent,
        entry=entry,
        stop_loss=stop_loss,
        target_1=target_1,
        target_2=target_2,
    )

    print("\n" + "=" * 45)

    for key, value in plan.as_dict().items():
        print(f"{key:<20}: {value}")

    print("=" * 45)


if __name__ == "__main__":
    main()

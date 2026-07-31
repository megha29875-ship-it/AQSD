"""
AQSD
Trading Calendar Engine

Module : DAQ-006
Version: 1.0.0

Description
-----------
Provides trading-day utilities for AQSD.

Current Features
----------------
✓ Weekend detection
✓ Trading day detection
✓ Previous trading day
✓ Next trading day

Future Features
---------------
- NSE Holiday Calendar
- Weekly Expiry
- Monthly Expiry
- Muhurat Trading
- Half Trading Days
"""

from __future__ import annotations

from datetime import date, timedelta


# ==========================================================
# WEEKEND
# ==========================================================

def is_weekend(check_date: date) -> bool:
    """
    Return True if Saturday or Sunday.
    """
    return check_date.weekday() >= 5


# ==========================================================
# HOLIDAY
# ==========================================================

def is_holiday(check_date: date) -> bool:
    """
    Placeholder.

    Version 1.0:
        No holiday list yet.
    """

    return False


# ==========================================================
# TRADING DAY
# ==========================================================

def is_trading_day(check_date: date) -> bool:
    """
    Determine whether the given date is a trading day.
    """

    if is_weekend(check_date):
        return False

    if is_holiday(check_date):
        return False

    return True


# ==========================================================
# PREVIOUS TRADING DAY
# ==========================================================

def previous_trading_day(check_date: date) -> date:
    """
    Return previous trading day.
    """

    current = check_date - timedelta(days=1)

    while not is_trading_day(current):
        current -= timedelta(days=1)

    return current


# ==========================================================
# NEXT TRADING DAY
# ==========================================================

def next_trading_day(check_date: date) -> date:
    """
    Return next trading day.
    """

    current = check_date + timedelta(days=1)

    while not is_trading_day(current):
        current += timedelta(days=1)

    return current


# ==========================================================
# LATEST TRADING DAY
# ==========================================================

def latest_trading_day(today: date) -> date:
    """
    Return today's trading day if open.

    Otherwise return previous trading day.
    """

    if is_trading_day(today):
        return today

    return previous_trading_day(today)
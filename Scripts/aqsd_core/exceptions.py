"""
AQSD
Custom Exceptions

Module    : exceptions.py
Module ID : CORE-004
Version   : 1.0.0
Author    : AQSD
Status    : Production

Description
-----------
Centralized exception classes used throughout AQSD.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AQSDError(Exception):
    """
    Base exception for AQSD.
    """

    error_code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


# ==========================================================
# Configuration
# ==========================================================

class ConfigurationError(AQSDError):
    """Configuration related errors."""


# ==========================================================
# Database
# ==========================================================

class DatabaseError(AQSDError):
    """Database related errors."""


class ValidationError(AQSDError):
    """Validation related errors."""


# ==========================================================
# Trading Calendar
# ==========================================================

class TradingCalendarError(AQSDError):
    """Trading calendar errors."""


class HolidayError(AQSDError):
    """Holiday related errors."""


class ExpiryError(AQSDError):
    """Expiry related errors."""


# ==========================================================
# Market Data
# ==========================================================

class MarketDataError(AQSDError):
    """Market data errors."""


class DataDownloadError(AQSDError):
    """Download failure."""


# ==========================================================
# Options
# ==========================================================

class OptionDataError(AQSDError):
    """Option chain errors."""


# ==========================================================
# Futures
# ==========================================================

class FuturesDataError(AQSDError):
    """Futures data errors."""


# ==========================================================
# Decision Engine
# ==========================================================

class DecisionEngineError(AQSDError):
    """Decision engine errors."""


# ==========================================================
# Experiment Engine
# ==========================================================

class ExperimentError(AQSDError):
    """Experiment engine errors."""
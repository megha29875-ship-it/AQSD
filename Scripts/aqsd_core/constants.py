"""
AQSD
Core Constants

Module    : constants.py
Module ID : CORE-001
Version   : 1.0.0
Author    : AQSD
Status    : Production

Description
-----------
Central location for all AQSD constants.
No hardcoded values should exist elsewhere.
"""

from pathlib import Path

# ==========================================================
# PROJECT
# ==========================================================

PROJECT_NAME = "AQSD"
VERSION = "1.0.0"

# ==========================================================
# PATHS
# ==========================================================

BASE_DIR = Path(__file__).resolve().parents[2]

CONFIG_DIR = BASE_DIR / "Config"
DATA_DIR = BASE_DIR / "Data"
OUTPUT_DIR = BASE_DIR / "Output"
LOG_DIR = BASE_DIR / "Logs"
REPORT_DIR = BASE_DIR / "Reports"
DOC_DIR = BASE_DIR / "Docs"

# ==========================================================
# DATABASE
# ==========================================================

AQSD_ID_PREFIX = "AQSD"

DATE_FORMAT = "%d-%b-%Y"

# ==========================================================
# FILES
# ==========================================================

MASTER_DATABASE = "AQSD_Master_Database.xlsx"
VALIDATION_REPORT = "validation_report.xlsx"

# ==========================================================
# LOGGING
# ==========================================================

LOG_FILE = "aqsd.log"

# ==========================================================
# PERFORMANCE
# ==========================================================

DEFAULT_LOOKBACK = 20

# ==========================================================
# VALIDATION
# ==========================================================

MIN_ROWS = 1

MAX_WARNINGS = 1000

# ==========================================================
# ERROR CODES
# ==========================================================

DB001 = "Missing Date"
DB002 = "Duplicate Date"
DB003 = "Missing Required Column"
DB004 = "Invalid Numeric Value"
DB005 = "Empty Workbook"
DB006 = "Invalid Date Format"
DB007 = "AQSD ID Generation Failed"
DB008 = "Weekend Date Found"
DB009 = "NSE Holiday Found"

# ==========================================================
# PARTICIPANT STATES
# ==========================================================

AGGRESSIVE_BULL = "Aggressive Bullish"
AGGRESSIVE_BEAR = "Aggressive Bearish"
LONG_BUILDUP = "Long Build-up"
LONG_UNWINDING = "Long Unwinding"
SHORT_BUILDUP = "Short Build-up"
SHORT_COVERING = "Short Covering"
HEDGED_ACCUMULATION = "Hedged Accumulation"
HEDGED_DISTRIBUTION = "Hedged Distribution"

# ==========================================================
# MARKET STATES
# ==========================================================

BULLISH = "Bullish"
BEARISH = "Bearish"
NEUTRAL = "Neutral"
RANGING = "Ranging"
TRENDING = "Trending"
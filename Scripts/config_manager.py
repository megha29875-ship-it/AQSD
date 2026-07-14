
"""
AQSD Professional
Module: Configuration Manager
Version: 1.0

Creates and manages one central configuration file:

    AQSD/Config/AQSD_Config.json

All future AQSD modules can read settings from this file instead of
hardcoding capital, risk, scanner thresholds and backup limits.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any


BASE = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE / "Config"
CONFIG_FILE = CONFIG_DIR / "AQSD_Config.json"


DEFAULT_CONFIG: dict[str, Any] = {
    "project": {
        "name": "AQSD Professional",
        "version": "4.1",
    },
    "trading": {
        "capital": 200000,
        "risk_percent": 1.0,
        "maximum_open_positions": 5,
        "maximum_position_percent": 25.0,
        "maximum_portfolio_risk_percent": 5.0,
    },
    "scanner": {
        "minimum_call_score": 72,
        "minimum_put_score": 72,
        "minimum_confidence": 65,
        "top_call_candidates": 10,
        "top_put_candidates": 10,
    },
    "indicators": {
        "ema_fast": 20,
        "ema_medium": 50,
        "ema_slow": 200,
        "rsi_period": 14,
        "adx_period": 14,
        "atr_period": 14,
        "supertrend_period": 10,
        "supertrend_multiplier": 3.0,
        "volume_multiplier": 1.5,
    },
    "risk_management": {
        "trailing_stop_enabled": True,
        "trailing_trigger_percent": 2.0,
        "trailing_distance_percent": 1.5,
        "target_1_rr": 2.0,
        "target_2_rr": 3.0,
    },
    "portfolio": {
        "default_quantity": 100,
        "auto_add_best_trade": True,
    },
    "backup": {
        "enabled": True,
        "keep_latest": 30,
    },
    "workflow": {
        "open_dashboard_after_run": True,
        "update_fno_daily": True,
    },
}


def deep_merge(defaults: dict, existing: dict) -> dict:
    """Add missing default settings without deleting user changes."""
    result = deepcopy(defaults)

    for key, value in existing.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def save_config(config: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    CONFIG_FILE.write_text(
        json.dumps(
            config,
            indent=4,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def load_config() -> dict[str, Any]:
    """
    Load the AQSD configuration.

    Creates the default file automatically if it is missing.
    Adds any newly introduced default settings while preserving
    the user's existing values.
    """

    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return deepcopy(DEFAULT_CONFIG)

    try:
        existing = json.loads(
            CONFIG_FILE.read_text(encoding="utf-8")
        )

    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Invalid JSON configuration:\n{CONFIG_FILE}\n{error}"
        ) from error

    merged = deep_merge(DEFAULT_CONFIG, existing)

    if merged != existing:
        save_config(merged)

    return merged


def get_setting(path: str, default: Any = None) -> Any:
    """
    Read a setting with dot notation.

    Example:
        get_setting("trading.capital")
        get_setting("scanner.minimum_call_score")
    """

    config: Any = load_config()

    for part in path.split("."):
        if not isinstance(config, dict) or part not in config:
            return default

        config = config[part]

    return config


def convert_value(raw_value: str) -> Any:
    """Convert command-line text into bool/int/float/string."""
    value = raw_value.strip()

    if value.lower() in {"true", "yes", "on"}:
        return True

    if value.lower() in {"false", "no", "off"}:
        return False

    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        return value


def set_setting(path: str, value: Any) -> None:
    """Update one dot-notation setting."""
    config = load_config()
    parts = path.split(".")

    current = config

    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}

        current = current[part]

    current[parts[-1]] = value
    save_config(config)


def show_config() -> None:
    config = load_config()

    print("\nAQSD CONFIGURATION")
    print("=" * 68)
    print(
        json.dumps(
            config,
            indent=4,
            ensure_ascii=False,
        )
    )
    print("=" * 68)
    print(f"File: {CONFIG_FILE}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create, view or update AQSD settings."
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help="Display all configuration settings.",
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset all settings to defaults.",
    )

    parser.add_argument(
        "--set",
        nargs=2,
        metavar=("SETTING", "VALUE"),
        help=(
            "Update one setting, for example: "
            "--set trading.risk_percent 1.5"
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.reset:
        save_config(DEFAULT_CONFIG)
        print("AQSD configuration reset to defaults.")
        print(CONFIG_FILE)
        return

    if args.set:
        path, raw_value = args.set
        value = convert_value(raw_value)

        set_setting(path, value)

        print("AQSD configuration updated.")
        print(f"{path} = {value}")
        print(CONFIG_FILE)
        return

    if args.show:
        show_config()
        return

    config = load_config()

    print("AQSD configuration is ready.")
    print(CONFIG_FILE)
    print(
        "Trading Capital:",
        config["trading"]["capital"],
    )
    print(
        "Risk per Trade:",
        f'{config["trading"]["risk_percent"]}%',
    )


if __name__ == "__main__":
    main()

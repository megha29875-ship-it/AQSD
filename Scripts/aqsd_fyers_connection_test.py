"""
AQSD FYERS CONNECTION TEST
Version: 1.0
"""

import os
from pathlib import Path

try:
    from fyers_apiv3 import fyersModel
except ImportError:
    print("\nERROR: fyers-apiv3 is not installed.")
    print("Run:")
    print("pip install fyers-apiv3")
    raise SystemExit

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "Data"

CONFIG_FILE = DATA / "fyers_config.env"


def load_config():
    cfg = {}

    if not CONFIG_FILE.exists():
        print(f"\nMissing configuration file:\n{CONFIG_FILE}")
        return None

    with open(CONFIG_FILE, "r") as f:
        for line in f:
            line = line.strip()

            if not line:
                continue

            if line.startswith("#"):
                continue

            if "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()

    return cfg


def test_connection():

    cfg = load_config()

    if cfg is None:
        return

    required = [
        "CLIENT_ID",
        "ACCESS_TOKEN"
    ]

    for item in required:
        if item not in cfg:
            print(f"Missing {item}")
            return

    fyers = fyersModel.FyersModel(
        client_id=cfg["CLIENT_ID"],
        token=cfg["ACCESS_TOKEN"],
        is_async=False,
        log_path=""
    )

    print("=" * 70)
    print("AQSD FYERS CONNECTION TEST")
    print("=" * 70)

    symbol = "NSE:RELIANCE-EQ"

    try:

        data = fyers.quotes(
            {"symbols": symbol}
        )

        print("\nConnection Successful.\n")

        print(data)

    except Exception as e:

        print("\nConnection Failed\n")
        print(e)


if __name__ == "__main__":
    test_connection()
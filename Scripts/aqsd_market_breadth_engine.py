"""
AQSD Market Breadth Engine v1.0

Purpose
-------
Builds market breadth from the latest AQSD live scanner output.

Supported scanner files
-----------------------
Output/AQSD_FYERS_Live_Scanner.csv
Output/AQSD_Live_Scanner.csv
Output/Live_Scanner.csv

Outputs
-------
Output/AQSD_Market_Breadth.csv
Output/AQSD_Market_Breadth_Sectors.csv
Output/AQSD_Market_Breadth.json

Examples
--------
python aqsd_market_breadth_engine.py --status
python aqsd_market_breadth_engine.py --run
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


BASE = Path(__file__).resolve().parent.parent
OUTPUT = BASE / "Output"
DATA = BASE / "Data"

SCANNER_CANDIDATES = [
    OUTPUT / "AQSD_FYERS_Live_Scanner.csv",
    OUTPUT / "AQSD_Live_Scanner.csv",
    OUTPUT / "Live_Scanner.csv",
    OUTPUT / "AQSD_Live_Watchlist.csv",
]

SUMMARY_OUTPUT = OUTPUT / "AQSD_Market_Breadth.csv"
SECTOR_OUTPUT = OUTPUT / "AQSD_Market_Breadth_Sectors.csv"
JSON_OUTPUT = OUTPUT / "AQSD_Market_Breadth.json"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return default if pd.isna(number) else number
    except Exception:
        return default


def find_scanner_file() -> Path:
    for path in SCANNER_CANDIDATES:
        if path.exists():
            return path

    matches = sorted(
        OUTPUT.glob("*scanner*.csv"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if matches:
        return matches[0]

    raise SystemExit(
        "No live scanner CSV found in Output folder."
    )


def choose_column(
    columns: list[str],
    candidates: list[str],
) -> str | None:
    lookup = {
        str(column).strip().lower(): column
        for column in columns
    }

    for candidate in candidates:
        if candidate.lower() in lookup:
            return lookup[candidate.lower()]

    return None


def classify_change(change: float) -> str:
    if change > 0:
        return "ADVANCE"
    if change < 0:
        return "DECLINE"
    return "UNCHANGED"


def build_breadth() -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    scanner_file = find_scanner_file()

    frame = pd.read_csv(
        scanner_file,
        low_memory=False,
    )

    if frame.empty:
        raise SystemExit(
            f"Scanner file is empty: {scanner_file}"
        )

    columns = list(frame.columns)

    symbol_col = choose_column(
        columns,
        [
            "symbol",
            "nse_symbol",
            "ticker",
            "underlying",
        ],
    )

    change_col = choose_column(
        columns,
        [
            "change_percent",
            "percent_change",
            "pct_change",
            "change_pct",
            "day_change_percent",
            "price_change_percent",
        ],
    )

    price_col = choose_column(
        columns,
        [
            "ltp",
            "last_price",
            "current_price",
            "close",
            "price",
        ],
    )

    prev_close_col = choose_column(
        columns,
        [
            "previous_close",
            "prev_close",
            "prevclose",
        ],
    )

    volume_col = choose_column(
        columns,
        [
            "volume",
            "day_volume",
            "traded_volume",
        ],
    )

    sector_col = choose_column(
        columns,
        [
            "sector",
            "industry",
            "sector_name",
        ],
    )

    if change_col:
        frame["_change_percent"] = pd.to_numeric(
            frame[change_col],
            errors="coerce",
        )
    elif price_col and prev_close_col:
        price = pd.to_numeric(
            frame[price_col],
            errors="coerce",
        )
        previous = pd.to_numeric(
            frame[prev_close_col],
            errors="coerce",
        )
        frame["_change_percent"] = (
            (price - previous) / previous * 100
        )
    else:
        raise SystemExit(
            "Could not find change-percent columns in scanner CSV."
        )

    frame = frame[
        frame["_change_percent"].notna()
    ].copy()

    if frame.empty:
        raise SystemExit(
            "No valid price-change rows found."
        )

    frame["_breadth_state"] = frame[
        "_change_percent"
    ].apply(classify_change)

    advances = int(
        frame["_breadth_state"].eq("ADVANCE").sum()
    )
    declines = int(
        frame["_breadth_state"].eq("DECLINE").sum()
    )
    unchanged = int(
        frame["_breadth_state"].eq("UNCHANGED").sum()
    )
    total = len(frame)

    advance_percent = advances / total * 100
    decline_percent = declines / total * 100

    ad_ratio = (
        advances / declines
        if declines > 0
        else float(advances)
    )

    average_change = frame[
        "_change_percent"
    ].mean()

    median_change = frame[
        "_change_percent"
    ].median()

    strong_advances = int(
        frame["_change_percent"].ge(1.0).sum()
    )
    strong_declines = int(
        frame["_change_percent"].le(-1.0).sum()
    )

    breadth_score = 50.0
    breadth_score += (
        advance_percent - decline_percent
    ) * 0.5
    breadth_score += max(
        -15,
        min(
            15,
            average_change * 10,
        ),
    )
    breadth_score = max(
        0,
        min(
            100,
            breadth_score,
        ),
    )

    if breadth_score >= 70:
        breadth_regime = "STRONG BULLISH"
    elif breadth_score >= 58:
        breadth_regime = "BULLISH"
    elif breadth_score <= 30:
        breadth_regime = "STRONG BEARISH"
    elif breadth_score <= 42:
        breadth_regime = "BEARISH"
    else:
        breadth_regime = "NEUTRAL / MIXED"

    volume_breadth = None

    if volume_col:
        frame["_volume"] = pd.to_numeric(
            frame[volume_col],
            errors="coerce",
        ).fillna(0)

        advancing_volume = frame.loc[
            frame["_breadth_state"].eq("ADVANCE"),
            "_volume",
        ].sum()

        declining_volume = frame.loc[
            frame["_breadth_state"].eq("DECLINE"),
            "_volume",
        ].sum()

        total_volume = (
            advancing_volume + declining_volume
        )

        if total_volume > 0:
            volume_breadth = (
                advancing_volume / total_volume * 100
            )

    summary = pd.DataFrame(
        [
            {
                "generated_at": datetime.now().isoformat(
                    timespec="seconds"
                ),
                "source_file": str(scanner_file),
                "symbols_count": total,
                "advances": advances,
                "declines": declines,
                "unchanged": unchanged,
                "advance_percent": round(
                    advance_percent,
                    2,
                ),
                "decline_percent": round(
                    decline_percent,
                    2,
                ),
                "advance_decline_ratio": round(
                    ad_ratio,
                    3,
                ),
                "average_change_percent": round(
                    average_change,
                    3,
                ),
                "median_change_percent": round(
                    median_change,
                    3,
                ),
                "strong_advances": strong_advances,
                "strong_declines": strong_declines,
                "volume_breadth_percent": (
                    round(volume_breadth, 2)
                    if volume_breadth is not None
                    else None
                ),
                "market_breadth_score": round(
                    breadth_score,
                    1,
                ),
                "breadth_regime": breadth_regime,
            }
        ]
    )

    sector_summary = pd.DataFrame()

    if sector_col:
        grouped = (
            frame.groupby(
                frame[sector_col]
                .fillna("UNKNOWN")
                .astype(str)
                .str.strip()
                .str.upper(),
                as_index=False,
            )
            .agg(
                symbols=(symbol_col, "count")
                if symbol_col
                else ("_breadth_state", "count"),
                advances=(
                    "_breadth_state",
                    lambda s: int(
                        s.eq("ADVANCE").sum()
                    ),
                ),
                declines=(
                    "_breadth_state",
                    lambda s: int(
                        s.eq("DECLINE").sum()
                    ),
                ),
                average_change_percent=(
                    "_change_percent",
                    "mean",
                ),
            )
        )

        grouped = grouped.rename(
            columns={sector_col: "sector"}
        )

        grouped["sector_breadth_score"] = (
            50
            + (
                grouped["advances"]
                - grouped["declines"]
            )
            / grouped["symbols"]
            * 50
            + grouped["average_change_percent"]
            * 8
        ).clip(0, 100)

        sector_summary = grouped.round(
            {
                "average_change_percent": 3,
                "sector_breadth_score": 1,
            }
        ).sort_values(
            "sector_breadth_score",
            ascending=False,
        )

    return summary, sector_summary, scanner_file


def save_outputs(
    summary: pd.DataFrame,
    sectors: pd.DataFrame,
) -> None:
    OUTPUT.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary.to_csv(
        SUMMARY_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    sectors.to_csv(
        SECTOR_OUTPUT,
        index=False,
        encoding="utf-8-sig",
    )

    JSON_OUTPUT.write_text(
        json.dumps(
            {
                "summary": summary.to_dict(
                    orient="records"
                ),
                "sectors": sectors.to_dict(
                    orient="records"
                ),
            },
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )


def show(
    summary: pd.DataFrame,
    scanner_file: Path,
) -> None:
    row = summary.iloc[0]

    print("\nAQSD MARKET BREADTH ENGINE")
    print("=" * 76)
    print(f"Source:                 {scanner_file.name}")
    print(f"Symbols:                {row['symbols_count']}")
    print(f"Advances:               {row['advances']}")
    print(f"Declines:               {row['declines']}")
    print(f"Unchanged:              {row['unchanged']}")
    print(f"Advance/Decline Ratio:  {row['advance_decline_ratio']}")
    print(f"Average Change:         {row['average_change_percent']}%")
    print(f"Breadth Score:          {row['market_breadth_score']}")
    print(f"Breadth Regime:         {row['breadth_regime']}")
    print("=" * 76)
    print(f"Summary:                {SUMMARY_OUTPUT}")
    print(f"Sectors:                {SECTOR_OUTPUT}")
    print(f"JSON:                   {JSON_OUTPUT}")


def status() -> None:
    print("\nAQSD MARKET BREADTH STATUS")
    print("=" * 72)

    found = False

    for path in SCANNER_CANDIDATES:
        state = "FOUND" if path.exists() else "MISSING"
        print(f"{path.name:<36} {state}")
        found = found or path.exists()

    if not found:
        matches = list(
            OUTPUT.glob("*scanner*.csv")
        )
        print(
            f"Other scanner CSV files: {len(matches)}"
        )

    print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AQSD Market Breadth Engine"
    )
    parser.add_argument(
        "--run",
        action="store_true",
    )
    parser.add_argument(
        "--status",
        action="store_true",
    )

    args = parser.parse_args()

    if args.status:
        status()
        return

    if args.run:
        summary, sectors, source = build_breadth()
        save_outputs(
            summary,
            sectors,
        )
        show(
            summary,
            source,
        )
        return

    raise SystemExit(
        "Use --status or --run"
    )


if __name__ == "__main__":
    main()

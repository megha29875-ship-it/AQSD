
"""
AQSD Professional
Module: AQSD Copilot
Version: 1.0

Purpose
-------
Provides a conversational command-line assistant for the AQSD database.

The Copilot does not call any external AI service. It uses AQSD's own
database, latest intelligence tables and a rule-based query interpreter.

Examples
--------
python aqsd_copilot.py --ask "Why is RELIANCE rated BUY?"
python aqsd_copilot.py --ask "Show top 10 stocks"
python aqsd_copilot.py --ask "Show banking stocks"
python aqsd_copilot.py --ask "Which sectors are strongest?"
python aqsd_copilot.py --ask "Which stocks should I avoid?"
python aqsd_copilot.py --interactive
python aqsd_copilot.py --status
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DB = BASE_DIR / "Data" / "aqsd_core.db"


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type='table' AND name=?
        """,
        (table,),
    ).fetchone()
    return row is not None


def latest_trade_date(con: sqlite3.Connection, table: str) -> str | None:
    try:
        row = con.execute(
            f"SELECT MAX(trade_date) AS d FROM {table}"
        ).fetchone()
        return row["d"] if row else None
    except Exception:
        return None


def show_status() -> None:
    with connect() as con:
        tables = [
            "unified_master_intelligence",
            "aqsd_trade_decisions",
            "sector_rotation_intelligence",
            "market_breadth_intelligence",
            "portfolio_allocation",
        ]

        print("\nAQSD COPILOT STATUS")
        print("=" * 72)
        print(f"Database: {DB}")

        for table in tables:
            exists = table_exists(con, table)
            count = 0
            latest = None

            if exists:
                try:
                    count = con.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                except Exception:
                    count = 0

                latest = latest_trade_date(con, table)

            print(
                f"{table:<36}"
                f"{'READY' if exists else 'MISSING':<10}"
                f"Rows: {count:<8}"
                f"Latest: {latest or '-'}"
            )

        print("=" * 72)


def extract_symbol(question: str) -> str | None:
    candidates = re.findall(r"\b[A-Z][A-Z0-9&\-]{1,15}\b", question.upper())

    stop_words = {
        "WHY", "SHOW", "TOP", "STOCKS", "STOCK", "WHICH", "WHAT",
        "BUY", "SELL", "AVOID", "WATCH", "STRONG", "SECTORS",
        "SECTOR", "RATED", "TODAY", "BEST", "WORST", "BANKING",
        "BANK", "IT", "AUTO", "PHARMA", "FMCG", "METAL", "REALTY",
    }

    with connect() as con:
        for candidate in candidates:
            if candidate in stop_words:
                continue

            row = con.execute(
                """
                SELECT nse_symbol
                FROM symbols
                WHERE UPPER(nse_symbol)=?
                LIMIT 1
                """,
                (candidate,),
            ).fetchone()

            if row:
                return row["nse_symbol"]

    return None


def extract_limit(question: str, default: int = 10) -> int:
    match = re.search(r"\b(\d{1,2})\b", question)

    if not match:
        return default

    return max(1, min(50, int(match.group(1))))


def answer_symbol(symbol: str) -> str:
    with connect() as con:
        if not table_exists(con, "unified_master_intelligence"):
            return "Unified Master Intelligence is not available."

        latest = latest_trade_date(con, "unified_master_intelligence")

        row = con.execute(
            """
            SELECT *
            FROM unified_master_intelligence
            WHERE trade_date=?
              AND UPPER(nse_symbol)=UPPER(?)
            LIMIT 1
            """,
            (latest, symbol),
        ).fetchone()

        if not row:
            return f"No latest intelligence found for {symbol}."

        decision = None

        if table_exists(con, "aqsd_trade_decisions"):
            decision_date = latest_trade_date(con, "aqsd_trade_decisions")
            decision = con.execute(
                """
                SELECT *
                FROM aqsd_trade_decisions
                WHERE trade_date=?
                  AND UPPER(nse_symbol)=UPPER(?)
                LIMIT 1
                """,
                (decision_date, symbol),
            ).fetchone()

        lines = [
            f"\nAQSD COPILOT — {symbol}",
            "=" * 72,
            f"Sector: {row['sector']}",
            f"Master Score: {row['master_score']}",
            f"Recommendation: {row['recommendation']}",
            f"Confidence: {row['confidence_percent']}%",
            f"Engine Agreement: {row['engine_agreement_percent']}%",
            f"Data Completeness: {row['data_completeness_percent']}%",
            f"Risk: {row['risk_level']}",
            f"Entry Quality: {row['entry_quality']}",
            f"Directional Bias: {row['directional_bias']}",
            "",
            "Engine Scores:",
            f"  Price Structure: {row['price_structure_score']}",
            f"  Sector Rotation: {row['sector_rotation_score']}",
            f"  Relative Strength: {row['relative_strength_score']}",
            f"  Market Breadth: {row['market_breadth_score']}",
            f"  News: {row['news_score']}",
            f"  Macro: {row['macro_score']}",
            f"  Futures: {row['futures_score']}",
            f"  Options: {row['options_score']}",
            "",
            f"Why: {row['reasons']}",
        ]

        if decision:
            lines.extend(
                [
                    "",
                    "Trade Decision:",
                    f"  Action: {decision['action']}",
                    f"  Priority Rank: {decision['priority_rank']}",
                    f"  Last Price: {decision['last_price']}",
                    f"  Entry Zone: {decision['entry_low']} to {decision['entry_high']}",
                    f"  Stop Loss: {decision['stop_loss']}",
                    f"  Target 1: {decision['target_1']}",
                    f"  Target 2: {decision['target_2']}",
                    f"  R:R 1: {decision['reward_risk_1']}",
                    f"  R:R 2: {decision['reward_risk_2']}",
                    f"  Rationale: {decision['rationale']}",
                ]
            )

        lines.append("=" * 72)
        return "\n".join(lines)


def answer_top(question: str) -> str:
    limit = extract_limit(question, 10)

    with connect() as con:
        if table_exists(con, "aqsd_trade_decisions"):
            latest = latest_trade_date(con, "aqsd_trade_decisions")

            df = pd.read_sql_query(
                """
                SELECT
                    priority_rank,
                    nse_symbol,
                    sector,
                    action,
                    master_score,
                    confidence_percent,
                    risk_level,
                    entry_quality,
                    last_price,
                    target_1,
                    stop_loss
                FROM aqsd_trade_decisions
                WHERE trade_date=?
                ORDER BY priority_rank
                LIMIT ?
                """,
                con,
                params=(latest, limit),
            )

        elif table_exists(con, "unified_master_intelligence"):
            latest = latest_trade_date(
                con,
                "unified_master_intelligence",
            )

            df = pd.read_sql_query(
                """
                SELECT
                    nse_symbol,
                    sector,
                    master_score,
                    recommendation,
                    confidence_percent,
                    risk_level
                FROM unified_master_intelligence
                WHERE trade_date=?
                ORDER BY master_score DESC
                LIMIT ?
                """,
                con,
                params=(latest, limit),
            )

        else:
            return "No ranking data is available."

    if df.empty:
        return "No ranked stocks found."

    return "\nTOP AQSD OPPORTUNITIES\n" + "=" * 72 + "\n" + df.to_string(index=False)


def answer_avoid(question: str) -> str:
    limit = extract_limit(question, 10)

    with connect() as con:
        if not table_exists(con, "aqsd_trade_decisions"):
            return "Decision Engine data is not available."

        latest = latest_trade_date(con, "aqsd_trade_decisions")

        df = pd.read_sql_query(
            """
            SELECT
                priority_rank,
                nse_symbol,
                sector,
                action,
                master_score,
                confidence_percent,
                risk_level,
                directional_bias,
                rationale
            FROM aqsd_trade_decisions
            WHERE trade_date=?
              AND action IN ('AVOID','EXIT / AVOID')
            ORDER BY master_score ASC, priority_rank
            LIMIT ?
            """,
            con,
            params=(latest, limit),
        )

    if df.empty:
        return "No Avoid or Exit signals found in the latest run."

    return "\nAQSD AVOID / EXIT LIST\n" + "=" * 72 + "\n" + df.to_string(index=False)


def answer_sectors(question: str) -> str:
    limit = extract_limit(question, 10)

    with connect() as con:
        if not table_exists(con, "sector_rotation_intelligence"):
            return "Sector Rotation data is not available."

        latest = latest_trade_date(con, "sector_rotation_intelligence")

        df = pd.read_sql_query(
            """
            SELECT
                sector,
                sector_rotation_score,
                rotation_state,
                trend_state,
                bullish_breadth_percent,
                average_5d_return,
                average_20d_return,
                leader_symbol,
                leader_score
            FROM sector_rotation_intelligence
            WHERE trade_date=?
            ORDER BY sector_rotation_score DESC
            LIMIT ?
            """,
            con,
            params=(latest, limit),
        )

    if df.empty:
        return "No sector rotation results found."

    return "\nSTRONGEST AQSD SECTORS\n" + "=" * 72 + "\n" + df.to_string(index=False)


def answer_sector_stocks(question: str) -> str:
    sector_keywords = {
        "BANK": ["BANK", "BANKING"],
        "IT": ["IT", "TECHNOLOGY"],
        "AUTO": ["AUTO", "AUTOMOBILE"],
        "PHARMA": ["PHARMA", "PHARMACEUTICAL"],
        "FMCG": ["FMCG"],
        "METAL": ["METAL", "METALS"],
        "REALTY": ["REALTY", "REAL ESTATE"],
        "ENERGY": ["ENERGY", "OIL", "GAS"],
        "DEFENCE": ["DEFENCE", "DEFENSE"],
        "POWER": ["POWER", "UTILITIES"],
    }

    upper = question.upper()
    detected = None

    for sector, words in sector_keywords.items():
        if any(word in upper for word in words):
            detected = sector
            break

    if not detected:
        return "I could not identify the sector in the question."

    limit = extract_limit(question, 10)

    with connect() as con:
        if not table_exists(con, "unified_master_intelligence"):
            return "Unified Master Intelligence is not available."

        latest = latest_trade_date(
            con,
            "unified_master_intelligence",
        )

        df = pd.read_sql_query(
            """
            SELECT
                nse_symbol,
                sector,
                master_score,
                recommendation,
                confidence_percent,
                risk_level,
                entry_quality
            FROM unified_master_intelligence
            WHERE trade_date=?
              AND UPPER(sector) LIKE ?
            ORDER BY master_score DESC
            LIMIT ?
            """,
            con,
            params=(latest, f"%{detected}%", limit),
        )

    if df.empty:
        return f"No latest stocks found for sector {detected}."

    return f"\nTOP {detected} STOCKS\n" + "=" * 72 + "\n" + df.to_string(index=False)


def answer(question: str) -> str:
    q = question.strip()

    if not q:
        return "Please enter a question."

    symbol = extract_symbol(q)

    if symbol:
        return answer_symbol(symbol)

    upper = q.upper()

    if any(word in upper for word in ["AVOID", "EXIT", "WORST"]):
        return answer_avoid(q)

    if "SECTOR" in upper and any(
        word in upper
        for word in ["STRONG", "BEST", "ROTATION", "LEADING"]
    ):
        return answer_sectors(q)

    if any(
        word in upper
        for word in [
            "BANKING", "BANK", "PHARMA", "FMCG",
            "METAL", "REALTY", "DEFENCE", "POWER",
            "AUTO", "ENERGY",
        ]
    ):
        return answer_sector_stocks(q)

    if any(
        word in upper
        for word in ["TOP", "BEST", "OPPORTUNITY", "OPPORTUNITIES"]
    ):
        return answer_top(q)

    return (
        "I understood the question, but the current Copilot supports these patterns:\n"
        "- Why is RELIANCE rated BUY?\n"
        "- Show top 10 stocks\n"
        "- Which sectors are strongest?\n"
        "- Show banking stocks\n"
        "- Which stocks should I avoid?"
    )


def interactive() -> None:
    print("\nAQSD COPILOT")
    print("=" * 72)
    print("Type 'exit' to close.")

    while True:
        question = input("\nAsk AQSD: ").strip()

        if question.lower() in {"exit", "quit", "close"}:
            print("AQSD Copilot closed.")
            break

        print(answer(question))


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD conversational market intelligence assistant."
    )

    parser.add_argument(
        "--ask",
        help="Ask one AQSD question.",
    )

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Start interactive Copilot mode.",
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show Copilot dependency status.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.status:
        show_status()
        return

    if args.ask:
        print(answer(args.ask))
        return

    interactive()


if __name__ == "__main__":
    main()

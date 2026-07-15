
"""
AQSD Core
Module: Data Hub API
Version: 1.0

Provides one reusable interface for AQSD modules to access:

- Symbol Master
- Cached OHLCV history
- Latest prices
- Sector / industry metadata
- Intelligence score history
- News events
- Macro events
- Global markets
- Commodities
- System settings

Typical use
-----------
from aqsd_datahub import AQSDDataHub

hub = AQSDDataHub()

history = hub.get_history("RELIANCE", rows=250)
last_price = hub.get_last_price("RELIANCE")
sector = hub.get_sector("RELIANCE")
symbols = hub.get_symbols(fno_only=True)

hub.save_intelligence_score(
    symbol="RELIANCE",
    score_date="2026-07-15",
    trend_score=88,
    structure_score=82,
    master_score=86,
    recommendation="BUY CANDIDATE",
)

Commands
--------
python aqsd_datahub.py --status
python aqsd_datahub.py --symbol RELIANCE
python aqsd_datahub.py --history RELIANCE --rows 20
python aqsd_datahub.py --leaders --days 5
python aqsd_datahub.py --improving --days 5
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from aqsd_database import connect, setup_database


# ============================================================
# PATHS
# ============================================================

SCRIPTS_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPTS_DIR.parent
DATABASE_FILE = BASE_DIR / "Data" / "aqsd_core.db"


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass(frozen=True)
class SymbolInfo:
    symbol_id: int
    nse_symbol: str
    yahoo_symbol: str
    company_name: str
    sector: str
    industry: str
    fno_eligible: bool
    active: bool
    source: str
    last_updated: str


# ============================================================
# NORMALIZATION
# ============================================================

def normalize_nse_symbol(value: str) -> str:
    symbol = str(value or "").strip().upper()

    if symbol.endswith(".NS"):
        symbol = symbol[:-3]

    return symbol.replace(" ", "")


def normalize_yahoo_symbol(value: str) -> str:
    symbol = normalize_nse_symbol(value)
    return f"{symbol}.NS" if symbol else ""


def iso_date(value: str | date | datetime | None) -> str:
    if value is None:
        return date.today().isoformat()

    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, date):
        return value.isoformat()

    return str(value)


# ============================================================
# DATA HUB
# ============================================================

class AQSDDataHub:
    """
    Central read/write API for AQSD Core.

    The class opens short-lived SQLite connections for each operation,
    which is safer for scripts that run independently.
    """

    def __init__(self) -> None:
        setup_database()

    # --------------------------------------------------------
    # Symbol Master
    # --------------------------------------------------------

    def get_symbol(self, symbol: str) -> SymbolInfo | None:
        nse_symbol = normalize_nse_symbol(symbol)
        yahoo_symbol = normalize_yahoo_symbol(symbol)

        with connect() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM symbols
                WHERE nse_symbol = ?
                   OR yahoo_symbol = ?
                LIMIT 1
                """,
                (nse_symbol, yahoo_symbol),
            ).fetchone()

        if not row:
            return None

        return SymbolInfo(
            symbol_id=int(row["symbol_id"]),
            nse_symbol=str(row["nse_symbol"]),
            yahoo_symbol=str(row["yahoo_symbol"]),
            company_name=str(row["company_name"] or ""),
            sector=str(row["sector"] or ""),
            industry=str(row["industry"] or ""),
            fno_eligible=bool(row["fno_eligible"]),
            active=bool(row["active"]),
            source=str(row["source"] or ""),
            last_updated=str(row["last_updated"] or ""),
        )

    def get_symbols(
        self,
        *,
        active_only: bool = True,
        fno_only: bool = False,
        sector: str | None = None,
    ) -> list[SymbolInfo]:
        clauses: list[str] = []
        params: list[Any] = []

        if active_only:
            clauses.append("active = 1")

        if fno_only:
            clauses.append("fno_eligible = 1")

        if sector:
            clauses.append("UPPER(sector) = UPPER(?)")
            params.append(sector)

        where_clause = (
            " WHERE " + " AND ".join(clauses)
            if clauses
            else ""
        )

        query = (
            "SELECT * FROM symbols"
            + where_clause
            + " ORDER BY nse_symbol"
        )

        with connect() as connection:
            rows = connection.execute(query, params).fetchall()

        return [
            SymbolInfo(
                symbol_id=int(row["symbol_id"]),
                nse_symbol=str(row["nse_symbol"]),
                yahoo_symbol=str(row["yahoo_symbol"]),
                company_name=str(row["company_name"] or ""),
                sector=str(row["sector"] or ""),
                industry=str(row["industry"] or ""),
                fno_eligible=bool(row["fno_eligible"]),
                active=bool(row["active"]),
                source=str(row["source"] or ""),
                last_updated=str(row["last_updated"] or ""),
            )
            for row in rows
        ]

    def get_sector(self, symbol: str) -> str:
        info = self.get_symbol(symbol)
        return info.sector if info else ""

    def search_symbols(self, text: str) -> pd.DataFrame:
        pattern = f"%{str(text or '').strip()}%"

        with connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    nse_symbol,
                    yahoo_symbol,
                    company_name,
                    sector,
                    industry,
                    fno_eligible,
                    active
                FROM symbols
                WHERE nse_symbol LIKE ?
                   OR yahoo_symbol LIKE ?
                   OR company_name LIKE ?
                   OR sector LIKE ?
                   OR industry LIKE ?
                ORDER BY active DESC, nse_symbol
                """,
                (pattern, pattern, pattern, pattern, pattern),
            ).fetchall()

        return pd.DataFrame([dict(row) for row in rows])

    # --------------------------------------------------------
    # Price Data
    # --------------------------------------------------------

    def get_history(
        self,
        symbol: str,
        *,
        rows: int = 250,
        start_date: str | date | datetime | None = None,
        end_date: str | date | datetime | None = None,
    ) -> pd.DataFrame:
        info = self.get_symbol(symbol)

        if not info:
            raise ValueError(f"Unknown symbol: {symbol}")

        clauses = ["symbol_id = ?"]
        params: list[Any] = [info.symbol_id]

        if start_date is not None:
            clauses.append("trade_date >= ?")
            params.append(iso_date(start_date))

        if end_date is not None:
            clauses.append("trade_date <= ?")
            params.append(iso_date(end_date))

        where_clause = " AND ".join(clauses)

        if start_date is None and end_date is None and rows > 0:
            query = f"""
                SELECT *
                FROM (
                    SELECT
                        trade_date,
                        open,
                        high,
                        low,
                        close,
                        adjusted_close,
                        volume,
                        source,
                        downloaded_at
                    FROM daily_prices
                    WHERE {where_clause}
                    ORDER BY trade_date DESC
                    LIMIT ?
                )
                ORDER BY trade_date
            """
            params.append(rows)

        else:
            query = f"""
                SELECT
                    trade_date,
                    open,
                    high,
                    low,
                    close,
                    adjusted_close,
                    volume,
                    source,
                    downloaded_at
                FROM daily_prices
                WHERE {where_clause}
                ORDER BY trade_date
            """

        with connect() as connection:
            frame = pd.read_sql_query(
                query,
                connection,
                params=params,
            )

        if frame.empty:
            return frame

        frame["trade_date"] = pd.to_datetime(frame["trade_date"])
        frame = frame.set_index("trade_date")

        return frame

    def get_last_price(self, symbol: str) -> dict | None:
        info = self.get_symbol(symbol)

        if not info:
            return None

        with connect() as connection:
            row = connection.execute(
                """
                SELECT
                    trade_date,
                    open,
                    high,
                    low,
                    close,
                    adjusted_close,
                    volume,
                    source,
                    downloaded_at
                FROM daily_prices
                WHERE symbol_id = ?
                ORDER BY trade_date DESC
                LIMIT 1
                """,
                (info.symbol_id,),
            ).fetchone()

        return dict(row) if row else None

    def get_returns(
        self,
        symbol: str,
        periods: Iterable[int] = (1, 5, 20, 60, 120),
    ) -> dict[int, float | None]:
        periods = tuple(sorted(set(int(item) for item in periods)))

        if not periods:
            return {}

        history = self.get_history(
            symbol,
            rows=max(periods) + 2,
        )

        if history.empty:
            return {period: None for period in periods}

        close = history["close"].dropna()

        results: dict[int, float | None] = {}

        for period in periods:
            if len(close) <= period:
                results[period] = None
                continue

            previous = float(close.iloc[-1 - period])
            current = float(close.iloc[-1])

            results[period] = (
                None
                if previous == 0
                else round((current / previous - 1) * 100, 2)
            )

        return results

    def get_price_status(self) -> pd.DataFrame:
        with connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    s.nse_symbol,
                    s.yahoo_symbol,
                    s.active,
                    COUNT(p.price_id) AS price_rows,
                    MIN(p.trade_date) AS first_date,
                    MAX(p.trade_date) AS latest_date
                FROM symbols s
                LEFT JOIN daily_prices p
                    ON p.symbol_id = s.symbol_id
                GROUP BY
                    s.symbol_id,
                    s.nse_symbol,
                    s.yahoo_symbol,
                    s.active
                ORDER BY s.nse_symbol
                """
            ).fetchall()

        return pd.DataFrame([dict(row) for row in rows])

    # --------------------------------------------------------
    # Intelligence Scores
    # --------------------------------------------------------

    def save_intelligence_score(
        self,
        *,
        symbol: str,
        score_date: str | date | datetime | None = None,
        structure_score: float | None = None,
        trend_score: float | None = None,
        relative_strength_score: float | None = None,
        sector_score: float | None = None,
        pivot_score: float | None = None,
        news_score: float | None = None,
        macro_score: float | None = None,
        commodity_score: float | None = None,
        global_score: float | None = None,
        derivatives_score: float | None = None,
        master_score: float | None = None,
        directional_bias: str = "",
        recommendation: str = "",
        confidence_grade: str = "",
        explanation: str = "",
    ) -> None:
        info = self.get_symbol(symbol)

        if not info:
            raise ValueError(f"Unknown symbol: {symbol}")

        value_date = iso_date(score_date)
        created_at = datetime.now().isoformat(timespec="seconds")

        with connect() as connection:
            connection.execute(
                """
                INSERT INTO intelligence_scores(
                    score_date,
                    symbol_id,
                    structure_score,
                    trend_score,
                    relative_strength_score,
                    sector_score,
                    pivot_score,
                    news_score,
                    macro_score,
                    commodity_score,
                    global_score,
                    derivatives_score,
                    master_score,
                    directional_bias,
                    recommendation,
                    confidence_grade,
                    explanation,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(score_date, symbol_id)
                DO UPDATE SET
                    structure_score = excluded.structure_score,
                    trend_score = excluded.trend_score,
                    relative_strength_score =
                        excluded.relative_strength_score,
                    sector_score = excluded.sector_score,
                    pivot_score = excluded.pivot_score,
                    news_score = excluded.news_score,
                    macro_score = excluded.macro_score,
                    commodity_score = excluded.commodity_score,
                    global_score = excluded.global_score,
                    derivatives_score = excluded.derivatives_score,
                    master_score = excluded.master_score,
                    directional_bias = excluded.directional_bias,
                    recommendation = excluded.recommendation,
                    confidence_grade = excluded.confidence_grade,
                    explanation = excluded.explanation,
                    created_at = excluded.created_at
                """,
                (
                    value_date,
                    info.symbol_id,
                    structure_score,
                    trend_score,
                    relative_strength_score,
                    sector_score,
                    pivot_score,
                    news_score,
                    macro_score,
                    commodity_score,
                    global_score,
                    derivatives_score,
                    master_score,
                    directional_bias,
                    recommendation,
                    confidence_grade,
                    explanation,
                    created_at,
                ),
            )
            connection.commit()

    def get_intelligence_history(
        self,
        symbol: str,
        *,
        days: int = 30,
    ) -> pd.DataFrame:
        info = self.get_symbol(symbol)

        if not info:
            raise ValueError(f"Unknown symbol: {symbol}")

        cutoff = (
            date.today() - timedelta(days=max(days, 1))
        ).isoformat()

        with connect() as connection:
            frame = pd.read_sql_query(
                """
                SELECT
                    score_date,
                    structure_score,
                    trend_score,
                    relative_strength_score,
                    sector_score,
                    pivot_score,
                    news_score,
                    macro_score,
                    commodity_score,
                    global_score,
                    derivatives_score,
                    master_score,
                    directional_bias,
                    recommendation,
                    confidence_grade,
                    explanation
                FROM intelligence_scores
                WHERE symbol_id = ?
                  AND score_date >= ?
                ORDER BY score_date
                """,
                connection,
                params=(info.symbol_id, cutoff),
            )

        if not frame.empty:
            frame["score_date"] = pd.to_datetime(
                frame["score_date"]
            )
            frame = frame.set_index("score_date")

        return frame

    def get_latest_intelligence(self) -> pd.DataFrame:
        with connect() as connection:
            frame = pd.read_sql_query(
                """
                SELECT
                    s.nse_symbol,
                    s.yahoo_symbol,
                    s.sector,
                    i.score_date,
                    i.structure_score,
                    i.trend_score,
                    i.relative_strength_score,
                    i.sector_score,
                    i.pivot_score,
                    i.news_score,
                    i.macro_score,
                    i.commodity_score,
                    i.global_score,
                    i.derivatives_score,
                    i.master_score,
                    i.directional_bias,
                    i.recommendation,
                    i.confidence_grade,
                    i.explanation
                FROM symbols s
                JOIN intelligence_scores i
                    ON i.score_id = (
                        SELECT score_id
                        FROM intelligence_scores x
                        WHERE x.symbol_id = s.symbol_id
                        ORDER BY score_date DESC, score_id DESC
                        LIMIT 1
                    )
                WHERE s.active = 1
                ORDER BY i.master_score DESC, s.nse_symbol
                """,
                connection,
            )

        return frame

    def get_leaders(
        self,
        *,
        limit: int = 20,
        minimum_score: float = 60,
    ) -> pd.DataFrame:
        frame = self.get_latest_intelligence()

        if frame.empty:
            return frame

        frame = frame[
            frame["master_score"].fillna(0) >= minimum_score
        ]

        return frame.head(limit).reset_index(drop=True)

    def get_improving_symbols(
        self,
        *,
        days: int = 5,
        minimum_change: float = 5,
        limit: int = 20,
    ) -> pd.DataFrame:
        cutoff = (
            date.today() - timedelta(days=max(days, 1) + 7)
        ).isoformat()

        with connect() as connection:
            frame = pd.read_sql_query(
                """
                SELECT
                    s.nse_symbol,
                    s.sector,
                    i.score_date,
                    i.master_score
                FROM symbols s
                JOIN intelligence_scores i
                    ON i.symbol_id = s.symbol_id
                WHERE s.active = 1
                  AND i.score_date >= ?
                  AND i.master_score IS NOT NULL
                ORDER BY s.nse_symbol, i.score_date
                """,
                connection,
                params=(cutoff,),
            )

        if frame.empty:
            return frame

        results = []

        for symbol, group in frame.groupby("nse_symbol"):
            group = group.sort_values("score_date").tail(max(days, 2))

            if len(group) < 2:
                continue

            first_score = float(group["master_score"].iloc[0])
            latest_score = float(group["master_score"].iloc[-1])
            change = latest_score - first_score

            if change >= minimum_change:
                results.append(
                    {
                        "nse_symbol": symbol,
                        "sector": group["sector"].iloc[-1],
                        "first_score": round(first_score, 2),
                        "latest_score": round(latest_score, 2),
                        "score_change": round(change, 2),
                        "observations": len(group),
                    }
                )

        return (
            pd.DataFrame(results)
            .sort_values(
                "score_change",
                ascending=False,
            )
            .head(limit)
            .reset_index(drop=True)
            if results
            else pd.DataFrame()
        )

    # --------------------------------------------------------
    # News / Macro / Global / Commodities
    # --------------------------------------------------------

    def add_news_event(
        self,
        *,
        event_time: str | datetime,
        source: str,
        headline: str,
        url: str = "",
        event_type: str = "",
        company_name: str = "",
        symbol: str = "",
        sector: str = "",
        country: str = "India",
        sentiment_score: float | None = None,
        materiality_score: float | None = None,
        credibility_score: float | None = None,
        urgency_score: float | None = None,
        expected_impact: str = "",
        time_horizon: str = "",
        status: str = "NEW",
        raw_payload: dict | list | str | None = None,
    ) -> int:
        event_time_text = (
            event_time.isoformat(timespec="seconds")
            if isinstance(event_time, datetime)
            else str(event_time)
        )

        nse_symbol = normalize_nse_symbol(symbol)

        raw_text = (
            json.dumps(
                raw_payload,
                ensure_ascii=False,
            )
            if isinstance(raw_payload, (dict, list))
            else str(raw_payload or "")
        )

        with connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO news_events(
                    event_time,
                    source,
                    headline,
                    url,
                    event_type,
                    company_name,
                    nse_symbol,
                    sector,
                    country,
                    sentiment_score,
                    materiality_score,
                    credibility_score,
                    urgency_score,
                    expected_impact,
                    time_horizon,
                    status,
                    raw_payload,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_time_text,
                    source,
                    headline,
                    url,
                    event_type,
                    company_name,
                    nse_symbol,
                    sector,
                    country,
                    sentiment_score,
                    materiality_score,
                    credibility_score,
                    urgency_score,
                    expected_impact,
                    time_horizon,
                    status,
                    raw_text,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def get_news_events(
        self,
        *,
        symbol: str = "",
        days: int = 7,
        limit: int = 100,
    ) -> pd.DataFrame:
        cutoff = (
            datetime.now() - timedelta(days=max(days, 1))
        ).isoformat(timespec="seconds")

        clauses = ["event_time >= ?"]
        params: list[Any] = [cutoff]

        if symbol:
            clauses.append("nse_symbol = ?")
            params.append(normalize_nse_symbol(symbol))

        params.append(limit)

        with connect() as connection:
            frame = pd.read_sql_query(
                f"""
                SELECT *
                FROM news_events
                WHERE {' AND '.join(clauses)}
                ORDER BY event_time DESC
                LIMIT ?
                """,
                connection,
                params=params,
            )

        return frame

    def set_setting(
        self,
        key: str,
        value: Any,
        setting_type: str = "text",
    ) -> None:
        with connect() as connection:
            connection.execute(
                """
                INSERT INTO settings(
                    setting_key,
                    setting_value,
                    setting_type,
                    updated_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(setting_key)
                DO UPDATE SET
                    setting_value = excluded.setting_value,
                    setting_type = excluded.setting_type,
                    updated_at = excluded.updated_at
                """,
                (
                    key,
                    json.dumps(value)
                    if not isinstance(value, str)
                    else value,
                    setting_type,
                    datetime.now().isoformat(timespec="seconds"),
                ),
            )
            connection.commit()

    def get_setting(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        with connect() as connection:
            row = connection.execute(
                """
                SELECT setting_value, setting_type
                FROM settings
                WHERE setting_key = ?
                """,
                (key,),
            ).fetchone()

        if not row:
            return default

        value = row["setting_value"]
        setting_type = row["setting_type"]

        if setting_type in {"json", "list", "dict", "number", "boolean"}:
            try:
                return json.loads(value)
            except Exception:
                return value

        return value

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    def status(self) -> dict:
        with connect() as connection:
            counts = {}

            for table in (
                "symbols",
                "daily_prices",
                "intelligence_scores",
                "news_events",
                "macro_events",
                "global_markets",
                "commodities",
                "system_runs",
            ):
                counts[table] = int(
                    connection.execute(
                        f"SELECT COUNT(*) FROM {table}"
                    ).fetchone()[0]
                )

            latest_price = connection.execute(
                "SELECT MAX(trade_date) FROM daily_prices"
            ).fetchone()[0]

            latest_score = connection.execute(
                "SELECT MAX(score_date) FROM intelligence_scores"
            ).fetchone()[0]

        return {
            "database": str(DATABASE_FILE),
            "counts": counts,
            "latest_price_date": latest_price or "No data",
            "latest_score_date": latest_score or "No data",
        }


# ============================================================
# CLI
# ============================================================

def print_dataframe(frame: pd.DataFrame) -> None:
    if frame.empty:
        print("No records found.")
        return

    with pd.option_context(
        "display.max_rows",
        50,
        "display.max_columns",
        30,
        "display.width",
        180,
    ):
        print(frame.to_string(index=False))


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AQSD Core Data Hub API."
    )

    parser.add_argument(
        "--status",
        action="store_true",
        help="Show Data Hub status.",
    )

    parser.add_argument(
        "--symbol",
        metavar="SYMBOL",
        help="Show symbol metadata and latest price.",
    )

    parser.add_argument(
        "--history",
        metavar="SYMBOL",
        help="Show cached history for one symbol.",
    )

    parser.add_argument(
        "--rows",
        type=int,
        default=20,
        help="Rows for --history.",
    )

    parser.add_argument(
        "--leaders",
        action="store_true",
        help="Show latest AQSD leaders.",
    )

    parser.add_argument(
        "--improving",
        action="store_true",
        help="Show symbols whose Master Score is improving.",
    )

    parser.add_argument(
        "--days",
        type=int,
        default=5,
        help="Lookback days for --improving.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum displayed rows.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    hub = AQSDDataHub()

    if args.symbol:
        info = hub.get_symbol(args.symbol)
        last = hub.get_last_price(args.symbol)

        print("\nAQSD SYMBOL SNAPSHOT")
        print("=" * 72)
        print(info or "Symbol not found")
        print(last or "No cached price")
        return

    if args.history:
        frame = hub.get_history(
            args.history,
            rows=args.rows,
        )

        print_dataframe(
            frame.reset_index()
        )
        return

    if args.leaders:
        print_dataframe(
            hub.get_leaders(limit=args.limit)
        )
        return

    if args.improving:
        print_dataframe(
            hub.get_improving_symbols(
                days=args.days,
                limit=args.limit,
            )
        )
        return

    status = hub.status()

    print("\nAQSD CORE DATA HUB STATUS")
    print("=" * 72)
    print(f"Database: {status['database']}")
    print(f"Latest price date: {status['latest_price_date']}")
    print(f"Latest score date: {status['latest_score_date']}")
    print("-" * 72)

    for table, count in status["counts"].items():
        print(f"{table:<24}{count:>12}")

    print("=" * 72)


if __name__ == "__main__":
    main()

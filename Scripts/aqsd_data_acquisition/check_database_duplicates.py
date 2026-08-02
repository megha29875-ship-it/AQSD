import sqlite3

DB = r"D:\AQSD_DATA\Databases\NSE_FNO_Historical.db"

conn = sqlite3.connect(DB)
cur = conn.cursor()

futures_duplicates = cur.execute("""
    SELECT COUNT(*)
    FROM (
        SELECT
            trade_date,
            symbol,
            expiry,
            COUNT(*) AS n
        FROM futures_history
        GROUP BY
            trade_date,
            symbol,
            expiry
        HAVING COUNT(*) > 1
    )
""").fetchone()[0]

options_duplicates = cur.execute("""
    SELECT COUNT(*)
    FROM (
        SELECT
            trade_date,
            symbol,
            expiry,
            strike,
            option_type,
            COUNT(*) AS n
        FROM options_history
        GROUP BY
            trade_date,
            symbol,
            expiry,
            strike,
            option_type
        HAVING COUNT(*) > 1
    )
""").fetchone()[0]

print()
print("AQSD DATABASE DUPLICATE CHECK")
print("=" * 45)
print(f"FUTURES DUPLICATE KEYS : {futures_duplicates:,}")
print(f"OPTIONS DUPLICATE KEYS : {options_duplicates:,}")
print("=" * 45)

# ---------------------------------------------------------
# SESSION COVERAGE CHECK
# ---------------------------------------------------------

futures_sessions = cur.execute("""
    SELECT COUNT(DISTINCT trade_date)
    FROM futures_history
""").fetchone()[0]

options_sessions = cur.execute("""
    SELECT COUNT(DISTINCT trade_date)
    FROM options_history
""").fetchone()[0]

all_sessions = cur.execute("""
    SELECT COUNT(DISTINCT trade_date)
    FROM (
        SELECT trade_date FROM futures_history
        UNION ALL
        SELECT trade_date FROM options_history
    )
""").fetchone()[0]

date_range = cur.execute("""
    SELECT MIN(trade_date), MAX(trade_date)
    FROM (
        SELECT trade_date FROM futures_history
        UNION ALL
        SELECT trade_date FROM options_history
    )
""").fetchone()

print()
print("AQSD DATABASE SESSION COVERAGE")
print("=" * 45)
print(f"FUTURES SESSIONS : {futures_sessions:,}")
print(f"OPTIONS SESSIONS : {options_sessions:,}")
print(f"TOTAL SESSIONS   : {all_sessions:,}")
print(f"FIRST SESSION    : {date_range[0]}")
print(f"LAST SESSION     : {date_range[1]}")
print("=" * 45)

# ---------------------------------------------------------
# ROW DISTRIBUTION BY SESSION
# ---------------------------------------------------------

rows = cur.execute("""
    SELECT
        trade_date,
        SUM(futures_rows) AS futures_rows,
        SUM(options_rows) AS options_rows,
        SUM(futures_rows + options_rows) AS total_rows
    FROM (
        SELECT
            trade_date,
            COUNT(*) AS futures_rows,
            0 AS options_rows
        FROM futures_history
        GROUP BY trade_date

        UNION ALL

        SELECT
            trade_date,
            0 AS futures_rows,
            COUNT(*) AS options_rows
        FROM options_history
        GROUP BY trade_date
    )
    GROUP BY trade_date
    ORDER BY trade_date
""").fetchall()

totals = [r[3] for r in rows]

print()
print("AQSD ROW DISTRIBUTION CHECK")
print("=" * 60)

print(f"SESSIONS        : {len(rows):,}")
print(f"MIN ROWS/DAY    : {min(totals):,}")
print(f"MAX ROWS/DAY    : {max(totals):,}")
print(f"AVG ROWS/DAY    : {sum(totals) / len(totals):,.0f}")

print()
print("LOWEST 5 SESSIONS")
for r in sorted(rows, key=lambda x: x[3])[:5]:
    print(
        f"{r[0]}  Futures={r[1]:,}  "
        f"Options={r[2]:,}  Total={r[3]:,}"
    )

print()
print("HIGHEST 5 SESSIONS")
for r in sorted(rows, key=lambda x: x[3], reverse=True)[:5]:
    print(
        f"{r[0]}  Futures={r[1]:,}  "
        f"Options={r[2]:,}  Total={r[3]:,}"
    )

print("=" * 60)

# ---------------------------------------------------------
# CONTRACT MASTER STRUCTURE
# ---------------------------------------------------------

contract_total = cur.execute("""
    SELECT COUNT(*)
    FROM contract_master
""").fetchone()[0]

contract_unique = cur.execute("""
    SELECT COUNT(DISTINCT symbol)
    FROM contract_master
""").fetchone()[0]

futures_contracts = cur.execute("""
    SELECT COUNT(DISTINCT symbol || '|' || expiry)
    FROM futures_history
""").fetchone()[0]

options_contracts = cur.execute("""
    SELECT COUNT(DISTINCT symbol || '|' || expiry || '|' || strike || '|' || option_type)
    FROM options_history
""").fetchone()[0]

print()
print("AQSD CONTRACT STRUCTURE CHECK")
print("=" * 60)
print(f"CONTRACT MASTER ROWS       : {contract_total:,}")
print(f"MASTER UNIQUE SYMBOLS      : {contract_unique:,}")
print(f"FUTURES UNIQUE CONTRACTS   : {futures_contracts:,}")
print(f"OPTIONS UNIQUE CONTRACTS   : {options_contracts:,}")
print(f"HISTORY UNIQUE CONTRACTS   : {futures_contracts + options_contracts:,}")
print("=" * 60)

conn.close()
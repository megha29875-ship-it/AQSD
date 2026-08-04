"""
AQSD
Historical Database Inspector

Module: DBI-001
Version: 1.0.0

Purpose:
Safely inspect the frozen NSE F&O historical SQLite database.

Protection:
- READ ONLY
- No INSERT
- No UPDATE
- No DELETE
- No schema modification
"""

from pathlib import Path
import sqlite3


DATABASE_FILE = Path(
    r"D:\AQSD_DATA\Databases\NSE_FNO_Historical.db"
)


def main() -> None:

    print("=" * 80)
    print("AQSD HISTORICAL DATABASE INSPECTOR")
    print("=" * 80)

    print(f"Database : {DATABASE_FILE}")
    print(f"Exists   : {DATABASE_FILE.exists()}")
    print()

    if not DATABASE_FILE.exists():
        raise FileNotFoundError(
            f"Database not found: {DATABASE_FILE}"
        )

    uri = f"file:{DATABASE_FILE.as_posix()}?mode=ro"

    with sqlite3.connect(uri, uri=True) as connection:

        tables = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        ).fetchall()

        print("-" * 80)
        print("DATABASE TABLES")
        print("-" * 80)

        if not tables:
            print("No tables found.")
            return

        for number, (table_name,) in enumerate(tables, start=1):

            row_count = connection.execute(
                f'SELECT COUNT(*) FROM "{table_name}"'
            ).fetchone()[0]

            print(
                f"{number:>3}. "
                f"{table_name:<40} "
                f"{row_count:>12,} rows"
            )

        print("-" * 80)
        print(f"Total Tables : {len(tables)}")
        print("Access Mode  : READ ONLY")
        print("-" * 80)

    print()
    print("Status : SUCCESS")
    print("=" * 80)


if __name__ == "__main__":
    main()
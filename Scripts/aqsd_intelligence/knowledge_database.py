"""
AQSD
Intelligence Layer

Module: knowledge_database.py
Version: 1.0
Author: AQSD
Description:
Creates and maintains the AQSD Knowledge Database.

The database stores:
- Knowledge categories
- Knowledge cards
- Sources
- Evidence
- Tags
- AI rules
- Knowledge-to-rule mappings
- Reviews
- Database schema version
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DATA_DIR = BASE_DIR / "Data"
DATABASE_DIR = DATA_DIR / "Databases"

DATABASE_FILE = DATABASE_DIR / "AQSD_Knowledge.db"

CURRENT_SCHEMA_VERSION = 1


# ============================================================
# DEFAULT KNOWLEDGE CATEGORIES
# ============================================================

DEFAULT_CATEGORIES = [
    ("Price Action", "Price movement and behavioural observations."),
    ("Market Structure", "Trend, swings, BOS, CHOCH and structural behaviour."),
    ("Options", "Option-chain analytics and option-market behaviour."),
    ("Futures", "Futures positioning, rollover and term-structure analysis."),
    ("Volatility", "IV, HV, IV Rank, IV Percentile and volatility regimes."),
    ("Expiry Behaviour", "Weekly and monthly expiry-related observations."),
    ("Market Psychology", "Trader behaviour, sentiment and behavioural patterns."),
    ("Seasonality", "Calendar, event and recurring market behaviour."),
    ("Macro", "RBI, inflation, GDP, budget and macroeconomic events."),
    ("Risk Management", "Position sizing, drawdown and capital protection."),
    ("Strategy", "Verified trading and analytical strategies."),
    ("Bank Nifty", "Behaviour specific to the Bank Nifty index."),
    ("Nifty", "Behaviour specific to the Nifty index."),
    ("Research", "Unclassified research and experimental observations."),
]


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_connection() -> sqlite3.Connection:
    """
    Create and return a SQLite database connection.

    Returns:
        sqlite3.Connection: Active SQLite connection.
    """
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_FILE)
    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON;")

    return connection


# ============================================================
# DATABASE TABLE CREATION
# ============================================================

def create_schema_version_table(connection: sqlite3.Connection) -> None:
    """Create the schema version table."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS SchemaVersion (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL,
            description TEXT
        );
        """
    )


def create_categories_table(connection: sqlite3.Connection) -> None:
    """Create the knowledge categories table."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS Categories (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )


def create_knowledge_cards_table(connection: sqlite3.Connection) -> None:
    """Create the knowledge cards table."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS KnowledgeCards (
            knowledge_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category_id INTEGER NOT NULL,
            subcategory TEXT,
            description TEXT,
            market_logic TEXT,
            conditions TEXT,
            indicators TEXT,
            expected_behaviour TEXT,
            confidence TEXT NOT NULL DEFAULT 'Experimental',
            status TEXT NOT NULL DEFAULT 'Draft',
            author TEXT DEFAULT 'AQSD',
            markdown_file TEXT,
            version TEXT NOT NULL DEFAULT '1.0',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,

            FOREIGN KEY (category_id)
                REFERENCES Categories(category_id)
                ON UPDATE CASCADE
                ON DELETE RESTRICT
        );
        """
    )


def create_sources_table(connection: sqlite3.Connection) -> None:
    """Create the knowledge sources table."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS Sources (
            source_id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            title TEXT,
            author TEXT,
            reference TEXT,
            url TEXT,
            notes TEXT,
            created_at TEXT NOT NULL,

            FOREIGN KEY (knowledge_id)
                REFERENCES KnowledgeCards(knowledge_id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        );
        """
    )


def create_evidence_table(connection: sqlite3.Connection) -> None:
    """Create the supporting and contradicting evidence table."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS Evidence (
            evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_id TEXT NOT NULL,
            evidence_type TEXT NOT NULL,
            description TEXT NOT NULL,
            result TEXT,
            confidence TEXT,
            evidence_date TEXT,
            created_at TEXT NOT NULL,

            FOREIGN KEY (knowledge_id)
                REFERENCES KnowledgeCards(knowledge_id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        );
        """
    )


def create_tags_table(connection: sqlite3.Connection) -> None:
    """Create the tags table."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS Tags (
            tag_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );
        """
    )


def create_knowledge_tags_table(connection: sqlite3.Connection) -> None:
    """Create the many-to-many relationship between cards and tags."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS KnowledgeTags (
            knowledge_id TEXT NOT NULL,
            tag_id INTEGER NOT NULL,

            PRIMARY KEY (knowledge_id, tag_id),

            FOREIGN KEY (knowledge_id)
                REFERENCES KnowledgeCards(knowledge_id)
                ON UPDATE CASCADE
                ON DELETE CASCADE,

            FOREIGN KEY (tag_id)
                REFERENCES Tags(tag_id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        );
        """
    )


def create_ai_rules_table(connection: sqlite3.Connection) -> None:
    """Create the AI rules table."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS AIRules (
            rule_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            objective TEXT,
            input_variables TEXT,
            conditions_json TEXT NOT NULL,
            interpretation TEXT NOT NULL,
            commentary_fragment TEXT,
            confidence TEXT NOT NULL DEFAULT 'Experimental',
            priority INTEGER NOT NULL DEFAULT 50,
            status TEXT NOT NULL DEFAULT 'Draft',
            version TEXT NOT NULL DEFAULT '1.0',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )


def create_rule_mappings_table(connection: sqlite3.Connection) -> None:
    """Create mappings between knowledge cards and AI rules."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS RuleMappings (
            rule_id TEXT NOT NULL,
            knowledge_id TEXT NOT NULL,

            PRIMARY KEY (rule_id, knowledge_id),

            FOREIGN KEY (rule_id)
                REFERENCES AIRules(rule_id)
                ON UPDATE CASCADE
                ON DELETE CASCADE,

            FOREIGN KEY (knowledge_id)
                REFERENCES KnowledgeCards(knowledge_id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        );
        """
    )


def create_reviews_table(connection: sqlite3.Connection) -> None:
    """Create the knowledge review history table."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS Reviews (
            review_id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_id TEXT NOT NULL,
            reviewer TEXT NOT NULL,
            review_date TEXT NOT NULL,
            outcome TEXT NOT NULL,
            remarks TEXT,
            created_at TEXT NOT NULL,

            FOREIGN KEY (knowledge_id)
                REFERENCES KnowledgeCards(knowledge_id)
                ON UPDATE CASCADE
                ON DELETE CASCADE
        );
        """
    )


def create_indexes(connection: sqlite3.Connection) -> None:
    """Create indexes for common knowledge database searches."""

    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_category
        ON KnowledgeCards(category_id);

        CREATE INDEX IF NOT EXISTS idx_knowledge_status
        ON KnowledgeCards(status);

        CREATE INDEX IF NOT EXISTS idx_knowledge_confidence
        ON KnowledgeCards(confidence);

        CREATE INDEX IF NOT EXISTS idx_sources_knowledge
        ON Sources(knowledge_id);

        CREATE INDEX IF NOT EXISTS idx_evidence_knowledge
        ON Evidence(knowledge_id);

        CREATE INDEX IF NOT EXISTS idx_rules_status
        ON AIRules(status);

        CREATE INDEX IF NOT EXISTS idx_rules_priority
        ON AIRules(priority);

        CREATE INDEX IF NOT EXISTS idx_reviews_knowledge
        ON Reviews(knowledge_id);
        """
    )


# ============================================================
# INITIAL DATA
# ============================================================

def insert_default_categories(connection: sqlite3.Connection) -> None:
    """Insert AQSD's standard knowledge categories."""

    timestamp = datetime.now().isoformat(timespec="seconds")

    connection.executemany(
        """
        INSERT OR IGNORE INTO Categories (
            name,
            description,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?);
        """,
        [
            (name, description, timestamp, timestamp)
            for name, description in DEFAULT_CATEGORIES
        ],
    )


def record_schema_version(connection: sqlite3.Connection) -> None:
    """Record the current database schema version."""

    connection.execute(
        """
        INSERT OR IGNORE INTO SchemaVersion (
            version,
            applied_at,
            description
        )
        VALUES (?, ?, ?);
        """,
        (
            CURRENT_SCHEMA_VERSION,
            datetime.now().isoformat(timespec="seconds"),
            "Initial AQSD Knowledge Database schema",
        ),
    )


# ============================================================
# DATABASE VALIDATION
# ============================================================

def get_table_names(connection: sqlite3.Connection) -> list[str]:
    """
    Return all user-created table names.

    Args:
        connection: Active SQLite connection.

    Returns:
        List of database table names.
    """
    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name;
        """
    ).fetchall()

    return [row["name"] for row in rows]


def get_category_count(connection: sqlite3.Connection) -> int:
    """Return the number of knowledge categories."""

    row = connection.execute(
        "SELECT COUNT(*) AS total FROM Categories;"
    ).fetchone()

    return int(row["total"])


def get_schema_version(connection: sqlite3.Connection) -> int | None:
    """Return the latest installed schema version."""

    row = connection.execute(
        """
        SELECT MAX(version) AS version
        FROM SchemaVersion;
        """
    ).fetchone()

    if row is None or row["version"] is None:
        return None

    return int(row["version"])


# ============================================================
# DATABASE INITIALISATION
# ============================================================

def initialize_database() -> None:
    """Create and validate the complete AQSD Knowledge Database."""

    print()
    print("=" * 65)
    print("AQSD KNOWLEDGE DATABASE INITIALISATION")
    print("=" * 65)

    try:
        with get_connection() as connection:
            create_schema_version_table(connection)
            create_categories_table(connection)
            create_knowledge_cards_table(connection)
            create_sources_table(connection)
            create_evidence_table(connection)
            create_tags_table(connection)
            create_knowledge_tags_table(connection)
            create_ai_rules_table(connection)
            create_rule_mappings_table(connection)
            create_reviews_table(connection)

            create_indexes(connection)

            insert_default_categories(connection)
            record_schema_version(connection)

            connection.commit()

            tables = get_table_names(connection)
            category_count = get_category_count(connection)
            schema_version = get_schema_version(connection)

        print(f"Database file : {DATABASE_FILE}")
        print(f"Schema version: {schema_version}")
        print(f"Tables created: {len(tables)}")
        print(f"Categories    : {category_count}")

        print()
        print("DATABASE TABLES")
        print("-" * 65)

        for table_name in tables:
            print(f"[OK] {table_name}")

        print()
        print("=" * 65)
        print("AQSD KNOWLEDGE DATABASE CREATED SUCCESSFULLY")
        print("=" * 65)

    except sqlite3.Error as error:
        print()
        print("=" * 65)
        print("DATABASE INITIALISATION FAILED")
        print("=" * 65)
        print(f"SQLite error: {error}")
        raise

    except Exception as error:
        print()
        print("=" * 65)
        print("UNEXPECTED ERROR")
        print("=" * 65)
        print(f"Error: {error}")
        raise


# ============================================================
# SCRIPT ENTRY POINT
# ============================================================

if __name__ == "__main__":
    initialize_database()
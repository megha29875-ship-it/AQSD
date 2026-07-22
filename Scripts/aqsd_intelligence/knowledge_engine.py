"""
AQSD
Intelligence Layer

Module: knowledge_engine.py
Version: 1.0
Author: AQSD

Description:
Loads, searches, creates and manages AQSD Knowledge Cards.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from Scripts.aqsd_intelligence.models import KnowledgeCard


BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_FILE = BASE_DIR / "Data" / "Databases" / "AQSD_Knowledge.db"


class KnowledgeEngine:
    """
    AQSD Knowledge Engine.

    Provides database access for creating, reading and searching
    AQSD Knowledge Cards.
    """

    def __init__(self, database_file: Path = DATABASE_FILE) -> None:
        self.database_file = database_file

        if not self.database_file.exists():
            raise FileNotFoundError(
                f"Knowledge database not found: {self.database_file}"
            )

    def get_connection(self) -> sqlite3.Connection:
        """
        Return a configured SQLite connection.
        """
        connection = sqlite3.connect(self.database_file)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        return connection

    def get_category_id(self, category_name: str) -> int:
        """
        Return the database ID for a category name.

        Args:
            category_name: AQSD knowledge category.

        Returns:
            Integer category ID.

        Raises:
            ValueError: If the category does not exist.
        """
        with self.get_connection() as connection:
            row = connection.execute(
                """
                SELECT category_id
                FROM Categories
                WHERE LOWER(name) = LOWER(?);
                """,
                (category_name.strip(),),
            ).fetchone()

        if row is None:
            raise ValueError(
                f"Unknown knowledge category: {category_name}"
            )

        return int(row["category_id"])

    def add_knowledge_card(self, card: KnowledgeCard) -> None:
        """
        Add a new Knowledge Card to the database.

        Args:
            card: KnowledgeCard object to insert.
        """
        category_id = self.get_category_id(card.category)
        timestamp = datetime.now().isoformat(timespec="seconds")

        with self.get_connection() as connection:
            connection.execute(
                """
                INSERT INTO KnowledgeCards (
                    knowledge_id,
                    title,
                    category_id,
                    subcategory,
                    description,
                    market_logic,
                    conditions,
                    indicators,
                    expected_behaviour,
                    confidence,
                    status,
                    author,
                    markdown_file,
                    version,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    card.knowledge_id,
                    card.title,
                    category_id,
                    card.subcategory,
                    card.description,
                    card.market_logic,
                    card.conditions,
                    json.dumps(card.indicators),
                    card.expected_behaviour,
                    card.confidence,
                    card.status,
                    "AQSD",
                    card.markdown_file,
                    card.version,
                    timestamp,
                    timestamp,
                ),
            )

            connection.commit()

    def update_knowledge_card(self, card: KnowledgeCard) -> None:
        """
        Update an existing Knowledge Card.

        Args:
            card: KnowledgeCard object containing updated values.
        """
        category_id = self.get_category_id(card.category)
        timestamp = datetime.now().isoformat(timespec="seconds")

        with self.get_connection() as connection:
            cursor = connection.execute(
                """
                UPDATE KnowledgeCards
                SET
                    title = ?,
                    category_id = ?,
                    subcategory = ?,
                    description = ?,
                    market_logic = ?,
                    conditions = ?,
                    indicators = ?,
                    expected_behaviour = ?,
                    confidence = ?,
                    status = ?,
                    markdown_file = ?,
                    version = ?,
                    updated_at = ?
                WHERE knowledge_id = ?;
                """,
                (
                    card.title,
                    category_id,
                    card.subcategory,
                    card.description,
                    card.market_logic,
                    card.conditions,
                    json.dumps(card.indicators),
                    card.expected_behaviour,
                    card.confidence,
                    card.status,
                    card.markdown_file,
                    card.version,
                    timestamp,
                    card.knowledge_id,
                ),
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    f"Knowledge Card not found: {card.knowledge_id}"
                )

            connection.commit()

    def get_knowledge_card(
        self,
        knowledge_id: str,
    ) -> KnowledgeCard | None:
        """
        Return one Knowledge Card by ID.
        """
        with self.get_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    kc.*,
                    c.name AS category_name
                FROM KnowledgeCards kc
                JOIN Categories c
                    ON c.category_id = kc.category_id
                WHERE kc.knowledge_id = ?;
                """,
                (knowledge_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_knowledge_card(row)

    def get_all_knowledge_cards(self) -> list[KnowledgeCard]:
        """
        Return every Knowledge Card.
        """
        return self._search_cards()

    def search_by_category(
        self,
        category: str,
    ) -> list[KnowledgeCard]:
        """
        Return Knowledge Cards belonging to a category.
        """
        return self._search_cards(
            where_clause="LOWER(c.name) = LOWER(?)",
            parameters=(category,),
        )

    def search_by_status(
        self,
        status: str,
    ) -> list[KnowledgeCard]:
        """
        Return Knowledge Cards matching a status.
        """
        return self._search_cards(
            where_clause="LOWER(kc.status) = LOWER(?)",
            parameters=(status,),
        )

    def search_by_confidence(
        self,
        confidence: str,
    ) -> list[KnowledgeCard]:
        """
        Return Knowledge Cards matching a confidence level.
        """
        return self._search_cards(
            where_clause="LOWER(kc.confidence) = LOWER(?)",
            parameters=(confidence,),
        )

    def search_by_text(
        self,
        search_text: str,
    ) -> list[KnowledgeCard]:
        """
        Search card titles, descriptions, logic and conditions.
        """
        search_value = f"%{search_text.strip()}%"

        return self._search_cards(
            where_clause="""
                kc.title LIKE ?
                OR kc.description LIKE ?
                OR kc.market_logic LIKE ?
                OR kc.conditions LIKE ?
                OR kc.expected_behaviour LIKE ?
            """,
            parameters=(
                search_value,
                search_value,
                search_value,
                search_value,
                search_value,
            ),
        )

    def delete_knowledge_card(self, knowledge_id: str) -> None:
        """
        Delete a Knowledge Card.

        Related sources, evidence, tags, reviews and rule mappings
        are deleted automatically through foreign-key cascades.
        """
        with self.get_connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM KnowledgeCards
                WHERE knowledge_id = ?;
                """,
                (knowledge_id,),
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    f"Knowledge Card not found: {knowledge_id}"
                )

            connection.commit()

    def count_knowledge_cards(self) -> int:
        """
        Return the total number of Knowledge Cards.
        """
        with self.get_connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM KnowledgeCards;
                """
            ).fetchone()

        return int(row["total"])

    def list_categories(self) -> list[str]:
        """
        Return all configured knowledge categories.
        """
        with self.get_connection() as connection:
            rows = connection.execute(
                """
                SELECT name
                FROM Categories
                ORDER BY name;
                """
            ).fetchall()

        return [str(row["name"]) for row in rows]

    def _search_cards(
        self,
        where_clause: str | None = None,
        parameters: tuple = (),
    ) -> list[KnowledgeCard]:
        """
        Execute a Knowledge Card query and return model objects.
        """
        query = """
            SELECT
                kc.*,
                c.name AS category_name
            FROM KnowledgeCards kc
            JOIN Categories c
                ON c.category_id = kc.category_id
        """

        if where_clause:
            query += f" WHERE {where_clause}"

        query += " ORDER BY kc.knowledge_id;"

        with self.get_connection() as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [
            self._row_to_knowledge_card(row)
            for row in rows
        ]

    @staticmethod
    def _row_to_knowledge_card(
        row: sqlite3.Row,
    ) -> KnowledgeCard:
        """
        Convert a SQLite row into a KnowledgeCard object.
        """
        indicators_value = row["indicators"]

        try:
            indicators = (
                json.loads(indicators_value)
                if indicators_value
                else []
            )
        except json.JSONDecodeError:
            indicators = []

        return KnowledgeCard(
            knowledge_id=row["knowledge_id"],
            title=row["title"],
            category=row["category_name"],
            subcategory=row["subcategory"],
            description=row["description"] or "",
            market_logic=row["market_logic"] or "",
            conditions=row["conditions"] or "",
            indicators=indicators,
            expected_behaviour=row["expected_behaviour"] or "",
            confidence=row["confidence"],
            status=row["status"],
            markdown_file=row["markdown_file"],
            version=row["version"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


def test_knowledge_engine() -> None:
    """
    Run a basic Knowledge Engine connection test.
    """
    print()
    print("=" * 65)
    print("AQSD KNOWLEDGE ENGINE TEST")
    print("=" * 65)

    engine = KnowledgeEngine()

    categories = engine.list_categories()
    card_count = engine.count_knowledge_cards()

    print(f"Database        : {engine.database_file}")
    print(f"Categories      : {len(categories)}")
    print(f"Knowledge Cards : {card_count}")

    print()
    print("AVAILABLE CATEGORIES")
    print("-" * 65)

    for category in categories:
        print(f"[OK] {category}")

    print()
    print("=" * 65)
    print("AQSD KNOWLEDGE ENGINE WORKING SUCCESSFULLY")
    print("=" * 65)


if __name__ == "__main__":
    test_knowledge_engine()
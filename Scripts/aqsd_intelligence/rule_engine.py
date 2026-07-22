"""
AQSD
Intelligence Layer

Module: rule_engine.py
Version: 1.0
Author: AQSD

Description:
Creates, stores, retrieves and evaluates AQSD AI Rules.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from Scripts.aqsd_intelligence.models import AIRule


BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_FILE = (
    BASE_DIR
    / "Data"
    / "Databases"
    / "AQSD_Knowledge.db"
)


class RuleEngine:
    """
    AQSD AI Rule Engine.

    The engine performs the following functions:

    - Saves new AI Rules.
    - Updates existing AI Rules.
    - Maps AI Rules to Knowledge Cards.
    - Retrieves stored AI Rules.
    - Evaluates rules against market data.
    - Returns explainable condition results.
    """

    def __init__(
        self,
        database_file: Path = DATABASE_FILE,
    ) -> None:
        """
        Initialize the Rule Engine.

        Args:
            database_file:
                Location of the AQSD Knowledge database.

        Raises:
            FileNotFoundError:
                If the database does not exist.
        """
        self.database_file = database_file

        if not self.database_file.exists():
            raise FileNotFoundError(
                "AQSD Knowledge database not found: "
                f"{self.database_file}"
            )

    def get_connection(self) -> sqlite3.Connection:
        """
        Create and return a configured SQLite connection.

        Returns:
            SQLite connection with dictionary-style row access.
        """
        connection = sqlite3.connect(self.database_file)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")

        return connection

    def save_rule(
        self,
        rule: AIRule,
        conditions: dict[str, Any],
        knowledge_ids: list[str],
    ) -> str:
        """
        Insert or update an AQSD AI Rule.

        Args:
            rule:
                AIRule model containing rule information.

            conditions:
                Machine-readable rule conditions.

            knowledge_ids:
                Knowledge Card IDs linked to the rule.

        Returns:
            CREATED when a new rule is inserted.
            UPDATED when an existing rule is replaced.
        """
        timestamp = datetime.now().isoformat(
            timespec="seconds"
        )

        with self.get_connection() as connection:
            existing_rule = connection.execute(
                """
                SELECT rule_id
                FROM AIRules
                WHERE rule_id = ?;
                """,
                (rule.rule_id,),
            ).fetchone()

            if existing_rule is None:
                connection.execute(
                    """
                    INSERT INTO AIRules (
                        rule_id,
                        title,
                        category,
                        objective,
                        input_variables,
                        conditions_json,
                        interpretation,
                        commentary_fragment,
                        confidence,
                        priority,
                        status,
                        version,
                        created_at,
                        updated_at
                    )
                    VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?
                    );
                    """,
                    (
                        rule.rule_id,
                        rule.title,
                        rule.category,
                        rule.objective,
                        json.dumps(
                            rule.input_variables,
                            indent=2,
                        ),
                        json.dumps(
                            conditions,
                            indent=2,
                        ),
                        rule.interpretation,
                        rule.commentary_fragment,
                        rule.confidence,
                        rule.priority,
                        rule.status,
                        rule.version,
                        timestamp,
                        timestamp,
                    ),
                )

                action = "CREATED"

            else:
                connection.execute(
                    """
                    UPDATE AIRules
                    SET
                        title = ?,
                        category = ?,
                        objective = ?,
                        input_variables = ?,
                        conditions_json = ?,
                        interpretation = ?,
                        commentary_fragment = ?,
                        confidence = ?,
                        priority = ?,
                        status = ?,
                        version = ?,
                        updated_at = ?
                    WHERE rule_id = ?;
                    """,
                    (
                        rule.title,
                        rule.category,
                        rule.objective,
                        json.dumps(
                            rule.input_variables,
                            indent=2,
                        ),
                        json.dumps(
                            conditions,
                            indent=2,
                        ),
                        rule.interpretation,
                        rule.commentary_fragment,
                        rule.confidence,
                        rule.priority,
                        rule.status,
                        rule.version,
                        timestamp,
                        rule.rule_id,
                    ),
                )

                action = "UPDATED"

            self._replace_rule_mappings(
                connection=connection,
                rule_id=rule.rule_id,
                knowledge_ids=knowledge_ids,
            )

            connection.commit()

        return action

    def _replace_rule_mappings(
        self,
        connection: sqlite3.Connection,
        rule_id: str,
        knowledge_ids: list[str],
    ) -> None:
        """
        Replace Knowledge Card mappings for one rule.

        Args:
            connection:
                Active SQLite connection.

            rule_id:
                AI Rule identifier.

            knowledge_ids:
                Knowledge Card identifiers.
        """
        connection.execute(
            """
            DELETE FROM RuleMappings
            WHERE rule_id = ?;
            """,
            (rule_id,),
        )

        for knowledge_id in knowledge_ids:
            knowledge_card = connection.execute(
                """
                SELECT knowledge_id
                FROM KnowledgeCards
                WHERE knowledge_id = ?;
                """,
                (knowledge_id,),
            ).fetchone()

            if knowledge_card is None:
                raise ValueError(
                    "Knowledge Card does not exist: "
                    f"{knowledge_id}"
                )

            connection.execute(
                """
                INSERT INTO RuleMappings (
                    rule_id,
                    knowledge_id
                )
                VALUES (?, ?);
                """,
                (
                    rule_id,
                    knowledge_id,
                ),
            )

    def get_rule(
        self,
        rule_id: str,
    ) -> dict[str, Any] | None:
        """
        Retrieve one stored AI Rule.

        Args:
            rule_id:
                AQSD AI Rule identifier.

        Returns:
            Rule information as a dictionary,
            or None when the rule does not exist.
        """
        with self.get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM AIRules
                WHERE rule_id = ?;
                """,
                (rule_id,),
            ).fetchone()

            if row is None:
                return None

            knowledge_rows = connection.execute(
                """
                SELECT knowledge_id
                FROM RuleMappings
                WHERE rule_id = ?
                ORDER BY knowledge_id;
                """,
                (rule_id,),
            ).fetchall()

        return {
            "rule_id": row["rule_id"],
            "title": row["title"],
            "category": row["category"],
            "objective": row["objective"],
            "input_variables": self._load_json(
                row["input_variables"],
                default=[],
            ),
            "conditions": self._load_json(
                row["conditions_json"],
                default={},
            ),
            "interpretation": row["interpretation"],
            "commentary_fragment": (
                row["commentary_fragment"]
            ),
            "confidence": row["confidence"],
            "priority": row["priority"],
            "status": row["status"],
            "version": row["version"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "knowledge_ids": [
                knowledge_row["knowledge_id"]
                for knowledge_row in knowledge_rows
            ],
        }

    def get_all_rules(self) -> list[dict[str, Any]]:
        """
        Return all AI Rules ordered by priority.

        Returns:
            List of stored AI Rule dictionaries.
        """
        with self.get_connection() as connection:
            rows = connection.execute(
                """
                SELECT rule_id
                FROM AIRules
                ORDER BY priority DESC, rule_id;
                """
            ).fetchall()

        rules: list[dict[str, Any]] = []

        for row in rows:
            rule = self.get_rule(row["rule_id"])

            if rule is not None:
                rules.append(rule)

        return rules

    def count_rules(self) -> int:
        """
        Return the total number of stored AI Rules.
        """
        with self.get_connection() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS total
                FROM AIRules;
                """
            ).fetchone()

        return int(row["total"])

    def delete_rule(
        self,
        rule_id: str,
    ) -> None:
        """
        Delete an AI Rule.

        Rule mappings are deleted automatically through
        database foreign-key cascade rules.

        Args:
            rule_id:
                AQSD AI Rule identifier.

        Raises:
            ValueError:
                If the rule does not exist.
        """
        with self.get_connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM AIRules
                WHERE rule_id = ?;
                """,
                (rule_id,),
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    f"AI Rule not found: {rule_id}"
                )

            connection.commit()

    def evaluate_rule(
        self,
        rule_id: str,
        market_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Evaluate one stored AI Rule.

        Args:
            rule_id:
                AQSD AI Rule identifier.

            market_data:
                Dictionary containing live or test
                market intelligence values.

        Returns:
            Explainable rule evaluation result.
        """
        rule = self.get_rule(rule_id)

        if rule is None:
            raise ValueError(
                f"AI Rule not found: {rule_id}"
            )

        conditions = rule["conditions"]

        all_conditions = conditions.get("all", [])
        any_conditions = conditions.get("any", [])

        all_results = self._evaluate_condition_group(
            conditions=all_conditions,
            market_data=market_data,
        )

        any_results = self._evaluate_condition_group(
            conditions=any_conditions,
            market_data=market_data,
        )

        all_matched = (
            all(result["matched"] for result in all_results)
            if all_results
            else True
        )

        any_matched = (
            any(result["matched"] for result in any_results)
            if any_results
            else True
        )

        active = all_matched and any_matched

        total_conditions = (
            len(all_results)
            + len(any_results)
        )

        matched_conditions = sum(
            result["matched"]
            for result in all_results + any_results
        )

        match_percentage = (
            matched_conditions
            / total_conditions
            * 100
            if total_conditions
            else 0.0
        )

        return {
            "rule_id": rule["rule_id"],
            "title": rule["title"],
            "category": rule["category"],
            "active": active,
            "status": rule["status"],
            "confidence": rule["confidence"],
            "priority": rule["priority"],
            "match_percentage": round(
                match_percentage,
                2,
            ),
            "matched_conditions": matched_conditions,
            "total_conditions": total_conditions,
            "interpretation": (
                rule["interpretation"]
                if active
                else ""
            ),
            "commentary": (
                rule["commentary_fragment"]
                if active
                else ""
            ),
            "knowledge_ids": rule["knowledge_ids"],
            "all_condition_results": all_results,
            "any_condition_results": any_results,
        }

    def evaluate_all_rules(
        self,
        market_data: dict[str, Any],
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Evaluate all stored AI Rules.

        Args:
            market_data:
                Market intelligence values.

            active_only:
                Return only triggered rules when True.

        Returns:
            Rule evaluation results sorted by priority.
        """
        stored_rules = self.get_all_rules()
        results: list[dict[str, Any]] = []

        for stored_rule in stored_rules:
            result = self.evaluate_rule(
                rule_id=stored_rule["rule_id"],
                market_data=market_data,
            )

            if active_only and not result["active"]:
                continue

            results.append(result)

        results.sort(
            key=lambda item: (
                item["active"],
                item["priority"],
                item["match_percentage"],
            ),
            reverse=True,
        )

        return results

    def _evaluate_condition_group(
        self,
        conditions: list[dict[str, Any]],
        market_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """
        Evaluate one group of rule conditions.
        """
        results: list[dict[str, Any]] = []

        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator")
            expected = condition.get("value")
            actual = market_data.get(field)

            matched = self._compare(
                actual=actual,
                operator=operator,
                expected=expected,
            )

            results.append(
                {
                    "field": field,
                    "operator": operator,
                    "expected": expected,
                    "actual": actual,
                    "matched": matched,
                }
            )

        return results

    @staticmethod
    def _compare(
        actual: Any,
        operator: str,
        expected: Any,
    ) -> bool:
        """
        Compare a market value against a rule condition.

        Supported operators:

        - equals
        - not_equals
        - greater_than
        - greater_than_or_equal
        - less_than
        - less_than_or_equal
        - in
        - not_in
        - contains
        - is_true
        - is_false
        """
        if operator == "is_true":
            return actual is True

        if operator == "is_false":
            return actual is False

        if actual is None:
            return False

        try:
            if operator == "equals":
                return actual == expected

            if operator == "not_equals":
                return actual != expected

            if operator == "greater_than":
                return actual > expected

            if operator == "greater_than_or_equal":
                return actual >= expected

            if operator == "less_than":
                return actual < expected

            if operator == "less_than_or_equal":
                return actual <= expected

            if operator == "in":
                return actual in expected

            if operator == "not_in":
                return actual not in expected

            if operator == "contains":
                return expected in actual

        except TypeError:
            return False

        raise ValueError(
            f"Unsupported rule operator: {operator}"
        )

    @staticmethod
    def _load_json(
        value: str | None,
        default: Any,
    ) -> Any:
        """
        Safely load a JSON database value.
        """
        if not value:
            return default

        try:
            return json.loads(value)

        except json.JSONDecodeError:
            return default


def build_aqsd_0001(
) -> tuple[
    AIRule,
    dict[str, Any],
    list[str],
]:
    """
    Build AQSD-0001.

    Rule:
        Modified PCR Rising with Stable IV.
    """
    rule = AIRule(
        rule_id="AQSD-0001",
        title="Modified PCR Rising with Stable IV",
        category="Options",
        objective=(
            "Identify conditions where improving options "
            "positioning may support bullish continuation."
        ),
        input_variables=[
            "modified_pcr_trend",
            "iv_regime",
            "market_structure",
            "call_wall_state",
            "major_event_active",
        ],
        interpretation=(
            "Bullish continuation conditions are improving, "
            "but resistance near the active Call Wall should "
            "still be monitored."
        ),
        commentary_fragment=(
            "Modified PCR is rising while implied volatility "
            "remains stable. This supports a bullish "
            "continuation interpretation, provided market "
            "structure remains constructive and event risk "
            "stays limited."
        ),
        confidence="Moderate",
        priority=60,
        status="Testing",
        version="1.0",
    )

    conditions: dict[str, Any] = {
        "all": [
            {
                "field": "modified_pcr_trend",
                "operator": "equals",
                "value": "RISING",
            },
            {
                "field": "iv_regime",
                "operator": "equals",
                "value": "STABLE",
            },
            {
                "field": "market_structure",
                "operator": "in",
                "value": [
                    "BULLISH",
                    "WEAK_BULLISH",
                    "NEUTRAL",
                ],
            },
            {
                "field": "call_wall_state",
                "operator": "in",
                "value": [
                    "STABLE",
                    "WEAKENING",
                ],
            },
            {
                "field": "major_event_active",
                "operator": "equals",
                "value": False,
            },
        ]
    }

    knowledge_ids = [
        "KC-0001",
    ]

    return (
        rule,
        conditions,
        knowledge_ids,
    )


def print_condition_results(
    result: dict[str, Any],
) -> None:
    """
    Print explainable rule condition results.
    """
    print()
    print("CONDITION RESULTS")
    print("-" * 70)

    all_results = result[
        "all_condition_results"
    ]

    any_results = result[
        "any_condition_results"
    ]

    for condition in all_results:
        status = (
            "PASS"
            if condition["matched"]
            else "FAIL"
        )

        print(
            f"[{status}] "
            f"{condition['field']} "
            f"{condition['operator']} "
            f"{condition['expected']} "
            f"| Actual: {condition['actual']}"
        )

    for condition in any_results:
        status = (
            "PASS"
            if condition["matched"]
            else "FAIL"
        )

        print(
            f"[{status}] "
            f"{condition['field']} "
            f"{condition['operator']} "
            f"{condition['expected']} "
            f"| Actual: {condition['actual']}"
        )


def main() -> None:
    """
    Save and test AQSD-0001.
    """
    print()
    print("=" * 70)
    print("AQSD AI RULE ENGINE")
    print("=" * 70)

    engine = RuleEngine()

    rule, conditions, knowledge_ids = (
        build_aqsd_0001()
    )

    action = engine.save_rule(
        rule=rule,
        conditions=conditions,
        knowledge_ids=knowledge_ids,
    )

    sample_market_data = {
        "modified_pcr_trend": "RISING",
        "iv_regime": "STABLE",
        "market_structure": "WEAK_BULLISH",
        "call_wall_state": "STABLE",
        "major_event_active": False,
    }

    result = engine.evaluate_rule(
        rule_id="AQSD-0001",
        market_data=sample_market_data,
    )

    print(f"Database          : {engine.database_file}")
    print(f"Action            : {action}")
    print(f"Rule ID           : {result['rule_id']}")
    print(f"Title             : {result['title']}")
    print(f"Category          : {result['category']}")
    print(f"Active            : {result['active']}")
    print(f"Confidence        : {result['confidence']}")
    print(f"Priority          : {result['priority']}")
    print(
        f"Conditions Passed : "
        f"{result['matched_conditions']}/"
        f"{result['total_conditions']}"
    )
    print(
        f"Match Percentage  : "
        f"{result['match_percentage']}%"
    )
    print(
        f"Total Rules       : "
        f"{engine.count_rules()}"
    )

    print_condition_results(result)

    print()
    print("INTERPRETATION")
    print("-" * 70)

    if result["interpretation"]:
        print(result["interpretation"])
    else:
        print("Rule conditions are not active.")

    print()
    print("AI COMMENTARY")
    print("-" * 70)

    if result["commentary"]:
        print(result["commentary"])
    else:
        print("No commentary generated.")

    print()
    print("=" * 70)
    print(
        "AQSD-0001 SAVED AND TESTED SUCCESSFULLY"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()
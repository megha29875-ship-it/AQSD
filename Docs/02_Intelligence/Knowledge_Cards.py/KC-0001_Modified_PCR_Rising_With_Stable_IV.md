# KC-0001 — Modified PCR Rising with Stable IV

---

## Metadata

**Knowledge ID:** KC-0001  
**Category:** Options  
**Subcategory:** PCR and Volatility  
**Version:** 1.0  
**Status:** Under Research  
**Confidence:** Moderate  
**Author:** AQSD  

---

## Description

A sustained increase in Modified PCR while implied volatility remains stable may indicate strengthening bullish positioning without panic-driven option buying.

---

## Market Logic

Modified PCR combines multiple option-market positioning measures rather than relying only on a single PCR value.

When Modified PCR rises while implied volatility remains stable, the market may be showing stronger put-side positioning without a corresponding volatility shock.

This can support bullish continuation when:

- Market structure is not strongly bearish.
- The active Call Wall is stable or weakening.
- Price is not facing immediate structural resistance.
- No major macro event is distorting option prices.

The rule must not be interpreted in isolation.

---

## Conditions

The knowledge card becomes relevant when:

- Modified PCR is rising across multiple observations.
- IV remains stable.
- Market structure is not strongly bearish.
- No major macro event is active.
- The Call Wall is stable or weakening.
- Put-side support remains intact.

---

## Indicators Used

- Modified PCR
- OI PCR
- Volume PCR
- Implied Volatility
- Call Wall
- Put Wall
- Market Trend
- Market Regime

---

## Expected Behaviour

Bullish continuation probability may improve.

However, price may still face resistance near the active Call Wall.

A breakout above the Call Wall or weakening call-side open interest would provide stronger confirmation.

---

## Supporting Evidence

Current supporting basis:

- Option-market positioning logic
- AQSD observations
- PCR trend interpretation
- Volatility behaviour analysis

Formal historical backtesting is still required.

---

## Contradicting Evidence

The behaviour may fail when:

- Market structure turns strongly bearish.
- IV expands sharply.
- A major RBI, budget, election, or global event occurs.
- Fresh call writing increases significantly.
- Price remains below an important structural resistance.
- PCR rises because of defensive put buying rather than bullish positioning.

---

## Limitations

Modified PCR should not be treated as a standalone directional indicator.

Its interpretation depends on:

- Trend
- Market structure
- Volatility regime
- Wall movement
- Expiry proximity
- Event risk

---

## Verification Plan

The card should be tested against historical observations containing:

1. Modified PCR trend over at least three observations.
2. IV change over the same period.
3. Call Wall movement.
4. Market structure classification.
5. Subsequent price behaviour.
6. Expiry context.
7. Event context.

---

## AI Rule Mapping

Planned AI Rule:

- AQSD-0001

"""
AQSD
Intelligence Layer

Module: rule_engine.py
Version: 1.0
Author: AQSD

Description:
Creates, stores and evaluates AQSD AI Rules.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from Scripts.aqsd_intelligence.models import AIRule


BASE_DIR = Path(__file__).resolve().parents[2]
DATABASE_FILE = BASE_DIR / "Data" / "Databases" / "AQSD_Knowledge.db"


class RuleEngine:
    """
    AQSD AI Rule Engine.
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

    def save_rule(
        self,
        rule: AIRule,
        conditions: dict[str, Any],
        knowledge_ids: list[str],
    ) -> str:
        """
        Insert or update an AI Rule.

        Returns:
            CREATED or UPDATED.
        """
        timestamp = datetime.now().isoformat(timespec="seconds")

        with self.get_connection() as connection:
            existing = connection.execute(
                """
                SELECT rule_id
                FROM AIRules
                WHERE rule_id = ?;
                """,
                (rule.rule_id,),
            ).fetchone()

            if existing is None:
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
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        rule.rule_id,
                        rule.title,
                        rule.category,
                        rule.objective,
                        json.dumps(rule.input_variables),
                        json.dumps(conditions),
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
                        json.dumps(rule.input_variables),
                        json.dumps(conditions),
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

            connection.execute(
                """
                DELETE FROM RuleMappings
                WHERE rule_id = ?;
                """,
                (rule.rule_id,),
            )

            for knowledge_id in knowledge_ids:
                connection.execute(
                    """
                    INSERT INTO RuleMappings (
                        rule_id,
                        knowledge_id
                    )
                    VALUES (?, ?);
                    """,
                    (rule.rule_id, knowledge_id),
                )

            connection.commit()

        return action

    def evaluate_rule(
        self,
        rule_id: str,
        market_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Evaluate one stored rule against market data.
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
            raise ValueError(f"AI Rule not found: {rule_id}")

        conditions = json.loads(row["conditions_json"])
        results: list[dict[str, Any]] = []

        for condition in conditions.get("all", []):
            field = condition["field"]
            operator = condition["operator"]
            expected = condition["value"]
            actual = market_data.get(field)

            matched = self._compare(actual, operator, expected)

            results.append(
                {
                    "field": field,
                    "operator": operator,
                    "expected": expected,
                    "actual": actual,
                    "matched": matched,
                }
            )

        active = all(result["matched"] for result in results)

        return {
            "rule_id": row["rule_id"],
            "title": row["title"],
            "active": active,
            "confidence": row["confidence"],
            "priority": row["priority"],
            "interpretation": row["interpretation"] if active else "",
            "commentary": row["commentary_fragment"] if active else "",
            "condition_results": results,
        }

    @staticmethod
    def _compare(
        actual: Any,
        operator: str,
        expected: Any,
    ) -> bool:
        """
        Compare one live value with a rule condition.
        """
        if actual is None:
            return False

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

        raise ValueError(f"Unsupported operator: {operator}")


def build_aqsd_0001() -> tuple[AIRule, dict[str, Any], list[str]]:
    """
    Build AQSD-0001.
    """
    rule = AIRule(
        rule_id="AQSD-0001",
        title="Modified PCR Rising with Stable IV",
        category="Options",
        objective=(
            "Identify conditions where improving options positioning "
            "may support bullish continuation."
        ),
        input_variables=[
            "modified_pcr_trend",
            "iv_regime",
            "market_structure",
            "call_wall_state",
            "major_event_active",
        ],
        interpretation=(
            "Bullish continuation conditions are improving, but resistance "
            "near the active Call Wall should still be monitored."
        ),
        commentary_fragment=(
            "Modified PCR is rising while IV remains stable. "
            "This supports a bullish continuation interpretation, "
            "provided market structure remains constructive and "
            "event risk stays limited."
        ),
        confidence="Moderate",
        priority=60,
        status="Testing",
        version="1.0",
    )

    conditions = {
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
                    "NEUTRAL",
                    "WEAK_BULLISH",
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

    return rule, conditions, ["KC-0001"]


def main() -> None:
    """
    Save and test AQSD-0001.
    """
    print()
    print("=" * 70)
    print("AQSD AI RULE ENGINE")
    print("=" * 70)

    engine = RuleEngine()
    rule, conditions, knowledge_ids = build_aqsd_0001()

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

    print(f"Action        : {action}")
    print(f"Rule ID       : {result['rule_id']}")
    print(f"Title         : {result['title']}")
    print(f"Active        : {result['active']}")
    print(f"Confidence    : {result['confidence']}")
    print(f"Priority      : {result['priority']}")

    print()
    print("INTERPRETATION")
    print("-" * 70)
    print(result["interpretation"])

    print()
    print("=" * 70)
    print("AQSD-0001 SAVED AND TESTED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    main()
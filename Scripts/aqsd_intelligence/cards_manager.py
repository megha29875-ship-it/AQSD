"""
AQSD
Intelligence Layer

Module: cards_manager.py
Version: 1.0
Author: AQSD

Description:
Creates and manages standard AQSD Knowledge Cards.
"""

from __future__ import annotations

from Scripts.aqsd_intelligence.knowledge_engine import KnowledgeEngine
from Scripts.aqsd_intelligence.models import KnowledgeCard


def build_kc_0001() -> KnowledgeCard:
    """
    Create Knowledge Card KC-0001.

    Returns:
        KnowledgeCard describing Modified PCR rising with stable IV.
    """
    return KnowledgeCard(
        knowledge_id="KC-0001",
        title="Modified PCR Rising with Stable IV",
        category="Options",
        subcategory="PCR and Volatility",
        description=(
            "A sustained increase in Modified PCR while implied volatility "
            "remains stable may indicate strengthening bullish positioning "
            "without panic-driven option buying."
        ),
        market_logic=(
            "Modified PCR combines option positioning information more broadly "
            "than a single PCR measure. When it rises while IV remains stable, "
            "put-side positioning may be strengthening without a corresponding "
            "volatility shock. This can support bullish continuation, provided "
            "market structure and resistance conditions are favourable."
        ),
        conditions=(
            "Modified PCR is rising across multiple observations; "
            "IV remains stable; no major macro event is active; "
            "market structure is not strongly bearish; "
            "Call Wall is stable or weakening."
        ),
        indicators=[
            "Modified PCR",
            "OI PCR",
            "Volume PCR",
            "Implied Volatility",
            "Call Wall",
            "Put Wall",
            "Market Trend",
            "Market Regime",
        ],
        expected_behaviour=(
            "Bullish continuation probability may improve, although resistance "
            "at the active Call Wall must still be respected."
        ),
        confidence="Moderate",
        status="Under Research",
        markdown_file=(
            "Docs/02_Intelligence/Knowledge_Cards/"
            "KC-0001_Modified_PCR_Rising_With_Stable_IV.md"
        ),
        version="1.0",
    )


def save_card(
    engine: KnowledgeEngine,
    card: KnowledgeCard,
) -> str:
    """
    Insert the card or update it when it already exists.

    Returns:
        Text describing the database action.
    """
    existing_card = engine.get_knowledge_card(card.knowledge_id)

    if existing_card is None:
        engine.add_knowledge_card(card)
        return "CREATED"

    engine.update_knowledge_card(card)
    return "UPDATED"


def main() -> None:
    """Create or update AQSD's first Knowledge Card."""

    print()
    print("=" * 70)
    print("AQSD KNOWLEDGE CARD MANAGER")
    print("=" * 70)

    engine = KnowledgeEngine()
    card = build_kc_0001()
    action = save_card(engine, card)

    saved_card = engine.get_knowledge_card(card.knowledge_id)

    if saved_card is None:
        raise RuntimeError("KC-0001 could not be read after saving.")

    print(f"Action             : {action}")
    print(f"Knowledge ID       : {saved_card.knowledge_id}")
    print(f"Title              : {saved_card.title}")
    print(f"Category           : {saved_card.category}")
    print(f"Confidence         : {saved_card.confidence}")
    print(f"Status             : {saved_card.status}")
    print(f"Indicators         : {len(saved_card.indicators)}")
    print(f"Total Cards        : {engine.count_knowledge_cards()}")

    print()
    print("=" * 70)
    print("KC-0001 SAVED SUCCESSFULLY")
    print("=" * 70)


if __name__ == "__main__":
    main()
"""
AQSD
Intelligence Layer

Module: models.py
Version: 1.0
Author: AQSD

Description:
Core data models used by the AQSD Intelligence Layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


# ==========================================================
# KNOWLEDGE CARD
# ==========================================================

@dataclass(slots=True)
class KnowledgeCard:
    """
    Represents one AQSD Knowledge Card.
    """

    knowledge_id: str

    title: str

    category: str

    subcategory: Optional[str] = None

    description: str = ""

    market_logic: str = ""

    conditions: str = ""

    indicators: List[str] = field(default_factory=list)

    expected_behaviour: str = ""

    confidence: str = "Experimental"

    status: str = "Draft"

    markdown_file: Optional[str] = None

    version: str = "1.0"

    created_at: datetime = field(default_factory=datetime.now)

    updated_at: datetime = field(default_factory=datetime.now)


# ==========================================================
# AI RULE
# ==========================================================

@dataclass(slots=True)
class AIRule:
    """
    Represents an executable AI Rule.
    """

    rule_id: str

    title: str

    category: str

    objective: str

    input_variables: List[str] = field(default_factory=list)

    interpretation: str = ""

    commentary_fragment: str = ""

    confidence: str = "Experimental"

    priority: int = 50

    status: str = "Draft"

    version: str = "1.0"

    created_at: datetime = field(default_factory=datetime.now)

    updated_at: datetime = field(default_factory=datetime.now)


# ==========================================================
# SOURCE
# ==========================================================

@dataclass(slots=True)
class Source:
    """
    Source of knowledge.
    """

    source_type: str

    title: str

    author: str = ""

    reference: str = ""

    url: str = ""

    notes: str = ""


# ==========================================================
# EVIDENCE
# ==========================================================

@dataclass(slots=True)
class Evidence:
    """
    Supporting or contradicting evidence.
    """

    evidence_type: str

    description: str

    result: str = ""

    confidence: str = ""

    evidence_date: Optional[datetime] = None


# ==========================================================
# REVIEW
# ==========================================================

@dataclass(slots=True)
class Review:
    """
    Knowledge review history.
    """

    reviewer: str

    outcome: str

    remarks: str = ""

    review_date: datetime = field(default_factory=datetime.now)
# KNOWLEDGE CARD STANDARD

---

# AQSD Knowledge Card Standard

Version: 1.0

Status: Design Approved

---

# Purpose

A Knowledge Card is the fundamental unit of intelligence within AQSD.

Each card captures a single market concept, behavioural observation, trading principle, or verified analytical rule in a consistent, structured format.

Knowledge Cards enable AQSD to grow its market intelligence while keeping research organised, explainable, and reusable.

---

# Guiding Principles

Each Knowledge Card should:

* Represent one idea only.
* Be evidence-based whenever possible.
* Distinguish observation from verified behaviour.
* Be understandable by both humans and software.
* Support future AI rule generation.

---

# Standard Structure

## 1. Metadata

| Field        | Description                                                             |
| ------------ | ----------------------------------------------------------------------- |
| Knowledge ID | Unique identifier (e.g. KC-0001)                                        |
| Title        | Short descriptive title                                                 |
| Category     | Market Structure, Options, Futures, Volatility, Psychology, Macro, etc. |
| Subcategory  | Optional classification                                                 |
| Author       | Creator or contributor                                                  |
| Created Date | Date first added                                                        |
| Last Updated | Most recent revision                                                    |
| Version      | Card version                                                            |
| Status       | Draft, Research, Verified, Deprecated                                   |

---

## 2. Description

Provide a concise explanation of the concept.

Example:

> Rising Modified PCR combined with stable IV may indicate increasing bullish positioning without panic buying.

---

## 3. Market Logic

Explain **why** this behaviour occurs.

Focus on the underlying market mechanics rather than the numerical indicator alone.

---

## 4. Conditions

Specify when the concept is expected to apply.

Example:

* Modified PCR increasing
* IV stable
* Call Wall unchanged
* No major macro event

---

## 5. Indicators Used

List all indicators or data sources relevant to the concept.

Examples:

* Modified PCR
* IV
* Open Interest
* Call Wall
* Put Wall
* Trend
* Market Phase

---

## 6. Expected Behaviour

Describe the likely market response if the conditions are satisfied.

Examples:

* Bullish continuation
* Mean reversion
* Volatility expansion
* Consolidation

---

## 7. Supporting Evidence

Reference material supporting the observation.

Possible sources include:

* Historical backtests
* Market observations
* Research papers
* Books
* Educational material
* Internal AQSD studies

---

## 8. Contradicting Evidence

Describe situations where the concept may fail.

Examples:

* RBI policy announcements
* Earnings surprises
* Significant global events
* Low-liquidity sessions

---

## 9. Confidence Assessment

Suggested scale:

| Level        | Meaning                   |
| ------------ | ------------------------- |
| Very High    | Consistently validated    |
| High         | Strong historical support |
| Moderate     | Useful with confirmation  |
| Low          | Early observation         |
| Experimental | Research only             |

---

## 10. Verification Status

Possible values:

* Draft
* Under Research
* Backtested
* Verified
* Archived

Only Verified cards should automatically contribute to AI rules.

---

## 11. AI Rule Mapping

If applicable, link the Knowledge Card to one or more AI Rules.

Example:

* AQSD-001
* AQSD-014

This creates traceability between research and implementation.

---

## 12. Remarks

Free-form notes, future ideas, limitations, or implementation considerations.

---

# Knowledge Card Lifecycle

Research

↓

Draft Card

↓

Evidence Collection

↓

Backtesting

↓

Verification

↓

AI Rule

↓

Knowledge Engine

↓

AI Commentary

---

# Example Knowledge Card

**Knowledge ID:** KC-0001

**Title:** Modified PCR Rising with Stable IV

**Category:** Options

**Status:** Verified

**Expected Behaviour:** Bullish continuation more likely than panic buying.

**Confidence:** High

**Linked AI Rule:** AQSD-001

---

# Design Philosophy

Knowledge should evolve through disciplined research rather than assumptions.

The Knowledge Card system separates observations from verified intelligence, allowing AQSD to grow in a controlled, explainable manner.

---

# Future Enhancements

Future versions may include:

* Confidence scoring from backtest statistics
* Source citations
* Cross-references between related cards
* Review schedules
* Owner assignment
* Automatic promotion from Draft to Verified after defined validation criteria

---

# Conclusion

The Knowledge Card Standard provides a consistent framework for capturing market intelligence.

By using a common structure, AQSD can transform individual observations into reusable knowledge, machine-readable AI rules, and ultimately explainable decision support.

---

**End of Document**

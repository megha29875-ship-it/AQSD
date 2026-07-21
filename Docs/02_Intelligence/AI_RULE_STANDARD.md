# AI RULE STANDARD

---

# AQSD AI Rule Standard

Version: 1.0

Status: Design Approved

---

# Purpose

An AI Rule is the machine-readable representation of verified trading knowledge within AQSD.

Each AI Rule converts one or more verified Knowledge Cards into structured logic that can be evaluated automatically against live market conditions.

AI Rules form the reasoning layer between analytics and explainable market commentary.

---

# Relationship to Knowledge Cards

Knowledge Cards capture research and understanding.

AI Rules capture executable logic.

Flow:

Research

↓

Knowledge Card

↓

Verification

↓

AI Rule

↓

Knowledge Engine

↓

Decision Engine

↓

AI Commentary

---

# AI Rule Structure

Every AI Rule should follow the same structure.

---

## Rule Metadata

| Field                  | Description                                                 |
| ---------------------- | ----------------------------------------------------------- |
| Rule ID                | Unique identifier (AQSD-0001)                               |
| Title                  | Short descriptive title                                     |
| Version                | Rule version                                                |
| Status                 | Draft, Testing, Verified, Deprecated                        |
| Priority               | Integer (1–100)                                             |
| Category               | Market Structure, Options, Futures, Volatility, Macro, etc. |
| Linked Knowledge Cards | One or more Knowledge IDs                                   |
| Created                | Date created                                                |
| Last Updated           | Most recent revision                                        |

---

## Rule Objective

Describe what the rule is trying to identify.

Example:

Detect conditions consistent with bullish continuation following strengthening options positioning.

---

## Input Variables

List every analytical value required.

Examples:

* Modified PCR
* OI PCR
* Volume PCR
* IV
* HV
* IV Rank
* Call Wall
* Put Wall
* Trend
* Market Regime
* Market Phase
* BOS
* CHOCH

---

## Rule Conditions

Rules should be expressed as logical conditions.

Example:

IF

Modified PCR Rising

AND

IV Stable

AND

Call Wall Stable

AND

Market Regime = Weak Bull Trend

THEN

Bullish Continuation Probability increases.

---

## Output

Each rule should return structured output.

Example:

* Interpretation
* Confidence Adjustment
* Probability Adjustment
* Commentary Fragment
* Supporting Rule ID

Rules should never return BUY, SELL, LONG, or SHORT instructions.

---

## Confidence

Suggested levels:

* Very High
* High
* Moderate
* Low
* Experimental

Confidence reflects evidence supporting the rule, not market certainty.

---

## Rule Priority

When multiple rules are active:

Higher-priority rules should be evaluated first.

Example:

* Macro Event Rule → Priority 95
* Earnings Rule → Priority 90
* Expiry Rule → Priority 85
* PCR Rule → Priority 60

Priority determines evaluation order, not correctness.

---

## Conflict Resolution

Rules may disagree.

Example:

Rule A

Bullish continuation

Rule B

Bearish reversal watch

The Knowledge Engine should:

* Identify conflicting rules.
* Compare priorities.
* Compare confidence.
* Present the conflict transparently.

The Decision Engine should explain why one interpretation is favoured.

---

## Rule Lifecycle

Draft

↓

Testing

↓

Backtesting

↓

Verified

↓

Production

↓

Review

↓

Retirement (if obsolete)

Rules should never bypass validation.

---

## Rule Versioning

Every modification should create a new version.

Example:

AQSD-001 v1.0

↓

AQSD-001 v1.1

↓

AQSD-001 v2.0

This preserves historical reasoning and supports reproducibility.

---

## Example Rule

Rule ID:

AQSD-0001

Title:

Modified PCR Rising with Stable IV

Conditions:

* Modified PCR rising
* IV stable
* No macro event
* Call Wall unchanged

Interpretation:

Bullish continuation more likely than panic buying.

Confidence:

High

Priority:

60

Knowledge Card:

KC-0001

---

# Rule Chaining

Some rules may depend on others.

Example:

Trend Rule

↓

Structure Rule

↓

PCR Rule

↓

Decision Rule

↓

Commentary Rule

This allows layered reasoning rather than isolated signals.

---

# Design Principles

Every AI Rule should be:

* Explainable
* Testable
* Traceable
* Modular
* Evidence-based
* Independent
* Reusable

---

# Future Enhancements

Future versions may include:

* Weighted scoring
* Statistical confidence
* Bayesian reasoning
* Rule ensembles
* Machine learning assisted weighting
* Automatic rule review based on backtest performance

---

# Conclusion

The AI Rule Standard defines how AQSD transforms verified market knowledge into structured analytical reasoning.

By separating research, executable rules, and commentary, AQSD remains transparent, extensible, and explainable while avoiding black-box decision making.

---

**End of Document**

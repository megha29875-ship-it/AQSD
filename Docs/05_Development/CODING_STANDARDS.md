# CODING STANDARDS

---

# AQSD Coding Standards

Version: 1.0

Status: Active Development

---

# Purpose

This document defines the coding standards for the AQSD project.

The objective is to maintain a consistent, readable, maintainable, and scalable codebase as the platform evolves.

---

# General Principles

Every piece of code should be:

* Simple
* Readable
* Modular
* Reusable
* Testable
* Documented
* Explainable

Code should prioritise clarity over cleverness.

---

# Single Responsibility Principle

Each Python file should have one primary responsibility.

Examples:

* `trend_engine.py` → Trend analysis
* `swing_engine.py` → Swing detection
* `decision_engine.py` → Decision aggregation

Avoid combining unrelated functionality into a single file.

---

# Module Header

Every Python file should begin with a standard header.

```python
"""
AQSD

Module:
Version:
Author:
Purpose:
Dependencies:
Created:
Last Updated:
"""
```

This provides consistent metadata across the project.

---

# Naming Conventions

## Files

Use lowercase with underscores.

Examples:

* trend_engine.py
* decision_engine.py
* probability_engine.py

---

## Classes

Use PascalCase.

Examples:

* TrendEngine
* DecisionEngine
* KnowledgeCard

---

## Functions

Use descriptive snake_case names.

Examples:

* calculate_trend()
* detect_bos()
* analyse_market_phase()

Function names should clearly describe their behaviour.

---

## Variables

Use meaningful names.

Good:

```python
trend_strength
market_phase
continuation_probability
```

Avoid:

```python
a
temp
value1
```

---

# Constants

Use uppercase.

```python
LOOKBACK_DAYS = 250
DEFAULT_TIMEFRAME = "1D"
MAX_HISTORY = 1000
```

---

# Comments

Write comments that explain **why**, not **what**.

Good:

```python
# Ignore incomplete candles to avoid false signals.
```

Avoid:

```python
# Increment i
i += 1
```

The code already explains the second example.

---

# Functions

Aim for small, focused functions.

Recommended guidelines:

* One clear responsibility
* Descriptive name
* Minimal side effects
* Return structured results where appropriate

---

# Error Handling

Handle expected failures gracefully.

Examples:

* Missing data
* API errors
* Database connection failures
* Invalid user input

Avoid silent failures.

---

# Logging

Use logging for significant events.

Log:

* Application start
* Application end
* Errors
* Warnings
* Database updates
* Important analytical events

Do not use excessive logging for routine operations.

---

# Documentation

Every public function should include a docstring.

Example:

```python
def calculate_trend(data):
    """
    Calculate the market trend using AQSD logic.

    Args:
        data: Historical market data.

    Returns:
        Dictionary containing trend analysis.
    """
```

---

# Testing

Every new engine should include corresponding tests.

Tests should cover:

* Normal operation
* Edge cases
* Invalid input
* Empty datasets
* Expected outputs

---

# Git Workflow

For every completed module:

1. Run tests.
2. Review changes.
3. Commit with a meaningful message.
4. Push to GitHub.
5. Run Robocopy backup.

Commit messages should describe the completed work rather than generic updates.

---

# Documentation Workflow

When a major feature is completed:

* Update the relevant architecture document.
* Add an entry to the development log.
* Update the change log.
* Create a milestone document if appropriate.

Documentation is considered part of the feature, not an optional extra.

---

# Design Philosophy

AQSD is designed around:

* Independent engines
* Layered architecture
* Explainable analytics
* Reusable components
* Continuous improvement

Each new module should reinforce these principles.

---

# Code Review Checklist

Before committing:

* Is the code readable?
* Is the module focused?
* Are functions documented?
* Are names descriptive?
* Are errors handled?
* Have tests been run?
* Has documentation been updated?
* Is Git ready for commit?

---

# Conclusion

Consistent coding standards are essential for building a professional analytical platform.

Following these standards ensures AQSD remains maintainable, scalable, and understandable as it grows in complexity.

---

**End of Document**

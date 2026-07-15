# AQSD - Automated Quantitative Stock Discovery

## Overview

AQSD (Automated Quantitative Stock Discovery) is a modular Python-based stock market intelligence platform designed to analyze NSE-listed securities using technical, quantitative, sectoral, and intelligence-driven models.

The objective is to build a professional decision-support system capable of identifying high-probability trading and investment opportunities through multiple independent intelligence engines.

---

# Project Objectives

- Create a centralized stock intelligence platform.
- Integrate multiple independent analytical engines.
- Automate daily market analysis.
- Generate actionable dashboards and reports.
- Maintain a scalable and modular architecture.
- Ensure reliability through version control and automated backups.

---

# Current Architecture

```
AQSD
│
├── Scripts/
│
├── Data/
│
├── Output/
│
├── Config/
│
├── Docs/
│
├── Logs/
│
├── Tests/
│
├── Backups/
│
├── README.md
│
└── .gitignore
```

---

# Major Intelligence Modules

## Market Structure Engine

Evaluates overall market structure and trend characteristics.

---

## Trend Intelligence Engine

Measures trend strength, sustainability, and continuation probability.

---

## Relative Strength Engine

Ranks securities based on relative performance versus benchmark indices.

---

## Sector Rotation Engine

Identifies sectors receiving institutional participation.

---

## News Intelligence Engine

Analyzes news sentiment and significant market events.

---

## Global Intelligence Engine

Tracks global indices, commodities, currencies, and macroeconomic influences.

---

## Master Intelligence Engine

Combines outputs from all analytical engines into a unified stock score.

---

## Price Cache Engine

Stores historical and current market data for rapid access.

---

## Symbol Resolver

Maintains standardized NSE symbol mapping.

---

## Database Engine

Handles storage and retrieval of market data.

---

# Technology Stack

Programming Language

- Python 3.14+

Libraries

- pandas
- numpy
- yfinance
- openpyxl
- ta
- sqlite3

Version Control

- Git
- GitHub

Backup

- Robocopy Mirror

Operating System

- Windows 11

---

# Development Workflow

1. Develop feature.
2. Test locally.
3. Commit using Git.
4. Push to GitHub.
5. Robocopy mirrors project automatically.

---

# Backup Strategy

## Source

```
C:\Users\Megha\AQSD
```

## Mirror

```
E:\Mirror\AQSD
```

Git protects source code history.

Robocopy protects the complete project.

---

# Future Modules

- Risk Management Engine
- Portfolio Optimizer
- Position Sizing
- Options Analytics
- F&O Scanner
- Volume Intelligence
- AI Pattern Recognition
- Machine Learning Models
- Performance Analytics
- Strategy Optimizer

---

# Long-Term Vision

AQSD aims to evolve into a comprehensive institutional-grade market intelligence platform capable of:

- Multi-factor stock ranking
- Portfolio construction
- Strategy development
- Risk assessment
- Trade generation
- Market monitoring
- Automated reporting
- AI-assisted market intelligence

---

# Author

Megha

Project: AQSD

Status: Active Development

Version: 3.x
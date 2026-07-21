# FOLDER STRUCTURE

---

# AQSD Folder Structure

Version: 1.0

Status: Active Development

---

# Purpose

This document defines the official folder structure for the AQSD project.

Every new module, document, database, test, and research artifact should be placed in its designated location. Following this structure keeps the project organized, simplifies maintenance, and makes onboarding easier.

---

# Root Directory

```text
AQSD
│
├── Config
├── Data
├── Docs
├── Library
├── Logs
├── Output
├── Releases
├── Scripts
├── Tests
├── Backup
├── .gitignore
├── README.md
└── requirements.txt
```

---

# Config

Purpose

Application configuration files.

Typical contents:

* Application settings
* Environment templates
* API configuration
* Logging configuration

Do not store secrets directly in version control.

---

# Data

Purpose

Persistent project data.

Suggested structure:

```text
Data
│
├── Market
├── OptionChain
├── Historical
├── Symbols
├── Databases
└── Cache
```

Examples:

* SQLite databases
* Symbol master files
* Historical datasets
* Cached reference data

---

# Docs

Purpose

All project documentation.

```text
Docs
│
├── 00_Project
├── 01_Architecture
├── 02_Intelligence
├── 03_Strategies
├── 04_AI
├── 05_Development
├── 06_Reference
└── 07_Research
```

---

# Library

Purpose

Reference material used to build AQSD.

Suggested structure:

```text
Library
│
├── Books
├── PDFs
├── Research Papers
├── Articles
├── QuantsApp
├── Images
└── Videos
```

This folder is intended for source material rather than generated outputs.

---

# Logs

Purpose

Application and execution logs.

Examples:

* Runtime logs
* Error logs
* Scheduler logs
* Import logs

---

# Output

Purpose

Generated reports and exported results.

Suggested structure:

```text
Output
│
├── Dashboard
├── Reports
├── Excel
├── CSV
├── JSON
└── Charts
```

This folder contains generated files and should not hold manually edited content.

---

# Releases

Purpose

Versioned release packages.

Example:

```text
Releases
│
├── v1.0
├── v1.1
└── v2.0
```

Each release should include release notes and packaged deliverables.

---

# Scripts

Purpose

Application source code.

Suggested structure:

```text
Scripts
│
├── Dashboard
├── MarketStructure
├── OptionIntelligence
├── DecisionEngine
├── KnowledgeEngine
├── Portfolio
├── Risk
├── Reports
├── Utilities
└── Shared
```

Each module should have a clearly defined responsibility.

---

# Tests

Purpose

Automated and manual testing resources.

Suggested structure:

```text
Tests
│
├── Unit
├── Integration
├── Regression
└── Performance
```

Every major engine should have corresponding tests.

---

# Backup

Purpose

Local project backups.

Suggested contents:

* Robocopy snapshots
* Manual archives
* Emergency recovery copies

This folder complements Git and should not replace version control.

---

# Folder Management Rules

* Keep generated files in `Output`.
* Keep source code in `Scripts`.
* Keep documentation in `Docs`.
* Keep research material in `Library`.
* Keep databases under `Data/Databases`.
* Do not mix source files with generated outputs.
* Archive obsolete material instead of deleting it immediately.

---

# Naming Conventions

* Use descriptive folder names.
* Prefer PascalCase for source-code module folders.
* Use lowercase with underscores for Markdown filenames where consistency is preferred.
* Avoid spaces and special characters in folder names.
* Maintain a consistent naming style throughout the project.

---

# Future Expansion

As AQSD grows, additional folders may be introduced for specialised capabilities, such as:

* MachineLearning
* API
* Web
* Mobile
* Cloud
* Monitoring
* Deployment

New folders should be documented before they become part of the standard project structure.

---

# Conclusion

A well-defined folder structure is essential for maintaining a scalable and professional codebase.

Following this document ensures AQSD remains organised, maintainable, and ready for future expansion.

---

**End of Document**

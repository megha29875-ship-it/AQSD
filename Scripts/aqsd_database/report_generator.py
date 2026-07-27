"""
AQSD
Validation Report Generator

Module    : report_generator.py
Module ID : DB-001F
Version   : 1.0.0
Author    : AQSD
Status    : Production

Description
-----------
Creates validation reports for AQSD Database Builder.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from aqsd_core.logger import get_logger
from aqsd_database.models import ValidationSummary

logger = get_logger(__name__)


class ReportGenerator:
    """
    Generates validation reports.
    """

    def __init__(
        self,
        output_folder: Path,
    ) -> None:

        self.output_folder = output_folder

        self.output_folder.mkdir(
            parents=True,
            exist_ok=True,
        )

    def create_validation_report(
        self,
        validation: ValidationSummary,
        filename: str = "validation_report.xlsx",
    ) -> Path:

        report_file = self.output_folder / filename

        errors = pd.DataFrame(
            {
                "Severity": ["ERROR"] * len(validation.errors),
                "Message": validation.errors,
            }
        )

        warnings = pd.DataFrame(
            {
                "Severity": ["WARNING"] * len(validation.warnings),
                "Message": validation.warnings,
            }
        )

        summary = pd.DataFrame(
            {
                "Metric": [
                    "Validation Passed",
                    "Error Count",
                    "Warning Count",
                ],
                "Value": [
                    validation.passed,
                    validation.error_count,
                    validation.warning_count,
                ],
            }
        )

        with pd.ExcelWriter(
            report_file,
            engine="openpyxl",
        ) as writer:

            summary.to_excel(
                writer,
                sheet_name="Summary",
                index=False,
            )

            errors.to_excel(
                writer,
                sheet_name="Errors",
                index=False,
            )

            warnings.to_excel(
                writer,
                sheet_name="Warnings",
                index=False,
            )

        logger.info(
            "Validation report created : %s",
            report_file,
        )

        return report_file
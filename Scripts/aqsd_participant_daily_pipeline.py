"""
AQSD
Participant Daily Pipeline

Module : APD-007
Version: 1.0.1
Author : AQSD

Description
-----------
Runs the complete AQSD participant-data workflow for one trading date.

Pipeline
--------
1. Select the required trading date.
2. Download NSE participant OI and Volume reports.
3. Validate and store the raw reports.
4. Import both reports into the APD SQLite database.
5. Run Participant Intelligence.
6. Run Participant Change Intelligence when sufficient history exists.
7. Print one consolidated daily summary.

Important
---------
This pipeline performs analytics only.

It does not place orders or generate BUY, SELL or SHORT instructions.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final

from Scripts.aqsd_core.trading_calendar import latest_trading_day
from Scripts.aqsd_data_acquisition.download_manager import (
    ManagerResult,
    run_nse_download_manager,
)
from Scripts.aqsd_database.participant_import_manager import (
    ParticipantImportResult,
    run_participant_import,
)
from Scripts.aqsd_intelligence.participant_change_engine import (
    ParticipantChangeResult,
    run_participant_change_engine,
)
from Scripts.aqsd_intelligence.participant_intelligence import (
    ParticipantIntelligenceResult,
    run_participant_intelligence,
)


# ==========================================================
# MODULE SETTINGS
# ==========================================================

MODULE_ID: Final[str] = "APD-007"
MODULE_VERSION: Final[str] = "1.0.1"


# ==========================================================
# RESULT MODEL
# ==========================================================

@dataclass(frozen=True)
class ParticipantPipelineResult:
    """
    Consolidated result from the participant daily pipeline.
    """

    requested_date: date
    selected_trade_date: date

    download_status: str
    download_successful: int
    download_failed: int
    download_skipped: int

    import_status: str
    records_inserted: int
    records_skipped: int
    database_records: int

    intelligence_status: str
    institutional_bias: str
    intelligence_confidence: int

    change_status: str
    institutional_change_bias: str | None
    change_conviction: int | None

    overall_status: str


# ==========================================================
# DATE HANDLING
# ==========================================================

def parse_date(value: str) -> date:
    """
    Convert YYYY-MM-DD text into a Python date.
    """

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    except ValueError as exc:
        raise ValueError(
            "Invalid date format. Use YYYY-MM-DD."
        ) from exc


def select_trade_date(
    requested_date: date | None,
) -> date:
    """
    Select the trading date for the pipeline.

    When no date is supplied, today's date is used.

    Weekend dates are shifted to the previous weekday using
    the AQSD Trading Calendar Engine.
    """

    base_date = (
        requested_date
        if requested_date is not None
        else date.today()
    )

    return latest_trading_day(base_date)


# ==========================================================
# STATUS LOGIC
# ==========================================================

def determine_pipeline_status(
    *,
    download_result: ManagerResult,
    import_result: ParticipantImportResult,
    intelligence_result: ParticipantIntelligenceResult | None,
) -> str:
    """
    Determine the overall participant pipeline status.
    """

    if download_result.reports_failed > 0:
        return "FAILED"

    if import_result.overall_status == "FAILED":
        return "FAILED"

    if intelligence_result is None:
        return "PARTIAL_SUCCESS"

    return "SUCCESS"


# ==========================================================
# FAILED RESULT HELPERS
# ==========================================================

def create_download_failure_result(
    *,
    requested_date: date | None,
    selected_trade_date: date,
    download_result: ManagerResult,
) -> ParticipantPipelineResult:
    """
    Create a pipeline result when the download stage fails.
    """

    return ParticipantPipelineResult(
        requested_date=(
            requested_date
            if requested_date is not None
            else selected_trade_date
        ),
        selected_trade_date=selected_trade_date,
        download_status=download_result.overall_status,
        download_successful=download_result.reports_successful,
        download_failed=download_result.reports_failed,
        download_skipped=download_result.reports_skipped,
        import_status="NOT RUN",
        records_inserted=0,
        records_skipped=0,
        database_records=0,
        intelligence_status="NOT RUN",
        institutional_bias="UNKNOWN",
        intelligence_confidence=0,
        change_status="NOT RUN",
        institutional_change_bias=None,
        change_conviction=None,
        overall_status="FAILED",
    )


def create_import_failure_result(
    *,
    requested_date: date | None,
    selected_trade_date: date,
    download_result: ManagerResult,
    import_result: ParticipantImportResult,
) -> ParticipantPipelineResult:
    """
    Create a pipeline result when the database import stage fails.
    """

    return ParticipantPipelineResult(
        requested_date=(
            requested_date
            if requested_date is not None
            else selected_trade_date
        ),
        selected_trade_date=selected_trade_date,
        download_status=download_result.overall_status,
        download_successful=download_result.reports_successful,
        download_failed=download_result.reports_failed,
        download_skipped=download_result.reports_skipped,
        import_status=import_result.overall_status,
        records_inserted=import_result.records_inserted,
        records_skipped=import_result.records_skipped,
        database_records=import_result.database_total_records,
        intelligence_status="NOT RUN",
        institutional_bias="UNKNOWN",
        intelligence_confidence=0,
        change_status="NOT RUN",
        institutional_change_bias=None,
        change_conviction=None,
        overall_status="FAILED",
    )


# ==========================================================
# PIPELINE
# ==========================================================

def run_participant_pipeline(
    requested_date: date | None = None,
) -> ParticipantPipelineResult:
    """
    Run the complete AQSD participant-data pipeline.
    """

    selected_trade_date = select_trade_date(
        requested_date
    )

    print()
    print("=" * 84)
    print("AQSD PARTICIPANT DAILY PIPELINE")
    print("=" * 84)
    print(f"Module              : {MODULE_ID}")
    print(f"Version             : {MODULE_VERSION}")
    print(f"Requested Date      : {requested_date}")
    print(f"Selected Trade Date : {selected_trade_date}")
    print("=" * 84)

    # ======================================================
    # STAGE 1 — DOWNLOAD
    # ======================================================

    print()
    print("STAGE 1 — NSE PARTICIPANT DOWNLOAD")
    print("-" * 84)

    download_result = run_nse_download_manager(
        selected_trade_date
    )

    if download_result.reports_failed > 0:
        print()
        print("PIPELINE STOPPED")
        print(
            "Reason: One or more participant reports "
            "could not be downloaded."
        )

        failure_result = create_download_failure_result(
            requested_date=requested_date,
            selected_trade_date=selected_trade_date,
            download_result=download_result,
        )

        display_pipeline_summary(
            failure_result
        )

        return failure_result

    # ======================================================
    # STAGE 2 — DATABASE IMPORT
    # ======================================================

    print()
    print("STAGE 2 — APD DATABASE IMPORT")
    print("-" * 84)

    import_result = run_participant_import(
        selected_trade_date
    )

    if import_result.overall_status == "FAILED":
        print()
        print("PIPELINE STOPPED")
        print(
            "Reason: Participant reports could not "
            "be imported into APD."
        )

        failure_result = create_import_failure_result(
            requested_date=requested_date,
            selected_trade_date=selected_trade_date,
            download_result=download_result,
            import_result=import_result,
        )

        display_pipeline_summary(
            failure_result
        )

        return failure_result

    # ======================================================
    # STAGE 3 — CURRENT PARTICIPANT INTELLIGENCE
    # ======================================================

    print()
    print("STAGE 3 — PARTICIPANT INTELLIGENCE")
    print("-" * 84)

    intelligence_result: ParticipantIntelligenceResult | None = None

    intelligence_status = "FAILED"
    institutional_bias = "UNKNOWN"
    intelligence_confidence = 0

    try:
        intelligence_result = run_participant_intelligence(
            selected_trade_date
        )

        intelligence_status = (
            intelligence_result.status
        )

        institutional_bias = (
            intelligence_result.institutional_bias
        )

        intelligence_confidence = (
            intelligence_result.overall_confidence
        )

        print(
            f"Institutional Bias : "
            f"{institutional_bias}"
        )

        print(
            f"Confidence         : "
            f"{intelligence_confidence}%"
        )

    except Exception as exc:
        print(
            "Participant Intelligence failed: "
            f"{exc}"
        )

    # ======================================================
    # STAGE 4 — CHANGE INTELLIGENCE
    # ======================================================

    print()
    print("STAGE 4 — PARTICIPANT CHANGE INTELLIGENCE")
    print("-" * 84)

    change_result: ParticipantChangeResult | None = None

    change_status = "INSUFFICIENT HISTORY"
    institutional_change_bias: str | None = None
    change_conviction: int | None = None

    try:
        change_result = run_participant_change_engine(
            selected_trade_date
        )

        change_status = (
            change_result.status
        )

        institutional_change_bias = (
            change_result.institutional_change_bias
        )

        change_conviction = (
            change_result.overall_conviction
        )

        print(
            f"Institutional Change Bias : "
            f"{institutional_change_bias}"
        )

        print(
            f"Change Conviction         : "
            f"{change_conviction}%"
        )

    except RuntimeError as exc:
        print(
            "Status : INSUFFICIENT HISTORY"
        )

        print(
            f"Reason : {exc}"
        )

    except Exception as exc:
        change_status = "FAILED"

        print(
            "Participant Change Engine failed: "
            f"{exc}"
        )

    # ======================================================
    # FINAL STATUS
    # ======================================================

    overall_status = determine_pipeline_status(
        download_result=download_result,
        import_result=import_result,
        intelligence_result=intelligence_result,
    )

    result = ParticipantPipelineResult(
        requested_date=(
            requested_date
            if requested_date is not None
            else selected_trade_date
        ),
        selected_trade_date=selected_trade_date,
        download_status=download_result.overall_status,
        download_successful=download_result.reports_successful,
        download_failed=download_result.reports_failed,
        download_skipped=download_result.reports_skipped,
        import_status=import_result.overall_status,
        records_inserted=import_result.records_inserted,
        records_skipped=import_result.records_skipped,
        database_records=import_result.database_total_records,
        intelligence_status=intelligence_status,
        institutional_bias=institutional_bias,
        intelligence_confidence=intelligence_confidence,
        change_status=change_status,
        institutional_change_bias=institutional_change_bias,
        change_conviction=change_conviction,
        overall_status=overall_status,
    )

    display_pipeline_summary(
        result
    )

    return result


# ==========================================================
# DISPLAY
# ==========================================================

def display_pipeline_summary(
    result: ParticipantPipelineResult,
) -> None:
    """
    Print one consolidated pipeline summary.
    """

    change_bias_display = (
        result.institutional_change_bias
        if result.institutional_change_bias is not None
        else "NOT AVAILABLE"
    )

    change_conviction_display = (
        f"{result.change_conviction}%"
        if result.change_conviction is not None
        else "NOT AVAILABLE"
    )

    print()
    print("=" * 84)
    print("AQSD PARTICIPANT PIPELINE SUMMARY")
    print("=" * 84)

    print(
        f"Trade Date                   : "
        f"{result.selected_trade_date}"
    )

    print("-" * 84)

    print(
        f"Download Status              : "
        f"{result.download_status}"
    )

    print(
        f"Reports Successful           : "
        f"{result.download_successful}"
    )

    print(
        f"Reports Skipped              : "
        f"{result.download_skipped}"
    )

    print(
        f"Reports Failed               : "
        f"{result.download_failed}"
    )

    print("-" * 84)

    print(
        f"Import Status                : "
        f"{result.import_status}"
    )

    print(
        f"Records Inserted             : "
        f"{result.records_inserted}"
    )

    print(
        f"Records Skipped              : "
        f"{result.records_skipped}"
    )

    print(
        f"Total APD Records            : "
        f"{result.database_records}"
    )

    print("-" * 84)

    print(
        f"Intelligence Status          : "
        f"{result.intelligence_status}"
    )

    print(
        f"Institutional Bias           : "
        f"{result.institutional_bias}"
    )

    print(
        f"Intelligence Confidence      : "
        f"{result.intelligence_confidence}%"
    )

    print("-" * 84)

    print(
        f"Change Status                : "
        f"{result.change_status}"
    )

    print(
        f"Institutional Change Bias    : "
        f"{change_bias_display}"
    )

    print(
        f"Change Conviction            : "
        f"{change_conviction_display}"
    )

    print("-" * 84)

    print(
        f"OVERALL STATUS               : "
        f"{result.overall_status}"
    )

    print("=" * 84)


# ==========================================================
# COMMAND LINE
# ==========================================================

def parse_arguments() -> argparse.Namespace:
    """
    Read command-line arguments.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Run the complete AQSD participant daily pipeline."
        )
    )

    parser.add_argument(
        "--date",
        required=False,
        help=(
            "Trading date in YYYY-MM-DD format. "
            "When omitted, AQSD selects the latest weekday."
        ),
    )

    return parser.parse_args()


def main() -> None:
    """
    Command-line entry point.
    """

    arguments = parse_arguments()

    requested_date = (
        parse_date(arguments.date)
        if arguments.date
        else None
    )

    result = run_participant_pipeline(
        requested_date
    )

    if result.overall_status == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
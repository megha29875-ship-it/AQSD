"""
AQSD Institutional Cockpit v1.0

Streamlit dashboard for the latest AQSD institutional decision outputs.

Run:
    streamlit run Scripts/aqsd_institutional_cockpit.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


BASE = Path(__file__).resolve().parent.parent
OUT = BASE / "Output"

FILES = {
    "command_center": OUT / "AQSD_Command_Center_v2.csv",
    "master_decision": OUT / "AQSD_AI_Master_Decision.csv",
    "execution_readiness": OUT / "AQSD_Execution_Readiness.csv",
    "daily_checklist": OUT / "AQSD_Daily_Checklist.csv",
    "institutional_scoring": OUT / "AQSD_Institutional_Scoring.csv",
    "market_breadth": OUT / "AQSD_Market_Breadth.csv",
    "trade_approval": OUT / "AQSD_Trade_Approval.csv",
    "run_status": OUT / "AQSD_Unified_Run_Summary.csv",
}


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if pd.isna(number):
            return default
        return number
    except Exception:
        return default


def safe_text(value: Any, default: str = "-") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return default
    return text


@st.cache_data(ttl=15)
def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return pd.DataFrame()


def latest_row(path: Path) -> dict[str, Any]:
    frame = read_csv(path)
    if frame.empty:
        return {}
    return frame.iloc[-1].to_dict()


def status_badge(text: str) -> str:
    value = text.upper()

    if value in {
        "BUY",
        "READY",
        "READY TO TRADE",
        "ACTIONABLE",
        "YES",
        "SUCCESS",
    }:
        return "🟢"

    if value in {
        "SELL",
        "WAIT",
        "NOT READY",
        "DO NOT TRADE",
        "BLOCKED",
        "NO",
        "REJECT",
        "REJECTED",
        "FAILED",
    }:
        return "🔴"

    return "🟡"


def metric_value(value: Any, suffix: str = "") -> str:
    if isinstance(value, float):
        return f"{value:.1f}{suffix}"
    return f"{value}{suffix}"


def show_missing_files() -> None:
    missing = [
        str(path.name)
        for path in FILES.values()
        if not path.exists()
    ]

    if missing:
        st.warning(
            "Missing output files: " + ", ".join(missing)
        )


def main() -> None:
    st.set_page_config(
        page_title="AQSD Institutional Cockpit",
        page_icon="📊",
        layout="wide",
    )

    st.title("AQSD Institutional Cockpit")
    st.caption(
        "Institutional analytics, approval, risk and execution-readiness dashboard"
    )

    col_refresh, col_time = st.columns([1, 4])

    with col_refresh:
        if st.button("Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    with col_time:
        st.write(
            "Dashboard refreshed:",
            datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
        )

    show_missing_files()

    command = latest_row(FILES["command_center"])
    master = latest_row(FILES["master_decision"])
    readiness = latest_row(FILES["execution_readiness"])
    scoring = latest_row(FILES["institutional_scoring"])
    breadth = latest_row(FILES["market_breadth"])
    approval = latest_row(FILES["trade_approval"])

    if not command and not master:
        st.error(
            "No AQSD decision output is available. Run the unified orchestrator first."
        )
        st.stop()

    source = command or master

    underlying = safe_text(source.get("underlying"))
    verdict = safe_text(
        source.get(
            "final_verdict",
            master.get("final_verdict", "WAIT"),
        )
    ).upper()

    final_state = safe_text(
        source.get("final_state", verdict)
    ).upper()

    execution_status = safe_text(
        source.get(
            "execution_status",
            readiness.get("execution_status", "NOT READY"),
        )
    ).upper()

    trade_approved = safe_text(
        source.get(
            "trade_approved",
            approval.get("trade_approved", "NO"),
        )
    ).upper()

    confidence = safe_float(
        source.get(
            "final_confidence_percent",
            master.get("final_confidence_percent", 0),
        )
    )

    probability = safe_float(
        source.get(
            "probability_success_percent",
            master.get("probability_success_percent", 0),
        )
    )

    risk_reward = safe_float(
        source.get(
            "risk_reward",
            master.get("risk_reward", 0),
        )
    )

    risk_grade = safe_text(
        source.get(
            "risk_grade",
            master.get("risk_grade", "-"),
        )
    )

    st.subheader(f"{underlying} — Final Institutional Decision")

    top1, top2, top3, top4, top5, top6 = st.columns(6)

    top1.metric(
        "Final Verdict",
        f"{status_badge(verdict)} {verdict}",
    )
    top2.metric(
        "Final State",
        f"{status_badge(final_state)} {final_state}",
    )
    top3.metric(
        "Execution",
        f"{status_badge(execution_status)} {execution_status}",
    )
    top4.metric(
        "Approval",
        f"{status_badge(trade_approved)} {trade_approved}",
    )
    top5.metric(
        "Confidence",
        f"{confidence:.1f}%",
    )
    top6.metric(
        "Success Probability",
        f"{probability:.1f}%",
    )

    second1, second2, second3, second4 = st.columns(4)

    second1.metric(
        "Spot Price",
        safe_text(source.get("spot_price")),
    )
    second2.metric(
        "Risk / Reward",
        f"{risk_reward:.2f}",
    )
    second3.metric(
        "Risk Grade",
        risk_grade,
    )
    second4.metric(
        "Trade Quality",
        safe_text(source.get("trade_quality")),
    )

    st.divider()
    st.subheader("Institutional Scoreboard")

    score_values = {
        "Institutional": safe_float(
            source.get(
                "institutional_score",
                scoring.get("overall_institutional_score", 0),
            )
        ),
        "Directional": safe_float(
            source.get(
                "directional_score",
                scoring.get("directional_score", 0),
            )
        ),
        "Trend": safe_float(
            source.get(
                "trend_score",
                scoring.get("trend_score", 0),
            )
        ),
        "Momentum": safe_float(
            source.get(
                "momentum_score",
                scoring.get("momentum_score", 0),
            )
        ),
        "Options": safe_float(
            source.get(
                "options_score",
                scoring.get("options_score", 0),
            )
        ),
        "Futures": safe_float(
            source.get(
                "futures_score",
                scoring.get("futures_score", 0),
            )
        ),
        "Smart Money": safe_float(
            source.get(
                "smart_money_score",
                scoring.get("smart_money_score", 0),
            )
        ),
        "Breadth": safe_float(
            source.get(
                "market_breadth_score",
                breadth.get("market_breadth_score", 0),
            )
        ),
    }

    score_columns = st.columns(4)

    for index, (label, value) in enumerate(score_values.items()):
        with score_columns[index % 4]:
            st.metric(label, f"{value:.1f}")

    score_frame = pd.DataFrame(
        {
            "Component": list(score_values.keys()),
            "Score": list(score_values.values()),
        }
    )

    st.bar_chart(
        score_frame.set_index("Component"),
        height=320,
    )

    st.divider()
    left, right = st.columns([1, 1])

    with left:
        st.subheader("AI Explanation")
        st.info(
            safe_text(
                source.get(
                    "ai_explanation",
                    master.get("ai_explanation"),
                ),
                "No AI explanation available.",
            )
        )

        reasons = []

        for index in range(1, 7):
            reason = safe_text(
                source.get(
                    f"reason_{index}",
                    master.get(f"reason_{index}", ""),
                ),
                "",
            )
            if reason:
                reasons.append(reason)

        if reasons:
            st.markdown("**Decision Reasons**")
            for reason in reasons:
                st.write("•", reason)

    with right:
        st.subheader("Risk and Portfolio")

        risk_data = {
            "Suggested Quantity": safe_text(
                source.get("suggested_quantity")
            ),
            "Portfolio Status": safe_text(
                source.get("portfolio_status")
            ),
            "Portfolio Risk Score": safe_float(
                source.get("portfolio_risk_score")
            ),
            "Open Positions": safe_text(
                source.get("open_positions")
            ),
            "Total Exposure %": safe_float(
                source.get("total_exposure_percent")
            ),
            "Unrealised P/L": safe_float(
                source.get("total_unrealised_pnl")
            ),
            "Breadth Regime": safe_text(
                source.get(
                    "breadth_regime",
                    breadth.get("breadth_regime"),
                )
            ),
        }

        risk_frame = pd.DataFrame(
            list(risk_data.items()),
            columns=["Measure", "Value"],
        )

        st.dataframe(
            risk_frame,
            use_container_width=True,
            hide_index=True,
        )

    st.divider()
    st.subheader("Daily Trading Checklist")

    checklist = read_csv(FILES["daily_checklist"])

    if checklist.empty:
        st.warning(
            "Daily checklist output is not available."
        )
    else:
        st.dataframe(
            checklist,
            use_container_width=True,
            hide_index=True,
        )

        final_check = checklist.iloc[-1].to_dict()
        final_status = safe_text(
            final_check.get("status"),
            "UNKNOWN",
        ).upper()

        if final_status == "READY TO TRADE":
            st.success("🟢 READY TO TRADE")
        else:
            st.error("🔴 DO NOT TRADE")

    st.divider()
    st.subheader("Latest Pipeline Run")

    run_summary = read_csv(FILES["run_status"])

    if run_summary.empty:
        st.warning(
            "Unified pipeline run summary is not available."
        )
    else:
        if "run_id" in run_summary.columns:
            latest_run_id = run_summary.iloc[-1]["run_id"]
            latest_run = run_summary[
                run_summary["run_id"] == latest_run_id
            ].copy()
        else:
            latest_run = run_summary.tail(12).copy()

        display_columns = [
            column
            for column in [
                "step",
                "status",
                "duration_seconds",
                "message",
            ]
            if column in latest_run.columns
        ]

        st.dataframe(
            latest_run[display_columns],
            use_container_width=True,
            hide_index=True,
        )

        if "status" in latest_run.columns:
            successful = int(
                latest_run["status"]
                .astype(str)
                .str.upper()
                .eq("SUCCESS")
                .sum()
            )
            failed = int(
                latest_run["status"]
                .astype(str)
                .str.upper()
                .eq("FAILED")
                .sum()
            )
            skipped = int(
                latest_run["status"]
                .astype(str)
                .str.upper()
                .eq("SKIPPED")
                .sum()
            )

            run1, run2, run3 = st.columns(3)
            run1.metric("Successful", successful)
            run2.metric("Failed", failed)
            run3.metric("Skipped", skipped)

    st.divider()
    st.caption(
        "AQSD analytics only. Order placement remains disabled."
    )


if __name__ == "__main__":
    main()

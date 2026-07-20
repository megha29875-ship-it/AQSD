"""
AQSD
Professional Option Intelligence Dashboard

Module: professional_option_dashboard.py
Version: 2.0
Author: AQSD

Description:
Creates the visual Tab-2 dashboard for live BANKNIFTY Option Intelligence.

The dashboard:
- Runs the live Decision Intelligence pipeline
- Reads the latest Decision JSON output
- Displays important analytics on one screen
- Uses colour-coded decision and probability cards
- Reloads automatically when the Decision JSON changes
- Provides a manual Reload button
- Does not launch duplicate pipelines
- Does not place orders

Data source:
Output/DECISION/BANKNIFTY_LIVE_DECISION_INTELLIGENCE.json
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import tkinter as tk
from tkinter import messagebox, ttk


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]

DECISION_JSON_FILE = (
    BASE_DIR
    / "Output"
    / "DECISION"
    / "BANKNIFTY_LIVE_DECISION_INTELLIGENCE.json"
)

LIVE_DECISION_MODULE = (
    "Scripts.option_intelligence.live_decision_runner"
)

DASHBOARD_POLL_MS = 2000


# ============================================================
# DISPLAY CONFIGURATION
# ============================================================

WINDOW_TITLE = "AQSD — Professional Option Intelligence"
WINDOW_WIDTH = 1540
WINDOW_HEIGHT = 890

BACKGROUND = "#10141C"
PANEL_BACKGROUND = "#19202B"
CARD_BACKGROUND = "#222B38"

TEXT_PRIMARY = "#F4F7FA"
TEXT_SECONDARY = "#AEB9C8"

POSITIVE = "#29C785"
NEGATIVE = "#F05D68"
WARNING = "#F4B942"
NEUTRAL = "#6FA8FF"
BORDER = "#344052"

FONT_FAMILY = "Segoe UI"


# ============================================================
# JSON HELPERS
# ============================================================

def load_json_file(
    file_path: Path,
) -> dict[str, Any]:
    """
    Read a JSON object from disk.
    """

    if not file_path.exists():
        raise FileNotFoundError(
            f"Decision JSON was not found:\n{file_path}"
        )

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        value = json.load(file)

    if not isinstance(value, dict):
        raise ValueError(
            "Decision JSON must contain a dictionary."
        )

    return value


def recursive_find(
    value: Any,
    key_name: str,
) -> Any:
    """
    Find a key anywhere inside nested JSON data.
    """

    target = str(key_name).strip().lower()

    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).strip().lower() == target:
                return item

        for item in value.values():
            found = recursive_find(
                item,
                key_name,
            )

            if found is not None:
                return found

    elif isinstance(value, list):
        for item in value:
            found = recursive_find(
                item,
                key_name,
            )

            if found is not None:
                return found

    return None


def first_available(
    data: dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:
    """
    Return the first available value from alternative key names.
    """

    for key in keys:
        value = recursive_find(
            data,
            key,
        )

        if value is not None:
            return value

    return default


def find_section(
    data: dict[str, Any],
    section_name: str,
) -> dict[str, Any]:
    """
    Find a named dictionary section inside nested JSON.
    """

    target = section_name.strip().lower()

    def search(
        value: Any,
    ) -> dict[str, Any] | None:
        if isinstance(value, dict):
            for key, item in value.items():
                if (
                    str(key).strip().lower() == target
                    and isinstance(item, dict)
                ):
                    return item

            for item in value.values():
                found = search(item)

                if found is not None:
                    return found

        elif isinstance(value, list):
            for item in value:
                found = search(item)

                if found is not None:
                    return found

        return None

    return search(data) or {}


def find_market_snapshot(
    data: dict[str, Any],
) -> dict[str, Any]:
    """
    Find the dictionary containing the main market snapshot.
    """

    best_match: dict[str, Any] = {}
    best_score = -1

    def search(
        value: Any,
    ) -> None:
        nonlocal best_match
        nonlocal best_score

        if isinstance(value, dict):
            keys = {
                str(key).strip().lower()
                for key in value.keys()
            }

            score = 0

            if "spot_price" in keys:
                score += 5

            if "atm_strike" in keys:
                score += 4

            if "strike_step" in keys:
                score += 3

            if "underlying" in keys:
                score += 2

            if "symbol" in keys:
                score += 2

            if score > best_score:
                best_score = score
                best_match = value

            for item in value.values():
                search(item)

        elif isinstance(value, list):
            for item in value:
                search(item)

    search(data)

    return best_match

    """
    Return the first available value from alternative key names.
    """

    for key in keys:
        value = recursive_find(
            data,
            key,
        )

        if value is not None:
            return value

    return default


def format_number(
    value: Any,
    decimals: int = 2,
    suffix: str = "",
) -> str:
    """
    Format a numeric value safely.
    """

    if value is None:
        return "N/A"

    try:
        number = float(value)

    except (
        TypeError,
        ValueError,
    ):
        return str(value)

    return f"{number:,.{decimals}f}{suffix}"


def format_ratio(
    value: Any,
) -> str:
    """
    Format a ratio safely.
    """

    return format_number(
        value,
        decimals=3,
    )


# ============================================================
# DECISION COLOUR
# ============================================================

def signal_colour(
    value: Any,
) -> str:
    """
    Choose a display colour from signal text.
    """

    text = str(value).strip().upper()

    positive_words = (
        "BUY CALL",
        "BULLISH",
        "STRONG BULLISH",
        "RANGE SHIFTED UP",
        "BREAKOUT ACTIVE",
        "RISING",
    )

    negative_words = (
        "BUY PUT",
        "BEARISH",
        "STRONG BEARISH",
        "RANGE SHIFTED DOWN",
        "BREAKDOWN ACTIVE",
        "FALLING",
    )

    warning_words = (
        "WAIT",
        "NO TRADE",
        "REVERSAL",
        "HIGH",
        "EXTREME",
        "WARNING",
    )

    if any(
        word in text
        for word in positive_words
    ):
        return POSITIVE

    if any(
        word in text
        for word in negative_words
    ):
        return NEGATIVE

    if any(
        word in text
        for word in warning_words
    ):
        return WARNING

    return NEUTRAL


# ============================================================
# REUSABLE CARD
# ============================================================

class MetricCard(tk.Frame):
    """
    Reusable dashboard metric card.
    """

    def __init__(
        self,
        parent: tk.Widget,
        title: str,
        value: str = "N/A",
        accent: str = NEUTRAL,
    ) -> None:
        super().__init__(
            parent,
            bg=CARD_BACKGROUND,
            highlightbackground=BORDER,
            highlightthickness=1,
            bd=0,
        )

        self.columnconfigure(
            0,
            weight=1,
        )

        self.title_label = tk.Label(
            self,
            text=title.upper(),
            bg=CARD_BACKGROUND,
            fg=TEXT_SECONDARY,
            font=(
                FONT_FAMILY,
                9,
                "bold",
            ),
            anchor="w",
        )

        self.title_label.grid(
            row=0,
            column=0,
            padx=14,
            pady=(
                11,
                2,
            ),
            sticky="ew",
        )

        self.value_label = tk.Label(
            self,
            text=value,
            bg=CARD_BACKGROUND,
            fg=accent,
            font=(
                FONT_FAMILY,
                18,
                "bold",
            ),
            anchor="w",
        )

        self.value_label.grid(
            row=1,
            column=0,
            padx=14,
            pady=(
                2,
                12,
            ),
            sticky="ew",
        )

    def set_value(
        self,
        value: Any,
        accent: str | None = None,
    ) -> None:
        """
        Update the displayed value.
        """

        self.value_label.configure(
            text=str(value)
        )

        if accent is not None:
            self.value_label.configure(
                fg=accent
            )


# ============================================================
# MAIN DASHBOARD
# ============================================================

class ProfessionalOptionDashboard:
    """
    AQSD Professional Option Intelligence dashboard.
    """

    def __init__(
        self,
        root: tk.Tk,
    ) -> None:
        self.root = root

        self.root.title(
            WINDOW_TITLE
        )

        self.root.geometry(
            f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"
        )

        self.root.minsize(
            1280,
            760,
        )

        self.root.configure(
            bg=BACKGROUND
        )

        self.refresh_running = False

        self.cards: dict[
            str,
            MetricCard,
        ] = {}

        self.status_variable = (
            tk.StringVar(
                value="Ready"
            )
        )

        self.updated_variable = (
            tk.StringVar(
                value="Last update: N/A"
            )
        )

        self.last_decision_file_mtime_ns: int | None = None
        self.dashboard_watch_job: str | None = None

        self.build_interface()
        self.load_existing_output()
        self.start_dashboard_file_watch()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close_dashboard,
        )

    # --------------------------------------------------------
    # GENERAL LAYOUT
    # --------------------------------------------------------

    def update_dashboard(
        self,
        data: dict[str, Any],
    ) -> None:
        """
        Update all dashboard cards from the live Decision JSON.
        """

        snapshot = find_market_snapshot(data)
        decision = find_section(data, "decision")
        probabilities = find_section(data, "probabilities")
        analytics = find_section(data, "supporting_analytics")

        self.update_decision_cards(
            decision=decision,
            probabilities=probabilities,
        )

        self.update_positioning_cards(
            snapshot=snapshot,
            analytics=analytics,
            data=data,
        )

        self.update_level_cards(
            decision=decision,
            analytics=analytics,
        )

        self.update_volatility_cards(
            analytics=analytics,
            data=data,
        )

        timestamp = first_available(
            data,
            "timestamp",
            default="N/A",
        )

        self.updated_variable.set(
            f"Last update: {timestamp}"
        )

        self.status_variable.set(
            f"Loaded: {DECISION_JSON_FILE}"
        )

    def update_decision_cards(
        self,
        decision: dict[str, Any],
        probabilities: dict[str, Any],
    ) -> None:
        """
        Update final decision and probability cards.
        """

        final_decision = decision.get(
            "final_decision",
            "WAIT",
        )

        directional_bias = decision.get(
            "decision_bias",
            "NEUTRAL",
        )

        confidence = decision.get(
            "confidence_score"
        )

        grade = decision.get(
            "trade_grade",
            "N/A",
        )

        quality = decision.get(
            "trade_quality",
            "N/A",
        )

        market_regime = decision.get(
            "market_regime",
            "N/A",
        )

        risk_level = decision.get(
            "risk_level",
            "N/A",
        )

        bullish = probabilities.get(
            "bullish"
        )

        bearish = probabilities.get(
            "bearish"
        )

        continuation = probabilities.get(
            "continuation"
        )

        reversal = probabilities.get(
            "reversal"
        )

        self.set_card(
            "final_decision",
            final_decision,
            signal_colour(
                final_decision
            ),
        )

        self.set_card(
            "directional_bias",
            directional_bias,
            signal_colour(
                directional_bias
            ),
        )

        self.set_card(
            "confidence_score",
            format_number(
                confidence,
                suffix="%",
            ),
        )

        self.set_card(
            "trade_grade",
            f"{grade} / {quality}",
        )

        self.set_card(
            "market_regime",
            market_regime,
            signal_colour(
                market_regime
            ),
        )

        self.set_card(
            "risk_level",
            risk_level,
            signal_colour(
                risk_level
            ),
        )

        self.set_card(
            "probability_pair",
            (
                f"{format_number(bullish, 1)}% / "
                f"{format_number(bearish, 1)}%"
            ),
        )

        self.set_card(
            "continuation_pair",
            (
                f"{format_number(continuation, 1)}% / "
                f"{format_number(reversal, 1)}%"
            ),
        )

    def update_positioning_cards(
        self,
        snapshot: dict[str, Any],
        analytics: dict[str, Any],
        data: dict[str, Any],
    ) -> None:
        """
        Update spot, PCR and Max Pain cards.
        """

        spot_price = snapshot.get(
            "spot_price"
        )

        atm_strike = snapshot.get(
            "atm_strike"
        )

        oi_pcr = analytics.get(
            "oi_pcr"
        )

        change_oi_pcr = analytics.get(
            "change_oi_pcr"
        )

        modified_pcr = analytics.get(
            "modified_pcr"
        )

        pcr_trend = analytics.get(
            "pcr_trend",
            "N/A",
        )

        max_pain = analytics.get(
            "max_pain_strike"
        )

        pinning_probability = first_available(
            data,
            "pinning_probability",
        )

        self.set_card(
            "spot_price",
            format_number(
                spot_price
            ),
        )

        self.set_card(
            "atm_strike",
            format_number(
                atm_strike,
                0,
            ),
        )

        self.set_card(
            "oi_pcr",
            format_ratio(
                oi_pcr
            ),
        )

        self.set_card(
            "change_oi_pcr",
            format_ratio(
                change_oi_pcr
            ),
        )

        self.set_card(
            "modified_pcr",
            format_ratio(
                modified_pcr
            ),
        )

        self.set_card(
            "pcr_trend",
            pcr_trend,
            signal_colour(
                pcr_trend
            ),
        )

        self.set_card(
            "max_pain_strike",
            format_number(
                max_pain,
                0,
            ),
        )

        self.set_card(
            "pinning_probability",
            format_number(
                pinning_probability,
                suffix="%",
            ),
        )

    def update_level_cards(
        self,
        decision: dict[str, Any],
        analytics: dict[str, Any],
    ) -> None:
        """
        Update wall, entry, stop and target cards.
        """

        call_wall = analytics.get(
            "call_wall"
        )

        put_wall = analytics.get(
            "put_wall"
        )

        entry_low = decision.get(
            "entry_low"
        )

        entry_high = decision.get(
            "entry_high"
        )

        stop_loss = decision.get(
            "stop_loss"
        )

        target_one = decision.get(
            "target_one"
        )

        target_two = decision.get(
            "target_two"
        )

        risk_reward_one = decision.get(
            "risk_reward_one"
        )

        risk_reward_two = decision.get(
            "risk_reward_two"
        )

        if (
            entry_low is None
            or entry_high is None
        ):
            entry_zone = "N/A"

        else:
            entry_zone = (
                f"{format_number(entry_low, 0)} - "
                f"{format_number(entry_high, 0)}"
            )

        self.set_card(
            "call_wall",
            format_number(
                call_wall,
                0,
            ),
        )

        self.set_card(
            "put_wall",
            format_number(
                put_wall,
                0,
            ),
        )

        self.set_card(
            "entry_zone",
            entry_zone,
        )

        self.set_card(
            "stop_loss",
            format_number(
                stop_loss,
                0,
            ),
        )

        self.set_card(
            "target_one",
            format_number(
                target_one,
                0,
            ),
        )

        self.set_card(
            "target_two",
            format_number(
                target_two,
                0,
            ),
        )

        self.set_card(
            "risk_reward_one",
            (
                "N/A"
                if risk_reward_one is None
                else (
                    "1 : "
                    + format_number(
                        risk_reward_one
                    )
                )
            ),
        )

        self.set_card(
            "risk_reward_two",
            (
                "N/A"
                if risk_reward_two is None
                else (
                    "1 : "
                    + format_number(
                        risk_reward_two
                    )
                )
            ),
        )

    def update_volatility_cards(
        self,
        analytics: dict[str, Any],
        data: dict[str, Any],
    ) -> None:
        """
        Update volatility and wall-watch cards.
        """

        atm_iv = analytics.get(
            "atm_iv"
        )

        historical_volatility = analytics.get(
            "historical_volatility"
        )

        iv_rank = analytics.get(
            "iv_rank"
        )

        iv_percentile = first_available(
            data,
            "iv_percentile",
        )

        volatility_regime = first_available(
            data,
            "volatility_regime",
            default="N/A",
        )

        wall_shift = first_available(
            data,
            "combined_wall_shift",
            default="N/A",
        )

        breakout_watch = first_available(
            data,
            "breakout_watch",
            default="N/A",
        )

        breakdown_watch = first_available(
            data,
            "breakdown_watch",
            default="N/A",
        )

        self.set_card(
            "atm_iv",
            format_number(
                atm_iv,
                suffix="%",
            ),
        )

        self.set_card(
            "historical_volatility",
            format_number(
                historical_volatility,
                suffix="%",
            ),
        )

        self.set_card(
            "iv_rank",
            format_number(
                iv_rank,
                suffix="%",
            ),
        )

        self.set_card(
            "iv_percentile",
            format_number(
                iv_percentile,
                suffix="%",
            ),
        )

        self.set_card(
            "volatility_regime",
            volatility_regime,
            signal_colour(
                volatility_regime
            ),
        )

        self.set_card(
            "wall_shift",
            wall_shift,
            signal_colour(
                wall_shift
            ),
        )

        self.set_card(
            "breakout_watch",
            breakout_watch,
        )

        self.set_card(
            "breakdown_watch",
            breakdown_watch,
        )

    def load_existing_output(
        self,
    ) -> None:
        """
        Load the most recently generated Decision JSON.
        """

        try:
            data = load_json_file(
                DECISION_JSON_FILE
            )

            self.update_dashboard(
                data
            )

            self.remember_decision_file_mtime()

        except Exception as error:
            self.status_variable.set(
                f"No live result loaded: {error}"
            )


    def build_interface(
        self,
    ) -> None:
        """
        Build the complete fixed-screen dashboard.
        """

        main_frame = tk.Frame(
            self.root,
            bg=BACKGROUND,
        )

        main_frame.pack(
            fill="both",
            expand=True,
            padx=14,
            pady=12,
        )

        main_frame.columnconfigure(
            0,
            weight=1,
        )

        main_frame.rowconfigure(
            1,
            weight=1,
        )

        self.build_header(
            main_frame
        )

        body = tk.Frame(
            main_frame,
            bg=BACKGROUND,
        )

        body.grid(
            row=1,
            column=0,
            sticky="nsew",
            pady=(
                12,
                0,
            ),
        )

        for column in range(4):
            body.columnconfigure(
                column,
                weight=1,
                uniform="dashboard",
            )

        body.rowconfigure(
            0,
            weight=1,
        )

        self.build_decision_panel(
            body
        )

        self.build_positioning_panel(
            body
        )

        self.build_levels_panel(
            body
        )

        self.build_volatility_panel(
            body
        )

        self.build_footer(
            main_frame
        )

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    def build_header(
        self,
        parent: tk.Widget,
    ) -> None:
        """
        Build dashboard heading and controls.
        """

        header = tk.Frame(
            parent,
            bg=PANEL_BACKGROUND,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

        header.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        header.columnconfigure(
            0,
            weight=1,
        )

        title_area = tk.Frame(
            header,
            bg=PANEL_BACKGROUND,
        )

        title_area.grid(
            row=0,
            column=0,
            sticky="w",
            padx=18,
            pady=13,
        )

        tk.Label(
            title_area,
            text=(
                "AQSD PROFESSIONAL "
                "OPTION INTELLIGENCE"
            ),
            bg=PANEL_BACKGROUND,
            fg=TEXT_PRIMARY,
            font=(
                FONT_FAMILY,
                19,
                "bold",
            ),
        ).pack(
            anchor="w"
        )

        tk.Label(
            title_area,
            text=(
                "TAB-2  |  LIVE BANKNIFTY  |  "
                "ANALYTICS ONLY — NO ORDER PLACEMENT"
            ),
            bg=PANEL_BACKGROUND,
            fg=TEXT_SECONDARY,
            font=(
                FONT_FAMILY,
                9,
                "bold",
            ),
        ).pack(
            anchor="w",
            pady=(
                3,
                0,
            ),
        )

        control_area = tk.Frame(
            header,
            bg=PANEL_BACKGROUND,
        )

        control_area.grid(
            row=0,
            column=1,
            sticky="e",
            padx=18,
            pady=13,
        )

        self.refresh_button = tk.Button(
            control_area,
            text="RELOAD DASHBOARD",
            command=self.start_live_refresh,
            bg=NEUTRAL,
            fg="#FFFFFF",
            activebackground="#5C92E5",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            font=(
                FONT_FAMILY,
                10,
                "bold",
            ),
            padx=16,
            pady=8,
        )

        self.refresh_button.pack(
            side="right"
        )

        tk.Label(
            control_area,
            textvariable=(
                self.updated_variable
            ),
            bg=PANEL_BACKGROUND,
            fg=TEXT_SECONDARY,
            font=(
                FONT_FAMILY,
                9,
            ),
        ).pack(
            side="right",
            padx=(
                0,
                16,
            ),
        )

    # --------------------------------------------------------
    # PANEL HELPERS
    # --------------------------------------------------------

    def create_panel(
        self,
        parent: tk.Widget,
        title: str,
        column: int,
    ) -> tk.Frame:
        """
        Create one dashboard vertical panel.
        """

        panel = tk.Frame(
            parent,
            bg=PANEL_BACKGROUND,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

        panel.grid(
            row=0,
            column=column,
            padx=(
                0 if column == 0 else 5,
                0 if column == 3 else 5,
            ),
            sticky="nsew",
        )

        panel.columnconfigure(
            0,
            weight=1,
        )

        tk.Label(
            panel,
            text=title,
            bg=PANEL_BACKGROUND,
            fg=TEXT_PRIMARY,
            font=(
                FONT_FAMILY,
                12,
                "bold",
            ),
            anchor="w",
        ).grid(
            row=0,
            column=0,
            padx=13,
            pady=(
                12,
                9,
            ),
            sticky="ew",
        )

        return panel

    def add_card(
        self,
        panel: tk.Frame,
        row: int,
        key: str,
        title: str,
        accent: str = NEUTRAL,
    ) -> None:
        """
        Add one metric card.
        """

        card = MetricCard(
            panel,
            title=title,
            accent=accent,
        )

        card.grid(
            row=row,
            column=0,
            padx=10,
            pady=5,
            sticky="ew",
        )

        self.cards[key] = card

    # --------------------------------------------------------
    # COLUMN 1 — DECISION
    # --------------------------------------------------------

    def build_decision_panel(
        self,
        parent: tk.Widget,
    ) -> None:
        panel = self.create_panel(
            parent,
            "FINAL DECISION",
            0,
        )

        self.add_card(
            panel,
            1,
            "final_decision",
            "Final Decision",
            WARNING,
        )

        self.add_card(
            panel,
            2,
            "directional_bias",
            "Directional Bias",
        )

        self.add_card(
            panel,
            3,
            "confidence_score",
            "Confidence",
        )

        self.add_card(
            panel,
            4,
            "trade_grade",
            "Trade Grade",
        )

        self.add_card(
            panel,
            5,
            "market_regime",
            "Market Regime",
        )

        self.add_card(
            panel,
            6,
            "risk_level",
            "Risk Level",
        )

        self.add_card(
            panel,
            7,
            "probability_pair",
            "Bull / Bear",
        )

        self.add_card(
            panel,
            8,
            "continuation_pair",
            "Continuation / Reversal",
        )

    # --------------------------------------------------------
    # COLUMN 2 — POSITIONING
    # --------------------------------------------------------

    def build_positioning_panel(
        self,
        parent: tk.Widget,
    ) -> None:
        panel = self.create_panel(
            parent,
            "POSITIONING",
            1,
        )

        self.add_card(
            panel,
            1,
            "spot_price",
            "BANKNIFTY Spot",
        )

        self.add_card(
            panel,
            2,
            "atm_strike",
            "ATM Strike",
        )

        self.add_card(
            panel,
            3,
            "oi_pcr",
            "OI PCR",
        )

        self.add_card(
            panel,
            4,
            "change_oi_pcr",
            "Change-OI PCR",
        )

        self.add_card(
            panel,
            5,
            "modified_pcr",
            "Modified PCR",
        )

        self.add_card(
            panel,
            6,
            "pcr_trend",
            "PCR Trend",
        )

        self.add_card(
            panel,
            7,
            "max_pain_strike",
            "Max Pain",
        )

        self.add_card(
            panel,
            8,
            "pinning_probability",
            "Pinning Probability",
        )

    # --------------------------------------------------------
    # COLUMN 3 — LEVELS
    # --------------------------------------------------------

    def build_levels_panel(
        self,
        parent: tk.Widget,
    ) -> None:
        panel = self.create_panel(
            parent,
            "LEVELS AND WALLS",
            2,
        )

        self.add_card(
            panel,
            1,
            "call_wall",
            "Positional Call Wall",
        )

        self.add_card(
            panel,
            2,
            "put_wall",
            "Positional Put Wall",
        )

        self.add_card(
            panel,
            3,
            "entry_zone",
            "Entry Zone",
        )

        self.add_card(
            panel,
            4,
            "stop_loss",
            "Stop Loss",
        )

        self.add_card(
            panel,
            5,
            "target_one",
            "Target 1",
        )

        self.add_card(
            panel,
            6,
            "target_two",
            "Target 2",
        )

        self.add_card(
            panel,
            7,
            "risk_reward_one",
            "Risk–Reward 1",
        )

        self.add_card(
            panel,
            8,
            "risk_reward_two",
            "Risk–Reward 2",
        )

    # --------------------------------------------------------
    # COLUMN 4 — VOLATILITY
    # --------------------------------------------------------

    def build_volatility_panel(
        self,
        parent: tk.Widget,
    ) -> None:
        panel = self.create_panel(
            parent,
            "VOLATILITY AND WATCH",
            3,
        )

        self.add_card(
            panel,
            1,
            "atm_iv",
            "ATM IV",
        )

        self.add_card(
            panel,
            2,
            "historical_volatility",
            "Historical Volatility",
        )

        self.add_card(
            panel,
            3,
            "iv_rank",
            "IV Rank",
        )

        self.add_card(
            panel,
            4,
            "iv_percentile",
            "IV Percentile",
        )

        self.add_card(
            panel,
            5,
            "volatility_regime",
            "Volatility Regime",
        )

        self.add_card(
            panel,
            6,
            "wall_shift",
            "Wall Shift",
        )

        self.add_card(
            panel,
            7,
            "breakout_watch",
            "Breakout Watch",
        )

        self.add_card(
            panel,
            8,
            "breakdown_watch",
            "Breakdown Watch",
        )

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------

    def build_footer(
        self,
        parent: tk.Widget,
    ) -> None:
        footer = tk.Frame(
            parent,
            bg=PANEL_BACKGROUND,
            highlightbackground=BORDER,
            highlightthickness=1,
        )

        footer.grid(
            row=2,
            column=0,
            sticky="ew",
            pady=(
                10,
                0,
            ),
        )

        footer.columnconfigure(
            0,
            weight=1,
        )

        tk.Label(
            footer,
            textvariable=self.status_variable,
            bg=PANEL_BACKGROUND,
            fg=TEXT_SECONDARY,
            font=(
                FONT_FAMILY,
                9,
                "bold",
            ),
            anchor="w",
        ).grid(
            row=0,
            column=0,
            padx=14,
            pady=8,
            sticky="ew",
        )

    # --------------------------------------------------------
    # DATA UPDATE
    # --------------------------------------------------------

    def set_card(
        self,
        key: str,
        value: Any,
        accent: str | None = None,
    ) -> None:
        """
        Update one dashboard card.
        """

        card = self.cards.get(
            key
        )

        if card is not None:
            card.set_value(
                value,
                accent,
            )

    # --------------------------------------------------------


    # --------------------------------------------------------
    # DASHBOARD RELOAD AND FILE WATCH
    # --------------------------------------------------------

    def start_live_refresh(
        self,
    ) -> None:
        """
        Reload the latest Decision JSON immediately.

        The Control Center runs the analytics pipeline. The dashboard only
        reads the latest output, so clicking this button never opens another
        console or starts a duplicate FYERS request.
        """

        if self.refresh_running:
            return

        self.refresh_running = True

        self.refresh_button.configure(
            state="disabled",
            text="RELOADING...",
        )

        self.status_variable.set(
            "Reloading latest Decision Intelligence output..."
        )

        self.root.after(
            10,
            self.reload_dashboard_now,
        )

    def reload_dashboard_now(
        self,
    ) -> None:
        """Reload the current JSON and restore the Reload button."""

        try:
            data = load_json_file(
                DECISION_JSON_FILE
            )

            self.update_dashboard(
                data
            )

            self.remember_decision_file_mtime()

            self.status_variable.set(
                "Dashboard reloaded successfully."
            )

        except Exception as error:
            self.status_variable.set(
                f"Dashboard reload failed: {error}"
            )

            messagebox.showerror(
                "AQSD Dashboard Reload Failed",
                str(error),
            )

        finally:
            self.refresh_running = False

            self.refresh_button.configure(
                state="normal",
                text="RELOAD DASHBOARD",
            )

    def remember_decision_file_mtime(
        self,
    ) -> None:
        """Remember the latest Decision JSON modification timestamp."""

        try:
            self.last_decision_file_mtime_ns = (
                DECISION_JSON_FILE.stat().st_mtime_ns
            )
        except OSError:
            self.last_decision_file_mtime_ns = None

    def start_dashboard_file_watch(
        self,
    ) -> None:
        """Start watching the Decision JSON for Control Center updates."""

        self.cancel_dashboard_file_watch()

        self.dashboard_watch_job = self.root.after(
            DASHBOARD_POLL_MS,
            self.check_for_dashboard_update,
        )

    def check_for_dashboard_update(
        self,
    ) -> None:
        """
        Reload only when the Decision JSON has changed.

        This keeps one dashboard window open all day and avoids repeated
        pipelines, consoles and duplicate browser/dashboard windows.
        """

        self.dashboard_watch_job = None

        try:
            current_mtime_ns = (
                DECISION_JSON_FILE.stat().st_mtime_ns
            )
        except OSError:
            current_mtime_ns = None

        if (
            current_mtime_ns is not None
            and current_mtime_ns
            != self.last_decision_file_mtime_ns
            and not self.refresh_running
        ):
            try:
                data = load_json_file(
                    DECISION_JSON_FILE
                )

                self.update_dashboard(
                    data
                )

                self.last_decision_file_mtime_ns = (
                    current_mtime_ns
                )

                self.status_variable.set(
                    "Dashboard updated automatically from the latest "
                    "Control Center refresh."
                )

            except Exception as error:
                self.status_variable.set(
                    f"Automatic dashboard update failed: {error}"
                )

        self.start_dashboard_file_watch()

    def cancel_dashboard_file_watch(
        self,
    ) -> None:
        """Cancel the active Tkinter file-watch callback."""

        if self.dashboard_watch_job is None:
            return

        try:
            self.root.after_cancel(
                self.dashboard_watch_job
            )
        except tk.TclError:
            pass

        self.dashboard_watch_job = None

    def close_dashboard(
        self,
    ) -> None:
        """Close the dashboard cleanly."""

        self.cancel_dashboard_file_watch()
        self.root.destroy()


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Launch the professional Option Intelligence dashboard.
    """

    root = tk.Tk()

    dashboard = ProfessionalOptionDashboard(
        root
    )

    root.update_idletasks()
    root.deiconify()

    try:
        root.state("zoomed")
    except tk.TclError:
        root.geometry(
            f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+20+20"
        )

    root.lift()
    root.attributes(
        "-topmost",
        True,
    )
    root.after(
        1200,
        lambda: root.attributes(
            "-topmost",
            False,
        ),
    )

    root.dashboard = dashboard

    print(
        "AQSD dashboard window opened successfully.",
        flush=True,
    )

    root.mainloop()


if __name__ == "__main__":
    main()
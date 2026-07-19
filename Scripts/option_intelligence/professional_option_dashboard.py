"""
AQSD
Professional Option Intelligence Dashboard

Module: professional_option_dashboard.py
Version: 1.0
Author: AQSD

Description:
Creates the visual Tab-2 dashboard for live BANKNIFTY Option Intelligence.

The dashboard:
- Runs the live Decision Intelligence pipeline
- Reads the latest Decision JSON output
- Displays important analytics on one screen
- Uses colour-coded decision and probability cards
- Provides a manual Refresh button
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

        self.build_interface()
        self.load_existing_output()

    # --------------------------------------------------------
    # GENERAL LAYOUT
    # --------------------------------------------------------

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
            text="REFRESH LIVE DATA",
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

    def update_dashboard(
        self,
        data: dict[str, Any],
    ) -> None:
        """
        Update every dashboard metric from JSON data.
        """

        final_decision = first_available(
            data,
            "final_decision",
            default="WAIT",
        )

        directional_bias = first_available(
            data,
            "decision_bias",
            "directional_bias",
            default="NEUTRAL",
        )

        confidence = first_available(
            data,
            "confidence_score",
        )

        grade = first_available(
            data,
            "trade_grade",
            default="N/A",
        )

        quality = first_available(
            data,
            "trade_quality",
            default="N/A",
        )

        market_regime = first_available(
            data,
            "market_regime",
            default="N/A",
        )

        risk_level = first_available(
            data,
            "risk_level",
            default="N/A",
        )

        bullish = first_available(
            data,
            "bullish_probability",
            "bullish",
        )

        bearish = first_available(
            data,
            "bearish_probability",
            "bearish",
        )

        continuation = first_available(
            data,
            "continuation_probability",
            "continuation",
        )

        reversal = first_available(
            data,
            "reversal_probability",
            "reversal",
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

        self.set_card(
            "spot_price",
            format_number(
                first_available(
                    data,
                    "spot_price",
                )
            ),
        )

        self.set_card(
            "atm_strike",
            format_number(
                first_available(
                    data,
                    "atm_strike",
                ),
                0,
            ),
        )

        self.set_card(
            "oi_pcr",
            format_ratio(
                first_available(
                    data,
                    "oi_pcr",
                )
            ),
        )

        self.set_card(
            "change_oi_pcr",
            format_ratio(
                first_available(
                    data,
                    "change_oi_pcr",
                )
            ),
        )

        self.set_card(
            "modified_pcr",
            format_ratio(
                first_available(
                    data,
                    "modified_pcr",
                )
            ),
        )

        pcr_trend = first_available(
            data,
            "pcr_trend",
            default="N/A",
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
                first_available(
                    data,
                    "max_pain_strike",
                ),
                0,
            ),
        )

        self.set_card(
            "pinning_probability",
            format_number(
                first_available(
                    data,
                    "pinning_probability",
                ),
                suffix="%",
            ),
        )

        self.set_card(
            "call_wall",
            format_number(
                first_available(
                    data,
                    "positional_call_wall",
                    "call_wall",
                ),
                0,
            ),
        )

        self.set_card(
            "put_wall",
            format_number(
                first_available(
                    data,
                    "positional_put_wall",
                    "put_wall",
                ),
                0,
            ),
        )

        entry_low = first_available(
            data,
            "entry_low",
        )

        entry_high = first_available(
            data,
            "entry_high",
        )

        self.set_card(
            "entry_zone",
            (
                f"{format_number(entry_low, 0)} - "
                f"{format_number(entry_high, 0)}"
            ),
        )

        self.set_card(
            "stop_loss",
            format_number(
                first_available(
                    data,
                    "stop_loss",
                ),
                0,
            ),
        )

        self.set_card(
            "target_one",
            format_number(
                first_available(
                    data,
                    "target_one",
                ),
                0,
            ),
        )

        self.set_card(
            "target_two",
            format_number(
                first_available(
                    data,
                    "target_two",
                ),
                0,
            ),
        )

        self.set_card(
            "risk_reward_one",
            (
                "1 : "
                + format_number(
                    first_available(
                        data,
                        "risk_reward_one",
                    ),
                )
            ),
        )

        self.set_card(
            "risk_reward_two",
            (
                "1 : "
                + format_number(
                    first_available(
                        data,
                        "risk_reward_two",
                    ),
                )
            ),
        )

        self.set_card(
            "atm_iv",
            format_number(
                first_available(
                    data,
                    "atm_iv",
                ),
                suffix="%",
            ),
        )

        self.set_card(
            "historical_volatility",
            format_number(
                first_available(
                    data,
                    "historical_volatility",
                ),
                suffix="%",
            ),
        )

        self.set_card(
            "iv_rank",
            format_number(
                first_available(
                    data,
                    "iv_rank",
                ),
                suffix="%",
            ),
        )

        self.set_card(
            "iv_percentile",
            format_number(
                first_available(
                    data,
                    "iv_percentile",
                ),
                suffix="%",
            ),
        )

        volatility_regime = first_available(
            data,
            "volatility_regime",
            default="N/A",
        )

        self.set_card(
            "volatility_regime",
            volatility_regime,
            signal_colour(
                volatility_regime
            ),
        )

        wall_shift = first_available(
            data,
            "combined_wall_shift",
            default="N/A",
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
            first_available(
                data,
                "breakout_watch",
                default="N/A",
            ),
        )

        self.set_card(
            "breakdown_watch",
            first_available(
                data,
                "breakdown_watch",
                default="N/A",
            ),
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

    # --------------------------------------------------------
    # LOAD EXISTING OUTPUT
    # --------------------------------------------------------

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

        except Exception as error:
            self.status_variable.set(
                f"No live result loaded: {error}"
            )

    # --------------------------------------------------------
    # RUN LIVE PIPELINE
    # --------------------------------------------------------

    def start_live_refresh(
        self,
    ) -> None:
        """
        Start FYERS refresh without freezing the window.
        """

        if self.refresh_running:
            return

        self.refresh_running = True

        self.refresh_button.configure(
            state="disabled",
            text="REFRESHING...",
        )

        self.status_variable.set(
            "Running live FYERS Decision Intelligence..."
        )

        worker = threading.Thread(
            target=self.run_live_pipeline,
            daemon=True,
        )

        worker.start()

    def run_live_pipeline(
        self,
    ) -> None:
        """
        Run the live Decision module in a background thread.
        """

        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    LIVE_DECISION_MODULE,
                ],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )

            if completed.returncode != 0:
                error_message = (
                    completed.stderr.strip()
                    or completed.stdout.strip()
                    or "Unknown pipeline error."
                )

                raise RuntimeError(
                    error_message
                )

            data = load_json_file(
                DECISION_JSON_FILE
            )

            self.root.after(
                0,
                lambda: self.finish_refresh_success(
                    data
                ),
            )

        except Exception as error:
            self.root.after(
                0,
                lambda: self.finish_refresh_error(
                    str(error)
                ),
            )

    def finish_refresh_success(
        self,
        data: dict[str, Any],
    ) -> None:
        """
        Complete a successful refresh.
        """

        self.update_dashboard(
            data
        )

        self.refresh_running = False

        self.refresh_button.configure(
            state="normal",
            text="REFRESH LIVE DATA",
        )

        self.status_variable.set(
            "Live Decision Intelligence refreshed successfully."
        )

    def finish_refresh_error(
        self,
        error_message: str,
    ) -> None:
        """
        Complete a failed refresh.
        """

        self.refresh_running = False

        self.refresh_button.configure(
            state="normal",
            text="REFRESH LIVE DATA",
        )

        self.status_variable.set(
            "Live refresh failed."
        )

        messagebox.showerror(
            "AQSD Live Refresh Failed",
            error_message,
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Launch the professional Option Intelligence dashboard.
    """

    root = tk.Tk()

    ProfessionalOptionDashboard(
        root
    )

    root.mainloop()


if __name__ == "__main__":
    main()
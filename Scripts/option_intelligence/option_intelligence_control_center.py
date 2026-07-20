"""
AQSD
OPTION INTELLIGENCE CONTROL CENTER

Module: option_intelligence_control_center.py
Version: 3.1
Author: AQSD

Features:
- Run complete Option Intelligence pipeline
- Start / stop Auto Refresh
- Refresh Now
- Select refresh interval
- Countdown timer
- Last refresh and next refresh time
- Open dashboard and individual modules
- Open FYERS token assistant
- Thread-safe execution
- Clean shutdown
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import tkinter as tk

from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Optional


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = BASE_DIR / "Scripts"
PACKAGE_DIR = SCRIPTS_DIR / "option_intelligence"
OUTPUT_DIR = BASE_DIR / "Output"

MASTER_MODULE = "Scripts.option_intelligence.live_option_intelligence_master"
TOKEN_MODULE = "Scripts.option_intelligence.fyers_token_assistant"

MODULES = {
    "Dashboard": "Scripts.option_intelligence.live_dashboard_runner",
    "Decision": "Scripts.option_intelligence.live_decision_runner",
    "IV Surface": "Scripts.option_intelligence.live_iv_surface_runner",
    "Volatility": "Scripts.option_intelligence.live_volatility_analytics_runner",
    "Probability": "Scripts.option_intelligence.live_probability_v2_runner",
}

INTERVAL_OPTIONS = {
    "30 sec": 30,
    "1 min": 60,
    "2 min": 120,
    "5 min": 300,
    "10 min": 600,
}


# ============================================================
# UI CONSTANTS
# ============================================================

WINDOW_TITLE = "AQSD — Option Intelligence Control Center v3.1"
WINDOW_SIZE = "1040x760"

COLOR_BG = "#0F172A"
COLOR_PANEL = "#172033"
COLOR_CARD = "#202B3D"
COLOR_BORDER = "#334155"

COLOR_TEXT = "#F8FAFC"
COLOR_MUTED = "#A7B1C2"

COLOR_BLUE = "#3B82F6"
COLOR_GREEN = "#22C55E"
COLOR_RED = "#EF4444"
COLOR_ORANGE = "#F59E0B"
COLOR_PURPLE = "#8B5CF6"
COLOR_CYAN = "#06B6D4"
COLOR_GREY_BUTTON = "#475569"


# ============================================================
# PROCESS HELPERS
# ============================================================

def current_python() -> str:
    """
    Return the currently active Python executable.

    When the BAT file activates .venv-fyers first, this automatically
    uses the FYERS virtual environment.
    """

    return sys.executable


def run_python_module(
    module_name: str,
    *,
    wait: bool = True,
) -> subprocess.CompletedProcess[str] | subprocess.Popen[str]:
    """
    Run a Python module from the AQSD project root.
    """

    command = [
        current_python(),
        "-m",
        module_name,
    ]

    if wait:
        # Open the pipeline in its own visible terminal window on Windows.
        # This makes every run easy to verify and preserves the complete
        # pipeline output while the Control Center remains responsive.
        creation_flags = 0

        if os.name == "nt":
            creation_flags = subprocess.CREATE_NEW_CONSOLE

        process = subprocess.Popen(
            command,
            cwd=BASE_DIR,
            text=True,
            creationflags=creation_flags,
        )

        return_code = process.wait()

        return subprocess.CompletedProcess(
            args=command,
            returncode=return_code,
            stdout="",
            stderr="",
        )

    # GUI utilities such as the FYERS Token Assistant are opened without
    # forcing an additional console window.
    return subprocess.Popen(
        command,
        cwd=BASE_DIR,
        text=True,
    )


def format_clock(
    value: Optional[datetime],
) -> str:
    """
    Format a datetime for the Control Center.
    """

    if value is None:
        return "--:--:--"

    return value.strftime("%H:%M:%S")


def format_countdown(
    seconds: int,
) -> str:
    """
    Convert seconds to HH:MM:SS or MM:SS.
    """

    seconds = max(
        0,
        int(seconds),
    )

    hours, remainder = divmod(
        seconds,
        3600,
    )

    minutes, seconds = divmod(
        remainder,
        60,
    )

    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return f"{minutes:02d}:{seconds:02d}"


# ============================================================
# CONTROL CENTER
# ============================================================

class OptionIntelligenceControlCenter:
    """
    AQSD Option Intelligence Control Center.
    """

    def __init__(
        self,
        root: tk.Tk,
    ) -> None:
        self.root = root

        self.pipeline_running = False
        self.auto_refresh_enabled = False
        self.closing = False

        self.refresh_interval_seconds = 60
        self.remaining_seconds = 0

        self.last_refresh_time: Optional[datetime] = None
        self.next_refresh_time: Optional[datetime] = None

        self.countdown_job: Optional[str] = None
        self.auto_cycle_pending = False

        self.status_var = tk.StringVar(
            value="STOPPED"
        )

        self.status_detail_var = tk.StringVar(
            value="Control Center ready."
        )

        self.auto_refresh_var = tk.StringVar(
            value="OFF"
        )

        self.interval_var = tk.StringVar(
            value="1 min"
        )

        self.last_refresh_var = tk.StringVar(
            value="--:--:--"
        )

        self.next_refresh_var = tk.StringVar(
            value="--:--:--"
        )

        self.countdown_var = tk.StringVar(
            value="--:--"
        )

        self.build_window()
        self.configure_styles()
        self.build_interface()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.on_close,
        )

        self.update_controls()

    # ========================================================
    # WINDOW
    # ========================================================

    def build_window(
        self,
    ) -> None:
        """
        Configure the main application window.
        """

        self.root.title(
            WINDOW_TITLE
        )

        self.root.geometry(
            WINDOW_SIZE
        )

        self.root.minsize(
            950,
            700,
        )

        self.root.configure(
            bg=COLOR_BG
        )

    def configure_styles(
        self,
    ) -> None:
        """
        Configure ttk styles.
        """

        style = ttk.Style(
            self.root
        )

        try:
            style.theme_use(
                "clam"
            )
        except tk.TclError:
            pass

        style.configure(
            "AQSD.TCombobox",
            fieldbackground=COLOR_CARD,
            background=COLOR_CARD,
            foreground=COLOR_TEXT,
            arrowcolor=COLOR_TEXT,
            bordercolor=COLOR_BORDER,
            lightcolor=COLOR_BORDER,
            darkcolor=COLOR_BORDER,
            padding=7,
        )

        style.map(
            "AQSD.TCombobox",
            fieldbackground=[
                ("readonly", COLOR_CARD),
            ],
            foreground=[
                ("readonly", COLOR_TEXT),
            ],
            selectbackground=[
                ("readonly", COLOR_CARD),
            ],
            selectforeground=[
                ("readonly", COLOR_TEXT),
            ],
        )

    # ========================================================
    # UI BUILDING
    # ========================================================

    def build_interface(
        self,
    ) -> None:
        """
        Build the full Control Center.
        """

        main = tk.Frame(
            self.root,
            bg=COLOR_BG,
        )

        main.pack(
            fill="both",
            expand=True,
            padx=22,
            pady=20,
        )

        self.build_header(
            main
        )

        content = tk.Frame(
            main,
            bg=COLOR_BG,
        )

        content.pack(
            fill="both",
            expand=True,
            pady=(
                16,
                0,
            ),
        )

        left = tk.Frame(
            content,
            bg=COLOR_BG,
        )

        left.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(
                0,
                10,
            ),
        )

        right = tk.Frame(
            content,
            bg=COLOR_BG,
            width=360,
        )

        right.pack(
            side="right",
            fill="y",
            padx=(
                10,
                0,
            ),
        )

        right.pack_propagate(
            False
        )

        self.build_pipeline_panel(
            left
        )

        self.build_module_panel(
            left
        )

        self.build_auto_refresh_panel(
            right
        )

        self.build_status_panel(
            right
        )

    def build_header(
        self,
        parent: tk.Widget,
    ) -> None:
        """
        Build title header.
        """

        panel = tk.Frame(
            parent,
            bg=COLOR_PANEL,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
        )

        panel.pack(
            fill="x",
        )

        title = tk.Label(
            panel,
            text="AQSD OPTION INTELLIGENCE",
            bg=COLOR_PANEL,
            fg=COLOR_TEXT,
            font=(
                "Segoe UI",
                22,
                "bold",
            ),
            anchor="w",
        )

        title.pack(
            fill="x",
            padx=22,
            pady=(
                18,
                3,
            ),
        )

        subtitle = tk.Label(
            panel,
            text=(
                "CONTROL CENTER v3  |  LIVE PIPELINE  |  "
                "AUTO REFRESH  |  FYERS"
            ),
            bg=COLOR_PANEL,
            fg=COLOR_MUTED,
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
            anchor="w",
        )

        subtitle.pack(
            fill="x",
            padx=22,
            pady=(
                0,
                17,
            ),
        )

    def create_button(
        self,
        parent: tk.Widget,
        *,
        text: str,
        command,
        background: str,
        width: int = 24,
    ) -> tk.Button:
        """
        Create a consistently styled button.
        """

        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=background,
            fg="#FFFFFF",
            activebackground=background,
            activeforeground="#FFFFFF",
            disabledforeground="#CBD5E1",
            relief="flat",
            cursor="hand2",
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
            width=width,
            padx=12,
            pady=10,
        )

        return button

    def build_pipeline_panel(
        self,
        parent: tk.Widget,
    ) -> None:
        """
        Build complete-pipeline controls.
        """

        panel = tk.Frame(
            parent,
            bg=COLOR_PANEL,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
        )

        panel.pack(
            fill="x",
            pady=(
                0,
                14,
            ),
        )

        heading = tk.Label(
            panel,
            text="MASTER PIPELINE",
            bg=COLOR_PANEL,
            fg=COLOR_TEXT,
            font=(
                "Segoe UI",
                13,
                "bold",
            ),
            anchor="w",
        )

        heading.pack(
            fill="x",
            padx=18,
            pady=(
                17,
                10,
            ),
        )

        description = tk.Label(
            panel,
            text=(
                "Runs Decision, IV Surface, Volatility, Probability "
                "and Dashboard in the correct order."
            ),
            bg=COLOR_PANEL,
            fg=COLOR_MUTED,
            font=(
                "Segoe UI",
                10,
            ),
            justify="left",
            anchor="w",
            wraplength=560,
        )

        description.pack(
            fill="x",
            padx=18,
            pady=(
                0,
                14,
            ),
        )

        button_row = tk.Frame(
            panel,
            bg=COLOR_PANEL,
        )

        button_row.pack(
            fill="x",
            padx=18,
            pady=(
                0,
                18,
            ),
        )

        self.run_pipeline_button = self.create_button(
            button_row,
            text="RUN COMPLETE PIPELINE",
            command=lambda: self.start_pipeline(
                source="manual"
            ),
            background=COLOR_BLUE,
            width=25,
        )

        self.run_pipeline_button.pack(
            side="left",
        )

        self.token_button = self.create_button(
            button_row,
            text="FYERS LOGIN / TOKEN",
            command=self.open_token_assistant,
            background=COLOR_PURPLE,
            width=22,
        )

        self.token_button.pack(
            side="left",
            padx=(
                10,
                0,
            ),
        )

    def build_module_panel(
        self,
        parent: tk.Widget,
    ) -> None:
        """
        Build individual module buttons.
        """

        panel = tk.Frame(
            parent,
            bg=COLOR_PANEL,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
        )

        panel.pack(
            fill="both",
            expand=True,
        )

        heading = tk.Label(
            panel,
            text="INDIVIDUAL MODULES",
            bg=COLOR_PANEL,
            fg=COLOR_TEXT,
            font=(
                "Segoe UI",
                13,
                "bold",
            ),
            anchor="w",
        )

        heading.pack(
            fill="x",
            padx=18,
            pady=(
                17,
                12,
            ),
        )

        grid = tk.Frame(
            panel,
            bg=COLOR_PANEL,
        )

        grid.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=(
                0,
                18,
            ),
        )

        for column in range(
            2
        ):
            grid.grid_columnconfigure(
                column,
                weight=1,
                uniform="module_columns",
            )

        module_colors = {
            "Dashboard": COLOR_CYAN,
            "Decision": COLOR_ORANGE,
            "IV Surface": COLOR_PURPLE,
            "Volatility": COLOR_GREEN,
            "Probability": COLOR_BLUE,
        }

        for index, (
            label,
            module_name,
        ) in enumerate(
            MODULES.items()
        ):
            row = index // 2
            column = index % 2

            button = self.create_button(
                grid,
                text=label.upper(),
                command=lambda selected=module_name, name=label: (
                    self.start_individual_module(
                        selected,
                        name,
                    )
                ),
                background=module_colors[label],
                width=22,
            )

            button.grid(
                row=row,
                column=column,
                sticky="ew",
                padx=(
                    0 if column == 0 else 6,
                    6 if column == 0 else 0,
                ),
                pady=6,
            )

    def build_auto_refresh_panel(
        self,
        parent: tk.Widget,
    ) -> None:
        """
        Build the auto-refresh scheduler panel.
        """

        panel = tk.Frame(
            parent,
            bg=COLOR_PANEL,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
        )

        panel.pack(
            fill="x",
            pady=(
                0,
                14,
            ),
        )

        heading_row = tk.Frame(
            panel,
            bg=COLOR_PANEL,
        )

        heading_row.pack(
            fill="x",
            padx=18,
            pady=(
                17,
                13,
            ),
        )

        heading = tk.Label(
            heading_row,
            text="AUTO REFRESH",
            bg=COLOR_PANEL,
            fg=COLOR_TEXT,
            font=(
                "Segoe UI",
                13,
                "bold",
            ),
            anchor="w",
        )

        heading.pack(
            side="left",
        )

        self.auto_indicator = tk.Label(
            heading_row,
            textvariable=self.auto_refresh_var,
            bg=COLOR_RED,
            fg="#FFFFFF",
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
            padx=13,
            pady=5,
        )

        self.auto_indicator.pack(
            side="right",
        )

        interval_row = tk.Frame(
            panel,
            bg=COLOR_PANEL,
        )

        interval_row.pack(
            fill="x",
            padx=18,
            pady=(
                0,
                13,
            ),
        )

        interval_label = tk.Label(
            interval_row,
            text="Refresh interval",
            bg=COLOR_PANEL,
            fg=COLOR_MUTED,
            font=(
                "Segoe UI",
                10,
            ),
            anchor="w",
        )

        interval_label.pack(
            side="left",
        )

        self.interval_combo = ttk.Combobox(
            interval_row,
            textvariable=self.interval_var,
            values=list(
                INTERVAL_OPTIONS.keys()
            ),
            state="readonly",
            width=11,
            style="AQSD.TCombobox",
        )

        self.interval_combo.pack(
            side="right",
        )

        self.interval_combo.bind(
            "<<ComboboxSelected>>",
            self.on_interval_changed,
        )

        controls = tk.Frame(
            panel,
            bg=COLOR_PANEL,
        )

        controls.pack(
            fill="x",
            padx=18,
            pady=(
                0,
                14,
            ),
        )

        self.start_auto_button = self.create_button(
            controls,
            text="START",
            command=self.start_auto_refresh,
            background=COLOR_GREEN,
            width=9,
        )

        self.start_auto_button.pack(
            side="left",
        )

        self.stop_auto_button = self.create_button(
            controls,
            text="STOP",
            command=self.stop_auto_refresh,
            background=COLOR_RED,
            width=9,
        )

        self.stop_auto_button.pack(
            side="left",
            padx=8,
        )

        self.refresh_now_button = self.create_button(
            controls,
            text="REFRESH NOW",
            command=lambda: self.start_pipeline(
                source="refresh_now"
            ),
            background=COLOR_BLUE,
            width=13,
        )

        self.refresh_now_button.pack(
            side="left",
        )

        information = tk.Frame(
            panel,
            bg=COLOR_CARD,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
        )

        information.pack(
            fill="x",
            padx=18,
            pady=(
                0,
                18,
            ),
        )

        self.add_info_row(
            information,
            "Last refresh",
            self.last_refresh_var,
            first=True,
        )

        self.add_info_row(
            information,
            "Next refresh",
            self.next_refresh_var,
        )

        self.add_info_row(
            information,
            "Countdown",
            self.countdown_var,
            last=True,
        )

    def add_info_row(
        self,
        parent: tk.Widget,
        title: str,
        variable: tk.StringVar,
        *,
        first: bool = False,
        last: bool = False,
    ) -> None:
        """
        Add one scheduler-information row.
        """

        row = tk.Frame(
            parent,
            bg=COLOR_CARD,
        )

        row.pack(
            fill="x",
            padx=13,
            pady=(
                11 if first else 5,
                11 if last else 5,
            ),
        )

        label = tk.Label(
            row,
            text=title,
            bg=COLOR_CARD,
            fg=COLOR_MUTED,
            font=(
                "Segoe UI",
                10,
            ),
            anchor="w",
        )

        label.pack(
            side="left",
        )

        value = tk.Label(
            row,
            textvariable=variable,
            bg=COLOR_CARD,
            fg=COLOR_TEXT,
            font=(
                "Consolas",
                11,
                "bold",
            ),
            anchor="e",
        )

        value.pack(
            side="right",
        )

    def build_status_panel(
        self,
        parent: tk.Widget,
    ) -> None:
        """
        Build live status panel.
        """

        panel = tk.Frame(
            parent,
            bg=COLOR_PANEL,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
        )

        panel.pack(
            fill="both",
            expand=True,
        )

        heading = tk.Label(
            panel,
            text="SYSTEM STATUS",
            bg=COLOR_PANEL,
            fg=COLOR_TEXT,
            font=(
                "Segoe UI",
                13,
                "bold",
            ),
            anchor="w",
        )

        heading.pack(
            fill="x",
            padx=18,
            pady=(
                17,
                12,
            ),
        )

        self.status_indicator = tk.Label(
            panel,
            textvariable=self.status_var,
            bg=COLOR_GREY_BUTTON,
            fg="#FFFFFF",
            font=(
                "Segoe UI",
                14,
                "bold",
            ),
            pady=12,
        )

        self.status_indicator.pack(
            fill="x",
            padx=18,
            pady=(
                0,
                13,
            ),
        )

        detail = tk.Label(
            panel,
            textvariable=self.status_detail_var,
            bg=COLOR_CARD,
            fg=COLOR_MUTED,
            font=(
                "Segoe UI",
                10,
            ),
            justify="left",
            anchor="nw",
            wraplength=300,
            padx=12,
            pady=12,
        )

        detail.pack(
            fill="both",
            expand=True,
            padx=18,
            pady=(
                0,
                13,
            ),
        )

        exit_button = self.create_button(
            panel,
            text="EXIT CONTROL CENTER",
            command=self.on_close,
            background=COLOR_RED,
            width=26,
        )

        exit_button.pack(
            fill="x",
            padx=18,
            pady=(
                0,
                18,
            ),
        )

    # ========================================================
    # STATUS
    # ========================================================

    def set_status(
        self,
        state: str,
        detail: str,
        color: str,
    ) -> None:
        """
        Update the visible system status.
        """

        self.status_var.set(
            state
        )

        self.status_detail_var.set(
            detail
        )

        self.status_indicator.configure(
            bg=color
        )

    def update_controls(
        self,
    ) -> None:
        """
        Enable or disable buttons based on current state.
        """

        if self.pipeline_running:
            self.run_pipeline_button.configure(
                state="disabled"
            )

            self.refresh_now_button.configure(
                state="disabled"
            )

            self.start_auto_button.configure(
                state="disabled"
            )

        else:
            self.run_pipeline_button.configure(
                state="normal"
            )

            self.refresh_now_button.configure(
                state="normal"
            )

            self.start_auto_button.configure(
                state=(
                    "disabled"
                    if self.auto_refresh_enabled
                    else "normal"
                )
            )

        self.stop_auto_button.configure(
            state=(
                "normal"
                if self.auto_refresh_enabled
                else "disabled"
            )
        )

    # ========================================================
    # PIPELINE
    # ========================================================

    def start_pipeline(
        self,
        *,
        source: str,
    ) -> None:
        """
        Start the master pipeline in a worker thread.
        """

        if self.pipeline_running:
            self.set_status(
                "BUSY",
                "A pipeline run is already in progress.",
                COLOR_ORANGE,
            )
            return

        self.pipeline_running = True
        self.auto_cycle_pending = (
            source == "auto"
        )

        self.set_status(
            "RUNNING PIPELINE",
            "Pipeline started in a separate terminal window. Follow its live output there.",
            COLOR_ORANGE,
        )

        self.update_controls()

        worker = threading.Thread(
            target=self.pipeline_worker,
            args=(source,),
            daemon=True,
        )

        worker.start()

    def pipeline_worker(
        self,
        source: str,
    ) -> None:
        """
        Execute the master pipeline.
        """

        try:
            result = run_python_module(
                MASTER_MODULE,
                wait=True,
            )

            success = (
                result.returncode == 0
            )

            stdout = (
                result.stdout or ""
            ).strip()

            stderr = (
                result.stderr or ""
            ).strip()

        except Exception as error:
            success = False
            stdout = ""
            stderr = str(error)

        self.root.after(
            0,
            lambda: self.finish_pipeline(
                source=source,
                success=success,
                stdout=stdout,
                stderr=stderr,
            ),
        )

    def finish_pipeline(
        self,
        *,
        source: str,
        success: bool,
        stdout: str,
        stderr: str,
    ) -> None:
        """
        Finish one pipeline run and schedule the next refresh.
        """

        if self.closing:
            return

        self.pipeline_running = False

        if success:
            self.last_refresh_time = (
                datetime.now()
            )

            self.last_refresh_var.set(
                format_clock(
                    self.last_refresh_time
                )
            )

            self.set_status(
                "SUCCESS",
                (
                    "Option Intelligence pipeline completed successfully.\n"
                    f"Source: {source.replace('_', ' ').title()}"
                ),
                COLOR_GREEN,
            )

        else:
            error_text = (
                stderr
                or stdout
                or "Unknown pipeline error."
            )

            if len(error_text) > 900:
                error_text = (
                    error_text[-900:]
                )

            self.set_status(
                "FAILED",
                error_text,
                COLOR_RED,
            )

            if source != "auto":
                messagebox.showerror(
                    "AQSD Pipeline Error",
                    error_text,
                )

        if self.auto_refresh_enabled:
            self.schedule_next_refresh()
        else:
            self.next_refresh_time = None
            self.next_refresh_var.set(
                "--:--:--"
            )
            self.countdown_var.set(
                "--:--"
            )

        self.auto_cycle_pending = False
        self.update_controls()

    # ========================================================
    # INDIVIDUAL MODULES
    # ========================================================

    def start_individual_module(
        self,
        module_name: str,
        display_name: str,
    ) -> None:
        """
        Run an individual module without blocking the GUI.
        """

        worker = threading.Thread(
            target=self.individual_module_worker,
            args=(
                module_name,
                display_name,
            ),
            daemon=True,
        )

        worker.start()

        self.set_status(
            f"OPENING {display_name.upper()}",
            f"Starting {display_name}.",
            COLOR_CYAN,
        )

    def individual_module_worker(
        self,
        module_name: str,
        display_name: str,
    ) -> None:
        """
        Launch an individual module.
        """

        try:
            result = run_python_module(
                module_name,
                wait=True,
            )

            success = (
                result.returncode == 0
            )

            error_text = (
                result.stderr
                or result.stdout
                or ""
            ).strip()

        except Exception as error:
            success = False
            error_text = str(error)

        self.root.after(
            0,
            lambda: self.finish_individual_module(
                display_name,
                success,
                error_text,
            ),
        )

    def finish_individual_module(
        self,
        display_name: str,
        success: bool,
        error_text: str,
    ) -> None:
        """
        Update status after an individual module.
        """

        if self.closing:
            return

        if success:
            self.set_status(
                "READY",
                f"{display_name} completed successfully.",
                COLOR_BLUE,
            )
            return

        if len(error_text) > 700:
            error_text = error_text[-700:]

        self.set_status(
            "MODULE FAILED",
            error_text or f"{display_name} failed.",
            COLOR_RED,
        )

        messagebox.showerror(
            f"AQSD {display_name}",
            error_text or f"{display_name} failed.",
        )

    # ========================================================
    # TOKEN ASSISTANT
    # ========================================================

    def open_token_assistant(
        self,
    ) -> None:
        """
        Open the FYERS token assistant.
        """

        try:
            run_python_module(
                TOKEN_MODULE,
                wait=False,
            )

        except Exception as error:
            self.set_status(
                "TOKEN ASSISTANT ERROR",
                str(error),
                COLOR_RED,
            )

            messagebox.showerror(
                "AQSD FYERS Login",
                str(error),
            )
            return

        self.set_status(
            "FYERS LOGIN OPENED",
            (
                "Complete FYERS login and 2FA, then generate "
                "and save the new access token."
            ),
            COLOR_PURPLE,
        )

    # ========================================================
    # AUTO REFRESH
    # ========================================================

    def start_auto_refresh(
        self,
    ) -> None:
        """
        Enable Auto Refresh and start an immediate pipeline run.
        """

        if self.auto_refresh_enabled:
            return

        self.refresh_interval_seconds = (
            INTERVAL_OPTIONS[
                self.interval_var.get()
            ]
        )

        self.auto_refresh_enabled = True
        self.auto_refresh_var.set(
            "ON"
        )

        self.auto_indicator.configure(
            bg=COLOR_GREEN
        )

        self.cancel_countdown_job()

        self.set_status(
            "AUTO REFRESH ON",
            (
                "Auto Refresh started. The first pipeline run will begin now in a separate terminal window."
            ),
            COLOR_GREEN,
        )

        self.update_controls()

        if not self.pipeline_running:
            self.start_pipeline(
                source="auto"
            )
        else:
            self.schedule_next_refresh()

    def stop_auto_refresh(
        self,
    ) -> None:
        """
        Disable Auto Refresh immediately.
        """

        self.auto_refresh_enabled = False
        self.auto_refresh_var.set(
            "OFF"
        )

        self.auto_indicator.configure(
            bg=COLOR_RED
        )

        self.next_refresh_time = None
        self.remaining_seconds = 0

        self.next_refresh_var.set(
            "--:--:--"
        )

        self.countdown_var.set(
            "--:--"
        )

        self.cancel_countdown_job()

        if self.pipeline_running:
            detail = (
                "Auto Refresh stopped. "
                "The current pipeline run will finish normally."
            )
        else:
            detail = (
                "Auto Refresh stopped."
            )

        self.set_status(
            "AUTO REFRESH OFF",
            detail,
            COLOR_RED,
        )

        self.update_controls()

    def schedule_next_refresh(
        self,
    ) -> None:
        """
        Schedule the countdown to the next pipeline run.
        """

        if (
            not self.auto_refresh_enabled
            or self.closing
        ):
            return

        self.refresh_interval_seconds = (
            INTERVAL_OPTIONS[
                self.interval_var.get()
            ]
        )

        self.remaining_seconds = (
            self.refresh_interval_seconds
        )

        self.next_refresh_time = (
            datetime.now()
            + timedelta(
                seconds=self.remaining_seconds
            )
        )

        self.next_refresh_var.set(
            format_clock(
                self.next_refresh_time
            )
        )

        self.countdown_var.set(
            format_countdown(
                self.remaining_seconds
            )
        )

        self.cancel_countdown_job()

        self.countdown_job = (
            self.root.after(
                1000,
                self.countdown_tick,
            )
        )

        if not self.pipeline_running:
            self.set_status(
                "AUTO REFRESH RUNNING",
                (
                    "Waiting for the next scheduled refresh.\n"
                    f"Interval: {self.interval_var.get()}"
                ),
                COLOR_GREEN,
            )

    def countdown_tick(
        self,
    ) -> None:
        """
        Update the countdown once every second.
        """

        self.countdown_job = None

        if (
            not self.auto_refresh_enabled
            or self.closing
        ):
            return

        if self.pipeline_running:
            self.countdown_var.set(
                "RUNNING"
            )

            self.countdown_job = (
                self.root.after(
                    1000,
                    self.countdown_tick,
                )
            )
            return

        self.remaining_seconds -= 1

        if self.remaining_seconds <= 0:
            self.countdown_var.set(
                "00:00"
            )

            self.next_refresh_var.set(
                format_clock(
                    datetime.now()
                )
            )

            self.start_pipeline(
                source="auto"
            )
            return

        self.countdown_var.set(
            format_countdown(
                self.remaining_seconds
            )
        )

        self.countdown_job = (
            self.root.after(
                1000,
                self.countdown_tick,
            )
        )

    def on_interval_changed(
        self,
        _event=None,
    ) -> None:
        """
        Apply a new refresh interval.
        """

        selected = (
            self.interval_var.get()
        )

        self.refresh_interval_seconds = (
            INTERVAL_OPTIONS[selected]
        )

        if self.auto_refresh_enabled:
            self.schedule_next_refresh()

            self.set_status(
                "INTERVAL UPDATED",
                (
                    f"Auto Refresh interval changed to {selected}. "
                    "The countdown has restarted."
                ),
                COLOR_CYAN,
            )

    def cancel_countdown_job(
        self,
    ) -> None:
        """
        Cancel the active Tkinter countdown callback.
        """

        if self.countdown_job is None:
            return

        try:
            self.root.after_cancel(
                self.countdown_job
            )
        except tk.TclError:
            pass

        self.countdown_job = None

    # ========================================================
    # SHUTDOWN
    # ========================================================

    def on_close(
        self,
    ) -> None:
        """
        Close the application cleanly.
        """

        if self.pipeline_running:
            confirmed = messagebox.askyesno(
                "Exit AQSD Control Center",
                (
                    "A pipeline run is still active.\n\n"
                    "Close the Control Center anyway?"
                ),
            )

            if not confirmed:
                return

        self.closing = True
        self.auto_refresh_enabled = False

        self.cancel_countdown_job()

        self.root.destroy()


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Launch AQSD Option Intelligence Control Center v3.
    """

    root = tk.Tk()

    OptionIntelligenceControlCenter(
        root
    )

    root.mainloop()


if __name__ == "__main__":
    main()

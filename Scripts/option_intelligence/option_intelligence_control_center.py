"""
AQSD
OPTION INTELLIGENCE CONTROL CENTER

Module: option_intelligence_control_center.py
Version: 2.0
Author: AQSD

Description:
Desktop control center for launching the AQSD BANKNIFTY
Option Intelligence modules.

Features:
- Run complete pipeline
- Open professional dashboard
- Run individual live analytics modules
- Auto refresh with selectable interval
- Countdown to next refresh
- Last update timestamp
- Thread-safe background execution
- Status and error messages

Analytics only. No order placement.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import tkinter as tk

from dataclasses import dataclass
from datetime import datetime
from tkinter import messagebox
from typing import Final


# ============================================================
# DISPLAY CONFIGURATION
# ============================================================

WINDOW_TITLE: Final = "AQSD — Option Intelligence Control Center"
WINDOW_WIDTH: Final = 980
WINDOW_HEIGHT: Final = 760

BACKGROUND: Final = "#111827"
PANEL_BACKGROUND: Final = "#182230"
CARD_BACKGROUND: Final = "#243041"
BORDER_COLOR: Final = "#3B4A5F"

TEXT_PRIMARY: Final = "#F8FAFC"
TEXT_SECONDARY: Final = "#AAB7C8"

ACCENT_BLUE: Final = "#6EA8FE"
ACCENT_GREEN: Final = "#4ADE80"
ACCENT_RED: Final = "#FB7185"
ACCENT_ORANGE: Final = "#FDBA74"
ACCENT_YELLOW: Final = "#FACC15"

AUTO_REFRESH_INTERVALS: Final = (
    "1 minute",
    "2 minutes",
    "5 minutes",
    "10 minutes",
    "15 minutes",
)

AUTO_REFRESH_MINUTES: Final = {
    "1 minute": 1,
    "2 minutes": 2,
    "5 minutes": 5,
    "10 minutes": 10,
    "15 minutes": 15,
}


# ============================================================
# MODULE CONFIGURATION
# ============================================================

@dataclass(frozen=True)
class ModuleAction:
    """One AQSD module launcher."""

    title: str
    module: str
    description: str
    opens_window: bool = False


MODULE_ACTIONS: Final = (
    ModuleAction(
        title="RUN COMPLETE PIPELINE",
        module=(
            "Scripts.option_intelligence."
            "live_option_intelligence_master"
        ),
        description=(
            "Run Decision, IV Surface, Volatility Analytics, "
            "Probability V2 and open the Professional Dashboard."
        ),
    ),
    ModuleAction(
        title="PROFESSIONAL DASHBOARD",
        module=(
            "Scripts.option_intelligence."
            "professional_option_dashboard_live"
        ),
        description=(
            "Open the latest professional BANKNIFTY dashboard."
        ),
        opens_window=True,
    ),
    ModuleAction(
        title="LIVE DECISION ENGINE",
        module=(
            "Scripts.option_intelligence."
            "live_decision_runner"
        ),
        description=(
            "Run the complete live BANKNIFTY decision workflow."
        ),
    ),
    ModuleAction(
        title="LIVE IV SURFACE",
        module=(
            "Scripts.option_intelligence."
            "live_iv_surface_runner"
        ),
        description=(
            "Fetch the live option chain and calculate the IV surface."
        ),
    ),
    ModuleAction(
        title="VOLATILITY ANALYTICS",
        module=(
            "Scripts.option_intelligence."
            "live_volatility_analytics_runner"
        ),
        description=(
            "Calculate IV Rank, IV Percentile, HV and IV-HV premium."
        ),
    ),
    ModuleAction(
        title="PROBABILITY ENGINE V2",
        module=(
            "Scripts.option_intelligence."
            "live_probability_v2_runner"
        ),
        description=(
            "Generate normalized live scenario probabilities."
        ),
    ),
)


# ============================================================
# CONTROL CENTER
# ============================================================

class OptionIntelligenceControlCenter:
    """AQSD desktop module launcher."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root

        self.running = False
        self.current_action_title = ""

        self.auto_refresh_active = False
        self.auto_refresh_job: str | None = None
        self.countdown_job: str | None = None
        self.seconds_until_refresh = 0

        self.status_variable = tk.StringVar(value="System ready.")
        self.last_update_variable = tk.StringVar(value="Last update: N/A")
        self.countdown_variable = tk.StringVar(value="Next refresh: OFF")
        self.interval_variable = tk.StringVar(value="5 minutes")

        self.build_window()
        self.build_interface()

        self.root.protocol("WM_DELETE_WINDOW", self.close_application)

    def build_window(self) -> None:
        """Configure the main window."""

        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
        self.root.configure(bg=BACKGROUND)

    def build_interface(self) -> None:
        """Build the control-center interface."""

        main_frame = tk.Frame(self.root, bg=BACKGROUND)
        main_frame.pack(fill="both", expand=True, padx=24, pady=20)

        self.build_header(main_frame)
        self.build_module_grid(main_frame)
        self.build_auto_refresh_panel(main_frame)
        self.build_status_panel(main_frame)

    def build_header(self, parent: tk.Widget) -> None:
        """Build title, subtitle and update timestamp."""

        header = tk.Frame(
            parent,
            bg=PANEL_BACKGROUND,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )
        header.pack(fill="x", pady=(0, 18))

        title_frame = tk.Frame(header, bg=PANEL_BACKGROUND)
        title_frame.pack(fill="x", padx=22, pady=(18, 6))

        title = tk.Label(
            title_frame,
            text="AQSD OPTION INTELLIGENCE CONTROL CENTER",
            bg=PANEL_BACKGROUND,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 21, "bold"),
            anchor="w",
        )
        title.pack(side="left", fill="x", expand=True)

        last_update = tk.Label(
            title_frame,
            textvariable=self.last_update_variable,
            bg=PANEL_BACKGROUND,
            fg=TEXT_SECONDARY,
            font=("Segoe UI", 9, "bold"),
            anchor="e",
        )
        last_update.pack(side="right")

        subtitle = tk.Label(
            header,
            text="LIVE BANKNIFTY ANALYTICS | NO ORDER PLACEMENT",
            bg=PANEL_BACKGROUND,
            fg=TEXT_SECONDARY,
            font=("Segoe UI", 10, "bold"),
            anchor="w",
        )
        subtitle.pack(fill="x", padx=22, pady=(0, 18))

    def build_module_grid(self, parent: tk.Widget) -> None:
        """Build launcher buttons."""

        grid_frame = tk.Frame(parent, bg=BACKGROUND)
        grid_frame.pack(fill="both", expand=True)
        grid_frame.grid_columnconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(1, weight=1)

        for index, action in enumerate(MODULE_ACTIONS):
            row = index // 2
            column = index % 2
            self.build_action_card(grid_frame, action, row, column)

    def build_action_card(
        self,
        parent: tk.Widget,
        action: ModuleAction,
        row: int,
        column: int,
    ) -> None:
        """Build one module launcher card."""

        card = tk.Frame(
            parent,
            bg=CARD_BACKGROUND,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )
        card.grid(row=row, column=column, sticky="nsew", padx=8, pady=8)
        parent.grid_rowconfigure(row, weight=1)

        title = tk.Label(
            card,
            text=action.title,
            bg=CARD_BACKGROUND,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 12, "bold"),
            anchor="w",
        )
        title.pack(fill="x", padx=18, pady=(16, 6))

        description = tk.Label(
            card,
            text=action.description,
            bg=CARD_BACKGROUND,
            fg=TEXT_SECONDARY,
            font=("Segoe UI", 9),
            justify="left",
            anchor="w",
            wraplength=370,
        )
        description.pack(fill="x", padx=18, pady=(0, 13))

        button_text = "OPEN" if action.opens_window else "RUN"

        button = tk.Button(
            card,
            text=button_text,
            command=lambda selected=action: self.start_action(selected),
            bg=ACCENT_BLUE,
            fg="#FFFFFF",
            activebackground="#4F8DE8",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            padx=18,
            pady=8,
        )
        button.pack(anchor="w", padx=18, pady=(0, 17))

    def build_auto_refresh_panel(self, parent: tk.Widget) -> None:
        """Build auto-refresh controls."""

        panel = tk.Frame(
            parent,
            bg=PANEL_BACKGROUND,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )
        panel.pack(fill="x", pady=(18, 0))

        title = tk.Label(
            panel,
            text="AUTO REFRESH",
            bg=PANEL_BACKGROUND,
            fg=TEXT_PRIMARY,
            font=("Segoe UI", 11, "bold"),
        )
        title.pack(side="left", padx=18, pady=15)

        interval_label = tk.Label(
            panel,
            text="Interval:",
            bg=PANEL_BACKGROUND,
            fg=TEXT_SECONDARY,
            font=("Segoe UI", 9, "bold"),
        )
        interval_label.pack(side="left", padx=(10, 6))

        interval_menu = tk.OptionMenu(
            panel,
            self.interval_variable,
            *AUTO_REFRESH_INTERVALS,
        )
        interval_menu.configure(
            bg=CARD_BACKGROUND,
            fg=TEXT_PRIMARY,
            activebackground=ACCENT_BLUE,
            activeforeground="#FFFFFF",
            highlightthickness=0,
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        interval_menu["menu"].configure(
            bg=CARD_BACKGROUND,
            fg=TEXT_PRIMARY,
            activebackground=ACCENT_BLUE,
            activeforeground="#FFFFFF",
            font=("Segoe UI", 9),
        )
        interval_menu.pack(side="left", padx=(0, 14))

        self.auto_refresh_button = tk.Button(
            panel,
            text="AUTO REFRESH: OFF",
            command=self.toggle_auto_refresh,
            bg=ACCENT_ORANGE,
            fg="#111827",
            activebackground="#F59E0B",
            activeforeground="#111827",
            relief="flat",
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            padx=18,
            pady=8,
        )
        self.auto_refresh_button.pack(side="left", padx=(0, 16), pady=10)

        countdown_label = tk.Label(
            panel,
            textvariable=self.countdown_variable,
            bg=PANEL_BACKGROUND,
            fg=ACCENT_YELLOW,
            font=("Consolas", 10, "bold"),
            anchor="e",
        )
        countdown_label.pack(side="right", padx=18, pady=15)

    def build_status_panel(self, parent: tk.Widget) -> None:
        """Build status and exit controls."""

        status_frame = tk.Frame(
            parent,
            bg=PANEL_BACKGROUND,
            highlightthickness=1,
            highlightbackground=BORDER_COLOR,
        )
        status_frame.pack(fill="x", pady=(12, 0))

        status_label = tk.Label(
            status_frame,
            textvariable=self.status_variable,
            bg=PANEL_BACKGROUND,
            fg=ACCENT_GREEN,
            font=("Consolas", 10, "bold"),
            anchor="w",
        )
        status_label.pack(side="left", fill="x", expand=True, padx=18, pady=16)

        exit_button = tk.Button(
            status_frame,
            text="EXIT",
            command=self.close_application,
            bg=ACCENT_RED,
            fg="#FFFFFF",
            activebackground="#E85A70",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            font=("Segoe UI", 10, "bold"),
            padx=20,
            pady=8,
        )
        exit_button.pack(side="right", padx=18, pady=10)

    def start_action(self, action: ModuleAction) -> None:
        """Start a module without freezing the interface."""

        if self.running and not action.opens_window:
            messagebox.showwarning(
                "AQSD",
                "Another analytics module is already running.",
            )
            return

        if action.opens_window:
            self.open_window_module(action)
            return

        self.running = True
        self.current_action_title = action.title
        self.status_variable.set(f"Running: {action.title}...")

        worker = threading.Thread(
            target=self.run_module,
            args=(action,),
            daemon=True,
        )
        worker.start()

    def open_window_module(self, action: ModuleAction) -> None:
        """Open a graphical module independently."""

        try:
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    action.module,
                ]
            )
        except Exception as error:
            self.status_variable.set(f"Failed: {error}")
            messagebox.showerror("AQSD Module Error", str(error))
            return

        self.status_variable.set(f"Opened: {action.title}")

    def run_module(self, action: ModuleAction) -> None:
        """Execute a command-line module."""

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    action.module,
                ],
                check=False,
            )
        except Exception as error:
            self.root.after(
                0,
                lambda message=str(error): self.finish_with_error(message),
            )
            return

        if result.returncode == 0:
            self.root.after(0, lambda: self.finish_success(action))
        else:
            self.root.after(
                0,
                lambda code=result.returncode: self.finish_with_error(
                    f"Module returned code {code}."
                ),
            )

    def toggle_auto_refresh(self) -> None:
        """Start or stop automatic pipeline refresh."""

        if self.auto_refresh_active:
            self.stop_auto_refresh()
        else:
            self.start_auto_refresh()

    def start_auto_refresh(self) -> None:
        """Enable automatic refresh and run immediately."""

        self.auto_refresh_active = True
        self.auto_refresh_button.configure(
            text="AUTO REFRESH: ON",
            bg=ACCENT_GREEN,
            fg="#111827",
        )

        interval_minutes = self.get_interval_minutes()
        self.status_variable.set(
            f"Auto refresh active: every {interval_minutes} minute(s)."
        )

        self.cancel_scheduled_jobs()

        if not self.running:
            self.start_action(MODULE_ACTIONS[0])

        self.schedule_next_auto_refresh()

    def stop_auto_refresh(self) -> None:
        """Disable automatic refresh."""

        self.auto_refresh_active = False
        self.cancel_scheduled_jobs()

        self.auto_refresh_button.configure(
            text="AUTO REFRESH: OFF",
            bg=ACCENT_ORANGE,
            fg="#111827",
        )
        self.countdown_variable.set("Next refresh: OFF")
        self.status_variable.set("Auto refresh stopped.")

    def get_interval_minutes(self) -> int:
        """Return the selected refresh interval."""

        return AUTO_REFRESH_MINUTES.get(self.interval_variable.get(), 5)

    def schedule_next_auto_refresh(self) -> None:
        """Schedule the next automatic pipeline run."""

        if not self.auto_refresh_active:
            return

        interval_minutes = self.get_interval_minutes()
        self.seconds_until_refresh = interval_minutes * 60
        self.update_countdown()

        self.auto_refresh_job = self.root.after(
            self.seconds_until_refresh * 1000,
            self.run_auto_refresh,
        )

    def update_countdown(self) -> None:
        """Update the next-refresh countdown every second."""

        if not self.auto_refresh_active:
            self.countdown_variable.set("Next refresh: OFF")
            return

        minutes, seconds = divmod(max(self.seconds_until_refresh, 0), 60)
        self.countdown_variable.set(
            f"Next refresh: {minutes:02d}:{seconds:02d}"
        )

        if self.seconds_until_refresh > 0:
            self.seconds_until_refresh -= 1
            self.countdown_job = self.root.after(1000, self.update_countdown)

    def run_auto_refresh(self) -> None:
        """Run the complete pipeline automatically."""

        self.auto_refresh_job = None

        if not self.auto_refresh_active:
            return

        if self.running:
            self.status_variable.set(
                "Auto refresh delayed: another module is running."
            )
            self.auto_refresh_job = self.root.after(30000, self.run_auto_refresh)
            return

        self.start_action(MODULE_ACTIONS[0])
        self.schedule_next_auto_refresh()

    def cancel_scheduled_jobs(self) -> None:
        """Cancel scheduled Tkinter jobs."""

        if self.auto_refresh_job is not None:
            try:
                self.root.after_cancel(self.auto_refresh_job)
            except tk.TclError:
                pass
            self.auto_refresh_job = None

        if self.countdown_job is not None:
            try:
                self.root.after_cancel(self.countdown_job)
            except tk.TclError:
                pass
            self.countdown_job = None

    def finish_success(self, action: ModuleAction) -> None:
        """Handle successful completion."""

        self.running = False
        self.current_action_title = ""

        timestamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        self.last_update_variable.set(f"Last update: {timestamp}")
        self.status_variable.set(f"Completed successfully: {action.title}")

    def finish_with_error(self, message: str) -> None:
        """Handle module failure."""

        self.running = False
        self.current_action_title = ""
        self.status_variable.set(f"Failed: {message}")
        messagebox.showerror("AQSD Module Error", message)

    def close_application(self) -> None:
        """Close the Control Center safely."""

        if self.running:
            should_close = messagebox.askyesno(
                "AQSD",
                (
                    "An analytics module is still running.\n\n"
                    "Close the Control Center anyway?"
                ),
            )
            if not should_close:
                return

        self.auto_refresh_active = False
        self.cancel_scheduled_jobs()
        self.root.destroy()


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """Launch the AQSD Control Center."""

    root = tk.Tk()
    OptionIntelligenceControlCenter(root)
    root.mainloop()


if __name__ == "__main__":
    main()

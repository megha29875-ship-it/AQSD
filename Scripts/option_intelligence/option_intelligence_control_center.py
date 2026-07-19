"""
AQSD
OPTION INTELLIGENCE CONTROL CENTER

Module: option_intelligence_control_center.py
Version: 1.0
Author: AQSD

Description:
Desktop control centre for launching the AQSD BANKNIFTY
Option Intelligence modules.

Analytics only. No order placement.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import tkinter as tk

from dataclasses import dataclass
from tkinter import messagebox


# ============================================================
# DISPLAY CONFIGURATION
# ============================================================

WINDOW_TITLE = "AQSD — Option Intelligence Control Center"
WINDOW_WIDTH = 900
WINDOW_HEIGHT = 650

BACKGROUND = "#111827"
PANEL_BACKGROUND = "#182230"
CARD_BACKGROUND = "#243041"

TEXT_PRIMARY = "#F8FAFC"
TEXT_SECONDARY = "#AAB7C8"

ACCENT_BLUE = "#6EA8FE"
ACCENT_GREEN = "#4ADE80"
ACCENT_RED = "#FB7185"
ACCENT_ORANGE = "#FDBA74"


# ============================================================
# MODULE CONFIGURATION
# ============================================================

@dataclass(frozen=True)
class ModuleAction:
    """
    One AQSD module launcher.
    """

    title: str
    module: str
    description: str
    opens_window: bool = False


MODULE_ACTIONS = (
    ModuleAction(
        title="RUN COMPLETE PIPELINE",
        module=(
            "Scripts.option_intelligence."
            "live_option_intelligence_master"
        ),
        description=(
            "Run Decision, IV Surface, Volatility, "
            "Probability V2 and open Dashboard."
        ),
    ),
    ModuleAction(
        title="PROFESSIONAL DASHBOARD",
        module=(
            "Scripts.option_intelligence."
            "professional_option_dashboard_live"
        ),
        description=(
            "Open the professional BANKNIFTY dashboard."
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
            "Run the complete live decision workflow."
        ),
    ),
    ModuleAction(
        title="LIVE IV SURFACE",
        module=(
            "Scripts.option_intelligence."
            "live_iv_surface_runner"
        ),
        description=(
            "Fetch the live option chain and calculate IV."
        ),
    ),
    ModuleAction(
        title="VOLATILITY ANALYTICS",
        module=(
            "Scripts.option_intelligence."
            "live_volatility_analytics_runner"
        ),
        description=(
            "Calculate IV Rank, IV Percentile, HV and premium."
        ),
    ),
    ModuleAction(
        title="PROBABILITY ENGINE V2",
        module=(
            "Scripts.option_intelligence."
            "live_probability_v2_runner"
        ),
        description=(
            "Generate normalized scenario probabilities."
        ),
    ),
)


# ============================================================
# CONTROL CENTER
# ============================================================

class OptionIntelligenceControlCenter:
    """
    AQSD desktop module launcher.
    """

    def __init__(
        self,
        root: tk.Tk,
    ) -> None:
        self.root = root

        self.running = False

        self.status_variable = tk.StringVar(
            value="System ready."
        )

        self.build_window()
        self.build_interface()

    # --------------------------------------------------------
    # WINDOW
    # --------------------------------------------------------

    def build_window(
        self,
    ) -> None:
        """
        Configure the main window.
        """

        self.root.title(
            WINDOW_TITLE
        )

        self.root.geometry(
            f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}"
        )

        self.root.minsize(
            WINDOW_WIDTH,
            WINDOW_HEIGHT,
        )

        self.root.configure(
            bg=BACKGROUND
        )

    # --------------------------------------------------------
    # INTERFACE
    # --------------------------------------------------------

    def build_interface(
        self,
    ) -> None:
        """
        Build the control-center interface.
        """

        main_frame = tk.Frame(
            self.root,
            bg=BACKGROUND,
        )

        main_frame.pack(
            fill="both",
            expand=True,
            padx=24,
            pady=20,
        )

        self.build_header(
            main_frame
        )

        self.build_module_grid(
            main_frame
        )

        self.build_status_panel(
            main_frame
        )

    def build_header(
        self,
        parent: tk.Widget,
    ) -> None:
        """
        Build title and subtitle.
        """

        header = tk.Frame(
            parent,
            bg=PANEL_BACKGROUND,
            highlightthickness=1,
            highlightbackground="#334155",
        )

        header.pack(
            fill="x",
            pady=(
                0,
                18,
            ),
        )

        title = tk.Label(
            header,
            text=(
                "AQSD OPTION INTELLIGENCE "
                "CONTROL CENTER"
            ),
            bg=PANEL_BACKGROUND,
            fg=TEXT_PRIMARY,
            font=(
                "Segoe UI",
                21,
                "bold",
            ),
            anchor="w",
        )

        title.pack(
            fill="x",
            padx=22,
            pady=(
                20,
                5,
            ),
        )

        subtitle = tk.Label(
            header,
            text=(
                "LIVE BANKNIFTY ANALYTICS | "
                "NO ORDER PLACEMENT"
            ),
            bg=PANEL_BACKGROUND,
            fg=TEXT_SECONDARY,
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
                20,
            ),
        )

    def build_module_grid(
        self,
        parent: tk.Widget,
    ) -> None:
        """
        Build launcher buttons.
        """

        grid_frame = tk.Frame(
            parent,
            bg=BACKGROUND,
        )

        grid_frame.pack(
            fill="both",
            expand=True,
        )

        grid_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        grid_frame.grid_columnconfigure(
            1,
            weight=1,
        )

        for index, action in enumerate(
            MODULE_ACTIONS
        ):
            row = index // 2
            column = index % 2

            self.build_action_card(
                parent=grid_frame,
                action=action,
                row=row,
                column=column,
            )

    def build_action_card(
        self,
        parent: tk.Widget,
        action: ModuleAction,
        row: int,
        column: int,
    ) -> None:
        """
        Build one module launcher card.
        """

        card = tk.Frame(
            parent,
            bg=CARD_BACKGROUND,
            highlightthickness=1,
            highlightbackground="#3B4A5F",
        )

        card.grid(
            row=row,
            column=column,
            sticky="nsew",
            padx=8,
            pady=8,
        )

        parent.grid_rowconfigure(
            row,
            weight=1,
        )

        title = tk.Label(
            card,
            text=action.title,
            bg=CARD_BACKGROUND,
            fg=TEXT_PRIMARY,
            font=(
                "Segoe UI",
                12,
                "bold",
            ),
            anchor="w",
        )

        title.pack(
            fill="x",
            padx=18,
            pady=(
                17,
                6,
            ),
        )

        description = tk.Label(
            card,
            text=action.description,
            bg=CARD_BACKGROUND,
            fg=TEXT_SECONDARY,
            font=(
                "Segoe UI",
                9,
            ),
            justify="left",
            anchor="w",
            wraplength=330,
        )

        description.pack(
            fill="x",
            padx=18,
            pady=(
                0,
                14,
            ),
        )

        button_text = (
            "OPEN"
            if action.opens_window
            else "RUN"
        )

        button = tk.Button(
            card,
            text=button_text,
            command=lambda selected=action: (
                self.start_action(
                    selected
                )
            ),
            bg=ACCENT_BLUE,
            fg="#FFFFFF",
            activebackground="#4F8DE8",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
            padx=16,
            pady=8,
        )

        button.pack(
            anchor="w",
            padx=18,
            pady=(
                0,
                18,
            ),
        )

    def build_status_panel(
        self,
        parent: tk.Widget,
    ) -> None:
        """
        Build status and exit controls.
        """

        status_frame = tk.Frame(
            parent,
            bg=PANEL_BACKGROUND,
            highlightthickness=1,
            highlightbackground="#334155",
        )

        status_frame.pack(
            fill="x",
            pady=(
                18,
                0,
            ),
        )

        status_label = tk.Label(
            status_frame,
            textvariable=self.status_variable,
            bg=PANEL_BACKGROUND,
            fg=ACCENT_GREEN,
            font=(
                "Consolas",
                10,
                "bold",
            ),
            anchor="w",
        )

        status_label.pack(
            side="left",
            fill="x",
            expand=True,
            padx=18,
            pady=16,
        )

        exit_button = tk.Button(
            status_frame,
            text="EXIT",
            command=self.root.destroy,
            bg=ACCENT_RED,
            fg="#FFFFFF",
            activebackground="#E85A70",
            activeforeground="#FFFFFF",
            relief="flat",
            cursor="hand2",
            font=(
                "Segoe UI",
                10,
                "bold",
            ),
            padx=20,
            pady=8,
        )

        exit_button.pack(
            side="right",
            padx=18,
            pady=10,
        )

    # --------------------------------------------------------
    # MODULE EXECUTION
    # --------------------------------------------------------

    def start_action(
        self,
        action: ModuleAction,
    ) -> None:
        """
        Start a module without freezing the interface.
        """

        if self.running and not action.opens_window:
            messagebox.showwarning(
                "AQSD",
                "Another analytics module is already running.",
            )

            return

        if action.opens_window:
            self.open_window_module(
                action
            )

            return

        self.running = True

        self.status_variable.set(
            f"Running: {action.title}..."
        )

        worker = threading.Thread(
            target=self.run_module,
            args=(action,),
            daemon=True,
        )

        worker.start()

    def open_window_module(
        self,
        action: ModuleAction,
    ) -> None:
        """
        Open a graphical module independently.
        """

        try:
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    action.module,
                ]
            )

        except Exception as error:
            self.status_variable.set(
                f"Failed: {error}"
            )

            messagebox.showerror(
                "AQSD Module Error",
                str(error),
            )

            return

        self.status_variable.set(
            f"Opened: {action.title}"
        )

    def run_module(
        self,
        action: ModuleAction,
    ) -> None:
        """
        Execute a command-line module.
        """

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
                lambda message=str(error): (
                    self.finish_with_error(
                        message
                    )
                ),
            )

            return

        if result.returncode == 0:
            self.root.after(
                0,
                lambda: self.finish_success(
                    action
                ),
            )

        else:
            self.root.after(
                0,
                lambda code=result.returncode: (
                    self.finish_with_error(
                        f"Module returned code {code}."
                    )
                ),
            )

    def finish_success(
        self,
        action: ModuleAction,
    ) -> None:
        """
        Handle successful completion.
        """

        self.running = False

        self.status_variable.set(
            f"Completed successfully: {action.title}"
        )

        messagebox.showinfo(
            "AQSD",
            f"{action.title} completed successfully.",
        )

    def finish_with_error(
        self,
        message: str,
    ) -> None:
        """
        Handle module failure.
        """

        self.running = False

        self.status_variable.set(
            f"Failed: {message}"
        )

        messagebox.showerror(
            "AQSD Module Error",
            message,
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Launch the AQSD Control Center.
    """

    root = tk.Tk()

    OptionIntelligenceControlCenter(
        root
    )

    root.mainloop()


if __name__ == "__main__":
    main()
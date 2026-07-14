
"""
AQSD Professional
Desktop Launcher
Version: 3.0

Adds research tools:
- Single-symbol backtest
- Batch backtest
- Strategy optimizer
- Symbol / period input dialogs
- Existing morning, evening and portfolio workflows
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk


# ============================================================
# PATHS
# ============================================================

SCRIPTS_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPTS_DIR.parent
DASHBOARD = BASE_DIR / "Output" / "Dashboard.xlsx"

AQSD_SCRIPT = SCRIPTS_DIR / "AQSD.py"
SCHEDULER_SCRIPT = SCRIPTS_DIR / "aqsd_scheduler.py"
BACKUP_SCRIPT = SCRIPTS_DIR / "auto_backup.py"
CONFIG_SYNC_SCRIPT = SCRIPTS_DIR / "config_sync.py"
MORNING_CHECKLIST_SCRIPT = SCRIPTS_DIR / "morning_checklist.py"

BACKTEST_SCRIPT = SCRIPTS_DIR / "backtest_engine.py"
BATCH_BACKTEST_SCRIPT = SCRIPTS_DIR / "batch_backtest.py"
OPTIMIZER_SCRIPT = SCRIPTS_DIR / "strategy_optimizer.py"


# ============================================================
# COLORS
# ============================================================

NAVY = "#17365D"
WHITE = "#FFFFFF"
DARK = "#1F1F1F"


# ============================================================
# APPLICATION
# ============================================================

class AQSDLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()

        self.title("AQSD Professional Launcher v3")
        self.geometry("1120x760")
        self.minsize(1020, 680)
        self.configure(bg=WHITE)

        self.output_queue: queue.Queue[str] = queue.Queue()
        self.running = False

        self._build_style()
        self._build_ui()
        self.after(100, self._drain_output_queue)

    def _build_style(self) -> None:
        style = ttk.Style(self)

        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure(
            "AQSD.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=9,
        )

        style.configure(
            "Header.TLabel",
            font=("Segoe UI", 22, "bold"),
            foreground=WHITE,
            background=NAVY,
            padding=18,
        )

    def _build_ui(self) -> None:
        ttk.Label(
            self,
            text="AQSD PROFESSIONAL TRADING WORKSTATION",
            style="Header.TLabel",
            anchor="center",
        ).pack(fill="x")

        content = tk.Frame(self, bg=WHITE)
        content.pack(fill="both", expand=True, padx=18, pady=18)

        left = tk.Frame(content, bg=WHITE)
        left.pack(side="left", fill="y", padx=(0, 16))

        middle = tk.Frame(content, bg=WHITE)
        middle.pack(side="left", fill="y", padx=(0, 16))

        right = tk.Frame(content, bg=WHITE)
        right.pack(side="right", fill="both", expand=True)

        self._build_workflow_panel(left)
        self._build_research_panel(middle)
        self._build_log_panel(right)

        self.write_log("AQSD Launcher v3 ready.\n")

    def _section_title(self, parent, text: str) -> None:
        tk.Label(
            parent,
            text=text,
            font=("Segoe UI", 13, "bold"),
            bg=WHITE,
            fg=NAVY,
        ).pack(anchor="w", pady=(0, 10))

    def _button(self, parent, text: str, command) -> None:
        ttk.Button(
            parent,
            text=text,
            command=command,
            style="AQSD.TButton",
            width=25,
        ).pack(fill="x", pady=4)

    def _build_workflow_panel(self, parent) -> None:
        self._section_title(parent, "WORKFLOWS")

        self._button(
            parent,
            "Morning Routine",
            lambda: self.run_scheduler("morning"),
        )
        self._button(
            parent,
            "Evening Routine",
            lambda: self.run_scheduler("evening"),
        )
        self._button(
            parent,
            "Run Everything",
            lambda: self.run_aqsd(
                ["--mode", "all", "--skip-update", "--no-open"]
            ),
        )
        self._button(
            parent,
            "Portfolio Update",
            lambda: self.run_aqsd(
                ["--mode", "portfolio", "--no-open"]
            ),
        )

        self._section_title(parent, "TOOLS")

        self._button(
            parent,
            "System Health Check",
            self.system_health_check,
        )
        self._button(
            parent,
            "Create Backup",
            lambda: self.run_script(BACKUP_SCRIPT),
        )
        self._button(
            parent,
            "Sync Settings to Excel",
            lambda: self.run_script(CONFIG_SYNC_SCRIPT),
        )
        self._button(
            parent,
            "Pull Settings from Excel",
            lambda: self.run_script(
                CONFIG_SYNC_SCRIPT,
                ["--pull"],
            ),
        )
        self._button(
            parent,
            "Morning Checklist",
            lambda: self.run_script(MORNING_CHECKLIST_SCRIPT),
        )
        self._button(
            parent,
            "Open Dashboard",
            self.open_dashboard,
        )
        self._button(
            parent,
            "Clear Log",
            self.clear_log,
        )

        self.status_var = tk.StringVar(value="Ready")

        status_frame = tk.Frame(parent, bg=WHITE)
        status_frame.pack(fill="x", pady=(18, 0))

        tk.Label(
            status_frame,
            text="Status:",
            font=("Segoe UI", 10, "bold"),
            bg=WHITE,
            fg=NAVY,
        ).pack(side="left")

        self.status_label = tk.Label(
            status_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 10, "bold"),
            bg=WHITE,
            fg="green",
        )
        self.status_label.pack(side="left", padx=(8, 0))

    def _build_research_panel(self, parent) -> None:
        self._section_title(parent, "RESEARCH LAB")

        self._button(
            parent,
            "Single Backtest",
            self.single_backtest_dialog,
        )
        self._button(
            parent,
            "Batch Backtest",
            self.batch_backtest_dialog,
        )
        self._button(
            parent,
            "Strategy Optimizer",
            self.optimizer_dialog,
        )

        tk.Label(
            parent,
            text=(
                "Backtests use historical Yahoo Finance data.\n"
                "Results are research estimates, not guarantees."
            ),
            font=("Segoe UI", 9),
            bg=WHITE,
            fg="#555555",
            justify="left",
            wraplength=220,
        ).pack(anchor="w", pady=(15, 0))

    def _build_log_panel(self, parent) -> None:
        self._section_title(parent, "LIVE LOG")

        log_frame = tk.Frame(parent, bg=DARK)
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_frame,
            wrap="word",
            font=("Consolas", 10),
            bg=DARK,
            fg=WHITE,
            insertbackground=WHITE,
            relief="flat",
        )
        self.log_text.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(
            log_frame,
            orient="vertical",
            command=self.log_text.yview,
        )
        scrollbar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    # ========================================================
    # RESEARCH DIALOGS
    # ========================================================

    def ask_symbol(self) -> str | None:
        symbol = simpledialog.askstring(
            "NSE Symbol",
            "Enter NSE symbol, for example RELIANCE.NS:",
            initialvalue="RELIANCE.NS",
            parent=self,
        )

        if not symbol:
            return None

        symbol = symbol.strip().upper()

        if not symbol.endswith(".NS"):
            symbol += ".NS"

        return symbol

    def ask_period(self, default: str = "5y") -> str | None:
        period = simpledialog.askstring(
            "History Period",
            "Enter history period: 1y, 3y, 5y or 10y",
            initialvalue=default,
            parent=self,
        )

        if not period:
            return None

        return period.strip().lower()

    def single_backtest_dialog(self) -> None:
        symbol = self.ask_symbol()

        if not symbol:
            return

        period = self.ask_period("3y")

        if not period:
            return

        self.run_script(
            BACKTEST_SCRIPT,
            ["--symbol", symbol, "--period", period],
        )

    def batch_backtest_dialog(self) -> None:
        period = self.ask_period("3y")

        if not period:
            return

        limit = simpledialog.askinteger(
            "Batch Size",
            "How many symbols should be tested?",
            initialvalue=20,
            minvalue=1,
            maxvalue=200,
            parent=self,
        )

        if limit is None:
            return

        self.run_script(
            BATCH_BACKTEST_SCRIPT,
            ["--period", period, "--limit", str(limit)],
        )

    def optimizer_dialog(self) -> None:
        symbol = self.ask_symbol()

        if not symbol:
            return

        period = self.ask_period("5y")

        if not period:
            return

        confirmed = messagebox.askyesno(
            "Strategy Optimizer",
            (
                "The optimizer tests many parameter combinations "
                "and may take several minutes.\n\nContinue?"
            ),
            parent=self,
        )

        if not confirmed:
            return

        self.run_script(
            OPTIMIZER_SCRIPT,
            ["--symbol", symbol, "--period", period],
        )

    # ========================================================
    # WORKFLOW COMMANDS
    # ========================================================

    def run_scheduler(self, mode: str) -> None:
        self.run_script(SCHEDULER_SCRIPT, [mode])

    def run_aqsd(self, arguments: list[str]) -> None:
        self.run_script(AQSD_SCRIPT, arguments)

    def run_script(
        self,
        script_path: Path,
        arguments: list[str] | None = None,
    ) -> None:
        if self.running:
            messagebox.showwarning(
                "AQSD Busy",
                "Another AQSD process is already running.",
            )
            return

        if not script_path.exists():
            messagebox.showerror(
                "Missing Script",
                f"Script not found:\n{script_path}",
            )
            return

        command = [
            sys.executable,
            str(script_path),
            *(arguments or []),
        ]

        self.running = True
        self.status_var.set("Running")
        self.status_label.configure(fg="dark orange")

        self.write_log("\n" + "=" * 74 + "\n")
        self.write_log("COMMAND: " + " ".join(command) + "\n")
        self.write_log("=" * 74 + "\n")

        threading.Thread(
            target=self._run_process,
            args=(command,),
            daemon=True,
        ).start()

    def _run_process(self, command: list[str]) -> None:
        try:
            process = subprocess.Popen(
                command,
                cwd=str(SCRIPTS_DIR),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            assert process.stdout is not None

            for line in process.stdout:
                self.output_queue.put(line)

            code = process.wait()

            if code == 0:
                self.output_queue.put("__SUCCESS__")
            else:
                self.output_queue.put(
                    f"\nProcess failed with exit code {code}.\n"
                )
                self.output_queue.put("__ERROR__")

        except Exception as error:
            self.output_queue.put(
                f"\nLauncher error:\n{error}\n"
            )
            self.output_queue.put("__ERROR__")

    def _drain_output_queue(self) -> None:
        try:
            while True:
                item = self.output_queue.get_nowait()

                if item == "__SUCCESS__":
                    self.running = False
                    self.status_var.set("Completed")
                    self.status_label.configure(fg="green")
                    self.write_log(
                        "\nAQSD process completed successfully.\n"
                    )

                elif item == "__ERROR__":
                    self.running = False
                    self.status_var.set("Failed")
                    self.status_label.configure(fg="red")

                else:
                    self.write_log(item)

        except queue.Empty:
            pass

        self.after(100, self._drain_output_queue)

    # ========================================================
    # UTILITIES
    # ========================================================

    def system_health_check(self) -> None:
        checks = {
            "AQSD.py": AQSD_SCRIPT.exists(),
            "Scheduler": SCHEDULER_SCRIPT.exists(),
            "Dashboard": DASHBOARD.exists(),
            "Backtest Engine": BACKTEST_SCRIPT.exists(),
            "Batch Backtest": BATCH_BACKTEST_SCRIPT.exists(),
            "Strategy Optimizer": OPTIMIZER_SCRIPT.exists(),
            "Backup Script": BACKUP_SCRIPT.exists(),
            "Config Sync": CONFIG_SYNC_SCRIPT.exists(),
        }

        self.write_log("\nSYSTEM HEALTH CHECK\n")
        self.write_log("=" * 44 + "\n")

        all_ok = True

        for name, ok in checks.items():
            status = "OK" if ok else "MISSING"
            self.write_log(f"{name:<24} {status}\n")
            all_ok = all_ok and ok

        self.write_log("=" * 44 + "\n")

        if all_ok:
            self.status_var.set("Healthy")
            self.status_label.configure(fg="green")
            messagebox.showinfo(
                "AQSD Health",
                "All critical AQSD files are available.",
            )
        else:
            self.status_var.set("Attention Needed")
            self.status_label.configure(fg="red")
            messagebox.showwarning(
                "AQSD Health",
                "One or more critical AQSD files are missing.",
            )

    def open_dashboard(self) -> None:
        if not DASHBOARD.exists():
            messagebox.showerror(
                "Dashboard Missing",
                f"Dashboard not found:\n{DASHBOARD}",
            )
            return

        try:
            if os.name == "nt":
                os.startfile(DASHBOARD)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(DASHBOARD)])

            self.write_log(
                f"\nOpened dashboard:\n{DASHBOARD}\n"
            )

        except OSError as error:
            messagebox.showerror(
                "Open Failed",
                str(error),
            )

    def clear_log(self) -> None:
        self.log_text.delete("1.0", tk.END)
        self.write_log("Log cleared.\n")

    def write_log(self, text: str) -> None:
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)


def main() -> None:
    app = AQSDLauncher()
    app.mainloop()


if __name__ == "__main__":
    main()

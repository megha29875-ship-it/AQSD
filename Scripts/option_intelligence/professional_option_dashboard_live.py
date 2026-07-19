"""
AQSD
Professional Option Intelligence Dashboard

Module: professional_option_dashboard_live.py
Version: 1.0
Author: AQSD

Description:
Launches the existing Professional Option Intelligence Dashboard
and automatically refreshes live FYERS analytics at a fixed interval.

This module:
- Uses the existing professional dashboard
- Runs the complete live Decision Intelligence pipeline
- Refreshes automatically
- Prevents overlapping refresh operations
- Does not place orders
"""

from __future__ import annotations

import tkinter as tk

from Scripts.option_intelligence.professional_option_dashboard import (
    ProfessionalOptionDashboard,
)


# ============================================================
# CONFIGURATION
# ============================================================

AUTO_REFRESH_SECONDS = 60
FIRST_REFRESH_DELAY_SECONDS = 3


# ============================================================
# AUTO-REFRESH DASHBOARD
# ============================================================

class AutoRefreshOptionDashboard(
    ProfessionalOptionDashboard
):
    """
    Professional Option Dashboard with automatic live refresh.
    """

    def __init__(
        self,
        root: tk.Tk,
    ) -> None:
        super().__init__(
            root
        )

        self.auto_refresh_enabled = True
        self.seconds_remaining = (
            FIRST_REFRESH_DELAY_SECONDS
        )

        self.status_variable.set(
            "Dashboard ready. First live refresh begins shortly."
        )

        self.root.after(
            1000,
            self.auto_refresh_countdown,
        )

    def auto_refresh_countdown(
        self,
    ) -> None:
        """
        Maintain the countdown and start refresh when due.
        """

        if not self.auto_refresh_enabled:
            return

        if self.refresh_running:
            self.status_variable.set(
                "Live refresh is running..."
            )

            self.root.after(
                1000,
                self.auto_refresh_countdown,
            )

            return

        if self.seconds_remaining <= 0:
            self.status_variable.set(
                "Starting automatic live refresh..."
            )

            self.start_live_refresh()

            self.seconds_remaining = (
                AUTO_REFRESH_SECONDS
            )

        else:
            self.status_variable.set(
                "Automatic refresh in "
                f"{self.seconds_remaining} seconds."
            )

            self.seconds_remaining -= 1

        self.root.after(
            1000,
            self.auto_refresh_countdown,
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Launch the automatically refreshing dashboard.
    """

    root = tk.Tk()

    root.title(
        "AQSD — Live Professional Option Intelligence"
    )

    AutoRefreshOptionDashboard(
        root
    )

    root.mainloop()


if __name__ == "__main__":
    main()

"""
AQSD Professional
Module: Dashboard Formatter
Version: 3.0
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side


BASE = Path(__file__).resolve().parent.parent
DASHBOARD = BASE / "Output" / "Dashboard.xlsx"

NAVY = "17365D"
BLUE = "D9EAF7"
GREEN = "C6EFCE"
YELLOW = "FFF2CC"
RED = "FFC7CE"
GOLD = "FFD966"
WHITE = "FFFFFF"
GREY = "E7E6E6"
THIN = Side(style="thin", color="D9D9D9")


def headers(ws):
    return {
        str(cell.value).strip(): cell.column
        for cell in ws[1]
        if cell.value is not None
    }


def market_summary(wb):
    if "Market Pulse" not in wb.sheetnames:
        return "UNKNOWN", "", ""

    ws = wb["Market Pulse"]
    bias = "UNKNOWN"
    confidence = ""
    strategy = ""

    for row in range(1, ws.max_row + 1):
        label = str(ws.cell(row, 1).value or "").strip()

        if label == "Market Bias":
            bias = str(ws.cell(row, 2).value or "")
        elif label == "Confidence":
            confidence = str(ws.cell(row, 2).value or "")
        elif label == "Strategy":
            strategy = str(ws.cell(row, 2).value or "")

    return bias, confidence, strategy


def create_home(wb):
    if "HOME" in wb.sheetnames:
        del wb["HOME"]

    ws = wb.create_sheet("HOME", 0)
    ws.sheet_view.showGridLines = False

    # Title
    ws.merge_cells("A1:N2")
    ws["A1"] = "AQSD PROFESSIONAL DASHBOARD"
    ws["A1"].font = Font(size=22, bold=True, color=WHITE)
    ws["A1"].fill = PatternFill("solid", fgColor=NAVY)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws["A4"] = "Last Updated"
    ws["B4"] = datetime.now().strftime("%d-%m-%Y %H:%M")

    bias, confidence, strategy = market_summary(wb)

    # Market pulse card
    ws.merge_cells("A6:C6")
    ws["A6"] = "MARKET PULSE"
    ws["A6"].font = Font(bold=True, color=WHITE)
    ws["A6"].fill = PatternFill("solid", fgColor=NAVY)
    ws["A6"].alignment = Alignment(horizontal="center")

    pulse_rows = [
        ("Market Bias", bias),
        ("Confidence", confidence),
        ("Strategy", strategy),
    ]

    for row_no, (label, value) in enumerate(pulse_rows, start=7):
        ws[f"A{row_no}"] = label
        ws[f"B{row_no}"] = value
        ws[f"A{row_no}"].font = Font(bold=True)
        ws[f"A{row_no}"].fill = PatternFill("solid", fgColor=BLUE)

    bias_upper = str(bias).upper()
    if bias_upper == "BULLISH":
        ws["B7"].fill = PatternFill("solid", fgColor=GREEN)
    elif bias_upper == "BEARISH":
        ws["B7"].fill = PatternFill("solid", fgColor=RED)
    else:
        ws["B7"].fill = PatternFill("solid", fgColor=YELLOW)

    option_ws = wb["Option Buying"]
    h = headers(option_ws)

    symbol_col = h.get("Symbol")
    score_col = h.get("Trade Score") or h.get("Option Score")
    conf_col = h.get("Trade Confidence") or h.get("Confidence")
    grade_col = h.get("Trade Grade") or h.get("Grade")
    stars_col = h.get("Stars")
    rec_col = h.get("Recommendation") or h.get("Action")
    reasons_col = h.get("Reasons")
    entry_col = h.get("Entry")
    stop_col = h.get("Stop Loss")
    t1_col = h.get("Target 1")
    t2_col = h.get("Target 2")

    if option_ws.max_row < 2:
        raise RuntimeError("Option Buying sheet has no data.")

    best_row = 2

    def val(col):
        return option_ws.cell(best_row, col).value if col else ""

    # Best trade card
    ws.merge_cells("E4:N4")
    ws["E4"] = "TODAY'S BEST TRADE"
    ws["E4"].font = Font(size=16, bold=True, color=WHITE)
    ws["E4"].fill = PatternFill("solid", fgColor=NAVY)
    ws["E4"].alignment = Alignment(horizontal="center")

    ws.merge_cells("E5:N6")
    ws["E5"] = val(symbol_col)
    ws["E5"].font = Font(size=24, bold=True, color=NAVY)
    ws["E5"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("E7:G8")
    ws["E7"] = f"Score\n{val(score_col)}"
    ws.merge_cells("H7:J8")
    ws["H7"] = f"Confidence\n{val(conf_col)}%"
    ws.merge_cells("K7:N8")
    ws["K7"] = f"{val(grade_col)}  {val(stars_col)}"

    for cell_ref in ("E7", "H7", "K7"):
        ws[cell_ref].font = Font(size=14, bold=True)
        ws[cell_ref].alignment = Alignment(
            horizontal="center",
            vertical="center",
            wrap_text=True,
        )
        ws[cell_ref].fill = PatternFill("solid", fgColor=GOLD)

    ws.merge_cells("E9:N9")
    ws["E9"] = str(val(rec_col))
    ws["E9"].font = Font(size=18, bold=True)
    ws["E9"].alignment = Alignment(horizontal="center")

    recommendation = str(val(rec_col)).upper()
    if recommendation in {"STRONG BUY", "BUY"}:
        ws["E9"].fill = PatternFill("solid", fgColor=GREEN)
    elif recommendation in {"WATCH", "WAIT"}:
        ws["E9"].fill = PatternFill("solid", fgColor=YELLOW)
    else:
        ws["E9"].fill = PatternFill("solid", fgColor=RED)

    ws.merge_cells("E10:N12")
    ws["E10"] = str(val(reasons_col))
    ws["E10"].alignment = Alignment(
        wrap_text=True,
        vertical="top",
    )
    ws["E10"].fill = PatternFill("solid", fgColor=GREY)

    # Trade plan
    trade_plan = [
        ("Entry", val(entry_col)),
        ("Stop Loss", val(stop_col)),
        ("Target 1", val(t1_col)),
        ("Target 2", val(t2_col)),
    ]

    for idx, (label, value) in enumerate(trade_plan, start=13):
        ws[f"E{idx}"] = label
        ws[f"F{idx}"] = value
        ws[f"E{idx}"].font = Font(bold=True)
        ws[f"E{idx}"].fill = PatternFill("solid", fgColor=BLUE)

    # Top 10 table
    ws.merge_cells("E17:N17")
    ws["E17"] = "TOP 10 TRADE SETUPS"
    ws["E17"].font = Font(bold=True, color=WHITE)
    ws["E17"].fill = PatternFill("solid", fgColor=NAVY)
    ws["E17"].alignment = Alignment(horizontal="center")

    table_headers = [
        "Rank", "Symbol", "Score", "Confidence",
        "Grade", "Stars", "Recommendation"
    ]

    for col, heading in enumerate(table_headers, start=5):
        cell = ws.cell(row=18, column=col, value=heading)
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor=GREY)
        cell.border = Border(bottom=THIN)

    for home_row, source_row in enumerate(
        range(2, min(option_ws.max_row, 11) + 1),
        start=19,
    ):
        row_values = [
            home_row - 18,
            option_ws.cell(source_row, symbol_col).value if symbol_col else "",
            option_ws.cell(source_row, score_col).value if score_col else "",
            option_ws.cell(source_row, conf_col).value if conf_col else "",
            option_ws.cell(source_row, grade_col).value if grade_col else "",
            option_ws.cell(source_row, stars_col).value if stars_col else "",
            option_ws.cell(source_row, rec_col).value if rec_col else "",
        ]

        for col, value in enumerate(row_values, start=5):
            ws.cell(home_row, col, value)
            ws.cell(home_row, col).border = Border(bottom=THIN)

        ws.cell(home_row, 5).fill = PatternFill("solid", fgColor=GOLD)

    widths = {
        "A": 18, "B": 18, "C": 4, "D": 4,
        "E": 14, "F": 16, "G": 14, "H": 14,
        "I": 14, "J": 14, "K": 14, "L": 14,
        "M": 14, "N": 14,
    }

    for column, width in widths.items():
        ws.column_dimensions[column].width = width


def main():
    if not DASHBOARD.exists():
        raise FileNotFoundError(f"Dashboard not found:\n{DASHBOARD}")

    wb = load_workbook(DASHBOARD)

    if "Option Buying" not in wb.sheetnames:
        raise RuntimeError("Option Buying sheet not found.")

    create_home(wb)
    wb.save(DASHBOARD)

    print("AQSD Trade Card Dashboard created successfully.")
    print(DASHBOARD)


if __name__ == "__main__":
    main()

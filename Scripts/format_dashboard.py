
from pathlib import Path
from datetime import datetime

from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


BASE = Path(__file__).resolve().parent.parent
DASHBOARD = BASE / "Output" / "Dashboard.xlsx"


# Colors
NAVY = "1F4E78"
BLUE = "D9EAF7"
GREEN = "C6EFCE"
DARK_GREEN = "006100"
YELLOW = "FFF2CC"
RED = "FFC7CE"
DARK_RED = "9C0006"
GOLD = "FFD966"
WHITE = "FFFFFF"
GREY = "E7E6E6"


def style_sheet(ws):
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    thin = Side(style="thin", color="D9D9D9")

    for cell in ws[1]:
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.font = Font(color=WHITE, bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = Border(bottom=thin)

    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.border = Border(bottom=thin)
            cell.alignment = Alignment(vertical="center")

    # Auto-width
    for col_idx, column_cells in enumerate(ws.columns, start=1):
        max_len = 0
        for cell in column_cells:
            value = "" if cell.value is None else str(cell.value)
            max_len = max(max_len, len(value))

        ws.column_dimensions[get_column_letter(col_idx)].width = min(
            max(max_len + 2, 10),
            28
        )

    ws.row_dimensions[1].height = 24


def color_option_rows(ws):
    headers = {
        str(cell.value).strip(): cell.column
        for cell in ws[1]
        if cell.value is not None
    }

    action_col = headers.get("Action")
    rank_col = headers.get("Rank")

    if not action_col:
        return

    for row in range(2, ws.max_row + 1):
        action = str(ws.cell(row, action_col).value or "").upper()

        if action in {"STRONG BUY", "BUY"}:
            fill = PatternFill("solid", fgColor=GREEN)
            font = Font(color=DARK_GREEN, bold=True)
        elif action in {"WATCH", "WAIT"}:
            fill = PatternFill("solid", fgColor=YELLOW)
            font = Font(bold=True)
        elif action == "AVOID":
            fill = PatternFill("solid", fgColor=RED)
            font = Font(color=DARK_RED, bold=True)
        else:
            continue

        for cell in ws[row]:
            cell.fill = fill

        ws.cell(row, action_col).font = font

        # Gold highlight for Top 10
        if rank_col and isinstance(ws.cell(row, rank_col).value, int):
            if ws.cell(row, rank_col).value <= 10:
                ws.cell(row, rank_col).fill = PatternFill("solid", fgColor=GOLD)
                ws.cell(row, rank_col).font = Font(bold=True)


def color_long_term_rows(ws):
    headers = {
        str(cell.value).strip(): cell.column
        for cell in ws[1]
        if cell.value is not None
    }

    action_col = headers.get("Investment Action")
    rank_col = headers.get("Rank")

    if not action_col:
        return

    for row in range(2, ws.max_row + 1):
        action = str(ws.cell(row, action_col).value or "").upper()

        if action in {"STRONG", "ACCUMULATE"}:
            fill = PatternFill("solid", fgColor=GREEN)
        elif action == "WATCH":
            fill = PatternFill("solid", fgColor=YELLOW)
        else:
            fill = PatternFill("solid", fgColor=RED)

        for cell in ws[row]:
            cell.fill = fill

        if rank_col and isinstance(ws.cell(row, rank_col).value, int):
            if ws.cell(row, rank_col).value <= 10:
                ws.cell(row, rank_col).fill = PatternFill("solid", fgColor=GOLD)
                ws.cell(row, rank_col).font = Font(bold=True)


def create_home_sheet(wb):
    if "HOME" in wb.sheetnames:
        del wb["HOME"]

    ws = wb.create_sheet("HOME", 0)

    ws["A1"] = "AQSD DASHBOARD"
    ws["A1"].font = Font(size=20, bold=True, color=WHITE)
    ws["A1"].fill = PatternFill("solid", fgColor=NAVY)
    ws.merge_cells("A1:F1")
    ws["A1"].alignment = Alignment(horizontal="center")

    ws["A3"] = "Last Updated"
    ws["B3"] = datetime.now().strftime("%d-%m-%Y %H:%M")

    option_ws = wb["Option Buying"]
    long_ws = wb["Long Term"]

    option_headers = {
        str(cell.value).strip(): cell.column
        for cell in option_ws[1]
        if cell.value is not None
    }

    action_col = option_headers.get("Action")

    counts = {
        "Stocks Scanned": option_ws.max_row - 1,
        "Strong Buy": 0,
        "Buy": 0,
        "Watch": 0,
        "Wait": 0,
        "Avoid": 0,
    }

    if action_col:
        for row in range(2, option_ws.max_row + 1):
            action = str(option_ws.cell(row, action_col).value or "").title()
            if action in counts:
                counts[action] += 1

    start_row = 5
    for i, (label, value) in enumerate(counts.items(), start=start_row):
        ws[f"A{i}"] = label
        ws[f"B{i}"] = value
        ws[f"A{i}"].font = Font(bold=True)
        ws[f"A{i}"].fill = PatternFill("solid", fgColor=BLUE)

    # Top 10 option picks
    ws["D3"] = "Top 10 Option Picks"
    ws["D3"].font = Font(bold=True, color=WHITE)
    ws["D3"].fill = PatternFill("solid", fgColor=NAVY)

    option_symbol_col = option_headers.get("Symbol")
    option_score_col = option_headers.get("Option Score")
    option_action_col = option_headers.get("Action")

    ws["D4"] = "Symbol"
    ws["E4"] = "Score"
    ws["F4"] = "Action"

    for c in ws[4][3:6]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor=GREY)

    if option_symbol_col and option_score_col and option_action_col:
        for i, row in enumerate(range(2, min(option_ws.max_row, 11) + 1), start=5):
            ws[f"D{i}"] = option_ws.cell(row, option_symbol_col).value
            ws[f"E{i}"] = option_ws.cell(row, option_score_col).value
            ws[f"F{i}"] = option_ws.cell(row, option_action_col).value

    # Top 10 long-term picks
    long_headers = {
        str(cell.value).strip(): cell.column
        for cell in long_ws[1]
        if cell.value is not None
    }

    ws["D17"] = "Top 10 Long-Term Picks"
    ws["D17"].font = Font(bold=True, color=WHITE)
    ws["D17"].fill = PatternFill("solid", fgColor=NAVY)

    ws["D18"] = "Symbol"
    ws["E18"] = "Score"
    ws["F18"] = "Action"

    for c in ws[18][3:6]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor=GREY)

    symbol_col = long_headers.get("Symbol")
    score_col = long_headers.get("Investment Score")
    action_col_lt = long_headers.get("Investment Action")

    if symbol_col and score_col and action_col_lt:
        for i, row in enumerate(range(2, min(long_ws.max_row, 11) + 1), start=19):
            ws[f"D{i}"] = long_ws.cell(row, symbol_col).value
            ws[f"E{i}"] = long_ws.cell(row, score_col).value
            ws[f"F{i}"] = long_ws.cell(row, action_col_lt).value

    for col in range(1, 7):
        ws.column_dimensions[get_column_letter(col)].width = 22

    ws.sheet_view.showGridLines = False


def main():
    if not DASHBOARD.exists():
        raise FileNotFoundError(f"Dashboard not found:\n{DASHBOARD}")

    wb = load_workbook(DASHBOARD)

    if "Option Buying" in wb.sheetnames:
        style_sheet(wb["Option Buying"])
        color_option_rows(wb["Option Buying"])

    if "Long Term" in wb.sheetnames:
        style_sheet(wb["Long Term"])
        color_long_term_rows(wb["Long Term"])

    if "Summary" in wb.sheetnames:
        style_sheet(wb["Summary"])

    if "Option Buying" in wb.sheetnames and "Long Term" in wb.sheetnames:
        create_home_sheet(wb)

    wb.save(DASHBOARD)

    print("Dashboard formatted successfully.")
    print(DASHBOARD)


if __name__ == "__main__":
    main()

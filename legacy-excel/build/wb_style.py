"""Shared visual style for magnet's Tower Tool (dark sci-fi HUD theme)."""
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

FONT = "Segoe UI"

BG = "0A0E14"        # near-black page
PANEL = "111823"     # panel body
PANEL2 = "16202D"    # alternate rows / tiles
EDGE = "243447"      # subtle borders
CYAN = "00E5FF"
CYAN_DIM = "0E7C8C"
VIOLET = "A78BFA"
VIOLET_DIM = "4C3A8C"
TEXT = "E6EDF3"
MUTED = "8B98A5"
GREEN = "34D399"
AMBER = "FBBF24"
RED = "F87171"
INPUT_BG = "1B2A3D"
INPUT_TXT = "FFFFFF"


def fill(c):
    return PatternFill("solid", start_color=c, end_color=c)


def font(color=TEXT, size=10, bold=False, italic=False, name=FONT):
    return Font(name=name, size=size, bold=bold, italic=italic, color=color)


thin = lambda c=EDGE: Side(style="thin", color=c)  # noqa: E731
BOX = Border(left=thin(), right=thin(), top=thin(), bottom=thin())
INPUT_BORDER = Border(left=thin(CYAN_DIM), right=thin(CYAN_DIM), top=thin(CYAN_DIM), bottom=thin(CYAN))
UNDER = Border(bottom=thin())
UNDER_CYAN = Border(bottom=Side(style="medium", color=CYAN))
UNDER_VIOLET = Border(bottom=Side(style="medium", color=VIOLET))

LEFT = Alignment(horizontal="left", vertical="center", indent=1)
LEFTW = Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1)
TOPW = Alignment(horizontal="left", vertical="top", wrap_text=True, indent=1)
CENTER = Alignment(horizontal="center", vertical="center")
RIGHT = Alignment(horizontal="right", vertical="center", indent=1)


def paint(ws, rng, bg=BG):
    for row in ws[rng]:
        for c in row:
            c.fill = fill(bg)


def setup_sheet(ws, tab_color=CYAN, zoom=90, widths=None, rows=200, cols=40):
    ws.sheet_view.showGridLines = False
    ws.sheet_view.zoomScale = zoom
    ws.sheet_properties.tabColor = tab_color
    from openpyxl.utils import get_column_letter
    for c in range(1, cols + 1):
        ws.column_dimensions[get_column_letter(c)].width = 3
    if widths:
        for k, v in widths.items():
            ws.column_dimensions[k].width = v
    # page background
    for r in range(1, rows + 1):
        for c in range(1, cols + 1):
            ws.cell(r, c).fill = fill(BG)


def title_bar(ws, row, col, text, sub=None, size=20, color=CYAN):
    c = ws.cell(row, col, text)
    c.font = font(color, size, True)
    c.alignment = Alignment(vertical="center")
    if sub:
        s = ws.cell(row + 1, col, sub)
        s.font = font(MUTED, 10, italic=True)
    ws.row_dimensions[row].height = size * 1.7


def section(ws, row, col, text, span=8, color=CYAN, bg=BG):
    c = ws.cell(row, col, text)
    c.font = font(color, 12, True)
    for i in range(span):
        ws.cell(row, col + i).border = UNDER_CYAN if color == CYAN else UNDER_VIOLET
        ws.cell(row, col + i).fill = fill(bg)
    ws.row_dimensions[row].height = 22


def header_row(ws, row, col, labels, bg=PANEL2, color=CYAN, height=30):
    for i, t in enumerate(labels):
        c = ws.cell(row, col + i, t)
        c.font = font(color, 9, True)
        c.fill = fill(bg)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = Border(bottom=Side(style="medium", color=color))
    ws.row_dimensions[row].height = height


def body(c, color=TEXT, bg=PANEL, bold=False, align=LEFT, size=10, fmt=None):
    c.font = font(color, size, bold)
    c.fill = fill(bg)
    c.alignment = align
    c.border = Border(bottom=thin("1C2837"))
    if fmt:
        c.number_format = fmt


def input_cell(c, fmt=None, align=RIGHT):
    c.font = font(INPUT_TXT, 10, True)
    c.fill = fill(INPUT_BG)
    c.border = INPUT_BORDER
    c.alignment = align
    if fmt:
        c.number_format = fmt

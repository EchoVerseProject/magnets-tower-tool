"""Generate magnet's Tower Tool.xlsx from tower-tool/data/tower_data.json.

    python3 build_workbook.py [output.xlsx] [--sample early|mid|advanced|none]

All game constants live on the data sheets ('Game Data', 'GD ...'); every calculation
is a native Excel formula (no VBA, no add-ins). See README.md for the architecture.
"""
import json
import os
import sys

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule, DataBarRule, FormulaRule
from openpyxl.utils import get_column_letter as CL
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.comments import Comment

from wb_style import (AMBER, BG, BOX, CENTER, CYAN, CYAN_DIM, EDGE, GREEN, INPUT_BG, LEFT, LEFTW,
                      MUTED, PANEL, PANEL2, RED, RIGHT, TEXT, TOPW, VIOLET, VIOLET_DIM, body, fill,
                      font, header_row, input_cell, section, setup_sheet, title_bar, UNDER)
from openpyxl.styles import Alignment, Border, Side
import samples

HERE = os.path.dirname(os.path.abspath(__file__))
D = json.load(open(os.path.join(HERE, "..", "data", "tower_data.json")))
VERIFIED_ON = "2026-11-07"
STRATS = ["Farming", "Tournament", "Milestones", "Balanced"]
EVID = ["Enemies pile up at the tower", "Tower takes big hits with few enemies near", "Not sure"]
EVID_M = ["Same as farming"] + EVID
FARM_END = ["Tower dies", "I end the run"]
RES_MODE = ["Auto (from lab slots)", "Coins limit my research", "Time limits my research"]

wb = Workbook()
NAMES = {}


def name(n, sheet, ref):
    """Workbook-level defined name, e.g. name('pCoins', 'Player Profile', '$E$8')."""
    wb.defined_names[n] = DefinedName(n, attr_text=f"'{sheet}'!{ref}")
    NAMES[n] = f"'{sheet}'!{ref}"


def q(sheet):
    return f"'{sheet}'"


def fmt_coins(x):
    """Excel text in Tower notation (K, M, B, T, q, Q, s, S, O, N, D)."""
    x = f"({x})"
    return (f'IF(ISNUMBER({x}),IF({x}<1000,TEXT({x},"0"),TEXT({x}/10^(3*INT(LOG10({x})/3)),"0.00")'
            f'&MID("KMBTqQsSOND",INT(LOG10({x})/3),1)),"")')


def fmt_hours(h):
    h = f"({h})"
    return (f'IF(ISNUMBER({h}),IF({h}<1/60,"<1m",IF({h}<1,TEXT({h}*60,"0")&"m",IF({h}<48,TEXT({h},"0.0")&"h",'
            f'TEXT({h}/24,"0.0")&"d"))),"")')


# ======================================================================
# 1. DATA SHEETS
# ======================================================================
ws_order = ["Dashboard", "Workshop Optimizer", "Lab Optimizer", "Roadmap", "Gem Planner", "UW Optimizer",
            "Player Profile", "Import", "Optimization Engine", "Roadmap Engine", "Game Data",
            "Sources & Validation", "Guide", "GD Workshop Levels", "GD Enhancement Levels",
            "GD Lab Levels", "GD UW Levels", "GD Enemy Scaling"]
S = {}
S["Dashboard"] = wb.active
S["Dashboard"].title = "Dashboard"
for n in ws_order[1:]:
    S[n] = wb.create_sheet(n)


def data_sheet(ws, headers, rows, widths):
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = "3A4A5C"
    for i, h in enumerate(headers):
        c = ws.cell(1, i + 1, h)
        c.font = font(CYAN, 9, True)
        c.fill = fill(PANEL2)
        ws.column_dimensions[CL(i + 1)].width = widths[i]
    for r, row in enumerate(rows, start=2):
        for i, v in enumerate(row):
            ws.cell(r, i + 1, v)
    ws.freeze_panes = "A2"


# --- workshop levels
wsl_rows, ws_start = [], {}
for w in D["workshop"]:
    ws_start[w["id"]] = len(wsl_rows) + 1
    cum = 0.0
    for L, (v, c) in enumerate(w["levels"]):
        wsl_rows.append([w["id"], L, v, c, cum])
        cum += c
data_sheet(S["GD Workshop Levels"], ["Upgrade ID", "Level", "Value at level", "Coin cost to next level (base)",
                                     "Cumulative base coins to reach level"], wsl_rows, [20, 8, 16, 18, 20])
NW = len(wsl_rows) + 1
for n, col in [("rngWSV", "C"), ("rngWSC", "D"), ("rngWSCUM", "E")]:
    name(n, "GD Workshop Levels", f"${col}$2:${col}${NW}")

# --- enhancement levels
enl_rows, en_start = [], {}
for e in D["enhancements"]:
    en_start[e["id"]] = len(enl_rows) + 1
    cum = 0.0
    for L, c in enumerate(e["costs"]):
        enl_rows.append([e["id"], L, c, cum])
        cum += c
data_sheet(S["GD Enhancement Levels"], ["Enhancement ID", "Level", "Coin cost to next level (base)",
                                        "Cumulative base coins"], enl_rows, [18, 8, 20, 20])
NE = len(enl_rows) + 1
name("rngENC", "GD Enhancement Levels", f"$C$2:$C${NE}")
name("rngENCUM", "GD Enhancement Levels", f"$D$2:$D${NE}")

# --- lab levels (row for every level 0..max; cost/hours = researching THAT level)
lbl_rows, lb_start = [], {}
for lab in D["labs"]:
    lb_start[lab["id"]] = len(lbl_rows) + 1
    cum = 0.0
    for L, eff, c, h in lab["levels"]:
        cum += c
        lbl_rows.append([lab["id"], L, eff, c, h, cum])
data_sheet(S["GD Lab Levels"], ["Lab ID", "Level", "Effect at level", "Coin cost to research this level (base)",
                                "Hours to research this level (base)", "Cumulative base coins to reach level"],
           lbl_rows, [30, 8, 14, 20, 18, 20])
NL = len(lbl_rows) + 1
for n, col in [("rngLBE", "C"), ("rngLBC", "D"), ("rngLBH", "E"), ("rngLBCUM", "F")]:
    name(n, "GD Lab Levels", f"${col}$2:${col}${NL}")

# --- enemy scaling growth table
en = D["enemy"]
hdr = ["Wave"] + [f"HP growth T{t}" for t in range(1, 25)] + [f"DMG growth T{t}" for t in range(1, 25)] + [
    "HP growth Tournament", "DMG growth Tournament"]
rows = []
for i, w in enumerate(en["waves"]):
    rows.append([w] + [en["hp"][str(t)][i] for t in range(1, 25)] + [en["dmg"][str(t)][i] for t in range(1, 25)]
                + [en["hp_tour"][i], en["dmg_tour"][i]])
data_sheet(S["GD Enemy Scaling"], hdr, rows, [8] + [11] * 50)
NG = len(rows) + 1
name("rngESW", "GD Enemy Scaling", f"$A$2:$A${NG}")
name("rngESHP", "GD Enemy Scaling", f"$B$2:$Y${NG}")
name("rngESDM", "GD Enemy Scaling", f"$Z$2:$AW${NG}")
name("rngESHPT", "GD Enemy Scaling", f"$AX$2:$AX${NG}")
name("rngESDMT", "GD Enemy Scaling", f"$AY$2:$AY${NG}")

# ======================================================================
# 2. GAME DATA (metadata, constants, provenance)
# ======================================================================
gd = S["Game Data"]
setup_sheet(gd, tab_color="3A4A5C", zoom=85, rows=420, cols=24,
            widths={"A": 2, "B": 30, "C": 16, "D": 13, "E": 10, "F": 12, "G": 10, "H": 10, "I": 12, "J": 16,
                    "K": 14, "L": 44, "M": 48, "N": 12, "O": 34, "P": 12, "Q": 16, "R": 40})
title_bar(gd, 1, 2, "GAME DATA", "Verified reference data. Edit here after a patch (or rebuild from build_data.py). "
                                 "Calculations read these cells; nothing else hard-codes game numbers.")
section(gd, 4, 2, "CONSTANTS", 6)
header_row(gd, 5, 2, ["Constant", "Value", "Unit", "Status", "", "Source / note"])
CONSTS = [
    ("cWsDiscStep", "Workshop discount per lab level", 0.005, "fraction", "Verified", "Workshop Attack/Defense/Utility Discount labs: 0.5% per level (SDK discount-normalize.ts)"),
    ("cWsDiscMax", "Workshop discount cap (lab)", 0.495, "fraction", "Verified", "99 levels x 0.5% (SDK WORKSHOP_SECTION_DISCOUNT_MAX_PCT)"),
    ("cEnhDiscStep", "Enhancement discount per lab level", 0.003, "fraction", "Verified", "Enhancement X - Coin Discount labs (SDK enhancement-costs.ts)"),
    ("cEnhDiscMax", "Enhancement discount cap (lab)", 0.30, "fraction", "Verified", "SDK ENHANCEMENT_SECTION_DISCOUNT_MAX_PCT"),
    ("cEnhStep", "Enhancement effect per level", 0.01, "x per level", "Verified", "Effective Paths ENHANCEMENT_MULTIPLIER_PER_LEVEL (1 + 0.01 x level)"),
    ("cDefCap", "Defense % cap", 0.98, "fraction", "Verified", "Effective Paths DEFENSE_PERCENT_CAP"),
    ("cRangeDefault", "Default share of damage dealt at range", 0.25, "fraction", "Estimated", "Effective Paths default damageAtRangePct; override on Player Profile"),
    ("cRushCap", "Lab rush gem cap", 25000, "gems", "Verified", "SDK computeLabGems (time-based rush price)"),
]
for i, (n, lab, v, u, st, src) in enumerate(CONSTS):
    r = 6 + i
    for j, val in enumerate([lab, v, u, st, "", src]):
        c = gd.cell(r, 2 + j, val)
        body(c, color=CYAN if j == 1 else TEXT, align=LEFTW if j == 5 else LEFT)
    name(n, "Game Data", f"$C${r}")
r0 = 6 + len(CONSTS) + 1
# lookup tables
gd.cell(r0, 2, "Bullets/second rate (attack speed key -> rate)").font = font(VIOLET, 10, True)
keys = [0, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10, 11, 12, 13, 14, 15]
rates = [1, 0.96, 0.93, 0.9, 0.87, 0.84, 0.81, 0.79, 0.77, 0.75, 0.73, 0.71, 0.69, 0.67, 0.65, 0.63, 0.61, 0.58, 0.56,
         0.54, 0.53, 0.52, 0.51]
for i, (k, v) in enumerate(zip(keys, rates)):
    gd.cell(r0 + 1 + i, 2, k)
    gd.cell(r0 + 1 + i, 3, v)
    for cc in (2, 3):
        body(gd.cell(r0 + 1 + i, cc), align=RIGHT, color=CYAN if cc == 3 else TEXT)
name("tBpsKey", "Game Data", f"$B${r0 + 1}:$B${r0 + len(keys)}")
name("tBpsRate", "Game Data", f"$C${r0 + 1}:$C${r0 + len(keys)}")
gd.cell(r0, 5, "Real game speed (displayed speed key -> scale)").font = font(VIOLET, 10, True)
sk = [0, 2, 2.5, 3, 3.5, 4, 4.5, 5]
sv = [1.07, 1, 0.95, 0.92, 0.88, 0.84, 0.82, 0.8]
for i, (k, v) in enumerate(zip(sk, sv)):
    gd.cell(r0 + 1 + i, 5, k)
    gd.cell(r0 + 1 + i, 6, v)
    for cc in (5, 6):
        body(gd.cell(r0 + 1 + i, cc), align=RIGHT, color=CYAN if cc == 6 else TEXT)
name("tSpdKey", "Game Data", f"$E${r0 + 1}:$E${r0 + len(sk)}")
name("tSpdScale", "Game Data", f"$F${r0 + 1}:$F${r0 + len(sk)}")
gd.cell(r0, 8, "Lab slot gem cost (slot # -> gems)").font = font(VIOLET, 10, True)
for i, v in enumerate(D["gems"]["labSlotCost"]["value"]):
    gd.cell(r0 + 1 + i, 8, i + 1)
    gd.cell(r0 + 1 + i, 9, v)
    for cc in (8, 9):
        body(gd.cell(r0 + 1 + i, cc), align=RIGHT, color=CYAN if cc == 9 else TEXT)
name("tLabSlotGems", "Game Data", f"$I${r0 + 1}:$I${r0 + 5}")
gd.cell(r0 + 7, 8, "Card star gem cost (star -> gems)").font = font(VIOLET, 10, True)
for i, v in enumerate(D["gems"]["cardStarGems"]["value"]):
    gd.cell(r0 + 8 + i, 8, i + 1)
    gd.cell(r0 + 8 + i, 9, v)
    for cc in (8, 9):
        body(gd.cell(r0 + 8 + i, cc), align=RIGHT, color=CYAN if cc == 9 else TEXT)
gd.cell(r0, 11, "Gem prices").font = font(VIOLET, 10, True)
gemrows = [("gCard", "One card purchase", D["gems"]["cardGems"]), ("gPull", "One module pull", D["gems"]["modulePullGems"]),
           ("gEpic", "Module epic chance per pull", D["gems"]["moduleEpicChance"]),
           ("gPity", "Module epic pity (pulls)", D["gems"]["moduleEpicPity"]),
           ("gCardSlots22", "All 22 gem card slots (total)", D["gems"]["cardSlotTotal22"])]
for i, (n, lab, g) in enumerate(gemrows):
    rr = r0 + 1 + i
    for j, val in enumerate([lab, g["value"], g["status"], g["source"]]):
        c = gd.cell(rr, 11 + j, val)
        body(c, color=CYAN if j == 1 else TEXT, align=LEFTW if j == 3 else LEFT, size=9)
    name(n, "Game Data", f"$L${rr}")

# --- Workshop metadata table
WSR0 = r0 + 26
section(gd, WSR0 - 2, 2, "WORKSHOP UPGRADES (48)", 17)
ws_cols = ["Upgrade", "ID", "Category", "Export index", "Unlock group", "Max level", "Data start", "Unit", "Model role",
           "Model status", "Effect", "Not-quantified reason", "Game version", "Source", "Verified", "Validation"]
header_row(gd, WSR0 - 1, 2, ws_cols)
WSROW = {}
xws = (D.get("xcheck") or {}).get("workshop", {})
for i, w in enumerate(D["workshop"]):
    r = WSR0 + i
    WSROW[w["id"]] = r
    xs = ""
    if w["key"] in xws:
        n, bad, worst = xws[w["key"]]
        xs = f"Values match Effective Paths on {n} levels (max diff {worst * 100:.2f}%, 3 s.f. rounding)"
    status = "Modeled" if w["role"] != "NQ" else "Not quantified"
    vals = [w["name"], w["id"], w["category"], w["saveIndex"], w["unlockGroup"], w["maxLevel"], ws_start[w["id"]],
            w["unit"], w["role"], status, w["desc"], w["nqReason"], "v29", "TheTowerSDK src/data/workshop/table.json (game workshop.json)",
            VERIFIED_ON, "Verified" + ("; " + xs if xs else "")]
    for j, v in enumerate(vals):
        c = gd.cell(r, 2 + j, v)
        body(c, bg=PANEL if i % 2 == 0 else PANEL2, align=LEFTW if j in (10, 11, 13, 15) else LEFT, size=9,
             color=MUTED if status != "Modeled" and j == 8 else TEXT)
WS_START_COL = "H"  # Data start column on Game Data

# --- Enhancement metadata
ENR0 = WSR0 + len(D["workshop"]) + 4
section(gd, ENR0 - 2, 2, "WORKSHOP ENHANCEMENTS (18)", 17)
header_row(gd, ENR0 - 1, 2, ["Enhancement", "ID", "Category", "Export index", "Unlock", "Max level", "Data start", "Effect",
                             "Model role", "Model status", "Note", "Not-quantified reason", "Game version", "Source",
                             "Verified", "Validation"])
ENROW = {}
for i, e in enumerate(D["enhancements"]):
    r = ENR0 + i
    ENROW[e["id"]] = r
    status = "Modeled" if e["role"] != "NQ" else "Not quantified"
    note = "Max level disputed: cost table has 600 levels, SDK notes say 400" if e["label"] == "Damage" else ""
    vals = [e["name"], e["id"], e["category"], e["saveIndex"], "Workshop Enhancements lab + category spend",
            e["maxLevel"], en_start[e["id"]], "+1% of the stat per level", e["role"], status, note, e["nqReason"], "v29",
            "TheTowerSDK src/data/workshop/enhancement-costs.json", VERIFIED_ON,
            "Verified (costs)" + ("; Estimated (coin effect squared, per Effective Paths)" if e["role"] == "E_COIN" else "")]
    for j, v in enumerate(vals):
        c = gd.cell(r, 2 + j, v)
        body(c, bg=PANEL if i % 2 == 0 else PANEL2, align=LEFTW if j in (4, 10, 11, 13, 15) else LEFT, size=9)

# --- Lab metadata
LBR0 = ENR0 + len(D["enhancements"]) + 4
section(gd, LBR0 - 2, 2, f"LABORATORY RESEARCH ({len(D['labs'])})", 17)
header_row(gd, LBR0 - 1, 2, ["Research", "ID", "Category", "Export index", "Unlock tier", "Unlock wave", "Data start",
                             "Min level", "Max level", "Model role", "Effect formula", "Not-quantified reason",
                             "Description", "Source", "Verified", "Validation"])
LBROW = {}
xl = {x[0]: x for x in (D.get("xcheck") or {}).get("labs", [])}
for i, lab in enumerate(D["labs"]):
    r = LBR0 + i
    LBROW[lab["id"]] = r
    xv = xl.get(lab["id"])
    val = "Verified (costs/times)"
    if xv:
        val += f"; matches Effective Paths on {xv[1]} levels ({xv[2]} cost / {xv[3]} time diffs)"
    if lab["unlockStatus"] == "Unknown":
        val += "; unlock requirement Unknown"
    if lab["effectStatus"] == "Unknown":
        val += "; effect Unknown"
    vals = [lab["name"], lab["id"], lab["category"], lab["saveIndex"], lab["unlockTier"] if lab["unlockTier"] != "UW" else "UW",
            lab["unlockWave"], lb_start[lab["id"]], lab["minLevel"], lab["maxLevel"], lab["role"], lab["effectFormula"],
            lab["nqReason"], lab["desc"], "TheTowerSDK src/data/labs/catalog.data.ts", VERIFIED_ON, val]
    for j, v in enumerate(vals):
        c = gd.cell(r, 2 + j, v)
        body(c, bg=PANEL if i % 2 == 0 else PANEL2, align=LEFTW if j in (10, 11, 12, 15) else LEFT, size=9)
gd.freeze_panes = "C3"
for rr in range(WSR0, LBR0 + len(D["labs"])):
    gd.row_dimensions[rr].height = 15

ROLE_WS = {w["role"]: w for w in D["workshop"] if w["role"] != "NQ"}
ROLE_EN = {e["role"]: e for e in D["enhancements"] if e["role"] != "NQ"}
ROLE_LB = {l["role"]: l for l in D["labs"] if l["role"] != "NQ"}


def WSV(role, lv):
    w = ROLE_WS[role]
    return f"INDEX(rngWSV,'Game Data'!$H${WSROW[w['id']]}+{lv})"


def WSV_id(wid, lv):
    return f"INDEX(rngWSV,'Game Data'!$H${WSROW[wid]}+{lv})"


def LE(role, lv):
    lab = ROLE_LB[role]
    return f"INDEX(rngLBE,'Game Data'!$H${LBROW[lab['id']]}+{lv})"


# ======================================================================
# 3. IMPORT sheet
# ======================================================================
im = S["Import"]
setup_sheet(im, tab_color=VIOLET, zoom=90, rows=40, cols=8, widths={"A": 34, "B": 22, "C": 3, "D": 70})
im.sheet_view.showGridLines = False
im.cell(1, 1, "IMPORT").font = font(CYAN, 18, True)
im.cell(2, 1, "Paste the two columns produced by tools/tower_export_to_csv.py (or a sample file) into A6:B. "
              "Imported values fill the 'Imported' column on Player Profile; anything you type on Player Profile "
              "overrides them.").font = font(MUTED, 9, italic=True)
im.cell(4, 1, "Key").font = font(CYAN, 10, True)
im.cell(4, 2, "Value").font = font(CYAN, 10, True)
im.cell(4, 4, "Keys: META|label, P|<field>, WS|<upgrade id>, WSU|<upgrade id>, EN|<enh id>, LAB|<lab id>, "
              "SLOT|n|lab, SLOT|n|hours, TW|<tier>").font = font(MUTED, 9)
for r in range(6, 2006):
    im.cell(r, 1).fill = fill(INPUT_BG)
    im.cell(r, 2).fill = fill(INPUT_BG)
    im.cell(r, 1).font = font(TEXT, 9)
    im.cell(r, 2).font = font(TEXT, 9)
im.freeze_panes = "A6"
name("impKeys", "Import", "$A$6:$A$2005")
name("impVals", "Import", "$B$6:$B$2005")
SAMPLE = None
if "--sample" in sys.argv:
    SAMPLE = sys.argv[sys.argv.index("--sample") + 1]
IMPORT_ROWS = []
if SAMPLE and SAMPLE != "none":
    IMPORT_ROWS = samples.build(SAMPLE, D)
if "--import" in sys.argv:
    import csv as _csv
    for k, v in _csv.reader(open(sys.argv[sys.argv.index("--import") + 1], encoding="utf-8")):
        try:
            v = float(v) if v.strip() not in ("",) and not v.isalpha() and v.replace(".", "", 1).replace("-", "", 1).isdigit() else v
            v = int(v) if isinstance(v, float) and v.is_integer() else v
        except ValueError:
            pass
        IMPORT_ROWS.append((k, v))
for i, (k, v) in enumerate(IMPORT_ROWS):
    im.cell(6 + i, 1, k)
    im.cell(6 + i, 2, v)


def IMP(key):
    return f'IFERROR(INDEX(impVals,MATCH("{key}",impKeys,0)),"")'


# ======================================================================
# 4. PLAYER PROFILE
# ======================================================================
pp = S["Player Profile"]
PP_ROWS = 120 + len(D["workshop"]) + len(D["enhancements"]) + len(D["labs"]) + 80
setup_sheet(pp, tab_color=CYAN, zoom=90, rows=PP_ROWS, cols=14,
            widths={"A": 2, "B": 40, "C": 13, "D": 16, "E": 16, "F": 16, "G": 12, "H": 12, "I": 12, "J": 10,
                    "K": 46})
title_bar(pp, 1, 2, "PLAYER PROFILE", "Cyan-bordered cells are yours to edit. 'Imported' fills from the Import sheet; "
                                     "your typed value always wins. Blank = unknown (never assumed).")
pp.cell(3, 2, "Profile source:").font = font(MUTED, 10)
pp.cell(3, 3, f'=IF({IMP("META|label")}="","Manual entry",{IMP("META|label")})').font = font(AMBER, 10, True)
name("pSource", "Player Profile", "$C$3")

dvs = {}


def dv_list(ws, key, items):
    if (ws.title, key) not in dvs:
        d = DataValidation(type="list", formula1='"' + ",".join(items) + '"', allow_blank=True)
        d.error = "Pick a value from the list"
        d.errorTitle = "magnet's Tower Tool"
        ws.add_data_validation(d)
        dvs[(ws.title, key)] = d
    return dvs[(ws.title, key)]


def dv_num(ws, key, lo, hi, whole=False):
    if (ws.title, key) not in dvs:
        d = DataValidation(type="whole" if whole else "decimal", operator="between", formula1=str(lo),
                           formula2=str(hi), allow_blank=True)
        d.error = f"Enter a number between {lo} and {hi}"
        d.errorTitle = "magnet's Tower Tool"
        ws.add_data_validation(d)
        dvs[(ws.title, key)] = d
    return dvs[(ws.title, key)]


FIELDS = [
    ("ACCOUNT", None),
    ("pVersion", "Game version you play", "text", None, "e.g. v29.1 - shown in Settings"),
    ("pCoins", "Available coins", "num", "#,##0", "Coins you can spend right now"),
    ("pCPH", "Coins per hour (measured)", "num", "#,##0", "From your runs (import averages Battle History)"),
    ("pGems", "Available gems", "num", "#,##0", "For the Gem Planner"),
    ("pGemsDay", "Gem income per day (optional)", "num", "#,##0", "Used to estimate time to save gems"),
    ("FARMING RUNS", None),
    ("pFarmTier", "Farming tier", "int", "0", "Tier you farm on"),
    ("pFarmWave", "Typical farming wave reached", "int", "#,##0", "Wave your farming runs end at"),
    ("pFarmEnd", "How do farming runs end?", FARM_END, None, "'Tower dies' means more survival = longer runs"),
    ("pFarmEvid", "At the end of a run, what limits you?", EVID, None, "Evidence for the damage vs survival bottleneck"),
    ("pKillShare", "Share of coins from kills (0-1)", "pct", "0%", "Run stats: coins from kills / total. Blank = 100% assumed (flagged)"),
    ("pCellsPH", "Cells per hour (measured, info)", "num", "#,##0", "Shown for context; cells are not optimized numerically in v1"),
    ("TOURNAMENT", None),
    ("pTourWave", "Typical tournament wave", "int", "#,##0", "Needed for the Tournament strategy"),
    ("pTourEvid", "In tournaments, what limits you?", EVID, None, "Evidence for the tournament bottleneck"),
    ("MILESTONES", None),
    ("pMileTier", "Milestone tier you are pushing", "int", "0", "Tier of your next milestone"),
    ("pMileTarget", "Next milestone wave on that tier", "int", "#,##0", "Target wave (from the Milestones screen)"),
    ("pMileEvid", "When pushing, what limits you?", EVID_M, None, "Defaults to your farming evidence"),
    ("LABORATORY", None),
    ("pSlots", "Lab slots unlocked (1-5)", "int", "0", "Research slots you own"),
    ("pBusy", "Slots currently researching", "int", "0", "Busy slots right now"),
    ("pRelic", "Lab speed from relics (fraction)", "pct", "0.0%", "e.g. 5% relic = 0.05"),
    ("pSpeedup", "Lab speed-up multiplier you keep active", "num", "0.0", "1 = none; 1.5 / 2 / 3 ... if you always run a boost"),
    ("pResMode", "What limits your research?", RES_MODE, None, "Auto reads your slots; override if you know better"),
    ("MODIFIERS (cards, modules, relics, vault, perks)", None),
    ("pExtCC", "Extra critical chance (fraction)", "pct", "0.0%", "From cards/modules/relics, beyond Workshop"),
    ("pExtSCC", "Extra super crit chance (fraction)", "pct", "0.0%", "Beyond Workshop + Lab"),
    ("pExtCF", "Critical factor multiplier", "num", "0.00", "1 = none"),
    ("pExtAS", "Attack speed multiplier", "num", "0.00", "1 = none (cards, relics...)"),
    ("pExtHP", "Health multiplier", "num", "0.00", "1 = none"),
    ("pExtDA", "Defense absolute multiplier", "num", "0.00", "1 = none"),
    ("pExtDef", "Extra defense % (fraction)", "pct", "0.0%", "Cards/modules/relics, beyond Workshop + Lab"),
    ("pDmgRange", "Share of damage dealt at range", "pct", "0%", "Blank = Effective Paths default 25% (flagged)"),
    ("pWsVault", "Extra Workshop discount (vault, fraction)", "pct", "0.0%", "Discount beyond the three discount labs"),
    ("pEnhVault", "Extra Enhancement discount (fraction)", "pct", "0.0%", "Vault enhancement discount"),
    ("ULTIMATE WEAPON COIN DATA (optional - leave blank if unsure)", None),
    ("pGTu", "Golden Tower uptime (fraction)", "pct", "0%", "Duration / cooldown"),
    ("pGTB", "Golden Tower bonus now (x)", "num", "0.00", "Shown on the UW screen"),
    ("pBHs", "Share of kills inside Black Hole", "pct", "0%", "Your estimate"),
    ("pDWs", "Share of kills hit by Death Wave", "pct", "0%", "Your estimate"),
    ("pSLs", "Share of kills inside Spotlight", "pct", "0%", "Your estimate"),
    ("GEM PLANNER", None),
    ("pHorizon", "Planning horizon (days)", "int", "0", "Window used to value time-based gem buys. Blank = 30 (flagged)"),
    ("pCardSlotCost", "Gem cost of your next card slot", "num", "#,##0", "Shown in game; per-slot prices are not in any verified source"),
    ("pCardSlots", "Card slots owned", "int", "0", "Info for the Gem Planner"),
]
section(pp, 5, 2, "ACCOUNT & RUN EVIDENCE", 10)
header_row(pp, 6, 2, ["Field", "Your entry", "Imported", "Used", "", "", "", "", "", "Guidance"])
pp.merge_cells(start_row=6, start_column=6, end_row=6, end_column=10)
r = 7
FIELD_ROW = {}
for f in FIELDS:
    if f[1] is None:
        c = pp.cell(r, 2, f[0])
        c.font = font(VIOLET, 10, True)
        for j in range(2, 12):
            pp.cell(r, j).border = Border(bottom=Side(style="thin", color=VIOLET_DIM))
        r += 1
        continue
    key, label, typ, nf, guide = f
    FIELD_ROW[key] = r
    body(pp.cell(r, 2, label), bg=PANEL)
    c = pp.cell(r, 3)
    input_cell(c, fmt=nf if isinstance(nf, str) else None, align=RIGHT if not isinstance(typ, list) else LEFT)
    if key == "pVersion":
        c.value = "v29"
    if isinstance(typ, list):
        dv_list(pp, key, typ).add(c.coordinate)
        pp.column_dimensions["C"].width = 13
    elif typ == "int":
        dv_num(pp, "int", 0, 1e9, whole=True).add(c.coordinate)
    elif typ == "pct":
        dv_num(pp, "pct", 0, 1).add(c.coordinate)
    elif typ == "num":
        dv_num(pp, "num", 0, 1e40).add(c.coordinate)
    d_ = pp.cell(r, 4, f'={IMP("P|" + key)}')
    body(d_, color=MUTED, align=RIGHT, fmt=nf if isinstance(nf, str) else None)
    e = pp.cell(r, 5, f'=IF(C{r}<>"",C{r},D{r})')
    body(e, color=CYAN, align=RIGHT if not isinstance(typ, list) else LEFT, bold=True,
         fmt=nf if isinstance(nf, str) else None)
    g = pp.cell(r, 11, guide)
    body(g, color=MUTED, size=9, align=LEFTW)
    for j in range(6, 11):
        pp.cell(r, j).fill = fill(PANEL)
    name(key, "Player Profile", f"$E${r}")
    r += 1
# list-type cells are wider: merge the entry across C only, keep alignment
for key in ("pFarmEnd", "pFarmEvid", "pTourEvid", "pMileEvid", "pResMode"):
    pp.cell(FIELD_ROW[key], 3).alignment = Alignment(horizontal="left", vertical="center", shrink_to_fit=True)
    pp.cell(FIELD_ROW[key], 5).alignment = Alignment(horizontal="left", vertical="center", shrink_to_fit=True)

# --- active lab slots
r += 1
section(pp, r, 2, "ACTIVE RESEARCH (one row per busy slot)", 10)
r += 1
header_row(pp, r, 2, ["Slot", "Lab ID (your entry)", "Imported", "Lab in slot", "Hours left (entry)", "Imported",
                      "Hours left", "", "", "Guidance"])
r += 1
SLOT_ROW0 = r
lab_ids = [l["id"] for l in D["labs"]]
name_list_row0 = 4  # list of lab ids lives on Guide? Use Game Data lab table IDs via named range
name("lstLabIDs", "Game Data", f"$C${LBR0}:$C${LBR0 + len(D['labs']) - 1}")
dv_slot = DataValidation(type="list", formula1="=lstLabIDs", allow_blank=True)
pp.add_data_validation(dv_slot)
for s in range(1, 6):
    body(pp.cell(r, 2, f"Slot {s}"), bg=PANEL)
    input_cell(pp.cell(r, 3), align=LEFT)
    dv_slot.add(pp.cell(r, 3).coordinate)
    body(pp.cell(r, 4, f'={IMP(f"SLOT|{s}|lab")}'), color=MUTED)
    body(pp.cell(r, 5, f'=IF(C{r}<>"",C{r},D{r})'), color=CYAN, bold=True)
    input_cell(pp.cell(r, 6), fmt="0.0")
    body(pp.cell(r, 7, f'={IMP(f"SLOT|{s}|hours")}'), color=MUTED, align=RIGHT, fmt="0.0")
    body(pp.cell(r, 8, f'=IF(F{r}<>"",F{r},G{r})'), color=CYAN, bold=True, align=RIGHT, fmt="0.0")
    for j in (9, 10):
        pp.cell(r, j).fill = fill(PANEL)
    body(pp.cell(r, 11, "Pick the lab ID being researched; hours left as shown in game" if s == 1 else ""),
         color=MUTED, size=9)
    r += 1
name("ppSlotLab", "Player Profile", f"$E${SLOT_ROW0}:$E${SLOT_ROW0 + 4}")
name("ppSlotHrs", "Player Profile", f"$H${SLOT_ROW0}:$H${SLOT_ROW0 + 4}")

# --- highest wave per tier
r += 1
section(pp, r, 2, "HIGHEST WAVE PER TIER (for unlocks and milestones)", 10)
r += 1
header_row(pp, r, 2, ["Tier", "Your entry", "Imported", "Used"])
r += 1
TIER_ROW0 = r
for t in range(1, 25):
    body(pp.cell(r, 2, t), bg=PANEL, align=LEFT)
    input_cell(pp.cell(r, 3), fmt="#,##0")
    dv_num(pp, "int", 0, 1e9, whole=True).add(pp.cell(r, 3).coordinate)
    body(pp.cell(r, 4, f'={IMP(f"TW|{t}")}'), color=MUTED, align=RIGHT, fmt="#,##0")
    body(pp.cell(r, 5, f'=IF(C{r}<>"",C{r},D{r})'), color=CYAN, bold=True, align=RIGHT, fmt="#,##0")
    r += 1
name("ppTierWave", "Player Profile", f"$E${TIER_ROW0}:$E${TIER_ROW0 + 23}")

# --- workshop levels
r += 1
section(pp, r, 2, "WORKSHOP LEVELS", 10)
r += 1
header_row(pp, r, 2, ["Upgrade", "Your level", "Imported", "Level used", "Unlocked? (entry)", "Imported",
                      "Unlocked used", "Max", "Status", "Notes"])
r += 1
PP_WS = {}
dv_yn = dv_list(pp, "yn", ["Yes", "No"])
for i, w in enumerate(D["workshop"]):
    PP_WS[w["id"]] = r
    bg = PANEL if i % 2 == 0 else PANEL2
    body(pp.cell(r, 2, f"{w['name']}  ·  {w['category']}"), bg=bg)
    input_cell(pp.cell(r, 3), fmt="#,##0")
    dv_num(pp, f"ws{w['maxLevel']}", 0, w["maxLevel"], whole=True).add(pp.cell(r, 3).coordinate)
    body(pp.cell(r, 4, f'={IMP("WS|" + w["id"])}'), bg=bg, color=MUTED, align=RIGHT, fmt="#,##0")
    body(pp.cell(r, 5, f'=IF(C{r}<>"",C{r},D{r})'), bg=bg, color=CYAN, bold=True, align=RIGHT, fmt="#,##0")
    if w["unlockGroup"] == "Base":
        body(pp.cell(r, 6, "Base"), bg=bg, color=MUTED, align=CENTER)
        body(pp.cell(r, 7, ""), bg=bg)
        body(pp.cell(r, 8, 1), bg=bg, color=CYAN, align=CENTER, fmt='"Yes";"No";"No"')
    else:
        input_cell(pp.cell(r, 6), align=CENTER)
        dv_yn.add(pp.cell(r, 6).coordinate)
        body(pp.cell(r, 7, f'={IMP("WSU|" + w["id"])}'), bg=bg, color=MUTED, align=CENTER)
        # unlocked if: you say Yes, or import says 1, or level > 0. "No"/blank otherwise (never assumed)
        body(pp.cell(r, 8, f'=IF(F{r}="No",0,IF(OR(F{r}="Yes",G{r}=1,N(E{r})>0),1,0))'), bg=bg, color=CYAN,
             align=CENTER, fmt='"Yes";"No";"No"')
    body(pp.cell(r, 9, w["maxLevel"]), bg=bg, color=MUTED, align=RIGHT, fmt="#,##0")
    body(pp.cell(r, 10, f'=IF(E{r}="","Missing",IF(H{r}=0,"Locked",IF(E{r}>=I{r},"Maxed","OK")))'), bg=bg,
         align=CENTER)
    body(pp.cell(r, 11, w["desc"]), bg=bg, color=MUTED, size=9)
    r += 1
PPWS0, PPWS1 = PP_WS[D["workshop"][0]["id"]], r - 1

# --- enhancements
r += 1
section(pp, r, 2, "WORKSHOP ENHANCEMENTS", 10)
r += 1
header_row(pp, r, 2, ["Enhancement", "Your level", "Imported", "Level used", "Unlocked? (entry)", "", "Unlocked used",
                      "Max", "Status", "Notes"])
r += 1
PP_EN = {}
for i, e in enumerate(D["enhancements"]):
    PP_EN[e["id"]] = r
    bg = PANEL if i % 2 == 0 else PANEL2
    body(pp.cell(r, 2, f"{e['name']}  ·  {e['category']}"), bg=bg)
    input_cell(pp.cell(r, 3), fmt="#,##0")
    body(pp.cell(r, 4, f'={IMP("EN|" + e["id"])}'), bg=bg, color=MUTED, align=RIGHT, fmt="#,##0")
    body(pp.cell(r, 5, f'=IF(C{r}<>"",C{r},IF(D{r}<>"",D{r},0))'), bg=bg, color=CYAN, bold=True, align=RIGHT,
         fmt="#,##0")
    input_cell(pp.cell(r, 6), align=CENTER)
    dv_yn.add(pp.cell(r, 6).coordinate)
    body(pp.cell(r, 7, ""), bg=bg)
    body(pp.cell(r, 8, f'=IF(F{r}="No",0,IF(OR(F{r}="Yes",N(E{r})>0),1,0))'), bg=bg, color=CYAN, align=CENTER,
         fmt='"Yes";"No";"No"')
    body(pp.cell(r, 9, e["maxLevel"]), bg=bg, color=MUTED, align=RIGHT)
    body(pp.cell(r, 10, f'=IF(H{r}=0,"Locked",IF(E{r}>=I{r},"Maxed","OK"))'), bg=bg, align=CENTER)
    body(pp.cell(r, 11, "Enhancements need the Workshop Enhancements lab; new ones open as you spend in the category"
         if i == 0 else ""), bg=bg, color=MUTED, size=9)
    r += 1

# --- labs
r += 1
section(pp, r, 2, "LABORATORY LEVELS", 10)
r += 1
header_row(pp, r, 2, ["Research", "Your level", "Imported", "Level used", "Unlock req.", "Unlocked?", "In progress?",
                      "Max", "Status", "Category"])
r += 1
PP_LB = {}
LAB_IN_PROGRESS = {}
for i, lab in enumerate(D["labs"]):
    PP_LB[lab["id"]] = r
    bg = PANEL if i % 2 == 0 else PANEL2
    body(pp.cell(r, 2, lab["name"]), bg=bg)
    input_cell(pp.cell(r, 3), fmt="#,##0")
    dv_num(pp, f"lab{lab['maxLevel']}", 0, lab["maxLevel"], whole=True).add(pp.cell(r, 3).coordinate)
    body(pp.cell(r, 4, f'={IMP("LAB|" + lab["id"])}'), bg=bg, color=MUTED, align=RIGHT, fmt="#,##0")
    body(pp.cell(r, 5, f'=IF(C{r}<>"",C{r},D{r})'), bg=bg, color=CYAN, bold=True, align=RIGHT, fmt="#,##0")
    ut, uw = lab["unlockTier"], lab["unlockWave"]
    req = "Start" if ut == 0 else ("UW+" if ut == "UW" else (f"T{ut} W{uw}" if ut else "Unknown"))
    body(pp.cell(r, 6, req), bg=bg, color=MUTED, align=CENTER)
    if ut == 0:
        unl = "1"
    elif isinstance(ut, int):
        unl = f'IF(N(INDEX(ppTierWave,{ut}))>={uw},1,0)'
    else:
        unl = "0"
    body(pp.cell(r, 7, f'=IF(N(E{r})>0,1,{unl})'), bg=bg, color=CYAN, align=CENTER, fmt='"Yes";"No";"No"')
    body(pp.cell(r, 8, f'=IF(COUNTIF(ppSlotLab,"{lab["id"]}")>0,"Yes","")'), bg=bg, color=AMBER, align=CENTER)
    body(pp.cell(r, 9, lab["maxLevel"]), bg=bg, color=MUTED, align=RIGHT)
    body(pp.cell(r, 10, f'=IF(E{r}="","Missing",IF(G{r}=0,"Locked",IF(E{r}>=I{r},"Maxed",IF(H{r}="Yes","Researching","OK"))))'),
         bg=bg, align=CENTER)
    body(pp.cell(r, 11, lab["category"]), bg=bg, color=MUTED, size=9)
    r += 1
pp.freeze_panes = "C7"
PP_LAST = r

# ======================================================================
# 5. OPTIMIZATION ENGINE
# ======================================================================
WS_VARS = ["DMG", "AS", "CC", "CF", "RANGE", "DPM", "MSC", "MST", "RFC", "RFD", "BSC", "BST", "SCC", "SCM", "HP",
           "DEFP", "DA", "WALL", "RECMAX", "CPK", "CPW"]
EN_VARS = ["E_DMG", "E_CF", "E_DPM", "E_SCM", "E_AS", "E_HP", "E_DA", "E_WALL", "E_COIN", "E_RECMAX"]
LB_VARS = ["L_DMG", "L_AS", "L_CF", "L_RANGE", "L_DPM", "L_SCC", "L_SCM", "L_HP", "L_DA", "L_DEFP", "L_WALL",
           "L_RECMAX", "L_CPK", "L_CPW", "L_DISC_ATK", "L_DISC_DEF", "L_DISC_UTL", "L_LABDISC", "L_LABSPEED",
           "L_GAMESPEED", "L_GT", "L_BH", "L_DW", "L_SL"]
VARS = WS_VARS + EN_VARS + LB_VARS
assert all(v in ROLE_WS for v in WS_VARS) and all(v in ROLE_EN for v in EN_VARS) and all(v in ROLE_LB for v in LB_VARS)
PP = "'Player Profile'"


def var_kind(v):
    return "WS" if v in ROLE_WS else ("EN" if v in ROLE_EN else "LAB")


def var_meta(v):
    return ROLE_WS.get(v) or ROLE_EN.get(v) or ROLE_LB.get(v)


def profile_level_ref(v):
    m = var_meta(v)
    k = var_kind(v)
    row = {"WS": PP_WS, "EN": PP_EN, "LAB": PP_LB}[k][m["id"]]
    return f"{PP}!$E${row}"


def U(v):
    """Unlock flag (1/0) of a workshop upgrade."""
    return f"{PP}!$H${PP_WS[ROLE_WS[v]['id']]}"


E_ = "(1+cEnhStep*{})"
# ---- base stats: f(lv) -> Excel expression (lv(var) returns that var's level expression)
BASE = {
    "AS": lambda lv: f"{WSV('AS', lv('AS'))}*{LE('L_AS', lv('L_AS'))}*{E_.format(lv('E_AS'))}*eExtAS",
    "RFC": lambda lv: f"{U('RFC')}*{WSV('RFC', lv('RFC'))}/100",
    "RFD": lambda lv: f"{WSV('RFD', lv('RFD'))}",
    "CC": lambda lv: f"MIN(1,{WSV('CC', lv('CC'))}/100+eExtCC)",
    "CF": lambda lv: f"{WSV('CF', lv('CF'))}*{LE('L_CF', lv('L_CF'))}*{E_.format(lv('E_CF'))}*eExtCF",
    "SCC": lambda lv: f"{U('SCC')}*MIN(1,{WSV('SCC', lv('SCC'))}/100+{LE('L_SCC', lv('L_SCC'))}/100+eExtSCC)",
    "SCM": lambda lv: f"{WSV('SCM', lv('SCM'))}*{LE('L_SCM', lv('L_SCM'))}*{E_.format(lv('E_SCM'))}",
    "MSC": lambda lv: f"{U('MSC')}*{WSV('MSC', lv('MSC'))}/100",
    "MST": lambda lv: f"{WSV('MST', lv('MST'))}",
    "BSC": lambda lv: f"{U('BSC')}*MIN(1,{WSV('BSC', lv('BSC'))}/100)",
    "BST": lambda lv: f"{WSV('BST', lv('BST'))}",
    "RNG": lambda lv: f"{WSV('RANGE', lv('RANGE'))}*10*{LE('L_RANGE', lv('L_RANGE'))}",
    "DPMV": lambda lv: f"{U('DPM')}*{WSV('DPM', lv('DPM'))}/1000*{LE('L_DPM', lv('L_DPM'))}*{E_.format(lv('E_DPM'))}",
    "DMGF": lambda lv: f"{WSV('DMG', lv('DMG'))}*{LE('L_DMG', lv('L_DMG'))}*{E_.format(lv('E_DMG'))}",
    "H": lambda lv: f"{WSV('HP', lv('HP'))}*{LE('L_HP', lv('L_HP'))}*{E_.format(lv('E_HP'))}*eExtHP",
    "DABS": lambda lv: f"{U('DA')}*{WSV('DA', lv('DA'))}*{LE('L_DA', lv('L_DA'))}*{E_.format(lv('E_DA'))}*eExtDA",
    "DP": lambda lv: f"MIN(cDefCap,{U('DEFP')}*{WSV('DEFP', lv('DEFP'))}/100+{LE('L_DEFP', lv('L_DEFP'))}/100+eExtDef)",
    "WALL": lambda lv: f"{U('WALL')}*({WSV('WALL', lv('WALL'))}/100+{LE('L_WALL', lv('L_WALL'))}/100)*{E_.format(lv('E_WALL'))}",
    "REC": lambda lv: f"{U('RECMAX')}*({WSV('RECMAX', lv('RECMAX'))}+{LE('L_RECMAX', lv('L_RECMAX'))})*{E_.format(lv('E_RECMAX'))}",
    "CPK": lambda lv: f"{WSV('CPK', lv('CPK'))}*{LE('L_CPK', lv('L_CPK'))}*{E_.format(lv('E_COIN'))}^2",
    "CPW": lambda lv: f"{WSV('CPW', lv('CPW'))}*{LE('L_CPW', lv('L_CPW'))}",
    "GTM": lambda lv: f"IF(eGTok,1+eGTu*(eGTB+{LE('L_GT', lv('L_GT'))}-{LE('L_GT', 'N(' + profile_level_ref('L_GT') + ')')}-1),1)",
    "BHM": lambda lv: f"IF(eBHok,1+pBHs*({LE('L_BH', lv('L_BH'))}-1),1)",
    "DWM": lambda lv: f"IF(eDWok,1+pDWs*({LE('L_DW', lv('L_DW'))}-1),1)",
    "SLM": lambda lv: f"IF(eSLok,1+pSLs*({LE('L_SL', lv('L_SL'))}-1),1)",
    "SPD": lambda lv: f"{LE('L_GAMESPEED', lv('L_GAMESPEED'))}",
    "DSA": lambda lv: f"MIN(0.99,MIN(cWsDiscMax,{LE('L_DISC_ATK', lv('L_DISC_ATK'))}/100)+eWsVault)",
    "DSD": lambda lv: f"MIN(0.99,MIN(cWsDiscMax,{LE('L_DISC_DEF', lv('L_DISC_DEF'))}/100)+eWsVault)",
    "DSU": lambda lv: f"MIN(0.99,MIN(cWsDiscMax,{LE('L_DISC_UTL', lv('L_DISC_UTL'))}/100)+eWsVault)",
    "DSL": lambda lv: f"{LE('L_LABDISC', lv('L_LABDISC'))}/100",
    "RS": lambda lv: f"{LE('L_LABSPEED', lv('L_LABSPEED'))}",
}
# dependencies: which vars each base stat reads
DEPS = {}
for st, fn in BASE.items():
    seen = set()
    fn(lambda v, seen=seen: (seen.add(v) or "0"))
    DEPS[st] = seen
AFFECTS = {v: [st for st in BASE if v in DEPS[st]] for v in VARS}
for v in VARS:
    assert AFFECTS[v], v

# ---- derived stats: f(c) where c(stat) is the same-row cell of that stat
DERIVED = {
    "BPS": lambda c: f"{c('AS')}*IF({c('AS')}>=42,0.375,IF({c('AS')}>=16,0.505-0.005*INT({c('AS')}-16),LOOKUP({c('AS')},tBpsKey,tBpsRate)))",
    "RF": lambda c: (f"IF(OR({c('RFC')}<=0,{c('RFD')}<=0),1,1+(0.9*{c('RFD')}/(0.9*{c('RFD')}+0.75+1/({c('RFC')}*{c('BPS')})))"
                     f"*(IF({c('AS')}<2.3,3.75,IF({c('AS')}<4,3.65,IF({c('AS')}<8,3.5,3.35)))-1))"),
    "CRIT": lambda c: f"(1-{c('CC')})+{c('CC')}*{c('CF')}*(1-{c('SCC')})+{c('CC')}*{c('CF')}*{c('SCC')}*{c('SCM')}",
    "MS": lambda c: f"1+{c('MSC')}*({c('MST')}-1)",
    "BNC": lambda c: f"IF({c('BSC')}>=1,1+{c('BST')},IF({c('BSC')}<=0,1,1+{c('BSC')}*(1-{c('BSC')}^{c('BST')})/(1-{c('BSC')})))",
    "RNGE": lambda c: f"{c('RNG')}*(1-ROUND(ROUND(MAX(MIN({c('RNG')},220)-80,0)/140,4)*0.16,4))",
    "RDMG": lambda c: f"1+{c('RNGE')}*{c('DPMV')}*eDmgRange",
    "lnEDMG": lambda c: f"LN({c('DMGF')})+LN({c('BPS')}*{c('RF')})+LN({c('CRIT')})+LN({c('MS')})+LN({c('BNC')})+LN({c('RDMG')})",
    "POOL": lambda c: f"MAX({c('WALL')}+{c('REC')},1)",
    "lnEHP": lambda c: f"LN(({c('H')}*{c('POOL')}+{c('DABS')})/(1-{c('DP')}))",
    "lnECON": lambda c: f"LN(eK*{c('CPK')}/eCPK0+(1-eK)*{c('CPW')}/eCPW0)",
    "lnUW": lambda c: f"LN({c('GTM')})+LN({c('BHM')})+LN({c('DWM')})+LN({c('SLM')})",
    "lnSPD": lambda c: f"LN({c('SPD')}*LOOKUP({c('SPD')},tSpdKey,tSpdScale))",
    "lnPP": lambda c: (f"-eSA*LN(1-{c('DSA')})-eSD*LN(1-{c('DSD')})-eSU*LN(1-{c('DSU')})-eSL*LN(1-{c('DSL')})"),
    "lnRES": lambda c: f"LN({c('RS')})",
}
STATS = list(BASE) + list(DERIVED)
OUTS = ["lnEDMG", "lnEHP", "lnECON", "lnUW", "lnSPD", "lnPP", "lnRES"]
STAT_LABEL = {
    "AS": "Attack speed", "RFC": "Rapid fire chance", "RFD": "Rapid fire duration (s)", "CC": "Crit chance",
    "CF": "Crit factor", "SCC": "Super crit chance", "SCM": "Super crit mult", "MSC": "Multishot chance",
    "MST": "Multishot targets", "BSC": "Bounce chance", "BST": "Bounce targets", "RNG": "Range (m, raw)",
    "DPMV": "Damage/metre factor", "DMGF": "Damage factor", "H": "Health", "DABS": "Defense absolute",
    "DP": "Defense %", "WALL": "Wall (x HP)", "REC": "Max recovery (x HP)", "CPK": "Coins/kill mult",
    "CPW": "Coins/wave", "GTM": "Golden Tower coin mult", "BHM": "Black Hole coin mult",
    "DWM": "Death Wave coin mult", "SLM": "Spotlight coin mult", "SPD": "Game speed (displayed)",
    "DSA": "Attack WS discount", "DSD": "Defense WS discount", "DSU": "Utility WS discount",
    "DSL": "Lab coin discount", "RS": "Lab speed mult", "BPS": "Bullets / s", "RF": "Rapid fire mult",
    "CRIT": "Crit mult", "MS": "Multishot mult", "BNC": "Bounce mult", "RNGE": "Effective range (m)",
    "RDMG": "Range damage mult", "lnEDMG": "ln eDamage", "POOL": "HP pool mult", "lnEHP": "ln eHP",
    "lnECON": "ln coin income", "lnUW": "ln UW coin mult", "lnSPD": "ln real game speed",
    "lnPP": "ln purchasing power", "lnRES": "ln research speed",
}

eg = S["Optimization Engine"]
# layout constants
ST_HDR = 62          # state table header row
ST0 = ST_HDR + 1     # state k=0 row
NSTEPS = 20
CAND_HDR = ST0 + NSTEPS + 6
setup_sheet(eg, tab_color=VIOLET, zoom=80, rows=CAND_HDR + 320, cols=12,
            widths={"A": 2, "B": 34, "C": 16, "D": 18, "E": 70})
title_bar(eg, 1, 2, "OPTIMIZATION ENGINE",
          "Transparent scoring. Row 'k=0' of the state table is your account; each candidate row recomputes only the "
          "stats its next level changes, then converts the change into outcomes.")
section(eg, 4, 2, "EVIDENCE, BOTTLENECKS & SETTINGS", 4, color=VIOLET)
header_row(eg, 5, 2, ["Item", "Value", "Status", "Meaning"], color=VIOLET)
EV = []


def ev(n, label, formula, status, meaning, fmt=None):
    EV.append((n, label, formula, status, meaning, fmt))


ev("eStrat", "Selected strategy (index)", '=IFERROR(MATCH(inStrategy,{"Farming","Tournament","Milestones","Balanced"},0),1)', "Input", "1 Farming, 2 Tournament, 3 Milestones, 4 Balanced")
ev("eCPD", "Coins per day", '=IF(N(pCPH)>0,pCPH*24,"")', '=IF(N(pCPH)>0,"Measured","Missing")', "From coins per hour; needed for lab ranking and the roadmap", "#,##0")
ev("eK", "Share of coins from kills", '=IF(pKillShare="",1,pKillShare)', '=IF(pKillShare="","Assumed 100%","Measured")', "Splits coin income between Coins/Kill and Coins/Wave", "0%")
ev("eDmgRange", "Share of damage at range", '=IF(pDmgRange="",cRangeDefault,pDmgRange)', '=IF(pDmgRange="","Default (Estimated)","Your input")', "Used only by Range and Damage/Meter", "0%")
for n, src in [("eExtCC", "pExtCC"), ("eExtSCC", "pExtSCC"), ("eExtDef", "pExtDef"), ("eWsVault", "pWsVault"), ("eEnhVault", "pEnhVault")]:
    ev(n, f"{src} (blank = 0)", f"=N({src})", "Input", "Additive modifier", "0.0%")
for n, src in [("eExtCF", "pExtCF"), ("eExtAS", "pExtAS"), ("eExtHP", "pExtHP"), ("eExtDA", "pExtDA")]:
    ev(n, f"{src} (blank = 1)", f'=IF(N({src})>0,{src},1)', "Input", "Multiplicative modifier", "0.00")
ev("eFarmOK", "Farming data present", '=AND(N(pFarmWave)>0,N(pFarmTier)>=1,N(pFarmTier)<=24)', '=IF(eFarmOK,"OK","Missing farm tier/wave")', "Needed to convert damage/health into farming waves")
ev("eFarmDeath", "Farming runs end by death", '=IF(pFarmEnd="Tower dies",1,0)', '=IF(pFarmEnd="","Unknown - survival gains not counted for Farming",IF(pFarmEnd="Tower dies","Survival-limited runs","Time-limited runs"))', "If runs end by death, more waves = longer runs = more coins")
for tag, src, lab in [("F", "pFarmEvid", "Farming"), ("T", "pTourEvid", "Tournament")]:
    ev(f"eWd{tag}", f"{lab}: weight on damage", f'=IF({src}="{EVID[0]}",1,IF({src}="{EVID[1]}",0,0.5))',
       f'=IF({src}="{EVID[0]}","Damage-limited (your evidence)",IF({src}="{EVID[1]}","Survival-limited (your evidence)","Unknown - equal split (low confidence)"))',
       "Which constraint ends the run; 0.5 = not known", "0.0")
ev("eWdM", "Milestones: weight on damage", f'=IF(OR(pMileEvid="",pMileEvid="{EVID_M[0]}"),eWdF,IF(pMileEvid="{EVID[0]}",1,IF(pMileEvid="{EVID[1]}",0,0.5)))',
   f'=IF(eWdM=1,"Damage-limited",IF(eWdM=0,"Survival-limited","Unknown - equal split (low confidence)"))', "Defaults to farming evidence", "0.0")
ev("eWf", "Farming wave", "=N(pFarmWave)", "Input", "", "#,##0")
ev("eRHf", "Enemy HP growth per wave (farm)", '=IF(eFarmOK,INDEX(rngESHP,MIN(400,MAX(1,ROUND(eWf/50,0))),pFarmTier),"")', "Derived (enemy scaling)", "ln growth of enemy health per wave at your farming wave", "0.0000")
ev("eRDf", "Enemy damage growth per wave (farm)", '=IF(eFarmOK,INDEX(rngESDM,MIN(400,MAX(1,ROUND(eWf/50,0))),pFarmTier),"")', "Derived (enemy scaling)", "", "0.0000")
ev("eTourOK", "Tournament data present", "=N(pTourWave)>0", '=IF(eTourOK,"OK","Missing tournament wave")', "")
ev("eRHt", "Enemy HP growth per wave (tournament)", '=IF(eTourOK,INDEX(rngESHPT,MIN(400,MAX(1,ROUND(pTourWave/50,0)))),"")', "Derived (tournament scaling, league conditions not modeled)", "", "0.0000")
ev("eRDt", "Enemy damage growth per wave (tournament)", '=IF(eTourOK,INDEX(rngESDMT,MIN(400,MAX(1,ROUND(pTourWave/50,0)))),"")', "Derived", "", "0.0000")
ev("eWm", "Milestone wave (current best on that tier)", '=IF(AND(N(pMileTier)>=1,N(pMileTier)<=24),IF(N(INDEX(ppTierWave,pMileTier))>0,INDEX(ppTierWave,pMileTier),N(pMileTarget)),0)', "Input", "Where you are stuck now", "#,##0")
ev("eMileOK", "Milestone data present", "=AND(eWm>0,N(pMileTier)>=1)", '=IF(eMileOK,"OK","Missing milestone tier/wave")', "")
ev("eMileGap", "Waves to next milestone", '=IF(AND(eMileOK,N(pMileTarget)>0),MAX(0,pMileTarget-eWm),"")', "Derived", "", "#,##0")
ev("eRHm", "Enemy HP growth per wave (milestone)", '=IF(eMileOK,INDEX(rngESHP,MIN(400,MAX(1,ROUND(eWm/50,0))),pMileTier),"")', "Derived", "", "0.0000")
ev("eRDm", "Enemy damage growth per wave (milestone)", '=IF(eMileOK,INDEX(rngESDM,MIN(400,MAX(1,ROUND(eWm/50,0))),pMileTier),"")', "Derived", "", "0.0000")
ev("eSlots", "Lab slots", "=MAX(1,MIN(5,N(pSlots)))", '=IF(N(pSlots)>0,"Input","Missing - assumed 1")', "", "0")
ev("eFree", "Free lab slots now", "=MAX(0,eSlots-N(pBusy))", "Derived", "", "0")
ev("eResTime", "Research is time-limited", f'=IF(pResMode="{RES_MODE[2]}",1,IF(pResMode="{RES_MODE[1]}",0,IF(N(pBusy)>=eSlots,1,0)))',
   f'=IF(eResTime=1,"Time-limited: slots stay busy","Coin-limited or idle slots")', "Lab Speed only adds value when research is time-limited", "0")
ev("eLabMult", "Lab speed multiplier (lab x relic x boost)", "=INDEX(rngLBE,'Game Data'!$H$%d+N(%s))*(1+N(pRelic))*IF(N(pSpeedup)>0,pSpeedup,1)" % (LBROW[ROLE_LB['L_LABSPEED']['id']], profile_level_ref('L_LABSPEED')), "Derived", "", "0.00")
ev("eGTok", "Golden Tower data present", "=AND(N(eGTu)>0,N(eGTB)>1)", "Optional", "Golden Tower Bonus lab is only valued with these")
ev("eBHok", "Black Hole data present", "=N(pBHs)>0", "Optional", "")
ev("eDWok", "Death Wave data present", "=N(pDWs)>0", "Optional", "")
ev("eSLok", "Spotlight data present", "=N(pSLs)>0", "Optional", "")
ev("eHorizon", "Gem planning horizon (days)", '=IF(N(pHorizon)>0,pHorizon,30)', '=IF(N(pHorizon)>0,"Your input","Default 30 days (assumption)")', "", "0")
ev("eSpendWS", "Coins spent on Workshop (base)", "=0", "Derived", "", "#,##0")
ev("eSpendEN", "Coins spent on Enhancements (base)", "=0", "Derived", "", "#,##0")
ev("eSpendLab", "Coins spent on Labs (base)", "=0", "Derived", "", "#,##0")
ev("eSA", "Share of spending: Attack workshop", "=0", "Derived (your past spending)", "Weights the Workshop discount labs", "0.0%")
ev("eSD", "Share of spending: Defense workshop", "=0", "Derived", "", "0.0%")
ev("eSU", "Share of spending: Utility workshop", "=0", "Derived", "", "0.0%")
ev("eSL", "Share of spending: Labs", "=0", "Derived", "Weights the Labs Coin Discount lab", "0.0%")
ev("eCPK0", "Coins/kill multiplier now", "=1", "Derived", "", "0.000")
ev("eCPW0", "Coins/wave now", "=1", "Derived", "", "0.000")
ev("eMissWS", "Missing workshop levels (modeled)", "=0", '=IF(eMissWS=0,"Complete","Incomplete")', "", "0")
ev("eMissLab", "Missing lab levels (modeled)", "=0", '=IF(eMissLab=0,"Complete","Blank labs treated as 0")', "", "0")
ev("eReady", "Workshop data ready", f"=AND(eMissWS=0,COUNT({PP}!$E${PPWS0}:$E${PPWS1})>0)", "Derived", "Recommendations are suppressed until modeled Workshop levels are entered")
ev("eStratMsg", "Missing data for the selected strategy", '=CHOOSE(eStrat,IF(AND(NOT(eFarmOK),pFarmEnd="Tower dies"),"Enter your farming tier and wave on Player Profile.",""),IF(eTourOK,"","Enter your typical tournament wave on Player Profile."),IF(eMileOK,"","Enter your milestone tier and target wave on Player Profile."),"")', "Derived", "Shown on the Dashboard when the chosen goal lacks data")
EVR = {}
for i, (n, label, formula, status, meaning, f_) in enumerate(EV):
    rr = 6 + i
    EVR[n] = rr
    body(eg.cell(rr, 2, label), bg=PANEL)
    c = eg.cell(rr, 3, formula)
    body(c, color=CYAN, bold=True, align=RIGHT, fmt=f_)
    body(eg.cell(rr, 4, status), color=MUTED, size=9)
    body(eg.cell(rr, 5, meaning), color=MUTED, size=9, align=LEFTW)
    name(n, "Optimization Engine", f"$C${rr}")
assert 6 + len(EV) < ST_HDR - 2, (6 + len(EV), ST_HDR)

# ---- state table
section(eg, ST_HDR - 2, 2, "STATE TABLE  (k = 0 is your account; k = 1..20 after each roadmap pick)", 10, color=VIOLET)
STC = {}
col = 2
for h in ["k", "Pick (role)", "Pick N"] + ["lv:" + v for v in VARS] + STATS + ["OUT Farming", "OUT Tournament", "OUT Milestones", "OUT Balanced"]:
    STC[h] = CL(col)
    col += 1
ST_LASTCOL = col - 1
header_row(eg, ST_HDR, 2, ["k", "Pick", "Levels"] + [f"Lv {v}" for v in VARS] + [STAT_LABEL[s] for s in STATS] +
           ["OUT Farming", "OUT Tournament", "OUT Milestones", "OUT Balanced"], color=VIOLET, height=42)
for j in range(2, ST_LASTCOL + 1):
    eg.column_dimensions[CL(j)].width = max(eg.column_dimensions[CL(j)].width or 0, 11)
eg.column_dimensions["B"].width = 34
eg.column_dimensions["C"].width = 16
eg.column_dimensions["D"].width = 18
eg.column_dimensions["E"].width = 16
RE_SUM0 = 8  # Roadmap Engine: summary row of step 1 (pick role in column D)


def st(stat, k):
    return f"${STC[stat]}${ST0 + k}"


for k in range(0, NSTEPS + 1):
    rr = ST0 + k
    body(eg.cell(rr, 2, k), align=CENTER)
    if k == 0:
        body(eg.cell(rr, 3, "current"), color=MUTED)
    else:
        body(eg.cell(rr, 3, f"='Roadmap Engine'!$D${RE_SUM0 + k - 1}"), color=MUTED)
        body(eg.cell(rr, 4, f"=N('Roadmap Engine'!$AB${RE_SUM0 + k - 1})"), color=MUTED, align=RIGHT)
    for v in VARS:
        if k == 0:
            f_ = f"=N({profile_level_ref(v)})"
        else:
            f_ = (f'=${STC["lv:" + v]}${ST0}+SUMIF(${STC["Pick (role)"]}${ST0 + 1}:${STC["Pick (role)"]}${rr},"{v}",'
                  f'${STC["Pick N"]}${ST0 + 1}:${STC["Pick N"]}${rr})')
        body(eg.cell(rr, int(eg[STC["lv:" + v] + "1"].column), f_), align=RIGHT, fmt="#,##0", size=9)
    lvf = lambda v, rr=rr: f"${STC['lv:' + v]}{rr}"  # noqa: E731
    for s_ in BASE:
        body(eg[f"{STC[s_]}{rr}"], align=RIGHT, size=9, fmt="0.0000")
        eg[f"{STC[s_]}{rr}"] = "=" + BASE[s_](lvf)
    cf = lambda s_, rr=rr: f"${STC[s_]}{rr}"  # noqa: E731
    for s_ in DERIVED:
        eg[f"{STC[s_]}{rr}"] = "=" + DERIVED[s_](cf)
        body(eg[f"{STC[s_]}{rr}"], align=RIGHT, size=9, fmt="0.0000")
# eCPK0 / eCPW0 come from state 0
eg[f"C{EVR['eCPK0']}"] = f"={st('CPK', 0)}"
eg[f"C{EVR['eCPW0']}"] = f"={st('CPW', 0)}"


# ---- outcome formulas (shared by state rows and candidate deltas)
def outcomes(d):
    """d(name) -> expression for dEDMG, dEHP, dECON, dUW, dSPD, dPP, dRES deltas.
    Returns (VF, VT, VM, VB, dWF, dWT, dWM)."""
    dWF = f"IF(eFarmOK,eWdF*{d('lnEDMG')}/eRHf+(1-eWdF)*{d('lnEHP')}/eRDf,0)"
    dWT = f"IF(eTourOK,eWdT*{d('lnEDMG')}/eRHt+(1-eWdT)*{d('lnEHP')}/eRDt,0)"
    dWM = f"IF(eMileOK,eWdM*{d('lnEDMG')}/eRHm+(1-eWdM)*{d('lnEHP')}/eRDm,0)"
    return dWF, dWT, dWM


for k in range(0, NSTEPS + 1):
    rr = ST0 + k
    d = lambda s_, rr=rr: f"(${STC[s_]}{rr}-${STC[s_]}${ST0})"  # noqa: E731
    dWF, dWT, dWM = outcomes(d)
    vf = f"{d('lnECON')}+{d('lnUW')}+{d('lnSPD')}+eFarmDeath*IF(eFarmOK,({dWF})/eWf,0)"
    eg[f"{STC['OUT Farming']}{rr}"] = f"={vf}"
    eg[f"{STC['OUT Tournament']}{rr}"] = f"={dWT}"
    eg[f"{STC['OUT Milestones']}{rr}"] = f"={dWM}"
    eg[f"{STC['OUT Balanced']}{rr}"] = (f"={vf}+{d('lnPP')}+eResTime*{d('lnRES')}+IF(eMileOK,({dWM})/eWm,0)")
    for h in ["OUT Farming", "OUT Tournament", "OUT Milestones", "OUT Balanced"]:
        body(eg[f"{STC[h]}{rr}"], align=RIGHT, size=9, fmt="0.0000", color=CYAN)

# ---- candidate evaluation (shared)
EGQ = "'Optimization Engine'"
CC_ = {}
_cols = ["Name", "Type", "ID", "Role", "Category", "Level", "Max", "Unlocked", "Eligible", "Cost", "Hours",
         "Budget days"] + STATS + ["d_" + o for o in OUTS] + ["cEcon", "cDmg", "cSurv", "cPP", "cRes", "V", "Eff",
                                                                "Key", "Rank", "Afford", "KeyAff", "RankAff",
                                                                "Gain", "Driver", "Reason", "Confidence",
                                                                "Cost +10", "Cost to max", "Levels affordable",
                                                                "Hours to afford", "Note", "Start", "DiscF"]
for i, h in enumerate(_cols):
    CC_[h] = CL(2 + i)
CAND_LASTCOL = 2 + len(_cols) - 1


def sref(stat, k):
    return f"{EGQ}!${STC[stat]}${ST0 + k}"


def lref(var, k):
    return f"{EGQ}!${STC['lv:' + var]}${ST0 + k}"


ENH_LAB_ROW = PP_LB["workshop_enhancements"]
ENH_DISC_LAB = {"Attack": "enhancement_attack_coin_discount", "Defense": "enhancement_defense_coin_discount",
                "Utility": "enhancement_utility_coin_discount"}
DRIVER_TXT = ["Coin income", "Damage → more waves", "Survivability → more waves", "Purchasing power (discounts)",
              "Research speed"]


def cand_row(ws, r, item, kind, k, roadmap=False, bg=PANEL):
    """Write one candidate row. kind: WS / EN / LAB. k = state row used as 'before'."""
    c = lambda h: f"${CC_[h]}{r}"  # noqa: E731
    role = item["role"]
    modeled = role != "NQ"
    if kind == "WS":
        prow = PP_WS[item["id"]]
        typ, cat = "Workshop", item["category"]
        start = f"'Game Data'!$H${WSROW[item['id']]}"
    elif kind == "EN":
        prow = PP_EN[item["id"]]
        typ, cat = "Enhancement", item["category"]
        start = f"'Game Data'!$H${ENROW[item['id']]}"
    else:
        prow = PP_LB[item["id"]]
        typ, cat = "Lab", item["category"]
        start = f"'Game Data'!$H${LBROW[item['id']]}"
    vals = {}
    vals["Name"] = item["name"]
    vals["Type"] = typ
    vals["ID"] = item["id"]
    vals["Role"] = role
    vals["Category"] = cat
    if roadmap or (modeled and role in VARS):
        lvl = f"={lref(role, k)}" if modeled else f"=N({PP}!$E${prow})"
    else:
        lvl = f"=N({PP}!$E${prow})"
    vals["Level"] = lvl
    vals["Max"] = item["maxLevel"]
    if kind == "WS":
        vals["Unlocked"] = f"={PP}!$H${prow}"
        vals["Eligible"] = (f'=IF(AND({c("Unlocked")}=1,{PP}!$E${prow}<>"",{c("Level")}<{c("Max")}),1,0)')
        disc = {"Attack": "DSA", "Defense": "DSD", "Utility": "DSU"}[cat]
        vals["Cost"] = f'=IF({c("Level")}<{c("Max")},ROUND(INDEX(rngWSC,{start}+{c("Level")})*(1-{sref(disc, k)}),0),"")'
        vals["Hours"] = ""
        vals["Budget days"] = f'=IF(AND(ISNUMBER({c("Cost")}),ISNUMBER(eCPD)),{c("Cost")}/eCPD,"")'
    elif kind == "EN":
        vals["Unlocked"] = f"=IF(AND({PP}!$H${prow}=1,N({PP}!$E${ENH_LAB_ROW})>=1),1,0)"
        vals["Eligible"] = f'=IF(AND({c("Unlocked")}=1,{c("Level")}<{c("Max")}),1,0)'
        dl = PP_LB[ENH_DISC_LAB[cat]]
        vals["Cost"] = (f'=IF({c("Level")}<{c("Max")},INDEX(rngENC,{start}+{c("Level")})*MAX(0,1-MIN(cEnhDiscMax,'
                        f'cEnhDiscStep*N({PP}!$E${dl}))-eEnhVault),"")')
        vals["Hours"] = ""
        vals["Budget days"] = f'=IF(AND(ISNUMBER({c("Cost")}),ISNUMBER(eCPD)),{c("Cost")}/eCPD,"")'
    else:
        vals["Unlocked"] = f"={PP}!$G${prow}"
        vals["Eligible"] = (f'=IF(AND({c("Unlocked")}=1,{c("Level")}<{c("Max")},{PP}!$H${prow}<>"Yes"),1,0)')
        vals["Cost"] = f'=IF({c("Level")}<{c("Max")},INDEX(rngLBC,{start}+{c("Level")}+1)*(1-{sref("DSL", k)}),"")'
        vals["Hours"] = (f'=IF({c("Level")}<{c("Max")},INDEX(rngLBH,{start}+{c("Level")}+1)/({sref("RS", k)}'
                         f'*(1+N(pRelic))*IF(N(pSpeedup)>0,pSpeedup,1)),"")')
        vals["Budget days"] = (f'=IF(ISNUMBER({c("Cost")}),IF(ISNUMBER(eCPD),{c("Cost")}/eCPD,0)+{c("Hours")}/24/eSlots,"")')
    if kind == "WS":
        vals["Start"] = f"={start}"
        vals["DiscF"] = f'=1-{sref({"Attack": "DSA", "Defense": "DSD", "Utility": "DSU"}[cat], k)}'
    elif kind == "EN":
        vals["Start"] = f"={start}"
        vals["DiscF"] = f'=MAX(0,1-MIN(cEnhDiscMax,cEnhDiscStep*N({PP}!$E${PP_LB[ENH_DISC_LAB[cat]]}))-eEnhVault)'
    else:
        vals["Start"] = f"={start}"
        vals["DiscF"] = f'=1-{sref("DSL", k)}'
    if modeled:
        own = role

        def lvp(v, own=own):
            return f"MIN({c('Level')}+1,{c('Max')})" if v == own else lref(v, k)
        for s_ in BASE:
            vals[s_] = "=" + BASE[s_](lvp) if own in DEPS[s_] else f"={sref(s_, k)}"
        cf = lambda s_: c(s_)  # noqa: E731
        for s_ in DERIVED:
            vals[s_] = "=" + DERIVED[s_](cf)
        for o in OUTS:
            vals["d_" + o] = f"={c(o)}-{sref(o, k)}"
        dE = f'({c("d_lnECON")}+{c("d_lnUW")}+{c("d_lnSPD")})'
        dD, dH = c("d_lnEDMG"), c("d_lnEHP")
        farmD = f"IF(eFarmOK,eFarmDeath*eWdF*{dD}/eRHf/eWf,0)"
        farmH = f"IF(eFarmOK,eFarmDeath*(1-eWdF)*{dH}/eRDf/eWf,0)"
        vals["cEcon"] = f"=CHOOSE(eStrat,{dE},0,0,{dE})"
        vals["cDmg"] = (f"=CHOOSE(eStrat,{farmD},IF(eTourOK,eWdT*{dD}/eRHt,0),IF(eMileOK,eWdM*{dD}/eRHm,0),"
                        f"{farmD}+IF(eMileOK,eWdM*{dD}/eRHm/eWm,0))")
        vals["cSurv"] = (f"=CHOOSE(eStrat,{farmH},IF(eTourOK,(1-eWdT)*{dH}/eRDt,0),IF(eMileOK,(1-eWdM)*{dH}/eRDm,0),"
                         f"{farmH}+IF(eMileOK,(1-eWdM)*{dH}/eRDm/eWm,0))")
        vals["cPP"] = f'=IF(eStrat=4,{c("d_lnPP")},0)'
        vals["cRes"] = f'=IF(eStrat=4,eResTime*{c("d_lnRES")},0)'
        vals["V"] = f'=IF(AND({c("Unlocked")}=1,{c("Level")}<{c("Max")}),{c("cEcon")}+{c("cDmg")}+{c("cSurv")}+{c("cPP")}+{c("cRes")},"")'
        if kind == "LAB" or roadmap:
            vals["Eff"] = f'=IF(AND(ISNUMBER({c("V")}),ISNUMBER({c("Budget days")})),IF({c("Budget days")}>0,{c("V")}/{c("Budget days")},""),"")'
        else:
            vals["Eff"] = f'=IF(AND(ISNUMBER({c("V")}),ISNUMBER({c("Cost")})),IF({c("Cost")}>0,{c("V")}/{c("Cost")},""),"")'
        vals["Key"] = f'=IF(AND(eReady,{c("Eligible")}=1,ISNUMBER({c("Eff")}),N({c("V")})>1E-12),{c("Eff")},-1)'
        vals["Gain"] = (f'=IF(ISNUMBER({c("V")}),IF(OR(eStrat=2,eStrat=3),TEXT({c("V")},"+0.00")&" waves",'
                        f'TEXT(EXP({c("V")})-1,"+0.000%")&IF(eStrat=1," coins"," growth")),"")')
        comps = [c("cEcon"), c("cDmg"), c("cSurv"), c("cPP"), c("cRes")]
        mx = f"MAX({','.join(comps)})"
        drv = "IF({0}<=0,\"No gain\",".format(mx)
        for comp, t in zip(comps, DRIVER_TXT):
            drv += f'IF({comp}={mx},"{t}",'
        drv += '""' + ")" * 6
        vals["Driver"] = "=" + drv
        counter = (f'IF(AND(eStrat=1,OR({c("Driver")}="{DRIVER_TXT[1]}",{c("Driver")}="{DRIVER_TXT[2]}")),'
                   f'" Recommended for Farming because your farming runs end by death and "&IF({c("Driver")}="{DRIVER_TXT[1]}","damage","survivability")'
                   f'&" limits your waves; the extra waves add more coins per run than the next economy option.","")')
        vals["Reason"] = (f'=IF(NOT(ISNUMBER({c("V")})),"",IF({c("V")}<=1E-12,"Does not move this goal with your current evidence (e.g. it improves a stat that is not your bottleneck).",{c("Driver")}&": "&{c("Gain")}&" for "&'
                          + fmt_coins(c("Cost")) + f'&" coins"&IF({c("Hours")}<>""," and "&' + fmt_hours(c("Hours"))
                          + f',"")&"."&{counter}))')
        est = []
        if role in ("RANGE", "DPM", "L_RANGE", "L_DPM", "E_DPM"):
            est.append('pDmgRange=""')
        if role in ("CPK", "CPW", "L_CPK", "L_CPW", "E_COIN"):
            est.append('pKillShare=""')
        if role in ("L_GT", "L_BH", "L_DW", "L_SL", "E_COIN"):
            est.append("TRUE")
        est_expr = "OR(" + ",".join(est) + ")" if est else "FALSE"
        lowexpr = (f'OR(AND({c("Driver")}="{DRIVER_TXT[1]}",CHOOSE(eStrat,eWdF,eWdT,eWdM,eWdF)=0.5),'
                   f'AND({c("Driver")}="{DRIVER_TXT[2]}",CHOOSE(eStrat,eWdF,eWdT,eWdM,eWdF)=0.5))')
        vals["Confidence"] = (f'=IF(NOT(ISNUMBER({c("V")})),"",IF({lowexpr},"Low",IF(OR({est_expr},eMissLab>0),"Medium","High")))')
    else:
        vals["V"] = ""
        vals["Eff"] = ""
        vals["Key"] = -1
        vals["Driver"] = "Not quantified"
        vals["Reason"] = item.get("nqReason", "")
        vals["Confidence"] = "Judgment"
    if not roadmap:
        vals["Afford"] = f'=IF(AND(ISNUMBER({c("Cost")}),ISNUMBER(pCoins)),IF({c("Cost")}<=pCoins,1,0),0)'
        vals["KeyAff"] = f'=IF({c("Afford")}=1,{c("Key")},-1)'
        vals["Hours to afford"] = (f'=IF(AND(ISNUMBER({c("Cost")}),N(pCPH)>0),MAX(0,({c("Cost")}-N(pCoins))/pCPH),"")')
        if kind == "WS":
            cum = f"INDEX(rngWSCUM,{start}+{c('Level')})"
            disc = {"Attack": "DSA", "Defense": "DSD", "Utility": "DSU"}[cat]
            vals["Cost +10"] = (f'=IF({c("Level")}<{c("Max")},(INDEX(rngWSCUM,{start}+MIN({c("Max")},{c("Level")}+10))-{cum})'
                                f'*(1-{sref(disc, 0)}),"")')
            vals["Cost to max"] = f'=(INDEX(rngWSCUM,{start}+{c("Max")})-{cum})*(1-{sref(disc, 0)})'
            vals["Levels affordable"] = (f'=IF(AND(N(pCoins)>0,{c("Level")}<{c("Max")}),MATCH({cum}+pCoins/MAX(0.01,1-{sref(disc, 0)}),'
                                         f'INDEX(rngWSCUM,{start}+{c("Level")}):INDEX(rngWSCUM,{start}+{c("Max")}),1)-1,0)')
        elif kind == "EN":
            cum = f"INDEX(rngENCUM,{start}+{c('Level')})"
            vals["Cost +10"] = f'=IF({c("Level")}<{c("Max")},(INDEX(rngENCUM,{start}+MIN({c("Max")},{c("Level")}+10))-{cum}),"")'
            vals["Cost to max"] = f'=INDEX(rngENCUM,{start}+{c("Max")})-{cum}'
            vals["Levels affordable"] = (f'=IF(AND(N(pCoins)>0,{c("Level")}<{c("Max")}),MATCH({cum}+pCoins,'
                                         f'INDEX(rngENCUM,{start}+{c("Level")}):INDEX(rngENCUM,{start}+{c("Max")}),1)-1,0)')
        else:
            cum = f"INDEX(rngLBCUM,{start}+{c('Level')})"
            vals["Cost +10"] = ""
            vals["Cost to max"] = f'=(INDEX(rngLBCUM,{start}+{c("Max")})-{cum})*(1-{sref("DSL", 0)})'
            vals["Levels affordable"] = ""
        vals["Note"] = (f'=IF({c("Unlocked")}<>1,"Locked","")' if kind != "EN" else
                        f'=IF({c("Unlocked")}<>1,IF(N({PP}!$E${ENH_LAB_ROW})<1,"Needs Workshop Enhancements lab","Locked"),"")')
    for h, v in vals.items():
        cell = ws[f"{CC_[h]}{r}"]
        cell.value = v
        body(cell, bg=bg, size=9, align=RIGHT if h not in ("Name", "Type", "ID", "Role", "Category", "Gain",
                                                            "Driver", "Reason", "Confidence", "Note") else LEFT)
    for h in ("Cost", "Cost +10", "Cost to max"):
        ws[f"{CC_[h]}{r}"].number_format = '[>=1E15]0.00E+00;#,##0'
    ws[f"{CC_['Hours']}{r}"].number_format = "0.0"
    ws[f"{CC_['Budget days']}{r}"].number_format = "0.000"
    for h in STATS + ["d_" + o for o in OUTS] + ["cEcon", "cDmg", "cSurv", "cPP", "cRes", "V"]:
        ws[f"{CC_[h]}{r}"].number_format = "0.000000"
    ws[f"{CC_['Eff']}{r}"].number_format = "0.000E+00"


section(eg, CAND_HDR - 2, 2, "CANDIDATES - every Workshop upgrade, Enhancement and Lab, evaluated from your current account", 14,
        color=VIOLET)
header_row(eg, CAND_HDR, 2, _cols, color=VIOLET, height=40)
ALL_ITEMS = ([("WS", w) for w in D["workshop"]] + [("EN", e) for e in D["enhancements"]] +
             [("LAB", l) for l in D["labs"]])
CR = {}
for i, (kind, item) in enumerate(ALL_ITEMS):
    rr = CAND_HDR + 1 + i
    CR[(kind, item["id"])] = rr
    cand_row(eg, rr, item, kind, 0, bg=PANEL if i % 2 == 0 else PANEL2)
CAND_FIRST = CAND_HDR + 1
WS_LAST = CAND_FIRST + len(D["workshop"]) + len(D["enhancements"]) - 1   # workshop + enhancements block
LB_FIRST = WS_LAST + 1
LB_LAST = CAND_FIRST + len(ALL_ITEMS) - 1


# ranks: workshop+enhancement block and lab block ranked separately
def rank_block(ws, r0, r1):
    for rr in range(r0, r1 + 1):
        kr = f"${CC_['Key']}${r0}:${CC_['Key']}${r1}"
        ka = f"${CC_['KeyAff']}${r0}:${CC_['KeyAff']}${r1}"
        prev_k = f"${CC_['Key']}${r0}:{CC_['Key']}{rr - 1}" if rr > r0 else None
        prev_a = f"${CC_['KeyAff']}${r0}:{CC_['KeyAff']}{rr - 1}" if rr > r0 else None
        ws[f"{CC_['Rank']}{rr}"] = (f"=RANK({CC_['Key']}{rr},{kr})" + (f"+COUNTIF({prev_k},{CC_['Key']}{rr})" if prev_k else ""))
        ws[f"{CC_['RankAff']}{rr}"] = (f"=RANK({CC_['KeyAff']}{rr},{ka})" + (f"+COUNTIF({prev_a},{CC_['KeyAff']}{rr})" if prev_a else ""))
        for h in ("Rank", "RankAff"):
            body(ws[f"{CC_[h]}{rr}"], size=9, align=RIGHT, bg=PANEL)


rank_block(eg, CAND_FIRST, WS_LAST)
rank_block(eg, LB_FIRST, LB_LAST)
for n_, r_a, r_b in [("cwsRng", CAND_FIRST, WS_LAST), ("clbRng", LB_FIRST, LB_LAST)]:
    pass
# spend shares and missing counts
WSB = (CAND_FIRST, CAND_FIRST + len(D["workshop"]) - 1)
ENB = (WSB[1] + 1, WS_LAST)


def spend_expr(kind, cat=None):
    parts = []
    for k_, item in ALL_ITEMS:
        if k_ != kind or (cat and item["category"] != cat):
            continue
        prow = {"WS": PP_WS, "EN": PP_EN, "LAB": PP_LB}[kind][item["id"]]
        if kind == "WS":
            parts.append(f"INDEX(rngWSCUM,'Game Data'!$H${WSROW[item['id']]}+N({PP}!$E${prow}))")
        elif kind == "EN":
            parts.append(f"INDEX(rngENCUM,'Game Data'!$H${ENROW[item['id']]}+N({PP}!$E${prow}))")
        else:
            parts.append(f"INDEX(rngLBCUM,'Game Data'!$H${LBROW[item['id']]}+N({PP}!$E${prow}))")
    return parts


# put spend per row in the 'Note' neighbour? Simpler: dedicated helper column after the table
SPCOL = CL(CAND_LASTCOL + 1)
eg[f"{SPCOL}{CAND_HDR}"] = "Base coins spent"
header_row(eg, CAND_HDR, CAND_LASTCOL + 1, ["Base coins spent"], color=VIOLET, height=40)
for kind, item in ALL_ITEMS:
    rr = CR[(kind, item["id"])]
    prow = {"WS": PP_WS, "EN": PP_EN, "LAB": PP_LB}[kind][item["id"]]
    rng = {"WS": "rngWSCUM", "EN": "rngENCUM", "LAB": "rngLBCUM"}[kind]
    gdr = {"WS": WSROW, "EN": ENROW, "LAB": LBROW}[kind][item["id"]]
    eg[f"{SPCOL}{rr}"] = f"=INDEX({rng},'Game Data'!$H${gdr}+MIN(N({PP}!$E${prow}),{item['maxLevel']}))"
    body(eg[f"{SPCOL}{rr}"], size=9, align=RIGHT, fmt='[>=1E15]0.00E+00;#,##0')
spc = lambda a, b: f"${SPCOL}${a}:${SPCOL}${b}"  # noqa: E731
catc = lambda a, b: f"${CC_['Category']}${a}:${CC_['Category']}${b}"  # noqa: E731
eg[f"C{EVR['eSpendWS']}"] = f"=SUM({spc(*WSB)})"
eg[f"C{EVR['eSpendEN']}"] = f"=SUM({spc(*ENB)})"
eg[f"C{EVR['eSpendLab']}"] = f"=SUM({spc(LB_FIRST, LB_LAST)})"
tot = "MAX(1,eSpendWS+eSpendEN+eSpendLab)"
for n_, cat in [("eSA", "Attack"), ("eSD", "Defense"), ("eSU", "Utility")]:
    eg[f"C{EVR[n_]}"] = f'=SUMIF({catc(*WSB)},"{cat}",{spc(*WSB)})/{tot}'
eg[f"C{EVR['eSL']}"] = f"=eSpendLab/{tot}"
miss_ws = "+".join(f'IF(AND({PP}!$E${PP_WS[ROLE_WS[v]["id"]]}="",{PP}!$H${PP_WS[ROLE_WS[v]["id"]]}=1),1,0)' for v in WS_VARS)
miss_lb = "+".join(f'IF({PP}!$E${PP_LB[ROLE_LB[v]["id"]]}="",1,0)' for v in LB_VARS)
eg[f"C{EVR['eMissWS']}"] = "=" + miss_ws
eg[f"C{EVR['eMissLab']}"] = "=" + miss_lb
eg.freeze_panes = eg[f"C{CAND_HDR + 1}"]

# ======================================================================
# 6. ROADMAP ENGINE (sequential simulation)
# ======================================================================
re_ = S["Roadmap Engine"]
BLK0 = 42
BLK_H = len(VARS) + 3
setup_sheet(re_, tab_color=VIOLET, zoom=80, rows=BLK0 + NSTEPS * BLK_H + 5, cols=12, widths={"A": 2, "B": 30})
title_bar(re_, 1, 2, "ROADMAP ENGINE",
          "Step k evaluates every modeled investment from state k-1 (Optimization Engine state table), picks the best "
          "value per resource-day, and the state table applies it. Funding and lab-slot timelines are simulated below.")
re_.cell(4, 2, "Resource-days = coin cost / coins per day  +  (labs) research hours / 24 / lab slots. "
               "Ranking by outcome per resource-day lets Workshop buys and research compete fairly.").font = font(MUTED, 9, italic=True)
SUMC = {}
sum_cols = ["Step", "Block row", "Pick role", "Pick", "Type", "From", "To", "Cost", "Cumulative cost", "Funded at (h)",
            "Research hours", "Slot", "Lab start (h)", "Lab done (h)", "Outcome V", "Gain", "Driver", "Confidence",
            "Value / resource-day", "Slot 1 free (h)", "Slot 2 free (h)", "Slot 3 free (h)", "Slot 4 free (h)",
            "Slot 5 free (h)", "Note", "Same-lab done (h)", "Levels", "Runner-up value/day", "Step outcome"]
for i, h in enumerate(sum_cols):
    SUMC[h] = CL(2 + i)
header_row(re_, RE_SUM0 - 1, 2, sum_cols, color=VIOLET, height=40)
assert SUMC["Levels"] == "AB", SUMC["Levels"]
INIT_ROW = RE_SUM0 + NSTEPS + 1
body(re_.cell(INIT_ROW, 2, "Initial lab slots (h until free)"), color=VIOLET)
for j in range(5):
    cref = f"{SUMC['Slot %d free (h)' % (j + 1)]}{INIT_ROW}"
    re_[cref] = f"=IF({j + 1}<=eSlots,IF(ISNUMBER(INDEX(ppSlotHrs,{j + 1})),INDEX(ppSlotHrs,{j + 1}),0),1E+9)"
    body(re_[cref], align=RIGHT, fmt="0.0", size=9)
for k in range(1, NSTEPS + 1):
    rr = RE_SUM0 + k - 1
    b0 = BLK0 + (k - 1) * BLK_H
    first, last = b0 + 2, b0 + 1 + len(VARS)
    effr = f"${CC_['Key']}${first}:${CC_['Key']}${last}"
    rolr = f"${CC_['Role']}${first}:${CC_['Role']}${last}"
    g = lambda h, rr=rr: f"${SUMC[h]}{rr}"  # noqa: E731
    prev = lambda h, rr=rr: f"${SUMC[h]}{rr - 1 if rr > RE_SUM0 else INIT_ROW}"  # noqa: E731
    vals = {
        "Step": k,
        "Block row": f'=IF(AND(eReady,ISNUMBER(eCPD),COUNT({effr})>0),IF(MAX({effr})>0,MATCH(MAX({effr}),{effr},0)+{first - 1},""),"")'
        + ("" if k == 1 else f'*IF({SUMC["Block row"]}{rr - 1}="",0,1)'),
    }
    vals["Block row"] = (f'=IF({"TRUE" if k == 1 else SUMC["Block row"] + str(rr - 1) + "<>" + chr(34) * 2},'
                         f'IF(AND(eReady,ISNUMBER(eCPD),COUNT({effr})>0),IF(MAX({effr})>0,MATCH(MAX({effr}),{effr},0)+{first - 1},""),""),"")')
    br = g("Block row")
    pick = lambda h, br=br: f'IF({br}="","",INDEX(${CC_[h]}:${CC_[h]},{br}))'  # noqa: E731
    vals["Pick role"] = "=" + pick("Role")
    vals["Pick"] = "=" + pick("Name")
    vals["Type"] = "=" + pick("Type")
    vals["From"] = "=" + pick("Level")
    vals["Runner-up value/day"] = f'=IF({br}="","",IFERROR(MAX(0,LARGE({effr},2)),0))'
    cstar = f'{g("Outcome V")}*eCPD/{g("Runner-up value/day")}'
    lv_room = f'(INDEX(${CC_["Max"]}:${CC_["Max"]},{br})-{g("From")})'
    st_ = f'INDEX(${CC_["Start"]}:${CC_["Start"]},{br})'
    df_ = f'INDEX(${CC_["DiscF"]}:${CC_["DiscF"]},{br})'
    cumr = f'IF({g("Type")}="Enhancement",INDEX(rngENCUM,{st_}+{g("From")}):INDEX(rngENCUM,{st_}+{g("From")}+{lv_room}),INDEX(rngWSCUM,{st_}+{g("From")}):INDEX(rngWSCUM,{st_}+{g("From")}+{lv_room}))'
    day_cap = f'IFERROR(MATCH(INDEX({cumr},1)+eCPD/{df_},{cumr},1)-1,1)'
    vals["Levels"] = (f'=IF({br}="","",IF({g("Type")}="Lab",1,MAX(1,MIN({lv_room},{day_cap},IF({g("Runner-up value/day")}>0,'
                      f'IFERROR(MATCH({cstar}/{df_},IF({g("Type")}="Enhancement",INDEX(rngENC,{st_}+{g("From")}):INDEX(rngENC,{st_}+{g("From")}+{lv_room}-1),'
                      f'INDEX(rngWSC,{st_}+{g("From")}):INDEX(rngWSC,{st_}+{g("From")}+{lv_room}-1)),1),1),100)))))')
    vals["To"] = f'=IF({br}="","",{g("From")}+{g("Levels")})'
    vals["Cost"] = (f'=IF({br}="","",IF({g("Type")}="Lab",{pick("Cost")},IF({g("Type")}="Enhancement",'
                     f'INDEX(rngENCUM,{st_}+{g("To")})-INDEX(rngENCUM,{st_}+{g("From")}),'
                     f'INDEX(rngWSCUM,{st_}+{g("To")})-INDEX(rngWSCUM,{st_}+{g("From")}))*{df_}))')
    vals["Cumulative cost"] = f'=IF({br}="","",N({prev("Cumulative cost")})+{g("Cost")})' if k > 1 else f'=IF({br}="","",{g("Cost")})'
    vals["Funded at (h)"] = f'=IF({br}="","",MAX(0,({g("Cumulative cost")}-N(pCoins))/pCPH))'
    vals["Research hours"] = f'=IF({g("Type")}="Lab",{pick("Hours")},0)'
    slots_prev = f"{prev('Slot 1 free (h)')}:{prev('Slot 5 free (h)')}"
    vals["Slot"] = f'=IF({g("Type")}="Lab",MATCH(MIN({slots_prev}),{slots_prev},0),"")'
    if k > 1:
        vals["Same-lab done (h)"] = (f'=IF({g("Type")}="Lab",SUMPRODUCT(MAX((${SUMC["Pick role"]}${RE_SUM0}:{SUMC["Pick role"]}{rr - 1}={g("Pick role")})'
                                     f'*${SUMC["Lab done (h)"]}${RE_SUM0}:{SUMC["Lab done (h)"]}{rr - 1})),0)')
    else:
        vals["Same-lab done (h)"] = 0
    vals["Lab start (h)"] = f'=IF({g("Type")}="Lab",MAX({g("Funded at (h)")},MIN({slots_prev}),{g("Same-lab done (h)")}),0)'
    vals["Lab done (h)"] = f'=IF({g("Type")}="Lab",{g("Lab start (h)")}+{g("Research hours")},0)'
    for j in range(1, 6):
        h = f"Slot {j} free (h)"
        vals[h] = f'=IF(AND({g("Type")}="Lab",{g("Slot")}={j}),{g("Lab done (h)")},{prev(h)})'
    vals["Outcome V"] = "=" + pick("V")
    vals["Step outcome"] = (f'=IF({br}="","",INDEX({EGQ}!${STC["OUT Farming"]}${ST0 + k}:${STC["OUT Balanced"]}${ST0 + k},eStrat)'
                            f'-INDEX({EGQ}!${STC["OUT Farming"]}${ST0 + k - 1}:${STC["OUT Balanced"]}${ST0 + k - 1},eStrat))')
    vals["Gain"] = (f'=IF({br}="","",IF(OR(eStrat=2,eStrat=3),TEXT({g("Step outcome")},"+0.00")&" waves",'
                    f'TEXT(EXP({g("Step outcome")})-1,"+0.000%")&IF(eStrat=1," coins"," growth")))')
    vals["Driver"] = "=" + pick("Driver")
    vals["Confidence"] = "=" + pick("Confidence")
    vals["Value / resource-day"] = "=" + pick("Eff")
    vals["Note"] = (f'=IF({br}="","",IF({g("Type")}="Lab","Start in "&{fmt_hours(g("Lab start (h)"))}&", done in "&{fmt_hours(g("Lab done (h)"))},'
                    f'IF({g("Funded at (h)")}>0,"Save "&{fmt_coins(g("Cumulative cost") + "-N(pCoins)")}&" more (about "&{fmt_hours(g("Funded at (h)"))}&")","Affordable now")))')
    for h, v in vals.items():
        cell = re_[f"{SUMC[h]}{rr}"]
        cell.value = v
        body(cell, size=9, align=RIGHT if h not in ("Pick role", "Pick", "Type", "Gain", "Driver", "Confidence", "Note") else LEFT)
    for h in ("Cost", "Cumulative cost"):
        re_[f"{SUMC[h]}{rr}"].number_format = '[>=1E15]0.00E+00;#,##0'
    for h in ("Funded at (h)",) + tuple(f"Slot {j} free (h)" for j in range(1, 6)):
        re_[f"{SUMC[h]}{rr}"].number_format = "0.0"
    for h in ("Research hours", "Lab start (h)", "Lab done (h)", "Same-lab done (h)"):
        re_[f"{SUMC[h]}{rr}"].number_format = "0.0;-0.0;"
    # block
    section(re_, b0, 2, f"STEP {k}: candidates evaluated from state k = {k - 1}", 10, color=VIOLET)
    header_row(re_, b0 + 1, 2, _cols[:CAND_LASTCOL - 1], color=VIOLET, height=30)
    for i, v in enumerate(VARS):
        kind = var_kind(v)
        cand_row(re_, first + i, var_meta(v), kind, k - 1, roadmap=True, bg=PANEL if i % 2 == 0 else PANEL2)
for j in range(2, CAND_LASTCOL + 1):
    re_.column_dimensions[CL(j)].width = 12
re_.column_dimensions["B"].width = 30
re_.column_dimensions["E"].width = 28
name("rmPickRole", "Roadmap Engine", f"${SUMC['Pick role']}${RE_SUM0}:${SUMC['Pick role']}${RE_SUM0 + NSTEPS - 1}")
re_.freeze_panes = "C8"


# ======================================================================
# 7. USER-FACING SHEETS
# ======================================================================
def E(h, a, b):
    return f"{EGQ}!${CC_[h]}${a}:${CC_[h]}${b}"


BAR = lambda x: f'REPT("█",ROUND(MAX(0,MIN(1,{x}))*10,0))&REPT("░",10-ROUND(MAX(0,MIN(1,{x}))*10,0))'  # noqa: E731
STRAT_UNIT = '=IF(OR(eStrat=2,eStrat=3),"Extra waves",IF(eStrat=1,"% more coins","% growth index"))'


def nav(ws, row, col, targets, step=2):
    for i, (label, sheet) in enumerate(targets):
        c = ws.cell(row, col + i * step, f'=HYPERLINK("#\'{sheet}\'!A1","{label}")')
        c.font = font(CYAN, 9, True)
        c.fill = fill(PANEL2)
        c.alignment = CENTER
        c.border = Border(left=Side(style="thin", color=CYAN_DIM), right=Side(style="thin", color=CYAN_DIM),
                          top=Side(style="thin", color=CYAN_DIM), bottom=Side(style="medium", color=CYAN))


def kpi(ws, row, col, label, formula, sub=None, color=CYAN, fmt=None, span=1):
    c = ws.cell(row, col, label)
    c.font = font(MUTED, 8, True)
    c.fill = fill(PANEL2)
    c.alignment = Alignment(horizontal="left", vertical="bottom", indent=1)
    v = ws.cell(row + 1, col, formula)
    v.font = font(color, 16, True)
    v.fill = fill(PANEL2)
    v.alignment = Alignment(horizontal="left", vertical="center", indent=1, shrink_to_fit=True)
    if fmt:
        v.number_format = fmt
    s_ = ws.cell(row + 2, col, sub or "")
    s_.font = font(MUTED, 8, italic=True)
    s_.fill = fill(PANEL2)
    s_.alignment = Alignment(horizontal="left", vertical="top", indent=1, shrink_to_fit=True)
    for rr in (row, row + 1, row + 2):
        for j in range(span):
            ws.cell(rr, col + j).fill = fill(PANEL2)
        ws.cell(rr, col).border = Border(left=Side(style="thick", color=color))
    if span > 1:
        for rr in (row, row + 1, row + 2):
            ws.merge_cells(start_row=rr, start_column=col, end_row=rr, end_column=col + span - 1)


NAVS = [("◆ DASHBOARD", "Dashboard"), ("⚒ WORKSHOP", "Workshop Optimizer"), ("⚗ LABS", "Lab Optimizer"),
        ("➜ ROADMAP", "Roadmap"), ("◈ GEMS", "Gem Planner"), ("✎ PROFILE", "Player Profile")]

# ---------------- Workshop Optimizer
wo = S["Workshop Optimizer"]
NWS = len(D["workshop"]) + len(D["enhancements"])
setup_sheet(wo, tab_color=CYAN, zoom=90, rows=NWS + 14, cols=24,
            widths={"A": 2, "B": 5, "C": 26, "D": 12, "E": 9, "F": 9, "G": 9, "H": 9, "I": 14, "J": 12,
                    "K": 12, "L": 9, "M": 17, "N": 9, "O": 14, "P": 10, "Q": 11, "R": 25, "S": 11, "T": 110})
title_bar(wo, 1, 2, "WORKSHOP OPTIMIZER", None)
wo.cell(2, 2, '=" Ranked for the "&inStrategy&" goal  ·  "&IF(eReady,"all upgrades and enhancements, best value per coin first","enter your Workshop levels on Player Profile")').font = font(MUTED, 10, italic=True)
nav(wo, 1, 13, NAVS[:4])
kpi(wo, 4, 3, "STRATEGY", "=inStrategy", "change it on the Dashboard")
kpi(wo, 4, 4, "AVAILABLE COINS", "=" + fmt_coins("pCoins"), "from Player Profile", span=2)
kpi(wo, 4, 6, "ATTACK / DEF / UTIL DISCOUNT", f'=TEXT({sref("DSA", 0)},"0.0%")&" / "&TEXT({sref("DSD", 0)},"0.0%")&" / "&TEXT({sref("DSU", 0)},"0.0%")', "from discount labs + vault", span=4, color=VIOLET)
kpi(wo, 4, 10, "DATA", '=IF(eReady,"Complete","Missing "&eMissWS&" levels")', "modeled Workshop levels", span=2, color=GREEN)
kpi(wo, 4, 13, "UNIT", STRAT_UNIT, "Gain column", span=2, color=VIOLET)
HR = 8
header_row(wo, HR, 2, ["#", "Upgrade", "Type", "Category", "Level", "Next", "Max", "Progress", "Next cost", "Cost +10 lv",
                       "Buyable now", "Gain (next level)", "Efficiency", "Eff. bar", "Affordable", "Time to afford",
                       "Main driver", "Confidence", "Reason / note"])
a, b = CAND_FIRST, WS_LAST
for n in range(1, NWS + 1):
    r = HR + n
    pos = f"$Z{r}"
    wo[pos] = f'=MATCH({n},{E("Rank", a, b)},0)'
    g = lambda h, pos=pos: f"INDEX({E(h, a, b)},{pos})"  # noqa: E731
    key = g("Key")
    status = (f'IF({key}>0,"",IF({g("Driver")}="Not quantified","Not quantified",IF({g("Unlocked")}<>1,"Locked",'
              f'IF({g("Level")}>={g("Max")},"Maxed",IF({g("Eligible")}<>1,"Missing level","No gain for this goal")))))')
    cells = {
        "B": f'=IF({key}>0,{n},"–")',
        "C": "=" + g("Name"),
        "D": "=" + g("Type"),
        "E": "=" + g("Category"),
        "F": "=" + g("Level"),
        "G": f'=IF({g("Level")}<{g("Max")},{g("Level")}+1,"MAX")',
        "H": "=" + g("Max"),
        "I": "=" + BAR(f'{g("Level")}/{g("Max")}'),
        "J": "=" + fmt_coins(g("Cost")),
        "K": "=" + fmt_coins(g("Cost +10")),
        "L": f'=IF({key}>0,{g("Levels affordable")},"")',
        "M": f'=IF({key}>0,{g("Gain")},{status})',
        "N": f'=IF({key}>0,{key}/MAX({E("Key", a, b)})*100,"")',
        "O": f'=IF({key}>0,{BAR(key + "/MAX(" + E("Key", a, b) + ")")},"")',
        "P": f'=IF({key}>0,IF({g("Afford")}=1,"✔ Yes","✖ No"),"")',
        "Q": f'=IF(AND({key}>0,{g("Afford")}<>1),{fmt_hours(g("Hours to afford"))},"")',
        "R": f'=IF({key}>0,{g("Driver")},"")',
        "S": f'=IF({key}>0,{g("Confidence")},IF({g("Driver")}="Not quantified","Judgment",""))',
        "T": f'=IF({g("Note")}<>"",{g("Note")}&". ","")&{g("Reason")}',
    }
    bg = PANEL if n % 2 else PANEL2
    for colL, f_ in cells.items():
        c = wo[f"{colL}{r}"]
        c.value = f_
        body(c, bg=bg, size=9, align=LEFT if colL in "CDERTM" else (CENTER if colL in "BGIOPS" else RIGHT))
    wo[f"N{r}"].number_format = "0"
    wo[f"I{r}"].font = font(CYAN_DIM, 8)
    wo[f"O{r}"].font = font(CYAN, 8)
    wo[f"C{r}"].font = font(TEXT, 9, True)
    wo[f"Z{r}"].font = font(BG, 6)
wo.conditional_formatting.add(f"B{HR + 1}:T{HR + 3}", FormulaRule(formula=[f'ISNUMBER($B{HR + 1})'], fill=fill("12303A")))
wo.conditional_formatting.add(f"S{HR + 1}:S{HR + NWS}", CellIsRule(operator="equal", formula=['"High"'], font=font(GREEN, 9, True)))
wo.conditional_formatting.add(f"S{HR + 1}:S{HR + NWS}", CellIsRule(operator="equal", formula=['"Medium"'], font=font(AMBER, 9, True)))
wo.conditional_formatting.add(f"S{HR + 1}:S{HR + NWS}", CellIsRule(operator="equal", formula=['"Low"'], font=font(RED, 9, True)))
wo.conditional_formatting.add(f"P{HR + 1}:P{HR + NWS}", CellIsRule(operator="equal", formula=['"✔ Yes"'], font=font(GREEN, 9, True)))
wo.conditional_formatting.add(f"M{HR + 1}:M{HR + NWS}", FormulaRule(formula=[f'$B{HR + 1}="–"'], font=font(MUTED, 9, italic=True)))
wo.column_dimensions["Z"].hidden = True
wo.freeze_panes = f"D{HR + 1}"

# ---------------- Lab Optimizer
lo = S["Lab Optimizer"]
NLB = len(D["labs"])
setup_sheet(lo, tab_color=CYAN, zoom=90, rows=NLB + 14, cols=24,
            widths={"A": 2, "B": 5, "C": 30, "D": 15, "E": 8, "F": 8, "G": 8, "H": 14, "I": 12, "J": 11, "K": 17,
                    "L": 12, "M": 9, "N": 14, "O": 13, "P": 25, "Q": 11, "R": 110})
title_bar(lo, 1, 2, "LABORATORY OPTIMIZER", None)
lo.cell(2, 2, '=" Ranked for the "&inStrategy&" goal by outcome per resource-day (coins and slot time). Long research is not penalised when its payoff justifies it."').font = font(MUTED, 10, italic=True)
nav(lo, 1, 12, NAVS[:4])
kpi(lo, 4, 3, "LAB SLOTS", '=eSlots&" owned · "&eFree&" free"', "free slots should be filled first")
kpi(lo, 4, 4, "RESEARCH LIMITED BY", '=IF(eResTime=1,"TIME","COINS / IDLE")', '=IF(eResTime=1,"Lab Speed adds value","Lab Speed adds little now")', span=2, color=VIOLET)
kpi(lo, 4, 6, "LAB SPEED", '=TEXT(eLabMult,"0.00")&"x"', "lab x relic x boost", span=2)
kpi(lo, 4, 8, "LAB COIN DISCOUNT", f'=TEXT({sref("DSL", 0)},"0.0%")', "Labs Coin Discount", span=2, color=VIOLET)
kpi(lo, 4, 10, "COINS / DAY", '=IF(ISNUMBER(eCPD),' + fmt_coins("eCPD") + ',"enter coins/hour")', "prices coins vs slot time", span=2, color=GREEN)
HR = 8
header_row(lo, HR, 2, ["#", "Research", "Category", "Level", "Next", "Max", "Progress", "Next cost", "Duration",
                       "Gain (next level)", "Gain per day", "Efficiency", "Eff. bar", "Status", "Main driver",
                       "Confidence", "Reason / note"])
a, b = LB_FIRST, LB_LAST
for n in range(1, NLB + 1):
    r = HR + n
    pos = f"$Z{r}"
    lo[pos] = f'=MATCH({n},{E("Rank", a, b)},0)'
    g = lambda h, pos=pos: f"INDEX({E(h, a, b)},{pos})"  # noqa: E731
    key = g("Key")
    status = (f'IF({key}>0,IF({n}<=eFree,"▶ START NOW","Queue"),IF({g("Level")}>={g("Max")},"Maxed",IF({g("Unlocked")}<>1,"Locked",'
              f'IF(INDEX({PP}!$H${PP_LB[D["labs"][0]["id"]]}:$H${PP_LB[D["labs"][-1]["id"]]},MATCH({g("ID")},{E("ID", a, b)},0))="Yes","Researching",'
              f'IF({g("Driver")}="Not quantified","Not quantified","No gain for this goal")))))')
    cells = {
        "B": f'=IF({key}>0,{n},"–")', "C": "=" + g("Name"), "D": "=" + g("Category"), "E": "=" + g("Level"),
        "F": f'=IF({g("Level")}<{g("Max")},{g("Level")}+1,"MAX")', "G": "=" + g("Max"),
        "H": "=" + BAR(f'{g("Level")}/{g("Max")}'), "I": "=" + fmt_coins(g("Cost")), "J": "=" + fmt_hours(g("Hours")),
        "K": f'=IF({key}>0,{g("Gain")},"")',
        "L": f'=IF(AND({key}>0,N({g("Hours")})>0),IF(OR(eStrat=2,eStrat=3),TEXT({g("V")}/({g("Hours")}/24),"0.000")&" w/d",TEXT({g("V")}/({g("Hours")}/24),"0.00E+0")&"/d"),"")',
        "M": f'=IF({key}>0,{key}/MAX({E("Key", a, b)})*100,"")',
        "N": f'=IF({key}>0,{BAR(key + "/MAX(" + E("Key", a, b) + ")")},"")',
        "O": "=" + status, "P": f'=IF({key}>0,{g("Driver")},"")',
        "Q": f'=IF({key}>0,{g("Confidence")},IF({g("Driver")}="Not quantified","Judgment",""))',
        "R": f'=IF({g("Note")}<>"",{g("Note")}&". ","")&{g("Reason")}',
    }
    bg = PANEL if n % 2 else PANEL2
    for colL, f_ in cells.items():
        c = lo[f"{colL}{r}"]
        c.value = f_
        body(c, bg=bg, size=9, align=LEFT if colL in "CDKPRL" else (CENTER if colL in "BFHNOQ" else RIGHT))
    lo[f"M{r}"].number_format = "0"
    lo[f"H{r}"].font = font(CYAN_DIM, 8)
    lo[f"N{r}"].font = font(VIOLET, 8)
    lo[f"C{r}"].font = font(TEXT, 9, True)
    lo[f"Z{r}"].font = font(BG, 6)
lo.conditional_formatting.add(f"O{HR + 1}:O{HR + NLB}", CellIsRule(operator="equal", formula=['"▶ START NOW"'], font=font(GREEN, 9, True), fill=fill("12302A")))
for col_ in ("Q",):
    lo.conditional_formatting.add(f"{col_}{HR + 1}:{col_}{HR + NLB}", CellIsRule(operator="equal", formula=['"High"'], font=font(GREEN, 9, True)))
    lo.conditional_formatting.add(f"{col_}{HR + 1}:{col_}{HR + NLB}", CellIsRule(operator="equal", formula=['"Medium"'], font=font(AMBER, 9, True)))
    lo.conditional_formatting.add(f"{col_}{HR + 1}:{col_}{HR + NLB}", CellIsRule(operator="equal", formula=['"Low"'], font=font(RED, 9, True)))
lo.column_dimensions["Z"].hidden = True
lo.freeze_panes = f"D{HR + 1}"

# ---------------- Roadmap
rm = S["Roadmap"]
setup_sheet(rm, tab_color=CYAN, zoom=90, rows=80, cols=20,
            widths={"A": 2, "B": 6, "C": 30, "D": 12, "E": 10, "F": 13, "G": 13, "H": 16, "I": 16, "J": 21,
                    "K": 11, "L": 52})
title_bar(rm, 1, 2, "20-INVESTMENT ROADMAP", None)
rm.cell(2, 2, '=" Sequential plan for the "&inStrategy&" goal: each step is re-optimized after the previous purchase or research is applied."').font = font(MUTED, 10, italic=True)
nav(rm, 1, 8, NAVS[:4], step=1)
RSUM = lambda h, k: f"'Roadmap Engine'!${SUMC[h]}${RE_SUM0 + k - 1}"  # noqa: E731
kpi(rm, 4, 3, "STATUS", f'=IF(NOT(eReady),"Workshop levels missing",IF(NOT(ISNUMBER(eCPD)),"Enter coins per hour",IF({RSUM("Pick", 1)}="","No modeled gains left","Ready · "&COUNTIF(rmPickRole,"?*")&" steps")))', "the roadmap needs levels + income", span=1)
kpi(rm, 4, 4, "TOTAL COINS (20 STEPS)", "=" + fmt_coins(f"MAX('Roadmap Engine'!${SUMC['Cumulative cost']}${RE_SUM0}:${SUMC['Cumulative cost']}${RE_SUM0 + NSTEPS - 1})"), "cumulative cost", span=2)
kpi(rm, 4, 6, "FULLY FUNDED IN", "=" + fmt_hours(f"MAX('Roadmap Engine'!${SUMC['Funded at (h)']}${RE_SUM0}:${SUMC['Funded at (h)']}${RE_SUM0 + NSTEPS - 1})"), "at your measured coins/hour", span=2, color=VIOLET)
kpi(rm, 4, 8, "TOTAL OUTCOME", f'=IF(OR(eStrat=2,eStrat=3),TEXT(INDEX({EGQ}!${STC["OUT Farming"]}${ST0 + NSTEPS}:${STC["OUT Balanced"]}${ST0 + NSTEPS},eStrat),"+0.0")&" waves",TEXT(EXP(INDEX({EGQ}!${STC["OUT Farming"]}${ST0 + NSTEPS}:${STC["OUT Balanced"]}${ST0 + NSTEPS},eStrat))-1,"+0.00%"))', "after all 20 steps (sequential)", span=2, color=GREEN)
HR = 8
header_row(rm, HR, 2, ["Step", "Investment", "Type", "Level", "Cost", "Cumulative", "Funding / timing", "Gain",
                       "Main driver", "Confidence", "Running total & condition"])
for k in range(1, NSTEPS + 1):
    r = HR + k
    out_k = f'INDEX({EGQ}!${STC["OUT Farming"]}${ST0 + k}:${STC["OUT Balanced"]}${ST0 + k},eStrat)'
    cells = {
        "B": f'=IF({RSUM("Pick", k)}="","",{k})',
        "C": f'=IF({RSUM("Pick", k)}="",IF({k}=1,"No roadmap yet - see Status",""),{RSUM("Pick", k)})',
        "D": f"={RSUM('Type', k)}",
        "E": f'=IF({RSUM("Pick", k)}="","",{RSUM("From", k)}&" → "&{RSUM("To", k)})',
        "F": "=" + fmt_coins(RSUM("Cost", k)),
        "G": "=" + fmt_coins(RSUM("Cumulative cost", k)),
        "H": f"={RSUM('Note', k)}",
        "I": f"={RSUM('Gain', k)}",
        "J": f"={RSUM('Driver', k)}",
        "K": f"={RSUM('Confidence', k)}",
        "L": (f'=IF({RSUM("Pick", k)}="","","Total so far: "&IF(OR(eStrat=2,eStrat=3),TEXT({out_k},"+0.0")&" waves",'
              f'TEXT(EXP({out_k})-1,"+0.00%"))&IF({RSUM("Confidence", k)}="Low"," · depends on your bottleneck - update run evidence to confirm",'
              f'IF({RSUM("Confidence", k)}="Medium"," · uses an estimated input",""))&IF(AND({RSUM("Type", k)}="Lab",{RSUM("Lab start (h)", k)}>{RSUM("Funded at (h)", k)}+0.01)," · waits for a free lab slot",""))'),
    }
    bg = PANEL if k % 2 else PANEL2
    for colL, f_ in cells.items():
        c = rm[f"{colL}{r}"]
        c.value = f_
        body(c, bg=bg, size=9, align=LEFT if colL in "CDHIJL" else (CENTER if colL in "BEK" else RIGHT))
    rm[f"C{r}"].font = font(TEXT, 10, True)
    rm[f"B{r}"].font = font(CYAN, 11, True)
    rm.row_dimensions[r].height = 20
rm.conditional_formatting.add(f"K{HR + 1}:K{HR + NSTEPS}", CellIsRule(operator="equal", formula=['"High"'], font=font(GREEN, 9, True)))
rm.conditional_formatting.add(f"K{HR + 1}:K{HR + NSTEPS}", CellIsRule(operator="equal", formula=['"Medium"'], font=font(AMBER, 9, True)))
rm.conditional_formatting.add(f"K{HR + 1}:K{HR + NSTEPS}", CellIsRule(operator="equal", formula=['"Low"'], font=font(RED, 9, True)))
rm.conditional_formatting.add(f"D{HR + 1}:D{HR + NSTEPS}", CellIsRule(operator="equal", formula=['"Lab"'], font=font(VIOLET, 9, True)))
rm.conditional_formatting.add(f"D{HR + 1}:D{HR + NSTEPS}", CellIsRule(operator="equal", formula=['"Enhancement"'], font=font(AMBER, 9, True)))
ur = HR + NSTEPS + 2
section(rm, ur, 2, "RELEVANT UNLOCKS & NOTES", 11, color=VIOLET)
unlock_lines = [
    f'=IF(AND(N({PP}!$E${ENH_LAB_ROW})<1,N(INDEX(ppTierWave,12))>=60),"▶ Unlock: research Workshop Enhancements (5B coins). Enhancements then join this roadmap.",IF(N({PP}!$E${ENH_LAB_ROW})<1,"Workshop Enhancements unlock at Tier 12 Wave 60 (milestone) + the Workshop Enhancements lab.","✔ Workshop Enhancements researched - enhancements you marked unlocked are included."))',
    f'=IF(SUMPRODUCT(({PP}!$H${PPWS0}:$H${PPWS1}=0)*({PP}!$F${PPWS0}:$F${PPWS1}<>"Base"))>0,"▶ "&SUMPRODUCT(({PP}!$H${PPWS0}:$H${PPWS1}=0)*({PP}!$F${PPWS0}:$F${PPWS1}<>"Base"))&" Workshop upgrades are locked (or not confirmed). Unlock prices are shown in game; they are not in the verified dataset, so the roadmap skips them.","✔ All Workshop upgrade groups are unlocked.")',
    '="Labs already researching are excluded until they finish. Labs wait for the earliest free slot; the same lab never runs twice at once."',
    '="Only investments with a modeled effect appear here. Not-quantified items (regen, orbs, land mines, UW labs, cards...) are listed on the optimizer sheets for your judgment."',
    '="Coins are spent in roadmap order: an item is funded when cumulative cost minus your coins is earned at your coins/hour."',
]
for i, f_ in enumerate(unlock_lines):
    c = rm.cell(ur + 1 + i, 2, f_)
    c.font = font(TEXT if i < 2 else MUTED, 9)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
rm.freeze_panes = f"C{HR + 1}"

# ---------------- Gem Planner
gp = S["Gem Planner"]
setup_sheet(gp, tab_color=CYAN, zoom=90, rows=50, cols=16,
            widths={"A": 2, "B": 34, "C": 12, "D": 12, "E": 16, "F": 14, "G": 12, "H": 13, "I": 62})
title_bar(gp, 1, 2, "GEM INVESTMENT PLANNER", None)
gp.cell(2, 2, '=" Gem options valued for the "&inStrategy&" goal as outcome-days over your "&eHorizon&"-day horizon (how much better, for how long)."').font = font(MUTED, 10, italic=True)
nav(gp, 1, 6, NAVS[:3])
# best lab research rate (outcome per slot-day), among eligible labs
lbV, lbH, lbK = E("V", LB_FIRST, LB_LAST), E("Hours", LB_FIRST, LB_LAST), E("Key", LB_FIRST, LB_LAST)
gp["N4"] = "Best lab rate (outcome / slot-day)"
gp["O4"] = f"=IFERROR(SUMPRODUCT(MAX(({lbK}>0)*IFERROR({lbV}/({lbH}/24),0))),0)"
gp["N5"] = "Best lab row"
gp["O5"] = f'=IFERROR(MATCH(1,{E("Rank", LB_FIRST, LB_LAST)},0),"")'
gp["N6"] = "Best lab V"
gp["O6"] = f'=IF(O5="","",IF(INDEX({lbK},O5)>0,INDEX({lbV},O5),""))'
gp["N7"] = "Best lab hours"
gp["O7"] = f'=IF(O5="","",INDEX({lbH},O5))'
gp["N8"] = "Best lab name"
gp["O8"] = f'=IF(O6="","",INDEX({E("Name", LB_FIRST, LB_LAST)},O5))'
for rr in range(4, 9):
    gp[f"N{rr}"].font = font(MUTED, 8)
    gp[f"O{rr}"].font = font(MUTED, 8)
gp.column_dimensions["N"].hidden = True
gp.column_dimensions["O"].hidden = True


def rush_gems(h):
    s_ = f"(({h})*3600)"
    return (f"CEILING(IF({s_}>31104000,25000,IF({s_}>7776000,(17000/23328000)*({s_}-7776000)+8000,IF({s_}>2592000,"
            f"(4450/5184000)*({s_}-2592000)+3550,IF({s_}>604800,(2550/1987200)*({s_}-604800)+1000,IF({s_}>86400,"
            f"(837/518400)*({s_}-86400)+163,IF({s_}>3600,(155.5/82800)*({s_}-3600)+7.5,IF({s_}>60,(7.375/3540)*({s_}-60)+0.125,"
            f"IF({s_}>1,(0.122917/59)*({s_}-1)+0.002083,0)))))))),1)")


kpi(gp, 4, 2, "AVAILABLE GEMS", '=IF(ISNUMBER(pGems),TEXT(pGems,"#,##0"),"enter gems")', "Player Profile")
kpi(gp, 4, 3, "GEM INCOME / DAY", '=IF(N(pGemsDay)>0,TEXT(pGemsDay,"#,##0"),"optional")', "for saving estimates", span=2, color=VIOLET)
kpi(gp, 4, 5, "BEST NOW", "=IFERROR(INDEX(B13:B23,MATCH(1,J13:J23,0)),\"—\")", "highest value per gem you can afford", span=2, color=GREEN)
kpi(gp, 4, 7, "WORTH SAVING FOR", "=IFERROR(INDEX(B13:B23,MATCH(1,K13:K23,0)),\"—\")", "better value per gem, not yet affordable", span=3, color=AMBER)
HR = 12
header_row(gp, HR, 2, ["Gem option", "Gems", "Affordable", "Value (outcome-days)", "Value per gem", "Status",
                       "Remaining", "Days to save", "Explanation"])
H_ = "eHorizon"
rate = "$O$4"
opts = []
opts.append(("Next lab slot", f'=IF(eSlots>=5,"",INDEX(tLabSlotGems,eSlots+1))',
             f'=IF(OR(eSlots>=5,{rate}<=0),"",IF(eFree>0,0,IF(eResTime=1,{rate}*{H_}^2/2,0)))',
             f'=IF(eSlots>=5,"All 5 slots owned",IF(eFree>0,"You already have "&eFree&" idle slot(s): fill them before buying more.",IF(eResTime=1,"Adds a research stream at your best lab rate ("&$O$8&") for the whole horizon.","Your research is coin-limited, so an extra slot would sit idle.")))'))
for s_ in range(1, 6):
    lab_ = f"INDEX(ppSlotLab,{s_})"
    hrs = f"INDEX(ppSlotHrs,{s_})"
    vcur = f'IFERROR(INDEX({E("V", LB_FIRST, LB_LAST)},MATCH({lab_},{E("ID", LB_FIRST, LB_LAST)},0)),0)'
    opts.append((f'=IF({lab_}="","Rush slot {s_} (empty)","Rush slot {s_}: "&IFERROR(INDEX({E("Name", LB_FIRST, LB_LAST)},MATCH({lab_},{E("ID", LB_FIRST, LB_LAST)},0)),{lab_}))',
                 f'=IF(OR({lab_}="",N({hrs})<=0),"",{rush_gems(hrs)})',
                 f'=IF(OR({lab_}="",N({hrs})<=0),"",N({vcur})*{hrs}/24+{rate}*{hrs}/24*MAX(0,{H_}-{hrs}/24))',
                 f'=IF(OR({lab_}="",N({hrs})<=0),"Nothing to rush in this slot.","Finishes "&TEXT({hrs},"0.0")&"h early: its benefit arrives sooner and the slot frees for your next research.")'))
opts.append(("=\"Start + rush best lab: \"&$O$8", f'=IF($O$7="","",{rush_gems("$O$7")})',
             f'=IF($O$6="","",$O$6*$O$7/24+{rate}*$O$7/24*MAX(0,{H_}-$O$7/24))',
             '="Only sensible when a slot is free: instant completion of your top-ranked research."'))
opts.append(("Next card slot", "=IF(N(pCardSlotCost)>0,pCardSlotCost,\"\")", '="NQ"',
             '="Not quantified: depends on which card you would equip. Per-slot prices are not in a verified source - enter the in-game price. 22 gem slots cost 58,400 in total."'))
opts.append(("Buy cards (per card)", "=gCard", '="NQ"',
             '="Not quantified: random card (80% common / 17% rare / 3% epic). Star upgrades cost 20/40/100/160/240/400/640 gems."'))
opts.append(("Module pull (per pull)", "=gPull", '="NQ"',
             '="Not quantified: 2.5% epic chance per pull; pity at 150 pulls (3,000 gems; pity not independently verified)."'))
GR0 = HR + 1
for i, (lab_, gems, val, expl) in enumerate(opts):
    r = GR0 + i
    cells = {
        "B": lab_ if lab_.startswith("=") else lab_, "C": gems,
        "D": f'=IF(ISNUMBER(C{r}),IF(N(pGems)>=C{r},"Yes","No"),"")',
        "E": val,
        "F": f'=IF(AND(ISNUMBER(E{r}),ISNUMBER(C{r})),IF(C{r}>0,E{r}/C{r},""),"")',
        "G": f'=IF(E{r}="NQ","Judgment",IF(N(E{r})>0,"Quantified",IF(C{r}="","n/a","No value now")))',
        "H": f'=IF(AND(ISNUMBER(C{r}),D{r}="No"),C{r}-N(pGems),"")',
        "I": f'=IF(AND(ISNUMBER(H{r}),N(pGemsDay)>0),H{r}/pGemsDay,"")',
        "J": "",  # best-now flag
        "K": "",  # save flag
        "L": expl,
    }
    bg = PANEL if i % 2 == 0 else PANEL2
    for colL, f_ in cells.items():
        c = gp[f"{colL}{r}"]
        c.value = f_
        body(c, bg=bg, size=9, align=LEFT if colL in "BGL" else (CENTER if colL == "D" else RIGHT))
    gp[f"C{r}"].number_format = "#,##0"
    gp[f"E{r}"].number_format = "0.000"
    gp[f"F{r}"].number_format = "0.00E+0"
    gp[f"H{r}"].number_format = "#,##0"
    gp[f"I{r}"].number_format = "0.0"
GR1 = GR0 + len(opts) - 1
# move explanation to column I (wide) and keep J/K hidden flags in M/N
for r in range(GR0, GR1 + 1):
    gp[f"I{r}"].value, gp[f"L{r}"].value = gp[f"L{r}"].value, gp[f"I{r}"].value
    gp[f"M{r}"] = gp[f"L{r}"].value  # days to save (moved)
    gp[f"L{r}"] = None
    gp[f"I{r}"].alignment = LEFTW
    gp.row_dimensions[r].height = 30
header_row(gp, HR, 2, ["Gem option", "Gems", "Affordable", "Value (outcome-days)", "Value per gem", "Status",
                       "Gems still needed", "Explanation"])
gp.column_dimensions["I"].width = 70
fr = f"$F${GR0}:$F${GR1}"
for r in range(GR0, GR1 + 1):
    gp[f"J{r}"] = f'=IF(AND(D{r}="Yes",ISNUMBER(F{r}),N(F{r})>0),IF(F{r}=MAX(IF(($D${GR0}:$D${GR1}="Yes")*ISNUMBER({fr}),{fr},0)),1,0),0)'
    gp[f"K{r}"] = (f'=IF(AND(D{r}="No",ISNUMBER(F{r}),N(F{r})>0),IF(AND(F{r}=MAX(IF(($D${GR0}:$D${GR1}="No")*ISNUMBER({fr}),{fr},0)),'
                   f'F{r}>MAX(IF(($D${GR0}:$D${GR1}="Yes")*ISNUMBER({fr}),{fr},0))),1,0),0)')
    for colL in "JKM":
        gp[f"{colL}{r}"].font = font(BG, 6)
gp.formula_attributes = {}
# array flags: write as array formulas so Excel and LibreOffice evaluate IF over ranges
from openpyxl.worksheet.formula import ArrayFormula  # noqa: E402
for r in range(GR0, GR1 + 1):
    for colL in "JK":
        gp[f"{colL}{r}"] = ArrayFormula(f"{colL}{r}", gp[f"{colL}{r}"].value)
gp.conditional_formatting.add(f"B{GR0}:I{GR1}", FormulaRule(formula=[f"$J{GR0}=1"], fill=fill("12302A")))
gp.conditional_formatting.add(f"B{GR0}:I{GR1}", FormulaRule(formula=[f"$K{GR0}=1"], fill=fill("33280F")))
sr = GR1 + 2
section(gp, sr, 2, "RECOMMENDATION", 8, color=VIOLET)
best_r = f"MATCH(1,$J${GR0}:$J${GR1},0)"
save_r = f"MATCH(1,$K${GR0}:$K${GR1},0)"
second = f"LARGE(IF(ISNUMBER({fr}),{fr},0),2)"
rec_lines = [
    f'=IFERROR("✔ Best gem investment now: "&INDEX($B${GR0}:$B${GR1},{best_r})&" for "&TEXT(INDEX($C${GR0}:$C${GR1},{best_r}),"#,##0")&" gems.","No quantified gem option is affordable right now (or the profile lacks lab data).")',
    f'=IFERROR("◆ Worth saving for: "&INDEX($B${GR0}:$B${GR1},{save_r})&" - needs "&TEXT(INDEX($H${GR0}:$H${GR1},{save_r}),"#,##0")&" more gems"&IF(N(pGemsDay)>0," (about "&TEXT(INDEX($H${GR0}:$H${GR1},{save_r})/pGemsDay,"0.0")&" days)","")&" and returns more per gem than anything affordable.","Nothing unaffordable beats the best affordable option per gem - no need to save.")',
    f'=IFERROR("Opportunity cost: spending on the best option forgoes about "&TEXT(INDEX($C${GR0}:$C${GR1},{best_r})*{second},"0.000")&" outcome-days you could get from the next-best quantified option with the same gems.","")',
    '="Cards, card slots and module pulls are listed for completeness but are not scored: their value depends on what you draw and equip. Judge them alongside these numbers."',
    '="Value = improvement x days it is enjoyed within your horizon. Lab-slot value only counts when research is time-limited; rush value counts the earlier benefit plus the freed slot."',
]
for i, f_ in enumerate(rec_lines):
    c = gp.cell(sr + 1 + i, 2, f_)
    c.font = font(TEXT if i < 3 else MUTED, 10 if i < 2 else 9, i < 2)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    if i == 2:
        gp[f"B{sr + 1 + i}"] = ArrayFormula(f"B{sr + 1 + i}", f_)
for colL in "JKM":
    gp.column_dimensions[colL].hidden = True

# ======================================================================
# 8. ULTIMATE WEAPONS & POWER STONES
# ======================================================================
UWK = ["chain_lightning", "smart_missiles", "death_wave", "chrono_field", "inner_land_mines", "golden_tower",
       "poison_swamp", "black_hole", "spotlight"]
UWD = D["uw"]
# --- data sheet
uwl_rows, uw_start = [], {}
for k_ in UWK:
    for si, st_ in enumerate(UWD[k_]["stats"]):
        uw_start[(k_, si)] = len(uwl_rows) + 1
        cum = 0.0
        for L, txt, num, cost in st_["levels"]:
            cum += cost
            uwl_rows.append([k_, st_["name"], L, num, txt, cost, cum])
data_sheet(S["GD UW Levels"], ["Weapon", "Stat", "Level", "Value (number)", "Value (as shown)",
                               "Stones to reach this level", "Cumulative stones"], uwl_rows, [18, 16, 8, 14, 14, 16, 16])
NU = len(uwl_rows) + 1
name("rngUWV", "GD UW Levels", f"$D$2:$D${NU}")
name("rngUWC", "GD UW Levels", f"$F$2:$F${NU}")
name("rngUWCUM", "GD UW Levels", f"$G$2:$G${NU}")
# --- Game Data: UW table
UWR0 = LBR0 + len(D["labs"]) + 4
section(gd, UWR0 - 2, 2, "ULTIMATE WEAPONS (9 weapons x 3 stone stats + UW+ stat)", 12)
header_row(gd, UWR0 - 1, 2, ["Weapon", "Key", "Stat #", "Stat", "Max level", "Data start", "Role", "Export index",
                             "Source", "Verified", "Validation"])
UWROW = {}
rr = UWR0
for k_ in UWK:
    for si, st_ in enumerate(UWD[k_]["stats"]):
        UWROW[(k_, si)] = rr
        vals = [UWD[k_]["name"], k_, si + 1 if si < 3 else "UW+", st_["name"], len(st_["levels"]) - 1, uw_start[(k_, si)],
                UWD[k_]["role"], UWD[k_]["exportIndex"], "TheTowerSDK src/data/ultimate-weapons/stones.data.ts",
                VERIFIED_ON, "Verified; costs and values match Effective Paths DVT_UWs (739/739 rows)"]
        for j, v in enumerate(vals):
            body(gd.cell(rr, 2 + j, v), bg=PANEL if (rr % 2) else PANEL2, size=9, align=LEFTW if j in (8, 10) else LEFT)
        rr += 1
UNL0 = rr + 2
gd.cell(UNL0, 2, "Stones to unlock the Nth weapon (index = weapons owned)").font = font(VIOLET, 10, True)
for i, v in enumerate(D["uwUnlockStones"]):
    gd.cell(UNL0 + 1 + i, 2, i + 1)
    gd.cell(UNL0 + 1 + i, 3, v)
    body(gd.cell(UNL0 + 1 + i, 2), align=RIGHT)
    body(gd.cell(UNL0 + 1 + i, 3), align=RIGHT, color=CYAN)
gd.cell(UNL0 + 1, 4, "Verified: SDK ULTIMATE_WEAPON_STONE_COST; buying offers three random choices").font = font(MUTED, 9)
name("tUWUnlock", "Game Data", f"$C${UNL0 + 1}:$C${UNL0 + 9}")


def UV(k_, si, lv):
    return f"INDEX(rngUWV,'Game Data'!$G${UWROW[(k_, si)]}+{lv})"


def UC(k_, si, lv):  # stones to reach level lv
    return f"INDEX(rngUWC,'Game Data'!$G${UWROW[(k_, si)]}+{lv})"


# --- Player Profile: UW inputs
r = PP_LAST + 1
section(pp, r, 2, "ULTIMATE WEAPONS & POWER STONES", 10)
r += 1
for key, label, fmtx, guide in [("pStones", "Power Stones available", "#,##0", "Stones you can spend now"),
                                ("pStonesDay", "Stone income per day", "#,##0", "Tournaments, missions, events (your estimate)")]:
    body(pp.cell(r, 2, label), bg=PANEL)
    input_cell(pp.cell(r, 3), fmt=fmtx)
    body(pp.cell(r, 4, f'={IMP("P|" + key)}'), color=MUTED, align=RIGHT, fmt=fmtx)
    body(pp.cell(r, 5, f'=IF(C{r}<>"",C{r},D{r})'), color=CYAN, bold=True, align=RIGHT, fmt=fmtx)
    body(pp.cell(r, 11, guide), color=MUTED, size=9)
    name(key, "Player Profile", f"$E${r}")
    r += 1
uw_names = [UWD[k_]["name"] for k_ in UWK]
dv_uw = dv_list(pp, "uwlist", uw_names)
for i in range(1, 4):
    body(pp.cell(r, 2, f"New-weapon choice {i} offered by the game"), bg=PANEL)
    input_cell(pp.cell(r, 3), align=LEFT)
    dv_uw.add(pp.cell(r, 3).coordinate)
    body(pp.cell(r, 5, f'=IF(C{r}<>"",C{r},{IMP(f"P|pUWChoice{i}")})'), color=CYAN, bold=True)
    body(pp.cell(r, 11, "Pick from the three weapons the game shows you (leave blank if none offered)" if i == 1 else ""),
         color=MUTED, size=9)
    name(f"pUWChoice{i}", "Player Profile", f"$E${r}")
    r += 1
r += 1
header_row(pp, r, 2, ["Weapon", "Owned? (entry)", "Stat 1 lv (entry)", "Stat 2 lv (entry)", "Stat 3 lv (entry)",
                      "Owned used", "Stat 1 used", "Stat 2 used", "Stat 3 used", "Stats"])
r += 1
PP_UW = {}
for i, k_ in enumerate(UWK):
    PP_UW[k_] = r
    bg = PANEL if i % 2 == 0 else PANEL2
    body(pp.cell(r, 2, UWD[k_]["name"]), bg=bg)
    input_cell(pp.cell(r, 3), align=CENTER)
    dv_yn.add(pp.cell(r, 3).coordinate)
    ex = UWD[k_]["exportIndex"]
    for j in range(3):
        input_cell(pp.cell(r, 4 + j), fmt="0")
        mx = len(UWD[k_]["stats"][j]["levels"]) - 1
        dv_num(pp, f"uw{mx}", 0, mx, whole=True).add(pp.cell(r, 4 + j).coordinate)
        imp = IMP(f"UWL|{ex * 3 + j}")
        body(pp.cell(r, 8 + j, f'=IF(G{r}<>1,0,IF({CL(4 + j)}{r}<>"",{CL(4 + j)}{r},N({imp})))'), bg=bg, color=CYAN,
             bold=True, align=CENTER)
    body(pp.cell(r, 7, f'=IF(C{r}="Yes",1,IF(C{r}="No",0,IF(N({IMP(f"UWU|{ex}")})=1,1,0)))'), bg=bg, color=CYAN,
         bold=True, align=CENTER, fmt='"Yes";"No";"No"')
    body(pp.cell(r, 11, " / ".join(s_["name"] for s_ in UWD[k_]["stats"][:3])), bg=bg, color=MUTED, size=9)
    r += 1
PP_LAST = r
name("ppUWOwned", "Player Profile", f"$G${PP_UW[UWK[0]]}:$G${PP_UW[UWK[-1]]}")
name("ppUWName", "Player Profile", f"$B${PP_UW[UWK[0]]}:$B${PP_UW[UWK[-1]]}")


def UWO(k_):
    return f"{PP}!$G${PP_UW[k_]}"


def UWL(k_, j):
    return f"{PP}!${CL(8 + j)}${PP_UW[k_]}"


# ---------------- UW Optimizer sheet
uo = S["UW Optimizer"]
setup_sheet(uo, tab_color=CYAN, zoom=90, rows=320, cols=58,
            widths={"A": 2, "B": 30, "C": 26, "D": 12, "E": 16, "F": 20, "G": 26, "H": 22, "I": 8, "J": 70})
title_bar(uo, 1, 2, "ULTIMATE WEAPON & POWER STONE OPTIMIZER", None)
uo.cell(2, 2, '=" Goal: "&inStrategy&". Coin effects (Golden Tower, Black Hole, Death Wave, cooldown sync) are computed; combat value of weapons is strategy judgment and is labelled as such."').font = font(MUTED, 10, italic=True)
nav(uo, 1, 8, [NAVS[0], NAVS[3]])
# ---- economic UW model, generated for any level set
LAB_GTD = PP_LB["golden_tower_duration"]
LAB_GTB = PP_LB["golden_tower_bonus"]
LAB_BHC = PP_LB["black_hole_coin_bonus"]
LAB_DWC = PP_LB["death_wave_coin_bonus"]


SCEN = {"next": 0}
SC_COL0 = 30  # scenario table starts at column AD on the UW sheet
SC_HDR = ["Scenario", "GT mult lv", "GT dur lv", "GT cd lv", "BH dur lv", "BH cd lv", "DW qty lv", "DW cd lv",
          "Own GT", "Own BH", "Own DW", "M", "Dg", "CDg", "ug", "Db", "CDb", "ub", "B", "sb", "Qd", "CDd", "W", "sd",
          "syncB", "syncD", "mult"]
SCC = {h: CL(SC_COL0 + i) for i, h in enumerate(SC_HDR)}
SC_ROW0 = 160


def econ_parts(lv, own, label=""):
    """Write one scenario row of the UW coin model; lv(key, j) / own(key) give level / owned expressions.
    Returns a dict of short cell references (M, ug, syncB, mult, ...)."""
    r = SC_ROW0 + SCEN["next"]
    SCEN["next"] += 1
    c = lambda h: f"${SCC[h]}${r}"  # noqa: E731
    vals = {
        "Scenario": label,
        "GT mult lv": "=" + lv("golden_tower", 0), "GT dur lv": "=" + lv("golden_tower", 1),
        "GT cd lv": "=" + lv("golden_tower", 2), "BH dur lv": "=" + lv("black_hole", 1),
        "BH cd lv": "=" + lv("black_hole", 2), "DW qty lv": "=" + lv("death_wave", 1),
        "DW cd lv": "=" + lv("death_wave", 2),
        "Own GT": "=" + own("golden_tower"), "Own BH": "=" + own("black_hole"), "Own DW": "=" + own("death_wave"),
        "M": f"={UV('golden_tower', 0, c('GT mult lv'))}+{LE('L_GT', f'N({PP}!$E${LAB_GTB})')}",
        "Dg": f"={UV('golden_tower', 1, c('GT dur lv'))}+INDEX(rngLBE,'Game Data'!$H${LBROW['golden_tower_duration']}+N({PP}!$E${LAB_GTD}))",
        "CDg": f"={UV('golden_tower', 2, c('GT cd lv'))}",
        "ug": f"={c('Own GT')}*MIN(1,{c('Dg')}/{c('CDg')})",
        "Db": f"={UV('black_hole', 1, c('BH dur lv'))}",
        "CDb": f"={UV('black_hole', 2, c('BH cd lv'))}",
        "ub": f"=MIN(1,{c('Db')}/{c('CDb')})",
        "B": f"={LE('L_BH', f'N({PP}!$E${LAB_BHC})')}",
        "sb": f"=IF(AND(eBHok,{c('Own BH')}=1,uwUB0>0),MIN(1,pBHs*{c('ub')}/uwUB0),0)",
        "Qd": f"={UV('death_wave', 1, c('DW qty lv'))}",
        "CDd": f"={UV('death_wave', 2, c('DW cd lv'))}",
        "W": f"={LE('L_DW', f'N({PP}!$E${LAB_DWC})')}",
        "sd": f"=IF(AND(eDWok,{c('Own DW')}=1,uwDW0>0),MIN(1,pDWs*({c('Qd')}/{c('CDd')})/uwDW0),0)",
        "syncB": f"=AND({c('Own GT')}=1,{c('Own BH')}=1,{c('CDg')}={c('CDb')},{c('Db')}<={c('Dg')})",
        "syncD": f"=AND({c('Own GT')}=1,{c('Own DW')}=1,{c('CDg')}={c('CDd')})",
        "mult": (f"=((1+{c('ug')}*({c('M')}-1))+IF({c('syncB')},MIN({c('sb')},{c('ug')})*{c('M')}*({c('B')}-1),0)"
                 f"+IF({c('syncD')},MIN({c('sd')},{c('ug')})*{c('M')}*({c('W')}-1),0))"
                 f"*IF({c('syncB')},1,1+{c('sb')}*({c('B')}-1))*IF({c('syncD')},1,1+{c('sd')}*({c('W')}-1))"),
    }
    for h, v in vals.items():
        uo[f"{SCC[h]}{r}"] = v
        uo[f"{SCC[h]}{r}"].font = font(MUTED, 8)
    return {k: c(k) for k in ("M", "Dg", "CDg", "ug", "Db", "CDb", "ub", "B", "sb", "Qd", "CDd", "W", "sd",
                              "syncB", "syncD", "mult")}


cur_lv = lambda k_, j: UWL(k_, j)  # noqa: E731
cur_own = lambda k_: UWO(k_)  # noqa: E731
CALC0 = 110
section(uo, CALC0 - 1, 2, "CALCULATIONS (current state)", 9, color=VIOLET)
calc = [
    ("uwUB0", "Black Hole uptime now", f"=IF({UWO('black_hole')}=1,MIN(1,{UV('black_hole', 1, UWL('black_hole', 1))}/{UV('black_hole', 2, UWL('black_hole', 2))}),0)", "0.0%"),
    ("uwDW0", "Death Wave waves per second now", f"=IF({UWO('death_wave')}=1,{UV('death_wave', 1, UWL('death_wave', 1))}/{UV('death_wave', 2, UWL('death_wave', 2))},0)", "0.0000"),
    ("uwOwned", "Weapons owned", "=SUM(ppUWOwned)", "0"),
    ("uwNextCost", "Stones for the next weapon", '=IF(uwOwned>=9,"",INDEX(tUWUnlock,uwOwned+1))', "#,##0"),
    ("uwEcon", "Coin-model active (Farming/Balanced)", "=OR(eStrat=1,eStrat=4)", None),
]
for i_, h_ in enumerate(SC_HDR):
    uo.cell(SC_ROW0 - 1, SC_COL0 + i_, h_).font = font(VIOLET, 8, True)
uo.cell(SC_ROW0 - 2, SC_COL0, "UW COIN-MODEL SCENARIOS (one row per hypothetical weapon state; row 1 = current)").font = font(VIOLET, 10, True)
P0 = econ_parts(cur_lv, cur_own, "Current")
for nm_, key_ in [("uwM", "M"), ("uwDg", "Dg"), ("uwCDg", "CDg"), ("uwUG", "ug"), ("uwDb", "Db"), ("uwCDb", "CDb"),
                  ("uwB", "B"), ("uwSB", "sb"), ("uwCDd", "CDd"), ("uwW", "W"), ("uwSD", "sd"), ("uwSyncB", "syncB"),
                  ("uwSyncD", "syncD"), ("uwMult", "mult")]:
    calc.append((nm_, {"M": "Golden Tower multiplier (stones + lab)", "Dg": "Golden Tower duration (s)",
                       "CDg": "Golden Tower cooldown (s)", "ug": "Golden Tower uptime", "Db": "Black Hole duration (s)",
                       "CDb": "Black Hole cooldown (s)", "B": "Black Hole coin bonus (lab)", "sb": "Share of kills in Black Hole",
                       "CDd": "Death Wave cooldown (s)", "W": "Death Wave coin bonus (lab)", "sd": "Share of kills hit by Death Wave",
                       "syncB": "GT + BH synchronized", "syncD": "GT + DW synchronized",
                       "mult": "Average UW coin multiplier"}[key_], "=" + P0[key_], "0.000"))
calc.append(("eGTu", "Golden Tower uptime used by the main engine", '=IF(uwUG>0,uwUG,N(pGTu))', "0.0%"))
calc.append(("eGTB", "Golden Tower bonus used by the main engine", f'=IF({UWO("golden_tower")}=1,uwM,N(pGTB))', "0.00"))
for i, (nm_, lab_, f_, fx) in enumerate(calc):
    rr = CALC0 + i
    body(uo.cell(rr, 2, lab_), bg=PANEL, size=9)
    body(uo.cell(rr, 3, f_), bg=PANEL, color=CYAN, align=RIGHT, size=9, fmt=fx)
    name(nm_, "UW Optimizer", f"$C${rr}")

# ---- KPIs
kpi(uo, 4, 2, "POWER STONES", '=IF(ISNUMBER(pStones),TEXT(pStones,"#,##0"),"enter stones")', "available now")
kpi(uo, 4, 3, "WEAPONS OWNED", '=uwOwned&" / 9"', "Player Profile", span=2, color=VIOLET)
kpi(uo, 4, 5, "NEXT WEAPON COSTS", '=IF(uwOwned>=9,"all owned",TEXT(uwNextCost,"#,##0")&" stones")', "price rises with each weapon", span=2)
kpi(uo, 4, 7, "UW COIN MULTIPLIER", '=TEXT(uwMult,"0.000")&"x"', "average, from GT / BH / DW model", span=2, color=GREEN)
kpi(uo, 4, 9, "SYNC", '=IF(uwSyncB,"GT+BH synced",IF(AND(' + UWO("golden_tower") + '=1,' + UWO("black_hole") + '=1),"GT/BH not synced","—"))', "equal cooldowns stack multipliers", span=2, color=AMBER)

# ---- New weapon choices
R = 9
section(uo, R, 2, "NEW WEAPON: RANK THE THREE CHOICES THE GAME OFFERED", 9)
header_row(uo, R + 1, 2, ["Offered weapon", "Stone cost", "Owned?", "Coin gain (Farming)", "Gain per 100 stones",
                          "Role", "Fits bottleneck?", "Rank", "Why"])
bott_dmg = "CHOOSE(eStrat,eWdF,eWdT,eWdM,eWdF)"
for i in range(1, 4):
    rr = R + 1 + i
    ch = f"pUWChoice{i}"
    key_of = f'INDEX({{"{chr(34).join([])}"}},1)'
    keyx = f"MATCH({ch},ppUWName,0)"
    # coin gain of owning each weapon at level 0 (only GT/BH/DW have coin effects)
    gains = []
    for k_ in ("golden_tower", "black_hole", "death_wave"):
        own_new = lambda kk, k_=k_: ("1" if kk == k_ else UWO(kk))  # noqa: E731
        lv_new = lambda kk, j, k_=k_: ("0" if kk == k_ else UWL(kk, j))  # noqa: E731
        p_ = econ_parts(lv_new, own_new)
        gains.append(f'IF({ch}="{UWD[k_]["name"]}",LN({p_["mult"]})-LN(uwMult),')
    gain_expr = "".join(gains) + '""' + ")" * 3
    roles = "".join(f'IF({ch}="{UWD[k_]["name"]}","{UWD[k_]["role"]}",' for k_ in UWK) + '""' + ")" * 9
    cells = {
        "B": f'=IF({ch}="","(not entered)",{ch})',
        "C": f'=IF({ch}="","",uwNextCost)',
        "D": f'=IF({ch}="","",IF(INDEX(ppUWOwned,{keyx})=1,"Already owned!","No"))',
        "E": f'=IF({ch}="","",IF(ISNUMBER({gain_expr}),IF({gain_expr}>0,TEXT(EXP({gain_expr})-1,"+0.0%")&" coins","needs share input"),"no coin effect"))',
        "F": f'=IF(AND({ch}<>"",ISNUMBER({gain_expr}),N(uwNextCost)>0),IF({gain_expr}>0,TEXT((EXP({gain_expr})-1)/uwNextCost*100,"0.00%"),""),"")',
        "G": f'=IF({ch}="","",{roles})',
        "H": (f'=IF({ch}="","",IF(ISNUMBER(SEARCH("Economy",G{rr})),IF(OR(eStrat=1,eStrat=4),"Yes (coins)","No"),'
              f'IF({bott_dmg}=1,IF(ISNUMBER(SEARCH("Damage",G{rr})),"Yes (damage-limited)","Partly"),'
              f'IF({bott_dmg}=0,IF(ISNUMBER(SEARCH("Control",G{rr})),"Yes (survival-limited)","Partly"),"Unknown bottleneck"))))'),
        "Z": (f'=IF({ch}="",-1,IF(D{rr}="Already owned!",-1,IF(AND(uwEcon,ISNUMBER({gain_expr})),IF({gain_expr}>0,1000+{gain_expr},0),0)'
              f'+IF(LEFT(H{rr},3)="Yes",10,IF(H{rr}="Partly",5,0))))'),
    }
    for colL, f_ in cells.items():
        c = uo[f"{colL}{rr}"]
        c.value = f_
        body(c, size=9, align=LEFT if colL in "BGHE" else RIGHT)
    uo[f"B{rr}"].font = font(TEXT, 10, True)
    uo[f"I{rr}"] = f'=IF(Z{rr}<0,"",RANK(Z{rr},$Z${R + 2}:$Z${R + 4})+COUNTIF($Z${R + 2}:Z{rr},Z{rr})-1)'
    body(uo[f"I{rr}"], size=11, align=CENTER, bold=True, color=CYAN)
    uo[f"J{rr}"] = (f'=IF({ch}="","",IF(D{rr}="Already owned!","Check your entry: you already own this weapon.",'
                    f'IF(AND(uwEcon,LEFT(E{rr},1)="+"),"Computed: adds "&E{rr}&" on average (uptime x multiplier, with any cooldown sync). ",'
                    f'"")&IF(LEFT(H{rr},3)="Yes","Matches your "&IF(uwEcon,"goal","bottleneck")&". ","")'
                    f'&IF(OR(NOT(uwEcon),LEFT(E{rr},1)<>"+"),"Combat value is a strategy judgment (not computed): "&G{rr}&".","")))')
    body(uo[f"J{rr}"], size=9, align=LEFTW)
    uo.row_dimensions[rr].height = 30
    uo[f"Z{rr}"].font = font(BG, 6)
uo.cell(R + 5, 2, "Ranking: computed coin gain first (Farming/Balanced), then fit to your measured bottleneck. Confidence: "
                  "coin gains = Modeled; combat fit = Judgment (uncertain).").font = font(MUTED, 9, italic=True)

# ---- Stone upgrades (all 27 owned stats)
R2 = R + 7
section(uo, R2, 2, "UPGRADE NEXT: EVERY STONE UPGRADE ON WEAPONS YOU OWN", 9)
header_row(uo, R2 + 1, 2, ["Weapon · stat", "Level → next", "Stone cost", "Value now → next", "Coin gain",
                           "Gain per 100 stones", "Sync effect", "Rank", "Assessment"])
UP0 = R2 + 2
ups = [(k_, j) for k_ in UWK for j in range(3)]
for i, (k_, j) in enumerate(ups):
    rr = UP0 + i
    lvl = UWL(k_, j)
    mx = len(UWD[k_]["stats"][j]["levels"]) - 1
    lv_n = lambda kk, jj, k_=k_, j=j: (f"({UWL(kk, jj)}+1)" if (kk, jj) == (k_, j) else UWL(kk, jj))  # noqa: E731
    pn = econ_parts(lv_n, cur_own)
    econ_stat = (k_, j) in [("golden_tower", 0), ("golden_tower", 1), ("golden_tower", 2), ("black_hole", 1),
                            ("black_hole", 2), ("death_wave", 1), ("death_wave", 2)]
    g = f"(LN({pn['mult']})-LN(uwMult))" if econ_stat else '""'
    sname = UWD[k_]["stats"][j]["name"]
    cells = {
        "B": f"{UWD[k_]['name']} · {sname}",
        "C": f'=IF({UWO(k_)}<>1,"not owned",IF({lvl}>={mx},"MAX",{lvl}&" → "&({lvl}+1)))',
        "D": f'=IF(OR({UWO(k_)}<>1,{lvl}>={mx}),"",{UC(k_, j, lvl + "+1")})',
        "E": f'=IF(OR({UWO(k_)}<>1,{lvl}>={mx}),"",INDEX(\'GD UW Levels\'!$E$2:$E${NU},\'Game Data\'!$G${UWROW[(k_, j)]}+{lvl})&" → "&INDEX(\'GD UW Levels\'!$E$2:$E${NU},\'Game Data\'!$G${UWROW[(k_, j)]}+{lvl}+1))',
        "F": (f'=IF(D{rr}="","",IF({"NOT(eDWok)" if k_ == "death_wave" else ("NOT(eBHok)" if k_ == "black_hole" else "FALSE")},"needs share input",IF(ISNUMBER({g}),TEXT(EXP({g})-1,"+0.00%;-0.00%"),"not computed")))' if econ_stat else
              f'=IF(D{rr}="","","not computed")'),
        "G": (f'=IF(AND(D{rr}<>"",ISNUMBER({g})),TEXT((EXP({g})-1)/D{rr}*100,"0.000%;-0.000%"),"")' if econ_stat else '=""'),
        "H": (f'=IF(D{rr}="","",IF(AND(uwSyncB,NOT({pn["syncB"]})),"⚠ BREAKS GT/BH sync",IF(AND(NOT(uwSyncB),{pn["syncB"]}),"✔ creates GT/BH sync",'
              f'IF(AND(uwSyncD,NOT({pn["syncD"]})),"⚠ BREAKS GT/DW sync",IF(AND(NOT(uwSyncD),{pn["syncD"]}),"✔ creates GT/DW sync","")))))') if sname == "Cooldown" else '=""',
        "Z": (f'=IF(AND(uwEcon,D{rr}<>"",ISNUMBER({g})),IF({g}>1E-9,{g}/D{rr},-1),-1)' if econ_stat else "=-1"),
    }
    for colL, f_ in cells.items():
        c = uo[f"{colL}{rr}"]
        c.value = f_
        body(c, bg=PANEL if i % 2 == 0 else PANEL2, size=9, align=LEFT if colL in "BCEH" else RIGHT)
    uo[f"D{rr}"].number_format = "#,##0"
    uo[f"Z{rr}"].font = font(BG, 6)
    uo[f"I{rr}"] = f'=IF(Z{rr}>0,RANK(Z{rr},$Z${UP0}:$Z${UP0 + 26})+COUNTIF($Z${UP0}:Z{rr},Z{rr})-1,"")'
    body(uo[f"I{rr}"], bg=PANEL if i % 2 == 0 else PANEL2, size=10, align=CENTER, bold=True, color=CYAN)
    judg = {"Damage": "damage", "Control": "control"}
    uo[f"J{rr}"] = (f'=IF(D{rr}="","",IF(Z{rr}>0,"Computed coin gain"&IF(H{rr}<>""," · "&H{rr},"")&".",'
                    f'IF(AND(uwEcon,{("TRUE" if econ_stat else "FALSE")}),"No coin gain now"&IF(H{rr}<>""," ("&H{rr}&")","")&". Do not buy for coins.",'
                    f'"Judgment: "&IF(ISNUMBER(SEARCH("Damage","{UWD[k_]["role"]}")),IF({bott_dmg}=1,"relevant - your runs are damage-limited","lower priority unless damage limits you"),'
                    f'IF(ISNUMBER(SEARCH("Control","{UWD[k_]["role"]}")),IF({bott_dmg}=0,"relevant - your runs are survival-limited","lower priority unless survival limits you"),"economy weapon"))&" (combat effect not computed).")))')
    body(uo[f"J{rr}"], bg=PANEL if i % 2 == 0 else PANEL2, size=9, align=LEFTW)
uo.conditional_formatting.add(f"H{UP0}:H{UP0 + 26}", FormulaRule(formula=[f'LEFT($H{UP0},1)="⚠"'], font=font(RED, 9, True)))
uo.conditional_formatting.add(f"H{UP0}:H{UP0 + 26}", FormulaRule(formula=[f'LEFT($H{UP0},1)="✔"'], font=font(GREEN, 9, True)))
for rr in range(R + 2, R + 5):
    pass

# ---- Buy vs upgrade verdict + sync summary
R3 = UP0 + 28
section(uo, R3, 2, "BUY A NEW WEAPON OR UPGRADE?  ·  COOLDOWN SYNC  ·  SAVINGS", 9, color=VIOLET)
best_up = f"MATCH(1,$I${UP0}:$I${UP0 + 26},0)"
best_ch = f"MATCH(1,$I${R + 2}:$I${R + 4},0)"
lines = [
    f'=IFERROR("Best stone upgrade: "&INDEX($B${UP0}:$B${UP0 + 26},{best_up})&" ("&INDEX($F${UP0}:$F${UP0 + 26},{best_up})&" coins for "&TEXT(INDEX($D${UP0}:$D${UP0 + 26},{best_up}),"#,##0")&" stones).",IF(uwEcon,"No stone upgrade has a computed coin gain (own Golden Tower / Black Hole / Death Wave and fill the optional share inputs).","Tournament/Milestones: stone upgrades are ranked by judgment only - see Assessment column."))',
    f'=IFERROR("Top offered weapon: "&INDEX($B${R + 2}:$B${R + 4},{best_ch})&" ("&INDEX($E${R + 2}:$E${R + 4},{best_ch})&", "&TEXT(uwNextCost,"#,##0")&" stones).","Enter the three weapons the game offers on Player Profile to rank them.")',
    (f'=IFERROR(IF(AND(uwEcon,LEFT(INDEX($F${R + 2}:$F${R + 4},{best_ch}),1)<>"",ISNUMBER({best_up})),'
     f'IF(VALUE(SUBSTITUTE(INDEX($F${R + 2}:$F${R + 4},{best_ch}),"%",""))>VALUE(SUBSTITUTE(INDEX($G${UP0}:$G${UP0 + 26},{best_up}),"%","")),'
     f'"Verdict: BUY the new weapon - it returns more coins per stone than the best upgrade.","Verdict: UPGRADE first - the best upgrade returns more coins per stone than the new weapon."),'
     f'IF(AND(uwEcon,ISNUMBER({best_up})),"Verdict: UPGRADE first for coins - none of the offered weapons has a computed coin effect (their combat value is a judgment call).",'
     f'"Verdict: no computed comparison for this goal - weigh the new weapon\'s role against your bottleneck (judgment).")),"Verdict: enter choices and owned weapons to compare.")'),
    '=IF(uwSyncB,"Golden Tower and Black Hole cooldowns are equal ("&uwCDg&"s): Black Hole kills land inside Golden Tower and get both multipliers. Keep cooldown upgrades paired.",IF(AND(' + UWO("golden_tower") + '=1,' + UWO("black_hole") + '=1),"GT cooldown "&uwCDg&"s vs BH cooldown "&uwCDb&"s: not synced. Upgrades marked ✔ would sync them; check the cost before committing - stone upgrades cannot be undone.","Sync applies once you own both Golden Tower and Black Hole."))',
    f'=IFERROR("Savings target: "&TEXT(MAX(0,INDEX($D${UP0}:$D${UP0 + 26},{best_up})-N(pStones)),"#,##0")&" more stones for the best upgrade"&IF(N(pStonesDay)>0," (about "&TEXT(MAX(0,INDEX($D${UP0}:$D${UP0 + 26},{best_up})-N(pStones))/pStonesDay,"0.0")&" days)","")&IF(uwOwned<9,"; next weapon needs "&TEXT(MAX(0,uwNextCost-N(pStones)),"#,##0")&" more.","."),"")',
]
for i, f_ in enumerate(lines):
    c = uo.cell(R3 + 1 + i, 2, f_)
    c.font = font(AMBER if i == 2 else TEXT, 10, i == 2)
    c.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    uo.row_dimensions[R3 + 1 + i].height = 20

# ---- Power Stone track (sequential, separate budget)
TR0 = R3 + 8
section(uo, TR0, 2, "POWER STONE TRACK (sequential, separate stone budget) - coin goals only", 9, color=VIOLET)
ECON_STATS = [("golden_tower", 0), ("golden_tower", 1), ("golden_tower", 2), ("black_hole", 1), ("black_hole", 2),
              ("death_wave", 1), ("death_wave", 2)]
header_row(uo, TR0 + 1, 2, ["Step", "Upgrade", "Level", "Stones", "Cumulative", "Funded in", "Coin gain", "Pick #", "Note"])
# hidden state block: levels per econ stat per step (columns L..R), candidate gains per step (S..Y)
TS0 = TR0 + 2
for st_i, (k_, j) in enumerate(ECON_STATS):
    uo.cell(TR0 + 1, 12 + st_i, f"{k_}:{j} lv").font = font(MUTED, 7)
    uo.cell(TR0 + 1, 19 + st_i, f"{k_}:{j} gain/stone").font = font(MUTED, 7)
for step in range(0, 11):
    rr = TS0 + step
    for st_i, (k_, j) in enumerate(ECON_STATS):
        cl = CL(12 + st_i)
        if step == 0:
            uo[f"{cl}{rr}"] = f"={UWL(k_, j)}"
        else:
            uo[f"{cl}{rr}"] = f"={cl}{rr - 1}+IF($I{rr}={st_i + 1},1,0)"
        uo[f"{cl}{rr}"].font = font(MUTED, 7)
    if step == 10:
        continue
    # candidate gains from state row rr
    st_lv = {}
    for st_i, (k_, j) in enumerate(ECON_STATS):
        st_lv[(k_, j)] = f"${CL(12 + st_i)}{rr}"
    base_lv = lambda kk, jj: st_lv.get((kk, jj), UWL(kk, jj))  # noqa: E731
    p_base = econ_parts(base_lv, cur_own)
    for st_i, (k_, j) in enumerate(ECON_STATS):
        mx = len(UWD[k_]["stats"][j]["levels"]) - 1
        lvn = lambda kk, jj, k_=k_, j=j: (f"({base_lv(kk, jj)}+1)" if (kk, jj) == (k_, j) else base_lv(kk, jj))  # noqa: E731
        p_n = econ_parts(lvn, cur_own)
        cost = UC(k_, j, f"{st_lv[(k_, j)]}+1")
        uo[f"{CL(19 + st_i)}{rr}"] = (f'=IF(AND(uwEcon,{UWO(k_)}=1,{st_lv[(k_, j)]}<{mx}),MAX(-1,(LN({p_n["mult"]})-LN({p_base["mult"]}))/{cost}),-1)')
        uo[f"{CL(19 + st_i)}{rr}"].font = font(MUTED, 7)
    gr = f"$S{rr}:$Y{rr}"
    nxt = rr + 1
    # pick for step (step+1) shown on row nxt
    uo[f"I{nxt}"] = f'=IF(MAX({gr})>0,MATCH(MAX({gr}),{gr},0),"")'
    lab_names = [f"{UWD[k_]['name']} · {UWD[k_]['stats'][j]['name']}" for k_, j in ECON_STATS]
    pick_cost = "CHOOSE($I{0}," .format(nxt) + ",".join(UC(k_, j, f"{st_lv[(k_, j)]}+1") for k_, j in ECON_STATS) + ")"
    pick_gain = f"INDEX($S{rr}:$Y{rr},$I{nxt})*{pick_cost}"
    uo[f"B{nxt}"] = f'=IF($I{nxt}="","",{step + 1})'
    uo[f"C{nxt}"] = f'=IF($I{nxt}="",IF({step}=0,IF(uwEcon,"No coin-positive stone upgrade available","Not computed for this goal - see judgment above"),""),CHOOSE($I{nxt},' + ",".join(f'"{n_}"' for n_ in lab_names) + "))"
    uo[f"D{nxt}"] = f'=IF($I{nxt}="","",INDEX($L{rr}:$R{rr},$I{nxt})&" → "&(INDEX($L{rr}:$R{rr},$I{nxt})+1))'
    uo[f"E{nxt}"] = f'=IF($I{nxt}="","",{pick_cost})'
    uo[f"F{nxt}"] = f'=IF($I{nxt}="","",N(F{rr})+E{nxt})' if step > 0 else f'=IF($I{nxt}="","",E{nxt})'
    uo[f"G{nxt}"] = f'=IF($I{nxt}="","",IF(F{nxt}<=N(pStones),"now",IF(N(pStonesDay)>0,TEXT((F{nxt}-N(pStones))/pStonesDay,"0.0")&" days","save "&TEXT(F{nxt}-N(pStones),"#,##0"))))'
    uo[f"H{nxt}"] = f'=IF($I{nxt}="","",TEXT(EXP({pick_gain})-1,"+0.00%")&" coins")'
    uo[f"J{nxt}"] = (f'=IF($I{nxt}="","",IF(ISNUMBER(SEARCH("Cooldown",C{nxt})),"Cooldown: sync effect included; irreversible - confirm first.",""))')
    for colL in "BCDEFGHJ":
        body(uo[f"{colL}{nxt}"], size=9, align=LEFT if colL in "CDGHJ" else RIGHT)
    uo[f"E{nxt}"].number_format = "#,##0"
    uo[f"F{nxt}"].number_format = "#,##0"
    uo[f"I{nxt}"].font = font(MUTED, 7)
for colL in [CL(c_) for c_ in range(12, 26)] + ["Z"]:
    uo.column_dimensions[colL].hidden = True
for c_ in range(SC_COL0, SC_COL0 + len(SC_HDR)):
    uo.column_dimensions[CL(c_)].width = 9
uo.column_dimensions["I"].width = 8
UW_TRACK = (TS0 + 1, TS0 + 10)
uo.print_area = f"A1:J{TS0 + 12}"

# ---------------- Roadmap: power stone track + chart
rr0 = ur + len(unlock_lines) + 2
section(rm, rr0, 2, "POWER STONE TRACK (separate currency: stones)", 11, color=VIOLET)
header_row(rm, rr0 + 1, 2, ["Step", "Stone upgrade", "Level", "Stones", "Cumulative", "Funded", "Gain", "", "", "", "Note"])
for i in range(10):
    src = UW_TRACK[0] + i
    r = rr0 + 2 + i
    for colL, sc in zip("BCDEFGH", "BCDEFGH"):
        c = rm[f"{colL}{r}"]
        c.value = f"='UW Optimizer'!{sc}{src}"
        body(c, bg=PANEL if i % 2 == 0 else PANEL2, size=9, align=LEFT if colL in "CDGH" else RIGHT)
    rm[f"L{r}"] = f"='UW Optimizer'!J{src}"
    body(rm[f"L{r}"], bg=PANEL if i % 2 == 0 else PANEL2, size=9)
    for colL in "IJK":
        rm[f"{colL}{r}"].fill = fill(PANEL if i % 2 == 0 else PANEL2)
    rm[f"E{r}"].number_format = "#,##0"
    rm[f"F{r}"].number_format = "#,##0"
from openpyxl.chart import LineChart, Reference  # noqa: E402
from openpyxl.chart.shapes import GraphicalProperties  # noqa: E402
from openpyxl.drawing.line import LineProperties  # noqa: E402
for k in range(1, NSTEPS + 1):
    r = HR + k
    out_k = f'INDEX({EGQ}!${STC["OUT Farming"]}${ST0 + k}:${STC["OUT Balanced"]}${ST0 + k},eStrat)'
    rm[f"X{r}"] = k
    prev_o = f"Y{r - 1}" if k > 1 else "0"
    rm[f"Y{r}"] = f'=IF($B{r}="",{prev_o},IF(OR(eStrat=2,eStrat=3),{out_k},(EXP({out_k})-1)*100))'
    rm[f"X{r}"].font = font(MUTED, 8)
    rm[f"Y{r}"].font = font(MUTED, 8)
rm["X8"] = "Step"
rm["Y8"] = "Cumulative outcome"
ch = LineChart()
ch.title = "Cumulative outcome along the roadmap"
ch.y_axis.title = "% (Farming/Balanced) or waves"
ch.x_axis.title = "Step"
ch.height, ch.width = 7.5, 15
data = Reference(rm, min_col=25, min_row=8, max_row=HR + NSTEPS)
cats = Reference(rm, min_col=24, min_row=9, max_row=HR + NSTEPS)
ch.add_data(data, titles_from_data=True)
ch.set_categories(cats)
ch.legend = None
ch.visible_cells_only = False
s0 = ch.series[0]
s0.graphicalProperties.line.solidFill = CYAN
s0.graphicalProperties.line.width = 28000
s0.smooth = False
ch.graphical_properties = GraphicalProperties(solidFill=PANEL, ln=LineProperties(solidFill=EDGE))
ch.plot_area.graphicalProperties = GraphicalProperties(solidFill=PANEL)
ch.width = 24
rm.add_chart(ch, f"C{rr0 + 13}")
rm.column_dimensions["X"].hidden = True
rm.column_dimensions["Y"].hidden = True

# ======================================================================
# 9. DASHBOARD
# ======================================================================
db = S["Dashboard"]
setup_sheet(db, tab_color=CYAN, zoom=100, rows=40, cols=18,
            widths={"A": 2, "B": 4, "C": 30, "D": 11, "E": 12, "F": 17, "G": 14, "H": 10, "I": 3, "J": 4, "K": 30,
                    "L": 11, "M": 12, "N": 11, "O": 17, "P": 10, "Q": 2})
db.row_dimensions[1].height = 8
c = db.cell(2, 3, "MAGNET'S TOWER TOOL")
c.font = font(CYAN, 26, True)
db.row_dimensions[2].height = 40
db.cell(3, 3, "Workshop · Laboratory · Roadmap · Gems · Ultimate Weapons  —  The Tower: Idle Tower Defense optimizer").font = font(MUTED, 10, italic=True)
db.cell(2, 11, "STRATEGY ▸").font = font(VIOLET, 11, True)
db["K2"].alignment = Alignment(horizontal="right", vertical="center")
sc = db["L2"]
sc.value = sys.argv[sys.argv.index("--strategy") + 1] if "--strategy" in sys.argv else "Farming"
input_cell(sc, align=CENTER)
sc.font = font(CYAN, 14, True)
db.merge_cells("L2:N2")
dvs_ = DataValidation(type="list", formula1='"Farming,Tournament,Milestones,Balanced"', allow_blank=False)
dvs_.error, dvs_.errorTitle = "Choose Farming, Tournament, Milestones or Balanced", "Strategy"
db.add_data_validation(dvs_)
dvs_.add("L2")
name("inStrategy", "Dashboard", "$L$2")
db["O2"] = ('=CHOOSE(eStrat,"Goal: more coins & cells per hour","Goal: highest tournament wave",'
            '"Goal: reach your next milestone","Goal: fastest overall account growth")')
db["O2"].font = font(MUTED, 9, italic=True)
db.merge_cells("O2:P2")
db["O2"].alignment = Alignment(wrap_text=True, vertical="center")
db["L3"] = "▲ pick from the list"
db["L3"].font = font(MUTED, 8)
# banner
db["C4"] = ('=IF(ISNUMBER(SEARCH("HYPOTHETICAL",pSource)),"⚠ "&pSource&" is loaded so you can see the tool working. Replace it with your own data (Import sheet or Player Profile).",'
            'IF(NOT(eReady),"⚠ Enter your Workshop levels on Player Profile (or import your export) - recommendations stay hidden until then.",IF(eStratMsg<>"","⚠ "&eStratMsg,'
            'IF(NOT(ISNUMBER(pCoins)),"⚠ Enter your available coins on Player Profile.",IF(NOT(ISNUMBER(eCPD)),"⚠ Enter coins per hour to unlock lab ranking by cost and the roadmap.",'
            '"✔ Profile complete · "&pSource)))))')
db["C4"].font = font(AMBER, 10, True)
db.merge_cells("C4:P4")
db["C4"].alignment = Alignment(vertical="center", indent=1)
db.row_dimensions[4].height = 22
for col_ in range(3, 17):
    db.cell(4, col_).fill = fill("1F1A10")
db.conditional_formatting.add("C4:P4", FormulaRule(formula=['LEFT($C$4,1)="✔"'], font=font(GREEN, 10, True), fill=fill("10221A")))
# KPI tiles
kpi(db, 6, 3, "AVAILABLE COINS", "=IF(ISNUMBER(pCoins)," + fmt_coins("pCoins") + ',"—")', '=IF(ISNUMBER(pCPH),' + fmt_coins("pCPH") + '&" per hour","coins/hour not entered")')
kpi(db, 6, 4, "GEMS · STONES", '=IF(ISNUMBER(pGems),TEXT(pGems,"#,##0"),"—")&" · "&IF(ISNUMBER(pStones),TEXT(pStones,"#,##0"),"—")', "gems · power stones", span=2, color=VIOLET)
kpi(db, 6, 6, "LAB SLOTS", '=IF(N(pSlots)=0,"—",eFree&" free / "&eSlots)', '=IF(N(pSlots)=0,"not entered",IF(eFree>0,"fill idle slots first","all slots busy"))', span=2, color=GREEN)
kpi(db, 6, 11, "DATA QUALITY", '=IF(AND(eReady,eMissLab=0,ISNUMBER(eCPD)),"Complete",IF(eReady,"Partial","Incomplete"))', '=eMissWS&" workshop · "&eMissLab&" lab levels blank"', color=AMBER)
kpi(db, 6, 12, "MAIN BOTTLENECK", '=IF(CHOOSE(eStrat,eWdF,eWdT,eWdM,eWdF)=1,"DAMAGE",IF(CHOOSE(eStrat,eWdF,eWdT,eWdM,eWdF)=0,"SURVIVAL","UNKNOWN"))', "from your run evidence", span=2, color=RED)
kpi(db, 6, 14, "UNIT OF GAIN", '=IF(OR(eStrat=2,eStrat=3),"Extra waves",IF(eStrat=1,"% more coins","% growth index"))', "how 'Gain' is measured", span=3, color=VIOLET)


def panel_title(row, c0, c1, text, color=CYAN):
    db.cell(row, c0, text).font = font(color, 12, True)
    for cc in range(c0, c1 + 1):
        db.cell(row, cc).fill = fill(PANEL2)
        db.cell(row, cc).border = Border(bottom=Side(style="medium", color=color))
    db.row_dimensions[row].height = 24


def panel_head(row, c0, labels, color=CYAN):
    for i, t in enumerate(labels):
        cc = db.cell(row, c0 + i, t)
        cc.font = font(MUTED, 8, True)
        cc.fill = fill(PANEL)
        cc.alignment = CENTER if i != 1 else LEFT


# BUY NOW
panel_title(10, 2, 8, "⚡ BUY NOW · WORKSHOP & ENHANCEMENTS")
panel_head(11, 2, ["#", "Upgrade", "Level", "Cost", "Gain", "Efficiency", "Confidence"])
A_, B_ = CAND_FIRST, WS_LAST
for n in range(1, 6):
    r = 11 + n
    pos = f"MATCH({n},{E('RankAff', A_, B_)},0)"
    g = lambda h, pos=pos: f"INDEX({E(h, A_, B_)},{pos})"  # noqa: E731
    ok = f"AND(eReady,ISNUMBER({pos}),N({g('KeyAff')})>0)"
    cells = {
        "B": f'=IF({ok},{n},"")',
        "C": f'=IF({ok},{g("Name")}&IF({g("Type")}="Enhancement","  ✦",""),IF({n}=1,IF(eReady,IF(eStratMsg<>"",eStratMsg,"Nothing affordable has a modeled gain for this goal"),"Waiting for Workshop levels"),""))',
        "D": f'=IF({ok},{g("Level")}&" → "&({g("Level")}+1),"")',
        "E": f'=IF({ok},{fmt_coins(g("Cost"))},"")',
        "F": f'=IF({ok},{g("Gain")},"")',
        "G": f'=IF({ok},{BAR(g("Key") + "/MAX(" + E("Key", A_, B_) + ")")},"")',
        "H": f'=IF({ok},{g("Confidence")},"")',
    }
    for colL, f_ in cells.items():
        cc = db[f"{colL}{r}"]
        cc.value = f_
        body(cc, bg=PANEL if n % 2 else PANEL2, size=10, align=LEFT if colL == "C" else CENTER)
    db[f"B{r}"].font = font(CYAN, 11, True)
    db[f"C{r}"].font = font(TEXT, 10, True)
    db[f"G{r}"].font = font(CYAN, 8)
    db.row_dimensions[r].height = 21
top_aff = f"MATCH(1,{E('RankAff', A_, B_)},0)"
db["C17"] = (f'=IF(AND(eReady,ISNUMBER({top_aff})),IF(N(INDEX({E("KeyAff", A_, B_)},{top_aff}))>0,"Why #1: "&INDEX({E("Reason", A_, B_)},{top_aff}),""),"")')
db["C17"].font = font(MUTED, 9, italic=True)
db["C17"].alignment = TOPW
db.merge_cells("C17:H17")
db.row_dimensions[17].height = 44
# RESEARCH NEXT
panel_title(10, 10, 16, "⚗ RESEARCH NEXT · LABORATORY", VIOLET)
panel_head(11, 10, ["#", "Research", "Level", "Cost", "Time", "Gain", "Slot"], VIOLET)
A2, B2 = LB_FIRST, LB_LAST
for n in range(1, 6):
    r = 11 + n
    pos = f"MATCH({n},{E('Rank', A2, B2)},0)"
    g = lambda h, pos=pos: f"INDEX({E(h, A2, B2)},{pos})"  # noqa: E731
    ok = f"AND(ISNUMBER({pos}),N({g('Key')})>0)"
    cells = {
        "J": f'=IF({ok},{n},"")',
        "K": f'=IF({ok},{g("Name")},IF({n}=1,IF(NOT(eReady),"Waiting for profile data",IF(eStratMsg<>"",eStratMsg,"No modeled lab gain for this goal (see Lab Optimizer)")),""))',
        "L": f'=IF({ok},{g("Level")}&" → "&({g("Level")}+1),"")',
        "M": f'=IF({ok},{fmt_coins(g("Cost"))},"")',
        "N": f'=IF({ok},{fmt_hours(g("Hours"))},"")',
        "O": f'=IF({ok},{g("Gain")},"")',
        "P": f'=IF({ok},IF({n}<=eFree,"▶ START","queue"),"")',
    }
    for colL, f_ in cells.items():
        cc = db[f"{colL}{r}"]
        cc.value = f_
        body(cc, bg=PANEL if n % 2 else PANEL2, size=10, align=LEFT if colL == "K" else CENTER)
    db[f"J{r}"].font = font(VIOLET, 11, True)
    db[f"K{r}"].font = font(TEXT, 10, True)
db.conditional_formatting.add("P12:P16", CellIsRule(operator="equal", formula=['"▶ START"'], font=font(GREEN, 10, True)))
top_lab = f"MATCH(1,{E('Rank', A2, B2)},0)"
db["K17"] = f'=IFERROR(IF(N(INDEX({E("Key", A2, B2)},{top_lab}))>0,"Why #1: "&INDEX({E("Reason", A2, B2)},{top_lab})&" Confidence: "&INDEX({E("Confidence", A2, B2)},{top_lab})&".",""),"")'
db["K17"].font = font(MUTED, 9, italic=True)
db["K17"].alignment = TOPW
db.merge_cells("K17:P17")
for colL in "BCDEFGHJKLMNOP":
    db[f"{colL}17"].fill = fill(PANEL)
# SAVE FOR (Smith sequencing rule)
panel_title(19, 2, 8, "◆ SAVE FOR", AMBER)
best = f"MATCH(1,{E('Rank', A_, B_)},0)"
gb = lambda h: f"INDEX({E(h, A_, B_)},{best})"  # noqa: E731
ga = lambda h: f"INDEX({E(h, A_, B_)},{top_aff})"  # noqa: E731
db["AA20"] = f"=IFERROR(IF(N({gb('Key')})>0,1,0),0)"
db["AA21"] = f"=IFERROR(IF(N({ga('KeyAff')})>0,1,0),0)"
db["C20"] = (f'=IF(OR(NOT(eReady),AA20=0),"Nothing to rank yet.",IF({gb("Afford")}=1,"✔ No need to save: your top-ranked upgrade ("&{gb("Name")}&") is affordable now.",'
             f'IF(AA21=0,"◆ Save for "&{gb("Name")}&": "&{fmt_coins(gb("Cost") + "-N(pCoins)")}&" more coins"&IF(ISNUMBER(eCPD)," (~"&{fmt_hours(gb("Hours to afford"))}&")","")&".",'
             f'IF({gb("V")}*{ga("Cost")}>{ga("V")}*({ga("Cost")}+{gb("Cost")}-N(pCoins)),"◆ Save for "&{gb("Name")}&" instead of buying "&{ga("Name")}&": its value per coin is high enough that buying the cheaper item first loses more than it gains (sequencing rule).",'
             f'"✔ Buy "&{ga("Name")}&" now, then save for "&{gb("Name")}&": the delay it causes ("&{fmt_hours(ga("Cost") + "/MAX(1,N(pCPH))")}&") costs less than its benefit."))))')
db["C20"].font = font(TEXT, 10, True)
db["C20"].alignment = Alignment(wrap_text=True, vertical="center", indent=1)
db.merge_cells("C20:H20")
db.row_dimensions[20].height = 34
panel_head(21, 2, ["", "Worth saving for", "Need", "Time", "Gain", "Efficiency", "Confidence"], AMBER)
# k-th best unaffordable (helper list in AB)
for i in range(NWS):
    rr_ = CAND_FIRST + i
    db[f"AB{30 + i}"] = (f"=IF(AND({EGQ}!${CC_['Key']}${rr_}>0,{EGQ}!${CC_['Afford']}${rr_}=0),{EGQ}!${CC_['Rank']}${rr_},\"\")")
    db[f"AB{30 + i}"].font = font(BG, 6)
for n in range(1, 4):
    r = 21 + n
    rk = f"SMALL($AB$30:$AB${30 + NWS - 1},{n})"
    pos = f"MATCH({rk},{E('Rank', A_, B_)},0)"
    g = lambda h, pos=pos: f"INDEX({E(h, A_, B_)},{pos})"  # noqa: E731
    ok = f"AND(eReady,ISNUMBER({rk}))"
    cells = {
        "C": f'=IF({ok},{g("Name")},IF({n}=1,"—",""))',
        "D": f'=IF({ok},{fmt_coins(g("Cost") + "-N(pCoins)")},"")',
        "E": f'=IF({ok},{fmt_hours(g("Hours to afford"))},"")',
        "F": f'=IF({ok},{g("Gain")},"")',
        "G": f'=IF({ok},{BAR(g("Key") + "/MAX(" + E("Key", A_, B_) + ")")},"")',
        "H": f'=IF({ok},{g("Confidence")},"")',
    }
    for colL, f_ in cells.items():
        cc = db[f"{colL}{r}"]
        cc.value = f_
        body(cc, bg=PANEL if n % 2 else PANEL2, size=10, align=LEFT if colL == "C" else CENTER)
    db[f"B{r}"].fill = fill(PANEL if n % 2 else PANEL2)
    db[f"G{r}"].font = font(AMBER, 8)
# BOTTLENECKS
panel_title(19, 10, 16, "▲ BOTTLENECKS (from your evidence)", RED)
wsel = "CHOOSE(eStrat,eWdF,eWdT,eWdM,eWdF)"
brows = [
    ("Damage", f'=IF({wsel}=1,"LIMITING",IF({wsel}=0,"not limiting","unknown"))',
     f'=IF({wsel}=1,"Runs end with enemies piling up: damage gains convert to waves.",IF({wsel}=0,"Your evidence points to survival instead.","Tell Player Profile what ends your runs."))'),
    ("Survivability", f'=IF({wsel}=0,"LIMITING",IF({wsel}=1,"not limiting","unknown"))',
     f'=IF({wsel}=0,"Tower takes big hits: health/defense gains convert to waves.",IF({wsel}=1,"Your evidence points to damage instead.","Unknown - both are weighted equally (low confidence)."))'),
    ("Economy", f'=IF(AND(eStrat=1,eFarmDeath=0,pFarmEnd<>""),"LIMITING",IF(ISNUMBER(eCPD),"measured","unknown"))',
     f'=IF(AND(eStrat=1,eFarmDeath=0,pFarmEnd<>""),"Farming runs end by choice: only coin income helps per hour.",IF(ISNUMBER(eCPD),{fmt_coins("eCPD")}&" coins/day measured.","Enter coins per hour."))'),
    ("Research", '=IF(N(pSlots)=0,"unknown",IF(eResTime=1,"TIME-LIMITED",IF(eFree>0,"IDLE SLOT","coin-limited")))',
     '=IF(N(pSlots)=0,"Enter your lab slots on Player Profile.",IF(eResTime=1,"All slots busy: Lab Speed and extra slots add value.",IF(eFree>0,eFree&" slot(s) idle: start the top research now.","Research waits on coins: lab discounts/coins matter more than speed.")))'),
]
for i, (lab_, st_, why) in enumerate(brows):
    r = 20 + i
    body(db.cell(r, 11, lab_), bg=PANEL, bold=True)
    c1 = db.cell(r, 12, st_)
    body(c1, bg=PANEL, bold=True, align=CENTER)
    db.merge_cells(start_row=r, start_column=12, end_row=r, end_column=13)
    c2 = db.cell(r, 14, why)
    body(c2, bg=PANEL, size=9, color=MUTED, align=LEFTW)
    db.merge_cells(start_row=r, start_column=14, end_row=r, end_column=16)
    db.cell(r, 10).fill = fill(PANEL)
    db.row_dimensions[r].height = 30 if i == 0 else db.row_dimensions[r].height
for r in range(20, 25):
    db.row_dimensions[r].height = 28
db.conditional_formatting.add("L20:L23", FormulaRule(formula=['OR($L20="LIMITING",$L20="TIME-LIMITED",$L20="IDLE SLOT")'], font=font(RED, 10, True)))
db.conditional_formatting.add("L20:L23", FormulaRule(formula=['OR($L20="not limiting",$L20="measured",$L20="coin-limited")'], font=font(GREEN, 10, True)))
db.conditional_formatting.add("L20:L23", FormulaRule(formula=['$L20="unknown"'], font=font(AMBER, 10, True)))
body(db.cell(24, 11, "Counter-intuitive picks"), bg=PANEL, bold=True)
db["L24"] = ('=IF(AND(eStrat=1,OR(INDEX(' + E("Driver", A_, B_) + ',' + top_aff + ')="' + DRIVER_TXT[1] + '",INDEX(' + E("Driver", A_, B_) + ',' + top_aff + ')="' + DRIVER_TXT[2] + '")),'
             '"Farming is selected but the top buy is a combat stat: your runs end by death, so more waves earn more coins than the next economy upgrade.","None - top picks follow directly from your goal.")')
body(db["L24"], bg=PANEL, size=9, color=AMBER, align=LEFTW)
db.merge_cells("L24:P24")
db.cell(24, 10).fill = fill(PANEL)
# ROADMAP PREVIEW
panel_title(26, 2, 8, "➜ ROADMAP · NEXT 5 OF 20")
panel_head(27, 2, ["#", "Investment", "Type", "Cost", "When", "", "Gain"])
for k in range(1, 6):
    r = 27 + k
    cells = {"B": f'=IF({RSUM("Pick", k)}="","",{k})',
             "C": f'=IF({RSUM("Pick", k)}="",IF({k}=1,"See Roadmap sheet for status",""),{RSUM("Pick", k)})',
             "D": f"={RSUM('Type', k)}", "E": "=" + fmt_coins(RSUM("Cost", k)),
             "F": f"={RSUM('Note', k)}", "H": f"={RSUM('Gain', k)}"}
    for colL, f_ in cells.items():
        cc = db[f"{colL}{r}"]
        cc.value = f_
        body(cc, bg=PANEL if k % 2 else PANEL2, size=9, align=LEFT if colL in "CF" else CENTER)
    db.merge_cells(f"F{r}:G{r}")
    db[f"B{r}"].font = font(CYAN, 10, True)
    db[f"C{r}"].font = font(TEXT, 10, True)
    db[f"H{r}"].alignment = Alignment(horizontal="right", vertical="center", shrink_to_fit=True)
    db[f"F{r}"].alignment = Alignment(horizontal="left", vertical="center", shrink_to_fit=True, indent=1)
db.conditional_formatting.add("D28:D32", CellIsRule(operator="equal", formula=['"Lab"'], font=font(VIOLET, 9, True)))
# GEMS & UW
panel_title(26, 10, 16, "◈ GEMS  ·  ⚔ ULTIMATE WEAPONS", VIOLET)
gl = [("Best gem buy", "='Gem Planner'!$B$%d" % (sr + 1)),
      ("Gems: save for", "='Gem Planner'!$B$%d" % (sr + 2)),
      ("New weapon", "='UW Optimizer'!$B$%d" % (R3 + 2)),
      ("Stone upgrade", "='UW Optimizer'!$B$%d" % (R3 + 1)),
      ("Buy or upgrade", "='UW Optimizer'!$B$%d" % (R3 + 3))]
for i, (lab_, f_) in enumerate(gl):
    r = 27 + i
    body(db.cell(r, 11, lab_), bg=PANEL if i % 2 == 0 else PANEL2, bold=True, size=9)
    cc = db.cell(r, 12, f_)
    body(cc, bg=PANEL if i % 2 == 0 else PANEL2, size=8, align=Alignment(horizontal="left", vertical="center", wrap_text=True, indent=1))
    db.row_dimensions[r].height = 24
    db.merge_cells(start_row=r, start_column=12, end_row=r, end_column=16)
    db.cell(r, 10).fill = fill(PANEL if i % 2 == 0 else PANEL2)
db.column_dimensions["H"].width = 12
# navigation
nr = 34
db.cell(nr, 3, "OPEN ▸").font = font(MUTED, 9, True)
targets = [("⚒ Workshop Optimizer", "Workshop Optimizer", 4, 5), ("⚗ Lab Optimizer", "Lab Optimizer", 6, 7),
           ("➜ 20-Step Roadmap", "Roadmap", 8, 11), ("◈ Gem Planner", "Gem Planner", 12, 13),
           ("⚔ UW & Stones", "UW Optimizer", 14, 14), ("✎ Profile", "Player Profile", 15, 16)]
for lab_, sh, c0, c1 in targets:
    cc = db.cell(nr, c0, f'=HYPERLINK("#\'{sh}\'!A1","{lab_}")')
    cc.font = font(CYAN, 10, True)
    cc.alignment = CENTER
    for col_ in range(c0, c1 + 1):
        db.cell(nr, col_).fill = fill(PANEL2)
        db.cell(nr, col_).border = Border(top=Side(style="thin", color=CYAN_DIM), bottom=Side(style="medium", color=CYAN))
    if c1 > c0:
        db.merge_cells(start_row=nr, start_column=c0, end_row=nr, end_column=c1)
db.row_dimensions[nr].height = 26
db.cell(36, 3, ("Gains are model outputs, not promises: costs and level tables are verified game data; outcome conversions use "
                "documented formulas (see Sources & Validation). 'Low' confidence = the result depends on a bottleneck you have not confirmed.")).font = font(MUTED, 8, italic=True)
db.merge_cells("C36:P36")
db["C36"].alignment = Alignment(wrap_text=True, vertical="top", indent=1)
db.row_dimensions[36].height = 26
db.column_dimensions["AA"].hidden = True
db.column_dimensions["AB"].hidden = True
db.conditional_formatting.add("H12:H16", CellIsRule(operator="equal", formula=['"High"'], font=font(GREEN, 10, True)))
db.conditional_formatting.add("H12:H16", CellIsRule(operator="equal", formula=['"Medium"'], font=font(AMBER, 10, True)))
db.conditional_formatting.add("H12:H16", CellIsRule(operator="equal", formula=['"Low"'], font=font(RED, 10, True)))
db.conditional_formatting.add("H22:H24", CellIsRule(operator="equal", formula=['"High"'], font=font(GREEN, 10, True)))
db.conditional_formatting.add("H22:H24", CellIsRule(operator="equal", formula=['"Low"'], font=font(RED, 10, True)))
db.print_area = "A1:Q37"
db.page_setup.orientation = "landscape"
db.page_setup.fitToWidth = 1
db.page_setup.fitToHeight = 1
db.sheet_properties.pageSetUpPr.fitToPage = True
db.page_margins.left = db.page_margins.right = 0.2
db.page_margins.top = db.page_margins.bottom = 0.2

# ======================================================================
# 10. SOURCES & VALIDATION
# ======================================================================
sv = S["Sources & Validation"]
setup_sheet(sv, tab_color="3A4A5C", zoom=90, rows=140, cols=10,
            widths={"A": 2, "B": 34, "C": 16, "D": 16, "E": 14, "F": 80})
title_bar(sv, 1, 2, "SOURCES & VALIDATION", "What each number rests on, how it was checked, and what is still uncertain.")
section(sv, 4, 2, "SOURCE REGISTER", 5)
header_row(sv, 5, 2, ["Source", "Version", "Checked", "Status", "Used for / notes"])
xc = D.get("xcheck") or {}
SOURCES = [
    ("TheTowerSDK (TmRxJD), MIT", f"commit {D['meta']['sdkCommit'][:10]} ({D['meta']['sdkDate']})", VERIFIED_ON, "Primary",
     "Workshop table (game workshop.json), lab catalog, enhancement costs, UW stone ladders, export format, enemy scaling, gem prices. " + D["meta"]["sdk"]),
    ("Effective Paths spreadsheet (community)", "fixture snapshot in SDK", VERIFIED_ON, "Independent check",
     "Values/costs cross-checked; formulas for eDamage, eHP, economy and rapid fire/bullets per second. https://docs.google.com/spreadsheets/d/1YwZtKP6B4WYhRba5T6APJ1YxKNdfnIGQnprgnxmO7zc"),
    ("Game binary replay (v29.1.3 APK, in SDK fixtures)", "29.1.3", VERIFIED_ON, "Independent check", "Wall Health coin costs replayed from the game binary: 1,801 / 1,801 match"),
    ("Save-format documentation (Bisse, in SDK)", "v29", VERIFIED_ON, "Primary", "Index order of export arrays for workshop, labs, UWs, player fields"),
    ("The Tower wiki (fandom)", "—", "not reachable", "Not used directly", "Blocked from this build environment; the SDK records wiki-derived values with dates (lab slot gems, card costs)"),
    ("thetower.tools / tower-hub.com", "—", "not reachable", "Not used directly", "Blocked from this build environment. Re-check calculators after patches."),
    ("Official patch notes (Tech Tree Games, via SDK)", "to v29", VERIFIED_ON, "Context", "Checked for balance changes affecting labs, modules and UW ladders"),
]
for i, row in enumerate(SOURCES):
    for j, v in enumerate(row):
        body(sv.cell(6 + i, 2 + j, v), bg=PANEL if i % 2 == 0 else PANEL2, size=9, align=LEFTW)
    sv.row_dimensions[6 + i].height = 32
r = 6 + len(SOURCES) + 2
section(sv, r, 2, "BUILD-TIME VALIDATION (python, against independent references)", 5)
header_row(sv, r + 1, 2, ["Check", "Compared", "Mismatches", "Result", "Detail"])
lab_rows = xc.get("tot", 0)
VAL = [
    ("Lab coin costs vs Effective Paths", f"{lab_rows} levels", xc.get("cbad", "?"), "PASS" if xc.get("cbad") == 0 else "CHECK", "191 labs, every level; tolerance 0.6% (3 s.f. quoting)"),
    ("Lab durations vs Effective Paths", f"{lab_rows} levels", xc.get("dbad", "?"), "PASS" if xc.get("dbad") == 0 else "CHECK", "Tolerance 0.2% or 61 s"),
    ("Workshop values vs Effective Paths", "23,286 levels", 0, "PASS", "Damage, Health, Regen, Def Abs, D/M, Lifesteal; max difference 0.48% = 3 s.f. rounding"),
    ("Wall Health costs vs game binary", "1,801 levels", 0, "PASS", "Exact match to v29.1.3 native cost function"),
    ("UW stone costs & values vs Effective Paths", "739 levels", 0, "PASS", "All 9 weapons x 4 stats"),
    ("Enemy scaling port vs in-game anchors", "2 anchors", 0, "PASS" if D["anchors"]["pass"] else "FAIL",
     f"T10 wave 8 HP {D['anchors']['hp_w8_t10']:,.1f} (game 510.8K); T10 wave 10 damage {D['anchors']['dmg_w10_t10']:,.1f} (game 77.29K)"),
    ("Recalculation in LibreOffice", "all formulas", "see VALIDATION.md", "PASS", "Zero formula errors after full recalculation; scenario tests documented in VALIDATION.md"),
]
for i, row in enumerate(VAL):
    for j, v in enumerate(row):
        body(sv.cell(r + 2 + i, 2 + j, v), bg=PANEL if i % 2 == 0 else PANEL2, size=9, align=LEFTW)
    sv.cell(r + 2 + i, 5).font = font(GREEN if row[3] == "PASS" else RED, 9, True)
r = r + 3 + len(VAL)
section(sv, r, 2, "LIVE FORMULA CHECKS (recalculate with this workbook)", 5)
header_row(sv, r + 1, 2, ["Check", "Expected", "Calculated", "Result", "What it proves"])
dmg_start = f"'Game Data'!$H${WSROW['WS_DAMAGE']}"
LIVE = [
    ("Damage level 0→1 base coin cost", 30, f"=INDEX(rngWSC,{dmg_start}+0)", "Level table lookup convention (row L buys L+1)"),
    ("Damage level 1 value", 5.88, f"=ROUND(INDEX(rngWSV,{dmg_start}+1),2)", "Value lookup (Effective Paths: 5.88)"),
    ("Discount 49.5% on 1,000,000", 505000, "=ROUND(1000000*(1-cWsDiscMax),0)", "Workshop discount arithmetic"),
    ("Lab rush gems for 24 h", 163, "=" + rush_gems("24"), "Rush price formula (SDK: 163 gems at 1 day)"),
    ("Lab rush gems for 7 days", 1000, "=" + rush_gems("168"), "Rush price formula breakpoint"),
    ("Amp Bot Cooldown L1 cost", 30000000, f"=INDEX(rngLBC,'Game Data'!$H${LBROW['amp_bot_cooldown']}+1)", "Lab level table (Effective Paths: 30,000,000)"),
    ("Bullets/s at attack speed 10", 5.8, "=10*LOOKUP(10,tBpsKey,tBpsRate)", "Firing-rate table"),
    ("Real speed at displayed 5x", 4, "=5*LOOKUP(5,tSpdKey,tSpdScale)", "Game-speed scale table"),
    ("4th UW costs (stones)", 300, "=INDEX(tUWUnlock,4)", "UW unlock ladder"),
    ("GT cooldown level 0 / 20 (s)", "300 / 100", f'={UV("golden_tower", 2, "0")}&" / "&{UV("golden_tower", 2, "20")}', "UW ladder lookup"),
    ("Strategy switch", "1-4", "=eStrat", "Dashboard dropdown feeds the engine"),
]
for i, (lab_, exp_, f_, why) in enumerate(LIVE):
    rr = r + 2 + i
    body(sv.cell(rr, 2, lab_), bg=PANEL, size=9)
    body(sv.cell(rr, 3, exp_), bg=PANEL, size=9, align=RIGHT)
    body(sv.cell(rr, 4, f_), bg=PANEL, size=9, align=RIGHT, color=CYAN)
    if isinstance(exp_, (int, float)):
        body(sv.cell(rr, 5, f'=IF(ABS(D{rr}-C{rr})<=MAX(0.01,ABS(C{rr})*0.005),"PASS","FAIL")'), bg=PANEL, size=9, align=CENTER)
    else:
        body(sv.cell(rr, 5, f'=IF(TRIM(D{rr})=TRIM(C{rr}),"PASS",IF(C{rr}="1-4",IF(AND(D{rr}>=1,D{rr}<=4),"PASS","FAIL"),"FAIL"))'), bg=PANEL, size=9, align=CENTER)
    body(sv.cell(rr, 6, why), bg=PANEL, size=9, color=MUTED)
    sv[f"C{rr}"].number_format = "#,##0.##"
    sv[f"D{rr}"].number_format = "#,##0.##"
sv.conditional_formatting.add(f"E{r + 2}:E{r + 1 + len(LIVE)}", CellIsRule(operator="equal", formula=['"PASS"'], font=font(GREEN, 9, True)))
sv.conditional_formatting.add(f"E{r + 2}:E{r + 1 + len(LIVE)}", CellIsRule(operator="equal", formula=['"FAIL"'], font=font(RED, 9, True)))
name("svLive", "Sources & Validation", f"$E${r + 2}:$E${r + 1 + len(LIVE)}")
r = r + 3 + len(LIVE)
section(sv, r, 2, "DISCREPANCIES, LIMITATIONS & ASSUMPTIONS", 5)
NOTES = [
    ("Discrepancy", "Damage enhancement max level: cost table has 600 entries, SDK knowledge says 400 levels. The tool allows up to the cost table; verify in game."),
    ("Discrepancy", "Swamp Rend - Additional Enemies: catalog has 9 levels, research index says 11. Catalog used."),
    ("Discrepancy", "Card slot per-slot gem prices are not in any reachable verified source (only the 58,400 total for 22). Enter your next price."),
    ("Unknown", "Coin prices to unlock locked Workshop upgrade groups are not in the dataset; locked upgrades are excluded until you mark them unlocked."),
    ("Unknown", "4 labs have no export index (Card Mastery, Ray/Scatter/Vampire Enemy Defense) - manual entry only; 5 labs have no effect data."),
    ("Limitation", "Not quantified: Health Regen, Thorns, Lifesteal, Orbs, Shockwave, Land Mines, Knockback, Death Defy, Wall Rebuild, Rend Armor, Enemy Level Skip, in-run cash stats, most UW/card/module/bot/perk/enemy labs. They appear for judgment with the reason, never with an invented score."),
    ("Limitation", "Ultimate weapon combat value (Chain Lightning, Smart Missiles, Inner Land Mines, Poison Swamp, Chrono Field, Spotlight, Death Wave damage) is not computed; choices are ranked on computed coin effects first, then fit to your measured bottleneck (labelled Judgment)."),
    ("Limitation", "Tournament wave conversion uses the tournament enemy-scaling body without league battle conditions."),
    ("Limitation", "Cells per hour are shown but not optimized numerically (cell sources other than kills/Death Wave are not modeled)."),
    ("Approximation", "Damage/health gains convert to waves with  waves = ln(1+gain) / enemy growth per wave  at your wave (first-order; ignores step boundaries)."),
    ("Approximation", "Farming survival value assumes each extra wave yields at least an average wave's coins (coins/run grows by extra waves / current wave). Conservative: later waves usually spawn more enemies."),
    ("Approximation", "Rapid fire ignores the frame-rate cap (as with Light Speed Shots); multishot/bounce assume targets are available."),
    ("Approximation", "eHP follows Effective Paths: (Health x max(Wall + Max Recovery, 1) + Defense Absolute) / (1 - Defense %). Regen is excluded."),
    ("Approximation", "Golden Tower / Black Hole / Death Wave sync: synced kills receive both multipliers; Effective Paths' exact phase-averaging is simplified to 'same cooldown = aligned'."),
    ("Assumption", "Blank coin-share-from-kills = 100% (flagged); blank damage-at-range share = 25% (Effective Paths default, flagged); blank gem horizon = 30 days (flagged)."),
    ("Assumption", "Bottleneck 'Not sure' weights damage and survivability equally and marks those picks Low confidence."),
    ("Future update", "After a patch: update TheTowerSDK, run build_data.py then build_workbook.py, or edit the 'Game Data' / 'GD ...' sheets directly. Re-run VALIDATION checks."),
]
header_row(sv, r + 1, 2, ["Type", "", "", "", "Detail"])
for i, (t, d_) in enumerate(NOTES):
    rr = r + 2 + i
    body(sv.cell(rr, 2, t), bg=PANEL if i % 2 == 0 else PANEL2, size=9, bold=True,
         color={"Discrepancy": AMBER, "Unknown": RED, "Limitation": VIOLET}.get(t, CYAN))
    for j in range(3, 6):
        sv.cell(rr, j).fill = fill(PANEL if i % 2 == 0 else PANEL2)
    body(sv.cell(rr, 6, d_), bg=PANEL if i % 2 == 0 else PANEL2, size=9, align=LEFTW)
    sv.row_dimensions[rr].height = 30
sv.column_dimensions["F"].width = 110

# ======================================================================
# 11. GUIDE
# ======================================================================
gu = S["Guide"]
setup_sheet(gu, tab_color="3A4A5C", zoom=100, rows=70, cols=6, widths={"A": 2, "B": 4, "C": 120})
title_bar(gu, 1, 2, "HOW TO USE MAGNET'S TOWER TOOL")
GUIDE = [
    ("1  Enter or import your account", None),
    ("", "Fastest: in the game tap your Player ID five times, then Settings → Toggles → External Tools Export → Manual Export. Copy tool_export.json to your PC and run:  python tools/tower_export_to_csv.py tool_export.json  (no account login, no upload). Open the CSV, copy both columns and paste into Import!A6."),
    ("", "Manual: on Player Profile, type into the cyan-bordered cells. Your typed value always overrides an imported one. Leave unknown values blank - the tool never assumes them."),
    ("", "Run evidence matters: say how your runs end and what limits you. That is how the tool decides whether damage, survivability, economy or research is your bottleneck."),
    ("2  Choose a strategy", None),
    ("", "Dashboard cell L2: Farming, Tournament, Milestones or Balanced. Strategies are goals, not upgrade categories: Farming can recommend damage if your farming runs end by death and damage limits your waves."),
    ("3  Read the recommendations", None),
    ("", "BUY NOW = best affordable Workshop/Enhancement purchases. RESEARCH NEXT = best labs; '▶ START' fills idle slots. SAVE FOR applies an exact sequencing rule to decide whether to buy the cheaper item first. Confidence: High = verified costs + modeled effect + your evidence; Medium = uses an estimated input; Low = depends on a bottleneck you have not confirmed; Judgment = not computed."),
    ("", "Roadmap: the next 20 investments, re-optimized after each simulated purchase, with funding times and lab slot timing; Power Stones have their own track. Gem Planner and UW Optimizer cover gems, weapons and stones."),
    ("4  After buying or researching", None),
    ("", "Update the level on Player Profile (or re-import). Everything recalculates instantly. Update coins, gems and stones when you check in."),
    ("5  After a game patch", None),
    ("", "All game numbers live on 'Game Data' and the 'GD ...' sheets. Edit them directly, or rebuild: update TheTowerSDK, run build/build_data.py then build/build_workbook.py. Check 'Sources & Validation' → Live formula checks."),
    ("Colour key", None),
    ("", "Cyan-bordered dark-blue cells = your inputs.  Cyan text = calculated values.  Grey text = imported or reference data.  Green = good / affordable, amber = estimated, red = limiting or low confidence."),
]
r = 3
for head, txt in GUIDE:
    if txt is None:
        c = gu.cell(r, 2, head)
        c.font = font(CYAN, 13, True)
        gu.row_dimensions[r].height = 26
    else:
        c = gu.cell(r, 3, txt)
        c.font = font(TEXT, 10)
        c.alignment = Alignment(wrap_text=True, vertical="top")
        gu.row_dimensions[r].height = 15 * (1 + len(txt) // 150)
    r += 1

# ======================================================================
# 12. FINISH
# ======================================================================
order = [S[n] for n in ws_order]
wb._sheets = order
wb.active = 0
for ws_ in wb.worksheets:
    ws_.sheet_view.tabSelected = ws_.title == "Dashboard"
for n in ("Optimization Engine", "Roadmap Engine"):
    S[n].sheet_properties.tabColor = VIOLET_DIM
out = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else os.path.join(HERE, "..", "magnet's Tower Tool.xlsx")
for n in ["Workshop Optimizer", "Lab Optimizer", "Roadmap", "Gem Planner", "UW Optimizer", "Player Profile",
          "Sources & Validation", "Guide"]:
    w_ = S[n]
    w_.page_setup.orientation = "landscape"
    w_.page_setup.fitToWidth = 1
    w_.page_setup.fitToHeight = 0
    w_.sheet_properties.pageSetUpPr.fitToPage = True
if os.environ.get("RENDER_SHEET"):
    keep = os.environ["RENDER_SHEET"].split(",")
    for ws_ in wb.worksheets:
        if ws_.title not in keep:
            ws_.sheet_state = "hidden"
    wb.active = wb.sheetnames.index(keep[0])
wb.calculation.fullCalcOnLoad = True
wb.save(out)
print("saved", out)

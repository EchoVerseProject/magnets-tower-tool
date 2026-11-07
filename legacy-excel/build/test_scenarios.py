"""Scenario tests for magnet's Tower Tool (all profiles are HYPOTHETICAL).

    python3 test_scenarios.py <workdir> <recalc.py path>

Builds the workbook per sample, applies scenario edits with openpyxl, recalculates in
LibreOffice and checks the outputs. Writes results to <workdir>/scenario_results.json.
"""
import json
import os
import subprocess
import sys

from openpyxl import load_workbook

HERE = os.path.dirname(os.path.abspath(__file__))
WORK, RECALC = sys.argv[1], sys.argv[2]


def build(sample, path):
    subprocess.run([sys.executable, os.path.join(HERE, "build_workbook.py"), path, "--sample", sample], check=True,
                   capture_output=True)


def set_import(wb, key, value):
    im = wb["Import"]
    for r in range(6, 2006):
        if im.cell(r, 1).value == key:
            im.cell(r, 2).value = value
            return
        if im.cell(r, 1).value is None:
            im.cell(r, 1).value, im.cell(r, 2).value = key, value
            return


def recalc(path):
    out = subprocess.run([sys.executable, RECALC, path, "600"], capture_output=True, text=True)
    return json.loads(out.stdout)


def read(path):
    v = load_workbook(path, data_only=True)
    db, rm, sv = v["Dashboard"], v["Roadmap"], v["Sources & Validation"]
    res = {
        "banner": db["C4"].value,
        "buy": [db[f"C{r}"].value for r in range(12, 17) if db[f"C{r}"].value],
        "buy_gain": [db[f"F{r}"].value for r in range(12, 17) if db[f"F{r}"].value],
        "buy_conf": [db[f"H{r}"].value for r in range(12, 17) if db[f"H{r}"].value],
        "research": [db[f"K{r}"].value for r in range(12, 17) if db[f"K{r}"].value],
        "save": db["C20"].value,
        "bottleneck": [db[f"L{r}"].value for r in range(20, 24)],
        "counter": db["L24"].value,
        "roadmap": [(rm[f"C{r}"].value, rm[f"E{r}"].value, rm[f"I{r}"].value) for r in range(9, 29) if rm[f"B{r}"].value],
        "roadmap_status": rm["C5"].value,
        "live_checks": [sv[f"E{r}"].value for r in range(27, 38)],
    }
    return res


SCEN = [
    ("blank", "none", "Farming", {}),
    ("early-farming", "early", "Farming", {}), ("early-tournament", "early", "Tournament", {}),
    ("early-milestones", "early", "Milestones", {}), ("early-balanced", "early", "Balanced", {}),
    ("mid-farming", "mid", "Farming", {}), ("mid-tournament", "mid", "Tournament", {}),
    ("mid-milestones", "mid", "Milestones", {}), ("mid-balanced", "mid", "Balanced", {}),
    ("adv-farming", "advanced", "Farming", {}), ("adv-tournament", "advanced", "Tournament", {}),
    ("adv-milestones", "advanced", "Milestones", {}), ("adv-balanced", "advanced", "Balanced", {}),
    ("mid-no-coins", "mid", "Farming", {"P|pCoins": 0}),
    ("mid-slots-full-balanced", "mid", "Balanced", {"P|pBusy": 4}),
    ("mid-unknown-bottleneck", "mid", "Farming", {"P|pFarmEvid": "Not sure"}),
    ("mid-farm-time-limited", "mid", "Farming", {"P|pFarmEnd": "I end the run"}),
    ("mid-tournament-no-wave", "mid", "Tournament", {"P|pTourWave": None}),
    ("mid-no-income", "mid", "Farming", {"P|pCPH": None}),
]
results = {}
cache = {}
for name, sample, strat, edits in SCEN:
    base = os.path.join(WORK, f"base_{sample}.xlsx")
    if sample not in cache:
        build(sample, base)
        cache[sample] = base
    wb = load_workbook(base)
    wb["Dashboard"]["L2"].value = strat
    for k, v in edits.items():
        set_import(wb, k, v)
    path = os.path.join(WORK, f"scn_{name}.xlsx")
    wb.save(path)
    rc = recalc(path)
    r = read(path)
    r["errors"] = rc.get("total_errors")
    r["formulas"] = rc.get("total_formulas")
    results[name] = r
    print(f"{name:28s} errors={r['errors']} buy={r['buy'][:3]} research={r['research'][:2]} roadmap={[x[0] for x in r['roadmap'][:3]]}")
json.dump(results, open(os.path.join(WORK, "scenario_results.json"), "w"), indent=1, default=str)

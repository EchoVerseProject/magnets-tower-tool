"""Extract computed engine values from recalculated legacy-Excel scenario files for cross-validation."""
import json, sys, csv
from openpyxl import load_workbook
out = {}
for path, name, strat, sample in [x.split("::") for x in sys.argv[2:]]:
    v = load_workbook(path, data_only=True, read_only=True)
    eg = v["Optimization Engine"]
    rows = list(eg.iter_rows(values_only=True))
    hdr_i = next(i for i, r in enumerate(rows) if r[1] == "Name" and r[2] == "Type")
    hdr = rows[hdr_i]
    col = {h: i for i, h in enumerate(hdr) if h}
    cands = {}
    for r in rows[hdr_i + 1:]:
        if not r[col["ID"]]:
            break
        cands[r[col["Type"]] + ":" + r[col["ID"]]] = {k: r[col[k]] for k in ("Level", "Cost", "Hours", "V", "cEcon", "cDmg", "cSurv", "cPP", "cRes", "Eligible", "Rank")}
    rm = v["Roadmap Engine"]
    rrows = list(rm.iter_rows(values_only=True))
    h_i = next(i for i, r in enumerate(rrows) if r[1] == "Step" and r[3] == "Pick role")
    rh = {h: i for i, h in enumerate(rrows[h_i]) if h}
    road = []
    for r in rrows[h_i + 1:h_i + 21]:
        if r[rh["Pick role"]]:
            road.append({k: r[rh[k]] for k in ("Pick role", "From", "To", "Cost", "Funded at (h)", "Slot", "Lab start (h)", "Lab done (h)")})
    imp = [(r[0], r[1]) for r in v["Import"].iter_rows(min_row=6, values_only=True) if r[0]]
    out[name] = {"strategy": strat, "sample": sample, "candidates": cands, "roadmap": road, "import": imp}
json.dump(out, open(sys.argv[1], "w"), default=str)
print({k: (len(x["candidates"]), len(x["roadmap"])) for k, x in out.items()})

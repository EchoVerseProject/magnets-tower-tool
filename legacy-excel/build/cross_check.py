"""Cross-check the dataset against independent references shipped in TheTowerSDK's fixtures
(Effective Paths spreadsheet snapshots). Writes data/xcheck.json and data/xcheck_uw.json.

    python3 cross_check.py <path-to-TheTowerSDK-checkout>

Run after build_data.py; then re-run build_data.py so the results are embedded in the workbook.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def hours(d):
    for pat, f in [(r"(\d+)d (\d+)h (\d+)m", lambda m: int(m[1]) * 24 + int(m[2]) + int(m[3]) / 60),
                   (r"(\d+):(\d+):(\d+)", lambda m: int(m[1]) + int(m[2]) / 60 + int(m[3]) / 3600),
                   (r"(\d+)s", lambda m: int(m[1]) / 3600)]:
        m = re.match(pat, d)
        if m:
            return f(m)
    return None


def main(sdk):
    fx = os.path.join(sdk, "fixtures", "data")
    D = json.load(open(os.path.join(DATA, "tower_data.json")))
    table = json.load(open(os.path.join(sdk, "src/data/workshop/table.json")))
    # workshop values
    ep = json.load(open(os.path.join(fx, "effective-paths-workshop.json")))
    ws = {}
    for k, arr in ep["stats"].items():
        n = bad = 0
        worst = 0.0
        for L, v in enumerate(arr):
            if v is None or str(L) not in table[k]:
                continue
            mine = table[k][str(L)]["value"]
            n += 1
            if v == 0 and mine == 0:
                continue
            rel = abs(mine - v) / max(abs(v), 1e-12)
            worst = max(worst, rel)
            bad += rel > 0.006
        ws[k] = (n, bad, worst)
    # labs
    epl = json.load(open(os.path.join(fx, "effective-paths-labs.json")))
    alias = {"ampbotcooldown": "amplifybotcooldown", "ampbotduration": "amplifybotduration",
             "goldbotcooldown": "goldenbotcooldown", "goldbotduration": "goldenbotduration",
             "commonenemyhealth": "basicenemyhealth", "commonenemyattack": "basicenemyattack"}
    by = {norm(l["name"]): l for l in D["labs"]}
    by.update({norm(l["id"]): l for l in D["labs"]})
    tot = cbad = dbad = 0
    labres, unmatched = [], []
    for L in epl["labs"]:
        k = alias.get(norm(L["name"]), norm(L["name"]))
        lab = by.get(k) or by.get(k.replace("multi", "mult"))
        if not lab:
            unmatched.append(L["name"])
            continue
        lv = {row[0]: row for row in lab["levels"]}
        n = nb = nd = 0
        for x in L["levels"]:
            if x["level"] == 999 or x["level"] not in lv:
                continue
            n += 1
            mine = lv[x["level"]]
            if x.get("cost") is not None and abs(mine[2] - x["cost"]) > max(1, abs(x["cost"]) * 0.006):
                nb += 1
            if x.get("durationSeconds") is not None and abs(mine[3] * 3600 - x["durationSeconds"]) > max(61, x["durationSeconds"] * 0.002):
                nd += 1
        tot += n
        cbad += nb
        dbad += nd
        labres.append((lab["id"], n, nb, nd))
    json.dump({"workshop": ws, "labs": labres, "unmatched": unmatched, "tot": tot, "cbad": cbad, "dbad": dbad},
              open(os.path.join(DATA, "xcheck.json"), "w"))
    # ultimate weapons
    epu = json.load(open(os.path.join(fx, "effective-paths-ultimate-weapons.json")))
    order = ["chain_lightning", "smart_missiles", "death_wave", "chrono_field", "inner_land_mines", "golden_tower",
             "poison_swamp", "black_hole", "spotlight"]
    num = lambda t: float(re.sub(r"[^0-9.\-]", "", str(t).replace(",", "")) or "nan")  # noqa: E731
    n = cb = vb = 0
    for w, key in zip(epu["weapons"], order):
        for st, mine in zip(w["stats"], D["uw"][key]["stats"]):
            for a, b in zip(st["levels"], mine["levels"]):
                n += 1
                cb += abs((a["cost"] or 0) - b[3]) > 0.5
                va = num(a["display"])
                vb += abs(va - b[2]) > max(0.011, abs(va) * 0.01)
    json.dump({"rows": n, "cost": cb, "value": vb}, open(os.path.join(DATA, "xcheck_uw.json"), "w"))
    print(f"labs: {tot} levels, {cbad} cost / {dbad} time mismatches, unmatched {unmatched}")
    print(f"workshop: {sum(v[0] for v in ws.values())} levels, {sum(v[1] for v in ws.values())} beyond tolerance")
    print(f"ultimate weapons: {n} levels, {cb} cost / {vb} value mismatches")


if __name__ == "__main__":
    main(sys.argv[1])

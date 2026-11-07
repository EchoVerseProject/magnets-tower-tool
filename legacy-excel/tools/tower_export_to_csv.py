#!/usr/bin/env python3
"""Convert The Tower's official External Tools export (tool_export.json) into rows
for the Import sheet of magnet's Tower Tool.

    python3 tower_export_to_csv.py tool_export.json [output.csv]

Standard library only. Runs offline: no account login, no credentials, no upload.
Open the CSV, copy columns A:B and paste them into Import!A6.

How to get the export (from the game): tap your Player ID five times, then
Settings -> Toggles -> External Tools Export -> Manual Export.
Only the official tool_export.json is supported (private save files are not).

Field layout follows the save-format documentation shipped with TheTowerSDK (MIT).
"""
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "tower_data.json")


def get(root, key, default=None):
    """Exports use camelCase or PascalCase depending on game version: match case-insensitively."""
    if key in root:
        return root[key]
    low = key.lower()
    for k, v in root.items():
        if k.lower() == low:
            return v
    return default


def arr(root, key):
    v = get(root, key)
    if isinstance(v, dict) and isinstance(v.get("_items"), list):
        v = v["_items"]
    return v if isinstance(v, list) else []


def num(x, default=None):
    try:
        if isinstance(x, bool):
            return 1 if x else 0
        return float(x)
    except (TypeError, ValueError):
        return default


def hours_left(root, idx):
    """Hours until a running research finishes, from ResearchCompleteDate and ExportedAt (newer exports)."""
    from datetime import datetime
    done, at = arr(root, "ResearchCompleteDate"), get(root, "ExportedAt")
    if idx >= len(done) or not at:
        return None
    try:
        f = lambda s: datetime.fromisoformat(str(s).replace("Z", "+00:00"))  # noqa: E731
        return round(max(0.0, (f(done[idx]) - f(at)).total_seconds() / 3600), 1)
    except ValueError:
        return None


def main(src, out):
    root = json.load(open(src, encoding="utf-8-sig"))
    if not isinstance(root, dict):
        sys.exit("This file does not look like an official tool_export.json")
    D = json.load(open(DATA, encoding="utf-8"))
    rows = [("META|label", "Imported from tool_export.json")]
    warn = []

    # ---- workshop levels (active block, falling back to the current preset like the SDK)
    cats = {"Attack": ("upgradeWorkshopLevel", "presetUpgradeWorkshopLevel", "upgradeTierUnlocked"),
            "Defense": ("upgradeWorkshopDefenseLevel", "presetUpgradeWorkshopDefenseLevel", "upgradeDefenseTierUnlocked"),
            "Utility": ("upgradeWorkshopUtilityLevel", "presetUpgradeWorkshopUtilityLevel", "upgradeUtilityTierUnlocked")}
    preset = int(num(get(root, "currentWorkshopPreset"), 0) or 0)
    from_groups = {}
    for w in D["workshop"]:
        from_groups.setdefault(w["category"], []).append(w)
    for cat, (key, pkey, ukey) in cats.items():
        items = sorted(from_groups[cat], key=lambda w: w["saveIndex"])
        n = len(items)
        active = [num(x, 0) for x in arr(root, key)[:n]]
        if not any(active):
            flat = [num(x, 0) for x in arr(root, pkey)]
            active = flat[preset * n:(preset + 1) * n]
            if active:
                warn.append(f"{cat}: used workshop preset {preset}")
        for w in items:
            if w["saveIndex"] < len(active):
                rows.append((f"WS|{w['id']}", int(active[w['saveIndex']])))
        # unlock groups: flag u (stride = category upgrade count; first block)
        unl = arr(root, ukey)
        groups = {}
        for w in items:
            if w["unlockGroup"] != "Base":
                groups.setdefault(int(w["unlockGroup"].split("G")[1]), []).append(w)
        for u, members in groups.items():
            if u < len(unl):
                for w in members:
                    rows.append((f"WSU|{w['id']}", 1 if unl[u] is True or num(unl[u], 0) == 1 else 0))

    # ---- enhancements
    ekeys = {"Attack": "enhancementLevel", "Defense": "enhancementDefenseLevel", "Utility": "enhancementUtilityLevel"}
    for e in D["enhancements"]:
        a = arr(root, ekeys[e["category"]])
        if e["saveIndex"] < len(a):
            rows.append((f"EN|{e['id']}", int(num(a[e["saveIndex"]], 0))))

    # ---- labs
    levels = arr(root, "researchLevel")
    by_index = {l["saveIndex"]: l for l in D["labs"] if l["saveIndex"] is not None}
    for i, v in enumerate(levels):
        if i in by_index:
            rows.append((f"LAB|{by_index[i]['id']}", int(num(v, 0))))
    if not levels:
        warn.append("No researchLevel array found - enter lab levels manually")
    ints, act = arr(root, "labResearchInt"), arr(root, "labActiveBool")
    slot = 0
    for s, ri in enumerate(ints):
        if s < len(act) and act[s] is True and num(ri) is not None and int(num(ri)) in by_index:
            slot += 1
            rows.append((f"SLOT|{slot}|lab", by_index[int(num(ri))]["id"]))
            hrs = hours_left(root, int(num(ri)))
            if hrs is not None:
                rows.append((f"SLOT|{slot}|hours", hrs))
            else:
                warn.append(f"Lab slot {slot}: enter 'hours left' on Player Profile (not in this export)")
    if slot:
        rows.append(("P|pBusy", slot))
    nslots = num(get(root, "labsUnlocked"))
    if nslots:
        rows.append(("P|pSlots", int(nslots)))
        if not slot:
            rows.append(("P|pBusy", 0))

    # ---- player
    tw = arr(root, "highestWaveThisTier")
    for t, w in enumerate(tw):
        if t >= 1 and num(w, 0) > 0:
            rows.append((f"TW|{t}", int(num(w))))
    # balances (present in newer exports)
    for key, field in (("Coins", "pCoins"), ("Gems", "pGems"), ("Stones", "pStones")):
        v = num(get(root, key))
        if v is not None:
            rows.append((f"P|{field}", round(v)))
    # share of run coins that come from kills (lifetime totals)
    fk, fw = num(get(root, "TotalCoinsEarnedFromKills")), num(get(root, "TotalCoinsEarnedFromWaves"))
    if fk and fw is not None and fk + fw > 0:
        rows.append(("P|pKillShare", round(fk / (fk + fw), 4)))
    # battle history: recent non-tournament runs on the tier you farm most recently
    hist = get(root, "battleHistory")
    if isinstance(hist, dict):
        hist = hist.get("_items")
    runs = []
    for run in hist or []:
        if not isinstance(run, dict):
            continue
        tour = get(run, "IsTournament") is True
        c, t = num(get(run, "coinsEarned")), num(get(run, "realTime"))
        tier, wave = num(get(run, "Tier")), num(get(run, "Wave"))
        runs.append((tour, c, t, tier, wave, str(get(run, "BattleDate") or "")))
    runs.sort(key=lambda r: r[5])
    farm = [r for r in runs if not r[0] and r[1] and r[2]]
    if farm:
        recent = farm[-8:]
        tiers = [r[3] for r in recent if r[3]]
        tier = max(set(tiers), key=lambda t: (tiers.count(t), tiers[::-1].index(t) * -1)) if tiers else None
        sel = [r for r in recent if r[3] == tier][-5:] if tier else recent[-5:]
        coins, secs = sum(r[1] for r in sel), sum(r[2] for r in sel)
        rows.append(("P|pCPH", round(coins / secs * 3600)))
        if tier:
            rows.append(("P|pFarmTier", int(tier)))
            waves = sorted(r[4] for r in sel if r[4])
            if waves:
                rows.append(("P|pFarmWave", int(waves[len(waves) // 2])))
        warn.append(f"Farming taken from your last {len(sel)} non-tournament runs on tier {int(tier) if tier else '?'} "
                    f"({secs / 3600:.1f} h of play): coins/hour and median wave")
    else:
        ct = num(get(root, "currentTier"))
        if ct:
            rows.append(("P|pFarmTier", int(ct)))
    tw_runs = [r[4] for r in runs if r[0] and r[4]]
    if tw_runs:
        rows.append(("P|pTourWave", int(max(tw_runs[-3:]))))

    # ---- ultimate weapons
    uu, ul = arr(root, "ultimateWeaponUnlocked"), arr(root, "ultimateWeaponLevel")
    for i, v in enumerate(uu[:9]):
        rows.append((f"UWU|{i}", 1 if v is True or num(v, 0) == 1 else 0))
    for i, v in enumerate(ul[:27]):
        rows.append((f"UWL|{i}", int(num(v, 0))))

    with open(out, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    print(f"Wrote {len(rows)} rows to {out}")
    for w in warn:
        print("note:", w)
    print("Not in the export (enter on Player Profile): run evidence (how runs end / what limits you), modifiers, "
          "UW choices on offer.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(sys.argv[1])[0] + "_import.csv")

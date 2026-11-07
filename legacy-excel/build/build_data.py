"""Build the verified game dataset for magnet's Tower Tool.

Reads TheTowerSDK (MIT, https://github.com/TmRxJD/TheTowerSDK) as plain text/JSON
-- it never executes SDK code -- and writes tower-tool/data/tower_data.json.

Usage:
    python3 build_data.py <path-to-TheTowerSDK-checkout>

Re-run after a game patch once the SDK has been updated, then run
build_workbook.py to regenerate the workbook.
"""
import json
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import enemy_scaling  # noqa: E402

SDK_URL = "https://github.com/TmRxJD/TheTowerSDK"
GAME_VERSION = "v29 (SDK data: v29.0.0 facts; v29.1.x checks)"

# --------------------------------------------------------------------------
# Workshop metadata. Order = position in the official export arrays.
# key: name in workshop table.json
# role: how the optimization engine uses the stat (see Optimization Engine)
# --------------------------------------------------------------------------
WS = [
    # (category, save index, table key, display, unit, role, description)
    ("Attack", 0, "Damage", "Damage", "dmg", "DMG", "Base damage of each projectile."),
    ("Attack", 1, "Attack Speed", "Attack Speed", "x", "AS", "Projectile firing rate."),
    ("Attack", 2, "Critical Chance", "Critical Chance", "%", "CC", "Chance for a shot to crit."),
    ("Attack", 3, "Critical Factor", "Critical Factor", "x", "CF", "Damage multiplier on crits."),
    ("Attack", 4, "Range", "Range", "x10 m", "RANGE", "Tower range (value x10 = metres)."),
    ("Attack", 5, "Damage / Meter", "Damage / Meter", "per mille/m", "DPM", "Bonus damage per metre of enemy distance."),
    ("Attack", 6, "Multishot Chance", "Multishot Chance", "%", "MSC", "Chance to fire at extra targets."),
    ("Attack", 7, "Multishot Targets", "Multishot Targets", "targets", "MST", "Targets hit by a multishot."),
    ("Attack", 8, "Rapid Fire Chance", "Rapid Fire Chance", "%", "RFC", "Chance to trigger rapid fire."),
    ("Attack", 9, "Rapid Fire Duration", "Rapid Fire Duration", "s", "RFD", "Rapid fire duration."),
    ("Attack", 10, "Bounce Shot Chance", "Bounce Shot Chance", "%", "BSC", "Chance for a shot to bounce."),
    ("Attack", 11, "Bounce Shot Targets", "Bounce Shot Targets", "targets", "BST", "Maximum bounces."),
    ("Attack", 12, "Bounce Shot Range", "Bounce Shot Range", "m", "NQ", "Bounce search range."),
    ("Attack", 13, "Super Crit Chance", "Super Crit Chance", "%", "SCC", "Chance for a crit to become a super crit."),
    ("Attack", 14, "Super Crit Mult", "Super Crit Mult", "x", "SCM", "Super crit damage multiplier."),
    ("Attack", 15, "Rend Armor Chance", "Rend Armor Chance", "%", "NQ", "Chance to rend armor (boss/tank damage ramp)."),
    ("Attack", 16, "Rend Armor Mult", "Rend Armor Mult", "x", "NQ", "Rend armor stack multiplier."),
    ("Defense", 0, "Health", "Health", "HP", "HP", "Tower maximum health."),
    ("Defense", 1, "Health Regen", "Health Regen", "HP/s", "NQ", "Health regenerated per second."),
    ("Defense", 2, "Defense Percent", "Defense %", "%", "DEFP", "Percentage damage reduction."),
    ("Defense", 3, "Defense Absolute", "Defense Absolute", "flat", "DA", "Flat damage reduction per hit."),
    ("Defense", 4, "Thorns", "Thorn Damage", "%", "NQ", "Reflects damage to attackers."),
    ("Defense", 5, "Lifesteal", "Lifesteal", "%", "NQ", "Heals a share of damage dealt."),
    ("Defense", 6, "Knockback Chance", "Knockback Chance", "%", "NQ", "Chance to knock enemies back."),
    ("Defense", 7, "Knockback Force", "Knockback Force", "force", "NQ", "Knockback strength."),
    ("Defense", 8, "Orb Speed", "Orb Speed", "speed", "NQ", "Orb rotation speed."),
    ("Defense", 9, "Orbs", "Orbs", "count", "NQ", "Number of orbs."),
    ("Defense", 10, "Shockwave Size", "Shockwave Size", "size", "NQ", "Shockwave radius."),
    ("Defense", 11, "Shockwave Frequency", "Shockwave Frequency", "s", "NQ", "Seconds between shockwaves (lower is better)."),
    ("Defense", 12, "Land Mine Chance", "Land Mine Chance", "%", "NQ", "Chance to drop a land mine."),
    ("Defense", 13, "Land Mine Damage", "Land Mine Damage", "%", "NQ", "Land mine damage."),
    ("Defense", 14, "Land Mine Radius", "Land Mine Radius", "radius", "NQ", "Land mine blast radius."),
    ("Defense", 15, "Death Defy", "Death Defy", "%", "NQ", "Chance to survive a lethal hit."),
    ("Defense", 16, "Wall Health", "Wall Health", "% of HP", "WALL", "Wall health as % of tower health."),
    ("Defense", 17, "Wall Rebuild", "Wall Rebuild", "s", "NQ", "Wall rebuild time (lower is better)."),
    ("Utility", 0, "Cash Bonus", "Cash Bonus", "x", "NQ", "In-run cash multiplier (in-run economy)."),
    ("Utility", 1, "Cash / Wave", "Cash / Wave", "cash", "NQ", "In-run cash per wave."),
    ("Utility", 2, "Coins / Kill Bonus", "Coins / Kill Bonus", "x", "CPK", "Coin multiplier on kills."),
    ("Utility", 3, "Coins / Wave", "Coins / Wave", "coins", "CPW", "Coins granted per wave."),
    ("Utility", 4, "Free Attack Upgrade", "Free Attack Upgrade", "%", "NQ", "Chance of a free in-run attack upgrade."),
    ("Utility", 5, "Free Defense Upgrade", "Free Defense Upgrade", "%", "NQ", "Chance of a free in-run defense upgrade."),
    ("Utility", 6, "Free Utility Upgrade", "Free Utility Upgrade", "%", "NQ", "Chance of a free in-run utility upgrade."),
    ("Utility", 7, "Interest / Wave", "Interest / Wave", "%", "NQ", "In-run cash interest."),
    ("Utility", 8, "Recovery Amount", "Recovery Amount", "fraction", "NQ", "Health restored per recovery package."),
    ("Utility", 9, "Max Recovery", "Max Recovery", "x HP", "RECMAX", "Maximum recovery (Effective Paths eHP pool term)."),
    ("Utility", 10, "Package Chance", "Package Chance", "fraction", "NQ", "Chance of a recovery package per wave."),
    ("Utility", 11, "Enemy Attack Level Skip", "Enemy Attack Level Skip", "fraction", "NQ", "Chance enemies skip an attack scaling level."),
    ("Utility", 12, "Enemy Health Level Skip", "Enemy Health Level Skip", "fraction", "NQ", "Chance enemies skip a health scaling level."),
]

# Upgrade groups that start locked (export field upgrade*TierUnlocked).
UNLOCK_GROUPS = {
    "Attack": [["Range", "Damage / Meter"], ["Multishot Chance", "Multishot Targets"],
               ["Rapid Fire Chance", "Rapid Fire Duration"],
               ["Bounce Shot Chance", "Bounce Shot Targets", "Bounce Shot Range"],
               ["Super Crit Chance", "Super Crit Mult"], ["Rend Armor Chance", "Rend Armor Mult"]],
    "Defense": [["Defense Percent", "Defense Absolute"], ["Thorns"], ["Lifesteal"],
                ["Knockback Chance", "Knockback Force"], ["Orb Speed", "Orbs"],
                ["Shockwave Size", "Shockwave Frequency"],
                ["Land Mine Chance", "Land Mine Damage", "Land Mine Radius"], ["Death Defy"],
                ["Wall Health", "Wall Rebuild"]],
    "Utility": [["Cash Bonus", "Cash / Wave"], ["Coins / Kill Bonus", "Coins / Wave"],
                ["Free Attack Upgrade", "Free Defense Upgrade", "Free Utility Upgrade"],
                ["Interest / Wave"], ["Recovery Amount", "Max Recovery", "Package Chance"],
                ["Enemy Attack Level Skip", "Enemy Health Level Skip"]],
}

NQ_REASON_WS = {
    "Bounce Shot Range": "Range only matters when enemies are spread out; no validated throughput formula.",
    "Rend Armor Chance": "Rend ramps damage against bosses/tanks; value depends on enemy mix and armor (not modeled).",
    "Rend Armor Mult": "Rend ramps damage against bosses/tanks; value depends on enemy mix and armor (not modeled).",
    "Health Regen": "Sustain stat: value depends on incoming damage rate between hits; no validated wave conversion.",
    "Thorns": "Damage reflected depends on enemy hits taken; not converted to waves.",
    "Lifesteal": "Healing depends on damage dealt vs incoming damage; not converted to waves.",
    "Knockback Chance": "Crowd control; effect depends on enemy mix and range.",
    "Knockback Force": "Crowd control; effect depends on enemy mix and range.",
    "Orb Speed": "Orb kills depend on enemy speed/paths.",
    "Orbs": "Orb kills depend on enemy speed/paths.",
    "Shockwave Size": "Crowd control/damage depends on Cannon module and enemy mix.",
    "Shockwave Frequency": "Crowd control/damage depends on Cannon module and enemy mix.",
    "Land Mine Chance": "Mine damage depends on enemy pathing.",
    "Land Mine Damage": "Mine damage depends on enemy pathing.",
    "Land Mine Radius": "Mine damage depends on enemy pathing.",
    "Death Defy": "Probabilistic extra life; depends on how runs end.",
    "Wall Rebuild": "Depends on how often the wall breaks.",
    "Cash Bonus": "In-run cash only; does not change coins or permanent stats.",
    "Cash / Wave": "In-run cash only; does not change coins or permanent stats.",
    "Free Attack Upgrade": "In-run upgrades only.",
    "Free Defense Upgrade": "In-run upgrades only.",
    "Free Utility Upgrade": "In-run upgrades only.",
    "Interest / Wave": "In-run cash only.",
    "Recovery Amount": "Healing value depends on package timing and incoming damage.",
    "Package Chance": "Healing value depends on package timing and incoming damage.",
    "Enemy Attack Level Skip": "Changes enemy scaling steps; no validated closed form in this model.",
    "Enemy Health Level Skip": "Changes enemy scaling steps; no validated closed form in this model.",
}

# --------------------------------------------------------------------------
# Lab roles. Anything not listed is shown, costed and timed, but its benefit is
# marked "Not quantified" (with a reason by category).
# --------------------------------------------------------------------------
LAB_ROLES = {
    "damage": "L_DMG", "attack_speed": "L_AS", "critical_factor": "L_CF", "range": "L_RANGE",
    "damage_meter": "L_DPM", "super_crit_chance": "L_SCC", "super_crit_multi": "L_SCM",
    "health": "L_HP", "defense_absolute": "L_DA", "defense": "L_DEFP", "wall_health": "L_WALL",
    "recovery_package_max": "L_RECMAX", "coins_kill_bonus": "L_CPK", "coins_per_wave": "L_CPW",
    "workshop_attack_discount": "L_DISC_ATK", "workshop_defense_discount": "L_DISC_DEF",
    "workshop_utility_discount": "L_DISC_UTL", "labs_coin_discount": "L_LABDISC",
    "labs_speed": "L_LABSPEED", "game_speed": "L_GAMESPEED", "golden_tower_bonus": "L_GT",
    "black_hole_coin_bonus": "L_BH", "death_wave_coin_bonus": "L_DW", "spotlight_coin_bonus": "L_SL",
}
NQ_REASON_LAB_CAT = {
    "Ultimate Weapon": "Ultimate Weapon effect: depends on UW ownership, stones and uptime.",
    "Card Mastery": "Card Mastery: depends on owning/equipping the card.",
    "Cards": "Card effect: depends on owning/equipping the card.",
    "Enemies": "Reduces a specific enemy type's stats: value depends on your enemy mix.",
    "Modules": "Module effect: depends on owned modules/shards.",
    "Bots": "Bot effect: depends on bot ownership and uptime.",
    "Perks": "Perk effect: depends on perk choices.",
    "Battle Condition (Enemy Ultimates)": "Tournament battle-condition counter: depends on league conditions.",
    "Battle Condition (Resistances)": "Tournament battle-condition counter: depends on league conditions.",
    "Battle Condition (Enemy/Spawn Buffs)": "Tournament battle-condition counter: depends on league conditions.",
    "Battle Condition (Durations/Reductions)": "Tournament battle-condition counter: depends on league conditions.",
    "Main": "Unlock / quality-of-life or system research (no direct stat effect modeled).",
    "Attack": "Not converted by the damage model.",
    "Defense": "Not converted by the health model.",
    "Utility": "Not converted by the economy model.",
}
LAB_NQ_SPECIFIC = {
    "health_regen": "Sustain stat: value depends on incoming damage rate; no validated wave conversion.",
    "max_rend_armor_multiplier": "Rend armor value depends on boss/tank mix (not modeled).",
    "enhancement_attack_coin_discount": "Discounts Workshop Enhancements (enhancements are out of scope for v1).",
    "enhancement_defense_coin_discount": "Discounts Workshop Enhancements (enhancements are out of scope for v1).",
    "enhancement_utility_coin_discount": "Discounts Workshop Enhancements (enhancements are out of scope for v1).",
    "cash_bonus": "In-run cash only.", "cash_wave": "In-run cash only.", "interest": "In-run cash only.",
    "max_interest": "In-run cash only.", "starting_cash": "In-run cash only.",
}

# Workshop Enhancements (export arrays enhancementLevel / enhancementDefenseLevel /
# enhancementUtilityLevel, in this order). Effect: +1% of the stat per level
# (Effective Paths ENHANCEMENT_MULTIPLIER_PER_LEVEL = 0.01).
ENH = [
    ("Attack", 0, "Damage", "E_DMG"), ("Attack", 1, "Rend Armor", "NQ"),
    ("Attack", 2, "Critical Factor", "E_CF"), ("Attack", 3, "Damage/Meter", "E_DPM"),
    ("Attack", 4, "Super Crit Mult", "E_SCM"), ("Attack", 5, "Attack Speed", "E_AS"),
    ("Defense", 0, "Health", "E_HP"), ("Defense", 1, "Health Regen", "NQ"),
    ("Defense", 2, "Defense Absolute", "E_DA"), ("Defense", 3, "Land Mine Damage", "NQ"),
    ("Defense", 4, "Wall Health", "E_WALL"), ("Defense", 5, "Orb Size", "NQ"),
    ("Utility", 0, "Cash Bonus", "NQ"), ("Utility", 1, "Coin Bonus", "E_COIN"),
    ("Utility", 2, "Cells / Kill Bonus", "NQ"), ("Utility", 3, "Free Upgrades", "NQ"),
    ("Utility", 4, "Recovery Package", "E_RECMAX"), ("Utility", 5, "Enemy Level Skips", "NQ"),
]
ENH_NQ = {
    "Rend Armor": "Rend value depends on boss/tank mix.",
    "Health Regen": "Sustain stat; no validated wave conversion.",
    "Land Mine Damage": "Mine damage depends on enemy pathing.",
    "Orb Size": "Orb kills depend on enemy paths.",
    "Cash Bonus": "In-run cash only.",
    "Cells / Kill Bonus": "Cells per kill: cell income is not modeled numerically in v1.",
    "Free Upgrades": "In-run upgrades only.",
    "Enemy Level Skips": "Changes enemy scaling steps; no validated closed form.",
}

# Gem prices. Source and status recorded with each value.
GEMS = {
    "labSlotCost": {"value": [0, 100, 400, 1400, 3000], "status": "Verified",
                    "source": "TheTowerSDK knowledge/compartments/labs.ts LAB_SLOT_GEM_COST (wiki 'Lab Upgrades', checked 2026-08-16; Game Vault agrees)"},
    "cardGems": {"value": 20, "status": "Verified", "source": "TheTowerSDK knowledge/compartments/cards.ts (one card = 20 gems)"},
    "cardStarGems": {"value": [20, 40, 100, 160, 240, 400, 640], "status": "Verified",
                     "source": "TheTowerSDK CARD_GEM_COST_PER_STAR"},
    "cardSlotTotal22": {"value": 58400, "status": "Verified (total only)",
                        "source": "TheTowerSDK cards.ts: 22 gem-buyable slots cost 58,400 in total; per-slot prices not in any reachable source"},
    "modulePullGems": {"value": 20, "status": "Verified", "source": "TheTowerSDK MODULE_BANNER_RULES.gemsPerPull"},
    "moduleEpicChance": {"value": 0.025, "status": "Verified", "source": "MODULE_BANNER_RULES.epicChancePercent"},
    "moduleEpicPity": {"value": 150, "status": "Unverified in SDK", "source": "MODULE_BANNER_RULES.epicPity (marked unverified by SDK)"},
    "labRush": {"value": "piecewise", "status": "Verified",
                "source": "TheTowerSDK data/labs/overview.ts computeLabGems (time-based rush price)"},
}

SAVE_ALIASES = {  # catalog display name -> export labOrder name
    "Amplify Bot - Cooldown": "Amp Bot - Cooldown", "Amplify Bot - Duration": "Amp Bot - Duration",
    "Basic Enemy Attack": "Common Enemy Attack", "Basic Enemy Health": "Common Enemy Health",
    "Golden Bot - Cooldown": "Gold Bot - Cooldown", "Golden Bot - Duration": "Gold Bot - Duration",
    "Missiles Despawn Time": "Missile Despawn Time", "Missiles Radius": "Missile Radius",
    "Module Shard Cost": "Module Shards Cost", "Orbs Boss Hit": "Orb Boss Hit",
    "Super Crit Mult": "Super Crit Multi", "Swamp Rend - Basic Enemies": "Swamp Rend",
}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def parse_lab_catalog(path):
    src = open(path, encoding="utf-8").read()
    start = src.index("export const LAB_CATALOG")
    body = src[src.index("= [", start) + 2:]
    body = body.replace("...PRIMARY_MODULE_BONUS_LABS,", "")
    body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
    body = re.sub(r"(?<!:)//[^\n]*", "", body)
    body = re.sub(r"([{,\s])([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', body)
    body = re.sub(r",(\s*[}\]])", r"\1", body).strip().rstrip(";")
    data = json.loads(body)
    # Primary module bonus labs (separate file, generated levels: cost x1.5, +16d16h per level)
    pm = open(os.path.join(os.path.dirname(path), "primary-module-bonus.ts"), encoding="utf-8").read()
    lv = re.findall(r"\{ level: (\d+), cost: ([0-9.e+]+), duration: '([^']+)' \}", pm)
    levels = [{"level": int(a), "cost": float(b), "duration": c} for a, b, c in lv]
    for slug, name in re.findall(r"slug: '(primary_module_bonus_\w+)',\s*name: '([^']+)'", pm):
        data.append({"slug": slug, "name": name, "category": "Modules", "levels": levels})
    return data


def parse_lab_index(path):
    src = open(path, encoding="utf-8").read()
    body = src[src.index("= [", src.index("LAB_RESEARCH_BY_INDEX")) + 2:]
    body = body[:body.index("\n]") + 2]
    body = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", lambda m: json.dumps(m.group(1).replace("\\'", "'")), body)
    body = re.sub(r",(\s*[}\]])", r"\1", body)
    return json.loads(body)


def parse_unlocks(path):
    s = open(path, encoding="utf-8").read()
    s = s[s.index("LAB_UNLOCKS"):]
    s = s[:s.index("\n}")]
    out = {}
    for m in re.finditer(r"'([^']+)':\s*(?:\{ tier: (\d+), wave: (\d+) \}|UNLOCKED_BY_ULTIMATE)", s):
        out[m.group(1)] = [int(m.group(2)), int(m.group(3))] if m.group(2) else "UW"
    return out


UW_ORDER = ["chain_lightning", "smart_missiles", "death_wave", "chrono_field", "inner_land_mines", "golden_tower",
            "poison_swamp", "black_hole", "spotlight"]  # export order (ultimateWeaponUnlocked)
# Stone price of the Nth weapon (index = weapons already owned). SDK knowledge/compartments/ultimate-weapons.ts
UW_UNLOCK = [5, 50, 150, 300, 800, 1250, 1750, 2400, 3000]
UW_ROLES = {  # factual: what the weapon's stats act on
    "chain_lightning": "Damage", "smart_missiles": "Damage", "death_wave": "Damage + Economy (DW coin/cell labs)",
    "chrono_field": "Control (slows enemies)", "inner_land_mines": "Damage", "golden_tower": "Economy",
    "poison_swamp": "Damage + Control (slow)", "black_hole": "Control + Economy (BH coin lab)",
    "spotlight": "Damage (boosts tower damage in the beam)",
}


def parse_uw(path):
    s = open(path, encoding="utf-8").read()
    s = s[s.index("uwStoneChartData"):]
    out = {}
    for m in re.finditer(r"\n  (\w+): \{\n    name: '([^']+)',(.*?)\n  \},", s, re.S):
        key, nm, body = m.groups()
        stats = []
        for sm in re.finditer(r"name: '([^']+)', levels: \[(.*?)\]", body, re.S):
            lv = []
            for l_ in re.finditer(r"\{ level: (\d+), value: '([^']*)', cost: ('Unlock'|[\d.]+) \}", sm.group(2)):
                txt = l_[2]
                num = float(re.sub(r"[^0-9.\-]", "", txt.replace(",", "")) or "nan")
                lv.append([int(l_[1]), txt, num, 0 if l_[3] == "'Unlock'" else float(l_[3])])
            stats.append({"name": sm.group(1), "levels": lv})
        out[key] = {"name": nm, "stats": stats, "role": UW_ROLES[key], "exportIndex": UW_ORDER.index(key)}
    assert len(out) == 9
    return out


def hours(d):
    m = re.match(r"(\d+)d (\d+)h (\d+)m", d)
    if m:
        return int(m[1]) * 24 + int(m[2]) + int(m[3]) / 60
    m = re.match(r"(\d+):(\d+):(\d+)", d)
    if m:
        return int(m[1]) + int(m[2]) / 60 + int(m[3]) / 3600
    m = re.match(r"(\d+)s", d)
    if m:
        return int(m[1]) / 3600
    raise ValueError(d)


def main(sdk):
    commit = subprocess.run(["git", "-C", sdk, "log", "-1", "--format=%H|%cs"],
                            capture_output=True, text=True).stdout.strip().split("|")
    table = json.load(open(os.path.join(sdk, "src/data/workshop/table.json"), encoding="utf-8"))

    # ---------------- workshop ----------------
    group_of = {}
    for cat, groups in UNLOCK_GROUPS.items():
        for gi, g in enumerate(groups):
            for k in g:
                group_of[k] = f"{cat[:3].upper()}-G{gi}"
    workshop = []
    for cat, idx, key, disp, unit, role, desc in WS:
        rows = table[key]
        lv = sorted(rows, key=int)
        levels = [[rows[x]["value"], rows[x]["coins"]] for x in lv]
        maxl = int(lv[-1])
        assert levels[-1][1] == 0 and all(c > 0 for _, c in levels[:-1]), key
        workshop.append({
            "id": "WS_" + norm(key).upper()[:14], "key": key, "name": disp, "category": cat,
            "saveIndex": idx, "unlockGroup": group_of.get(key, "Base"), "maxLevel": maxl,
            "unit": unit, "role": role, "desc": desc,
            "nqReason": NQ_REASON_WS.get(key, ""), "levels": levels,
        })
    ids = [w["id"] for w in workshop]
    assert len(ids) == len(set(ids))

    # ---------------- labs ----------------
    cat = parse_lab_catalog(os.path.join(sdk, "src/data/labs/catalog.data.ts"))
    idx = parse_lab_index(os.path.join(sdk, "src/data/generated/labs-research.generated.ts"))
    unl = parse_unlocks(os.path.join(sdk, "src/data/labs/unlocks.ts"))
    fmt = json.load(open(os.path.join(sdk, "fixtures/data/save-format/lab_save_format.json")))["labOrder"]
    fmt_by = {norm(v): int(k) for k, v in fmt.items() if v}
    idx_by_slug = {r["slug"]: r for r in idx if r["slug"]}
    labs = []
    for r in cat:
        ir = idx_by_slug.get(r["slug"])
        save = ir["index"] if ir else fmt_by.get(norm(SAVE_ALIASES.get(r["name"], r["name"])))
        lvmap = {x["level"]: x for x in r["levels"]}
        minl = min(lvmap)
        maxl = max(lvmap)
        val = r.get("value")
        base = r.get("base")
        rows = []
        for L in range(0, maxl + 1):
            if isinstance(val, dict):
                eff = val.get(str(L))
            elif val is not None and base is not None:
                eff = base + val * L
            else:
                eff = None
            if L in lvmap and L >= 1 or (L in lvmap and lvmap[L]["cost"] > 0):
                c = float(lvmap[L]["cost"])
                h = hours(lvmap[L]["duration"])
            else:
                c, h = 0.0, 0.0
            rows.append([L, eff, c, h])
        if r["name"] in unl:
            u = unl[r["name"]]
            unlock = ("UW", None) if u == "UW" else (u[0], u[1])
            ustat = "Verified"
        elif ir and ir["tierUnlock"] == 0:
            unlock, ustat = (0, 0), "Verified"
        else:
            unlock, ustat = (None, None), "Unknown"
        role = LAB_ROLES.get(r["slug"], "NQ")
        nq = "" if role != "NQ" else LAB_NQ_SPECIFIC.get(r["slug"], NQ_REASON_LAB_CAT.get(r["category"], "Not modeled."))
        if isinstance(val, dict):
            eform = "Effect table by level"
        elif val is not None and base is not None:
            eform = f"{base:g} + {val:g} x level"
        else:
            eform = "Unknown (no effect data in source)"
        labs.append({
            "id": r["slug"], "name": r["name"], "category": r["category"], "saveIndex": save,
            "minLevel": minl, "maxLevel": maxl, "unlockTier": unlock[0], "unlockWave": unlock[1],
            "unlockStatus": ustat, "role": role, "nqReason": nq, "effectFormula": eform,
            "effectStatus": "Unknown" if val is None else "Verified",
            "desc": (ir or {}).get("description") or "", "levels": rows,
        })

    # ---------------- workshop enhancements ----------------
    enh_costs = json.load(open(os.path.join(sdk, "src/data/workshop/enhancement-costs.json")))["costs"]
    enhancements = []
    for cat_, i, label, role in ENH:
        costs = enh_costs[label]
        enhancements.append({
            "id": "EN_" + norm(label).upper()[:12], "name": label + " +", "label": label,
            "category": cat_, "saveIndex": i, "maxLevel": len(costs), "role": role,
            "nqReason": "" if role != "NQ" else ENH_NQ.get(label, "Not converted by the model."),
            # row L = cost of buying level L+1 (same convention as the workshop table)
            "costs": costs + [0],
        })

    # ---------------- ultimate weapons ----------------
    uws = parse_uw(os.path.join(sdk, "src/data/ultimate-weapons/stones.data.ts"))

    # ---------------- enemy scaling ----------------
    growth = enemy_scaling.growth_table()
    anchors = enemy_scaling.anchor_check()

    xcheck = json.load(open(os.path.join(HERE, "..", "data", "xcheck.json"))) if os.path.exists(
        os.path.join(HERE, "..", "data", "xcheck.json")) else None

    out = {"meta": {"sdk": SDK_URL, "sdkCommit": commit[0], "sdkDate": commit[1],
                    "gameVersion": GAME_VERSION, "license": "MIT (c) 2026 TmRxJD"},
           "workshop": workshop, "labs": labs, "enhancements": enhancements, "gems": GEMS,
           "uw": uws, "uwUnlockStones": UW_UNLOCK,
           "enemy": growth, "anchors": anchors,
           "xcheck": xcheck}
    os.makedirs(os.path.join(HERE, "..", "data"), exist_ok=True)
    with open(os.path.join(HERE, "..", "data", "tower_data.json"), "w") as f:
        json.dump(out, f)
    print(f"workshop {len(workshop)} upgrades, {sum(len(w['levels']) for w in workshop)} level rows")
    print(f"labs {len(labs)} researches, {sum(len(l['levels']) for l in labs)} level rows")
    print("anchors", anchors)


if __name__ == "__main__":
    main(sys.argv[1])

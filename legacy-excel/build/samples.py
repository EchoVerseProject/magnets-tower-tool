"""HYPOTHETICAL sample profiles for testing and demonstration.

These are invented account states, NOT real players. Every sample is labelled
"HYPOTHETICAL SAMPLE" so the Dashboard shows a banner while one is loaded.
They produce Import-sheet rows (key, value) in the same format as
tools/tower_export_to_csv.py.
"""

PROFILES = {
    "early": {
        "label": "HYPOTHETICAL SAMPLE - Early game",
        "P": {"pCoins": 2.5e6, "pCPH": 4.0e5, "pGems": 600, "pGemsDay": 60, "pFarmTier": 3, "pFarmWave": 900,
              "pFarmEnd": "Tower dies", "pFarmEvid": "Enemies pile up at the tower", "pKillShare": 0.9,
              "pTourWave": 250, "pTourEvid": "Not sure", "pMileTier": 4, "pMileTarget": 500,
              "pSlots": 2, "pBusy": 2, "pStones": 120, "pStonesDay": 8},
        "ws": {"Damage": 260, "Attack Speed": 40, "Critical Chance": 35, "Critical Factor": 40, "Range": 20,
               "Damage / Meter": 15, "Multishot Chance": 10, "Multishot Targets": 1, "Health": 280, "Health Regen": 120,
               "Defense Percent": 25, "Defense Absolute": 60, "Cash Bonus": 40, "Cash / Wave": 40,
               "Coins / Kill Bonus": 40, "Coins / Wave": 30},
        "unlocked_groups": [("Attack", 0), ("Attack", 1), ("Defense", 0), ("Utility", 0), ("Utility", 1)],
        "labs": {"damage": 12, "attack_speed": 8, "critical_factor": 6, "health": 12, "defense_absolute": 5,
                 "coins_kill_bonus": 10, "coins_per_wave": 5, "labs_speed": 6, "workshop_attack_discount": 4,
                 "workshop_defense_discount": 4, "workshop_utility_discount": 2, "game_speed": 2, "range": 4,
                 "damage_meter": 3, "labs_coin_discount": 3, "defense": 3},
        "tw": {1: 1600, 2: 1200, 3: 900, 4: 420},
        "slots": [("health", 30), ("damage", 12)],
        "uw": {"golden_tower": [2, 3, 1]},
    },
    "mid": {
        "label": "HYPOTHETICAL SAMPLE - Mid game",
        "P": {"pCoins": 3.2e11, "pCPH": 2.4e10, "pGems": 2600, "pGemsDay": 90, "pFarmTier": 10, "pFarmWave": 3200,
              "pFarmEnd": "Tower dies", "pFarmEvid": "Tower takes big hits with few enemies near", "pKillShare": 0.95,
              "pTourWave": 1100, "pTourEvid": "Enemies pile up at the tower", "pMileTier": 11, "pMileTarget": 2500,
              "pSlots": 4, "pBusy": 3, "pStones": 900, "pStonesDay": 25, "pBHs": 0.15, "pHorizon": 30},
        "ws": {"Damage": 2400, "Attack Speed": 99, "Critical Chance": 79, "Critical Factor": 130, "Range": 70,
               "Damage / Meter": 150, "Multishot Chance": 99, "Multishot Targets": 7, "Rapid Fire Chance": 85,
               "Rapid Fire Duration": 99, "Bounce Shot Chance": 85, "Bounce Shot Targets": 7, "Bounce Shot Range": 40,
               "Super Crit Chance": 60, "Super Crit Mult": 70, "Health": 2600, "Health Regen": 2000,
               "Defense Percent": 99, "Defense Absolute": 1800, "Thorns": 99, "Lifesteal": 80, "Knockback Chance": 80,
               "Knockback Force": 40, "Orb Speed": 38, "Orbs": 4, "Shockwave Size": 35, "Shockwave Frequency": 40,
               "Land Mine Chance": 50, "Land Mine Damage": 120, "Land Mine Radius": 30, "Death Defy": 60,
               "Wall Health": 300, "Wall Rebuild": 120, "Cash Bonus": 149, "Cash / Wave": 149,
               "Coins / Kill Bonus": 149, "Coins / Wave": 149, "Free Attack Upgrade": 99, "Free Defense Upgrade": 99,
               "Free Utility Upgrade": 99, "Interest / Wave": 99, "Recovery Amount": 150, "Max Recovery": 200,
               "Package Chance": 60},
        "unlocked_groups": [("Attack", g) for g in range(5)] + [("Defense", g) for g in range(9)] +
                           [("Utility", g) for g in range(5)],
        "labs": {"damage": 70, "attack_speed": 60, "critical_factor": 55, "health": 70, "health_regen": 60,
                 "defense_absolute": 60, "defense": 30, "coins_kill_bonus": 70, "coins_per_wave": 40, "labs_speed": 60,
                 "labs_coin_discount": 50, "workshop_attack_discount": 60, "workshop_defense_discount": 60,
                 "workshop_utility_discount": 50, "game_speed": 5, "range": 40, "damage_meter": 40,
                 "super_crit_chance": 20, "super_crit_multi": 15, "wall_health": 20, "recovery_package_max": 10,
                 "golden_tower_bonus": 10, "black_hole_coin_bonus": 8, "golden_tower_duration": 10,
                 "death_wave_coin_bonus": 5, "unlock_perks": 1, "standard_perks_bonus": 10},
        "tw": {t: w for t, w in zip(range(1, 12), [4500, 4500, 4500, 4500, 4000, 3600, 3400, 3200, 3000, 3200, 1800])},
        "slots": [("damage", 80), ("health", 60), ("labs_speed", 120)],
        "uw": {"golden_tower": [10, 12, 10], "black_hole": [8, 10, 9], "death_wave": [6, 2, 4],
               "chain_lightning": [10, 2, 6]},
        "choices": ["Smart Missiles", "Spotlight", "Chrono Field"],
    },
    "advanced": {
        "label": "HYPOTHETICAL SAMPLE - Advanced",
        "P": {"pCoins": 4.0e16, "pCPH": 1.2e15, "pGems": 9000, "pGemsDay": 120, "pFarmTier": 18, "pFarmWave": 5200,
              "pFarmEnd": "I end the run", "pFarmEvid": "Not sure", "pKillShare": 0.97,
              "pTourWave": 2600, "pTourEvid": "Tower takes big hits with few enemies near", "pMileTier": 20,
              "pMileTarget": 3000, "pSlots": 5, "pBusy": 5, "pStones": 4200, "pStonesDay": 60, "pBHs": 0.25,
              "pDWs": 0.2, "pHorizon": 60},
        "ws": {"Damage": 5200, "Attack Speed": 99, "Critical Chance": 79, "Critical Factor": 150, "Range": 79,
               "Damage / Meter": 199, "Multishot Chance": 99, "Multishot Targets": 7, "Rapid Fire Chance": 85,
               "Rapid Fire Duration": 99, "Bounce Shot Chance": 85, "Bounce Shot Targets": 7, "Bounce Shot Range": 60,
               "Super Crit Chance": 100, "Super Crit Mult": 115, "Rend Armor Chance": 200, "Rend Armor Mult": 180,
               "Health": 5400, "Health Regen": 5000, "Defense Percent": 99, "Defense Absolute": 4300, "Thorns": 99,
               "Lifesteal": 80, "Knockback Chance": 80, "Knockback Force": 40, "Orb Speed": 38, "Orbs": 4,
               "Shockwave Size": 35, "Shockwave Frequency": 40, "Land Mine Chance": 50, "Land Mine Damage": 200,
               "Land Mine Radius": 50, "Death Defy": 75, "Wall Health": 1200, "Wall Rebuild": 300, "Cash Bonus": 149,
               "Cash / Wave": 149, "Coins / Kill Bonus": 149, "Coins / Wave": 149, "Free Attack Upgrade": 99,
               "Free Defense Upgrade": 99, "Free Utility Upgrade": 99, "Interest / Wave": 99, "Recovery Amount": 300,
               "Max Recovery": 500, "Package Chance": 60, "Enemy Attack Level Skip": 300, "Enemy Health Level Skip": 300},
        "unlocked_groups": [("Attack", g) for g in range(6)] + [("Defense", g) for g in range(9)] +
                           [("Utility", g) for g in range(6)],
        "enh": {"Damage": 60, "Attack Speed": 20, "Critical Factor": 30, "Health": 70, "Defense Absolute": 40,
                "Coin Bonus": 25, "Wall Health": 20},
        "labs": {"damage": 100, "attack_speed": 99, "critical_factor": 99, "health": 100, "health_regen": 100,
                 "defense_absolute": 100, "defense": 50, "coins_kill_bonus": 99, "coins_per_wave": 99, "labs_speed": 99,
                 "labs_coin_discount": 99, "workshop_attack_discount": 99, "workshop_defense_discount": 99,
                 "workshop_utility_discount": 99, "game_speed": 7, "range": 80, "damage_meter": 99,
                 "super_crit_chance": 50, "super_crit_multi": 40, "wall_health": 50, "recovery_package_max": 20,
                 "golden_tower_bonus": 25, "black_hole_coin_bonus": 20, "death_wave_coin_bonus": 20,
                 "golden_tower_duration": 20, "spotlight_coin_bonus": 15, "workshop_enhancements": 1,
                 "enhancement_attack_coin_discount": 40, "enhancement_defense_coin_discount": 40,
                 "enhancement_utility_coin_discount": 30},
        "tw": {t: 4500 if t < 15 else w for t, w in zip(range(1, 21), [4500] * 14 + [4500, 4200, 4000, 5200, 3600, 2400])},
        "slots": [("damage_mastery", 300), ("assist_module_bonus_cannon", 900), ("battle_condition_reduction", 400),
                  ("dissonant_echo_attack", 700), ("primary_module_bonus_core", 2000)],
        "uw": {k: v for k, v in [("golden_tower", [18, 30, 18]), ("black_hole", [15, 20, 10]),
                                 ("death_wave", [25, 4, 23]), ("chain_lightning", [28, 4, 15]),
                                 ("smart_missiles", [25, 12, 14]), ("chrono_field", [30, 10, 12]),
                                 ("inner_land_mines", [25, 3, 12]), ("poison_swamp", [20, 10, 12]),
                                 ("spotlight", [25, 40, 3])]},
    },
}


def build(which, D):
    p = PROFILES[which]
    rows = [("META|label", p["label"])]
    for k, v in p["P"].items():
        rows.append((f"P|{k}", v))
    for i, ch in enumerate(p.get("choices", []), start=1):
        rows.append((f"P|pUWChoice{i}", ch))
    by_key = {w["key"]: w for w in D["workshop"]}
    for w in D["workshop"]:
        rows.append((f"WS|{w['id']}", p["ws"].get(w["key"], 0)))
    from build_data import UNLOCK_GROUPS
    for cat, g in p["unlocked_groups"]:
        for key in UNLOCK_GROUPS[cat][g]:
            rows.append((f"WSU|{by_key[key]['id']}", 1))
    for e in D["enhancements"]:
        rows.append((f"EN|{e['id']}", p.get("enh", {}).get(e["label"], 0)))
    for lab in D["labs"]:
        rows.append((f"LAB|{lab['id']}", min(lab["maxLevel"], p["labs"].get(lab["id"], 0))))
    for t, w in p["tw"].items():
        rows.append((f"TW|{t}", w))
    for i, (lab, hrs) in enumerate(p.get("slots", []), start=1):
        rows.append((f"SLOT|{i}|lab", lab))
        rows.append((f"SLOT|{i}|hours", hrs))
    for k, lv in p.get("uw", {}).items():
        idx = D["uw"][k]["exportIndex"]
        rows.append((f"UWU|{idx}", 1))
        for j, v in enumerate(lv):
            rows.append((f"UWL|{idx * 3 + j}", v))
    return rows


def choices(which):
    return PROFILES[which].get("choices", [])

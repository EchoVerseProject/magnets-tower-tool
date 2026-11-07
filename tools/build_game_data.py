"""Bundle the verified dataset into data/game.json for the web app.

    python3 tools/build_game_data.py <tower_data.json> <TheTowerSDK checkout>

tower_data.json comes from tools/legacy-excel/build/build_data.py (verified, cross-checked
dataset). Cards are read as text from the SDK (MIT, TmRxJD). No SDK code is executed.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "game.json")

# Cards whose effect the engine models (others are shown for judgment).
CARD_MODEL = {
    "dmg": ("damage", "x tower damage"),
    "as": ("attackSpeed", "x attack speed"),
    "hp": ("health", "x tower health"),
    "range": ("range", "x range"),
    "coins": ("coins", "x coins"),
    "crit-chance": ("critChance", "+ critical chance (percentage points)"),
    "def": ("defense", "+ defense % (percentage points)"),
}


def parse_cards(sdk):
    src = open(os.path.join(sdk, "src/data/cards/data.ts"), encoding="utf-8").read()
    body = src[src.index("const cardTemplates"):]
    cards = []
    for m in re.finditer(r"\{\s*id: '([^']+)',\s*name: '([^']+)',\s*description: '((?:[^'\\]|\\.)*)',\s*rarity: '(\w+)',"
                         r"\s*levelType: '(\w+)',", body):
        cid, nm, desc, rar, lt = m.groups()
        vm = re.search(r"levelValues: \[([^\]]*)\]", body[m.end():m.end() + 800])
        vals = vm.group(1) if vm else ""
        cards.append({"id": cid, "name": nm, "desc": desc.replace("\\'", "'"), "rarity": rar, "levelType": lt,
                      "values": [float(x) for x in vals.split(",") if x.strip()]})
    order = json.load(open(os.path.join(sdk, "fixtures/data/save-format/cards_save_format.json")))["cardOrder"]
    idx = {v: int(k) for k, v in order.items() if v}
    norm = lambda s: re.sub(r"[^a-z]", "", s.lower())  # noqa: E731
    by_norm = {norm(k): v for k, v in idx.items()}
    benefits = {norm(c["cardId"]): c["levelValues"]
                for c in json.load(open(os.path.join(sdk, "facts/v29.0.0/card-benefits.json")))["cards"]}
    for c in cards:
        c["saveIndex"] = by_norm.get(norm(c["name"]))
        gv = benefits.get(norm(c["name"])) or benefits.get(norm(c["name"]) + "s")
        if gv:  # game v29 values take precedence over the template list
            c["values"] = [round(x, 4) for x in gv]
            c["valueSource"] = "facts/v29.0.0/card-benefits.json (game)"
        else:
            c["valueSource"] = "src/data/cards/data.ts"
        if c["id"] in CARD_MODEL:
            c["model"], c["effect"] = CARD_MODEL[c["id"]]
    return cards


def main(tower_data, sdk):
    D = json.load(open(tower_data))
    cards = parse_cards(sdk)
    assert len(cards) >= 30, len(cards)
    killed_by = ["Basic", "Fast", "Tank", "Boss", "Ranged", "Protector", "Vampire", "Scatter", "Scatter", "Ray",
                 "Saboteur", "Commander", "Overcharge"]
    game = {k: D[k] for k in ("meta", "workshop", "labs", "enhancements", "gems", "uw", "uwUnlockStones", "enemy",
                              "anchors")}
    game["cards"] = cards
    game["cardStarGems"] = D["gems"]["cardStarGems"]["value"]
    game["cardCopiesPerLevel"] = [0, 1, 2, 5, 8, 12, 20, 32]  # copies to reach star N (SDK CARD_COPIES_PER_STAR)
    game["killedBy"] = killed_by
    game["xcheck"] = {"labs": {k: D["xcheck"][k] for k in ("tot", "cbad", "dbad")},
                      "workshopLevels": sum(v[0] for v in D["xcheck"]["workshop"].values())}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    s = json.dumps(game, separators=(",", ":"))
    open(OUT, "w").write(s)
    print(f"wrote {OUT}: {len(s) / 1e6:.2f} MB, {len(cards)} cards "
          f"({sum(1 for c in cards if 'model' in c)} modeled)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])

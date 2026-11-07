# magnet's Tower Tool

An Excel 365 optimizer for **The Tower – Idle Tower Defense** (Tech Tree Games). Enter or import your
account, pick a goal, and it tells you which Workshop upgrades to buy, which Labs to research, what to
save for, how to spend gems and Power Stones, and a sequential 20-step plan.

| File | What it is |
|---|---|
| `magnet's Tower Tool.xlsx` | **The tool.** Clean, ready for your data. |
| `magnet's Tower Tool - DEMO (hypothetical mid-game).xlsx` | Same workbook with an invented mid-game profile loaded, so you can see it working. Not a real account. |
| `tools/tower_export_to_csv.py` | Converts the game's official `tool_export.json` into rows for the Import sheet. |
| `samples/HYPOTHETICAL_*_profile_import.csv` | Invented early / mid / advanced profiles for testing. |
| `RESEARCH_REPORT.md` | Sources, verified formulas, discrepancies, what could not be modeled. |
| `VALIDATION.md` | What was tested and how; what remains approximate. |
| `build/` | Scripts that regenerate the data and the workbook after a game patch. |

No macros, add-ins, accounts or internet connection are needed to use the workbook.

---

## 1. Enter your account

**Option A — import (recommended).**

1. In the game, tap your **Player ID five times**, then go to **Settings → Toggles → External Tools Export →
   Manual Export**. (Turn on *Auto Export* to keep it current.) On Android the file is at
   `Android/data/com.TechTreeGames.TheTower/files/tool_export.json`.
2. Copy the file to your computer and run (Python 3, nothing to install):

   ```bash
   python3 tools/tower_export_to_csv.py tool_export.json
   ```

3. Open the `tool_export_import.csv` it writes, select columns A and B, copy, and paste into
   **Import!A6** in the workbook.

The export fills Workshop levels and unlocks, Enhancements, Lab levels, the labs currently researching,
highest wave per tier, current tier, coins per hour (averaged over your Battle History) and Ultimate Weapons.
It runs entirely on your computer; nothing is uploaded.

**Still enter by hand on Player Profile** (the export does not contain them): available coins, gems and
stones, hours left on each researching lab, your run evidence (below), card/module/relic modifiers, and the
three weapons the game is currently offering.

**Option B — manual.** Type into the cyan-bordered cells on **Player Profile**. A value you type always
overrides an imported one. Leave anything you don't know **blank** — the tool never fills in guesses
silently; it either excludes the item or flags the assumption.

### Run evidence (important)

The tool detects your bottleneck from what you tell it about real runs, not from your upgrade levels:

* **How do farming runs end?** *Tower dies* → extra survival/damage means longer runs and more coins.
  *I end the run* → only coin-income upgrades help per hour.
* **What limits you at the end of a run?** *Enemies pile up at the tower* → damage-limited.
  *Tower takes big hits with few enemies near* → survival-limited. *Not sure* → both weighted equally and
  those picks are marked **Low** confidence.
* Same question for tournaments and milestone pushes, plus your typical waves and lab slots.

## 2. Choose a strategy

Dashboard cell **L2**: **Farming**, **Tournament**, **Milestones** or **Balanced**. A strategy is a *goal*,
not an upgrade category — every Workshop upgrade, Enhancement and Lab is scored on how much it moves that goal:

| Strategy | Measured outcome |
|---|---|
| Farming | % more coins: coin multipliers, game speed, UW coin labs — plus extra waves when your farming runs end by death |
| Tournament | Extra tournament waves (damage and survivability, converted with tournament enemy scaling) |
| Milestones | Extra waves on your milestone tier |
| Balanced | Long-term growth: coin income + purchasing power (discount labs) + research speed (when research is time-limited) + milestone progress |

So Farming *can* recommend Damage or Health — and the Dashboard says why when it does.

## 3. Read the recommendations

* **BUY NOW** — best affordable Workshop upgrades/Enhancements by value per coin.
* **RESEARCH NEXT** — best labs by value per *resource-day* (coin cost converted to days of income + slot
  time), so long research is not penalised when its payoff justifies it. `▶ START` marks labs for idle slots.
* **SAVE FOR** — uses an exact sequencing rule: buying a cheaper item first is only right if
  `V_A × (C_A + C_B − coins) > V_B × C_A`.
* **BOTTLENECKS** — damage, survivability, economy and research status from your evidence.
* **Roadmap** — the next 20 investments, re-optimized after each simulated purchase/research. Workshop
  steps bundle levels (up to one day of income, or until the runner-up becomes better). Labs respect slot
  capacity and finish-before-next-level. Power Stones have their own track and budget.
* **Gem Planner** — lab slots and lab rushes valued as outcome × days within your horizon; cards, card slots
  and module pulls listed with prices for judgment.
* **UW Optimizer** — ranks the three weapons the game offered, compares buying vs upgrading, ranks stone
  upgrades, and evaluates Golden Tower / Black Hole / Death Wave cooldown sync (flagging upgrades that would
  break a sync).

**Confidence:** *High* = verified costs + modeled effect + your evidence. *Medium* = uses an estimated input
(e.g. default range share). *Low* = depends on a bottleneck you have not confirmed. *Judgment* = not computed;
shown with the reason.

## 4. After buying or researching

Update the level on Player Profile (or re-export and re-paste the Import rows). Update coins, gems and
stones when you check in. Everything recalculates instantly.

To try a sample, paste a `samples/HYPOTHETICAL_*` CSV into Import!A6 (a banner will remind you it is not
real). To clear, delete Import!A6:B2005.

## 5. After a game patch

All game numbers live on **Game Data** and the **GD …** sheets (workshop/lab/enhancement/UW level tables,
enemy scaling, gem prices, constants). Nothing else hard-codes game values. Either:

* edit those sheets directly, or
* rebuild everything from an updated TheTowerSDK checkout:

  ```bash
  git clone https://github.com/TmRxJD/TheTowerSDK.git
  ```

  ```bash
  python3 build/build_data.py TheTowerSDK
  ```

  ```bash
  python3 build/cross_check.py TheTowerSDK
  ```

  ```bash
  python3 build/build_data.py TheTowerSDK
  ```

  ```bash
  python3 build/build_workbook.py "magnet's Tower Tool.xlsx" --sample none
  ```

Then open **Sources & Validation → Live formula checks** (all should say PASS) and re-run
`build/test_scenarios.py` if you have LibreOffice.

## Workbook map

| Sheet | Purpose |
|---|---|
| Dashboard | Strategy selector, BUY NOW, RESEARCH NEXT, SAVE FOR, bottlenecks, roadmap preview, gems/UW summary, navigation |
| Workshop Optimizer | All 48 upgrades + 18 enhancements ranked, costs (+1, +10, to max), buyable levels, time to afford |
| Lab Optimizer | All 234 labs ranked with cost, duration, gain per day, status |
| Roadmap | 20-step sequential plan + Power Stone track + chart |
| Gem Planner | Gem options with value per gem, savings and opportunity cost |
| UW Optimizer | New-weapon choice, stone upgrades, sync, stone track; audit table of scenarios on the right |
| Player Profile | All inputs (entry / imported / used) |
| Import | Paste area for the converter output |
| Optimization Engine | Evidence and settings, state table (your account + 20 roadmap states), every candidate's calculation |
| Roadmap Engine | The 20 sequential evaluation blocks and the funding / lab-slot timeline |
| Game Data, GD … | Verified data with source, version, date and validation status per item |
| Sources & Validation | Source register, build-time and live checks, discrepancies, limitations |
| Guide | Short in-workbook version of these instructions |

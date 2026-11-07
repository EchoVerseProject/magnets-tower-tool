# Validation Summary — magnet's Tower Tool

All profiles used in testing are **hypothetical** (invented account states), not real players.

## 1. Data checked against independent references (build time)

| Check | Compared | Mismatches | Result |
|---|---|---|---|
| Lab coin costs vs Effective Paths | 5,541 levels, 191 labs | 0 | PASS |
| Lab durations vs Effective Paths | 5,541 levels | 0 | PASS |
| Workshop values vs Effective Paths (Damage, Health, Regen, Def Abs, D/M, Lifesteal) | 23,286 levels | 0 beyond 3-s.f. rounding (max 0.48%) | PASS |
| Wall Health coin costs vs v29.1.3 game-binary replay | 1,801 levels | 0 | PASS |
| Ultimate Weapon stone costs and values vs Effective Paths | 739 levels | 0 cost / 0 value | PASS |
| Enemy scaling port vs in-game anchors (Tier 10) | wave 8 HP 510,798.9 (game 510.8K); wave 10 damage 77,293.8 (game 77.29K) | 0 | PASS |
| Export converter round trip (synthetic export built from the hypothetical mid profile) | 340 mappable fields | 0 | PASS |

## 2. Live checks inside the workbook

`Sources & Validation → Live formula checks` recompute in Excel: workshop cost lookup (Damage 0→1 = 30), value lookup (Damage L1 = 5.88), 49.5% discount, lab rush price (24 h = 163 gems, 7 d = 1,000), lab cost lookup, bullets/second table, real game-speed table, UW unlock ladder, UW cooldown ladder, strategy switch. All PASS in every scenario below.

## 3. Recalculation

Both delivered workbooks were fully recalculated in LibreOffice: **102,495 formulas, 0 errors**. Every formula is under Excel's 8,192-character limit; only Excel-2007-era functions plus `HYPERLINK` are used (no dynamic arrays, no LET/LAMBDA, no VBA). Data validations, conditional formats, names and the chart survive the recalculation pass (validation coverage compared cell by cell: 449/449).

## 4. Scenario tests (hypothetical profiles)

`build/test_scenarios.py` builds each profile, applies the scenario edits, recalculates and reads the Dashboard and Roadmap.

| Scenario | Errors | Top BUY NOW | Top RESEARCH NEXT | First roadmap steps | What it shows |
|---|---|---|---|---|---|
| blank | 0 | Waiting for Workshop levels | Waiting for profile data | — | Blank profile cannot produce recommendations: everything waits for data |
| early-farming | 0 | Multishot Targets | Game Speed | Multishot Targets, Multishot Chance, Multishot Targets | Damage-limited, runs end by death → cheap damage stats beat economy |
| early-tournament | 0 | Multishot Targets | Critical Factor | Multishot Targets, Multishot Chance, Multishot Targets | Same buys (damage-limited in both), different labs (Crit Factor, D/M) |
| early-milestones | 0 | Multishot Targets | Critical Factor | Multishot Targets, Multishot Chance, Multishot Targets |  |
| early-balanced | 0 | Multishot Targets | Game Speed | Multishot Targets, Multishot Chance, Multishot Targets |  |
| mid-farming | 0 | Health | Black Hole Coin Bonus | Health, Health, Black Hole Coin Bonus | Survival-limited farming → Health / Max Recovery; econ labs for research |
| mid-tournament | 0 | Range | Damage / Meter | Range, Damage, Critical Factor | Tournament evidence = damage-limited → Range, Damage, Crit Factor |
| mid-milestones | 0 | Health | Wall Health | Health, Health, Health | Milestone evidence defaults to farming (survival) → Health, Wall labs |
| mid-balanced | 0 | Health | Black Hole Coin Bonus | Health, Health, Health | Adds purchasing power and research speed to the outcome |
| adv-farming | 0 | Coin Bonus +  ✦ | No modeled lab gain for this goal (see Lab Optimizer) | Coin Bonus +, Coin Bonus +, Coin Bonus + | Runs end by choice → only coin income counts; Coin Bonus enhancement |
| adv-tournament | 0 | Health | No modeled lab gain for this goal (see Lab Optimizer) | Health, Wall Health +, Health | Survival-limited tournaments → Health, Wall Health enhancement |
| adv-milestones | 0 | Health | No modeled lab gain for this goal (see Lab Optimizer) | Health, Damage, Health |  |
| adv-balanced | 0 | Health | No modeled lab gain for this goal (see Lab Optimizer) | Health, Damage, Health |  |
| mid-no-coins | 0 | Nothing affordable has a modeled gain for this goal | Black Hole Coin Bonus | Health, Health, Black Hole Coin Bonus | Insufficient coins: BUY NOW empty, SAVE FOR names the target |
| mid-slots-full-balanced | 0 | Health | Black Hole Coin Bonus | Health, Health, Health | Research status switches to time-limited |
| mid-unknown-bottleneck | 0 | Range | Black Hole Coin Bonus | Range, Health, Damage | Mixed damage/health picks, all marked Low confidence |
| mid-farm-time-limited | 0 | Nothing affordable has a modeled gain for this goal | Black Hole Coin Bonus | Black Hole Coin Bonus, Black Hole Coin Bonus, Game Speed | Survival no longer counts for Farming: only labs with coin effects remain |
| mid-tournament-no-wave | 0 | Enter your typical tournament wave on Player Profile. | Enter your typical tournament wave on Player Profile. | — | Missing strategy data → explicit 'enter your tournament wave' message |
| mid-no-income | 0 | Health | Black Hole Coin Bonus | — | Roadmap and lab cost-pricing withheld until coins/hour is entered |

Strategy switching re-ranks the same profile (e.g. mid-game: Farming → Health; Tournament → Range/Damage), and the roadmap regenerates. Maxed upgrades show *Maxed*, locked groups *Locked*, labs already researching are excluded, and idle lab slots are flagged `▶ START`.

## 5. Visual check

Dashboard, optimizer, roadmap, gem, UW and profile sheets were rendered to images and inspected; clipping, link styling, chart visibility, column widths and a comma inside a dropdown option (which Excel would split) were found and fixed. The Dashboard fits one 1920×1080 screen at 100% zoom and prints on one landscape page.

## 6. What remains approximate

* Damage/health → waves uses a first-order conversion at your current wave (large jumps are capped by bundling roadmap steps at one day of income).
* Farming survival value assumes each extra wave yields at least an average wave's coins.
* Rapid fire ignores the frame-rate cap; multishot/bounce assume targets are available.
* UW cooldown sync is simplified to 'equal cooldowns = aligned'.
* Tournament scaling excludes league battle conditions.
* Defaults when blank (all flagged in the workbook): kill share 100%, damage at range 25%, gem horizon 30 days.
* Not tested in desktop Excel itself (not available in the build environment); formulas were restricted to functions with identical behaviour in Excel 365 and LibreOffice.

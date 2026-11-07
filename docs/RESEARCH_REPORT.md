# Research & Source Report — magnet's Tower Tool

Verified on 2026-11-07 against game version **v29** (SDK data: v29.0.0 facts, v29.1.x checks).

## 1. Sources and how much weight each carries

| Source | Role | Notes |
|---|---|---|
| [TheTowerSDK](https://github.com/TmRxJD/TheTowerSDK) (TmRxJD, MIT), commit `9a95672`, 2026-11-05 | **Primary dataset** | Workshop table described as the game's own `workshop.json`; lab catalog; enhancement cost ladders; UW stone ladders; export save-format documentation; empirical enemy scaling; gem prices. Read as text/JSON — no SDK code was executed. |
| Effective Paths community spreadsheet (snapshot fixtures inside the SDK) | **Independent cross-check + formulas** | Lab costs/times, workshop values, UW ladders compared row by row. Source of the eDamage / eHP / economy composition formulas. |
| v29.1.3 game-binary cost replay (SDK fixture) | **Independent cross-check** | Wall Health coin costs computed by the game's native code. |
| Save-format enums (contributed by "Bisse", in the SDK) | Primary for import mapping | Index order of every export array. |
| Official patch notes (archived in the SDK) | Context | Checked for changes to labs, modules, UW ladders, gem rewards up to v29. |
| The Tower wiki, thetower.tools, tower-hub.com | Not reachable from the build environment | The SDK records the wiki-derived values it uses with their check dates (e.g. lab slot gem prices, card costs). Worth re-checking after patches. |

Community strategy opinion was **not** treated as game math. Where the tool uses judgment (e.g. which
combat Ultimate Weapon suits a damage bottleneck) it is labelled *Judgment* in the workbook.

## 2. What is in the dataset

| System | Coverage | Status |
|---|---|---|
| Workshop upgrades | All 48, every level (31,155 rows): value, coin cost, max level, export index, unlock group | Verified |
| Workshop Enhancements | All 18 cost ladders, export index, discount labs | Verified (costs) |
| Laboratory | 234 researches, every level (6,368 rows): cost, duration, effect, max, unlock tier/wave, export index | Verified (costs/times); 5 labs have no effect data; 29 have no unlock requirement in the source (marked Unknown unless available from the start) |
| Ultimate Weapons | 9 weapons × 3 stone stats + UW+ stat, every level; unlock ladder 5/50/150/300/800/1,250/1,750/2,400/3,000 stones | Verified |
| Gems | Lab slots 0/100/400/1,400/3,000; card 20; card stars 20…640; module pull 20 (2.5% epic); lab rush price formula | Verified (module pity 150 is unverified in the SDK) |
| Enemy scaling | Per-wave growth of enemy health and damage, tiers 1–24, waves 50–20,000, campaign and tournament | Derived (port of the SDK's empirical model) |

Every item carries ID, name, category, currency, max level, data location, formula/effect, game version,
source, verification date and validation status on the **Game Data** sheet.

## 3. Formulas used (and where they come from)

* **Workshop cost** = table cost × (1 − min(49.5%, 0.5% × discount-lab level) − vault discount), rounded.
  Row *L* buys level *L+1*.
* **Lab cost** = table cost × (1 − 0.3% × Labs Coin Discount level).
  **Lab time** = table time ÷ ((1 + 2% × Labs Speed level) × (1 + relic) × boost).
* **Enhancement cost** = table cost × (1 − min(30%, 0.3% × category discount lab) − vault). Effect: +1% of the stat per level.
* **eDamage** (Effective Paths): damage × bullets/second × rapid fire × crit × multishot × bounce × range damage.
  Crit = (1−CC) + CC·CF·(1−SCC) + CC·CF·SCC·SCM. Bullets/second and rapid-fire uptime use the sheet's firing tables.
* **eHP** (Effective Paths): (Health × max(Wall + Max Recovery, 1) + Defense Absolute) ÷ (1 − Defense %), Defense % capped at 98%.
* **Coin income**: share-weighted Coins/Kill × Coins/Wave multipliers; Golden Tower 1 + uptime × (multiplier − 1);
  Black Hole and Death Wave coin labs weighted by your share of affected kills; real game speed table.
* **Damage/health → waves**: extra waves = ln(1 + gain) ÷ enemy growth per wave at your wave and tier
  (enemy health growth for damage gains, enemy damage growth for health gains), weighted by your bottleneck evidence.
* **Lab rush gems**: the game's piecewise time-to-gems curve (e.g. 1 day = 163 gems, 7 days = 1,000).
* **UW sync**: when Golden Tower and Black Hole (or Death Wave) cooldowns are equal, affected kills receive both multipliers.

## 4. Discrepancies found

| Item | Disagreement | Handling |
|---|---|---|
| Damage enhancement max | Cost table has 600 levels; SDK notes say 400 | Cost table used; flagged |
| Swamp Rend – Additional Enemies | Catalog 9 levels vs research index 11 | Catalog used; flagged |
| Card slot prices | Only the 22-slot total (58,400) is in a reachable source | User enters the in-game price |
| Coins / Kill and Cash Bonus workshop values | Effective Paths sheet diverges from the game table | Game table used |
| Wiki claims (thorns protector penalty, perk wave rule, module slot level) | SDK documents game-observed values overriding the wiki | Not used in calculations |

## 5. What could not be modeled reliably

These appear in the optimizers with their costs and a reason, but receive **no invented score**:

* Health Regen, Thorns, Lifesteal, Orbs, Shockwave, Land Mines, Knockback, Death Defy, Wall Rebuild, Rend Armor,
  Enemy Level Skip, in-run cash stats (Cash Bonus, Interest, Free Upgrades).
* Combat value of Ultimate Weapons (Chain Lightning, Smart Missiles, Inner Land Mines, Poison Swamp, Chrono Field,
  Spotlight, Death Wave damage, Black Hole size).
* Card, card-mastery, module, bot, perk, enemy-type and battle-condition labs (value depends on what you own and
  your enemy mix / league conditions).
* Cells per hour (shown, not optimized), tournament battle conditions, prices to unlock locked Workshop groups.

## 6. Player data import

The official **External Tools Export** (`tool_export.json`, plain JSON) contains Workshop/Enhancement levels and
unlock flags (5 presets, packed), lab levels and the active research queue, highest wave per tier, current tier,
battle history (coins and real time per run), and Ultimate Weapon ownership and levels. It does **not** contain
current coins, gems or stones balances, lab time remaining, or anything about how your runs end. The converter maps
the documented fields; the rest is entered by hand.

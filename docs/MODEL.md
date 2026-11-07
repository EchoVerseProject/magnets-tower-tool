# The model

All code is in `js/engine.js`. It is a port of the verified Excel engine (`legacy-excel/`), and
`tests/engine.test.mjs` checks that the two agree.

## 1. State and stats

A *state* is the level of each modeled variable: 21 Workshop upgrades, 10 Enhancements and 24 Labs.
`stats(state)` computes:

| Outcome | Formula |
|---|---|
| eDamage | damage × bullets/s × rapid fire × crit × multishot × bounce × range damage |
| eHP | (health × max(wall + max recovery, 1) + defense absolute) ÷ (1 − defense %) |
| Coin income | share-weighted coins/kill and coins/wave multipliers |
| UW coins | Golden Tower uptime × multiplier, Black Hole / Death Wave / Spotlight coin labs |
| Game speed | real game speed (displayed speed × the game's scaling table) |
| Purchasing power | −ln(1 − discount), weighted by your share of past spending |
| Research speed | Labs Speed multiplier |

Crit = (1−CC) + CC·CF·(1−SCC) + CC·CF·SCC·SCM. The rapid-fire uptime and bullets/second tables come
from the Effective Paths model. Equipped Damage, Attack Speed, Health, Range, Coins, Critical Chance
and Extra Defense cards are applied from your export.

## 2. Turning stat changes into a goal

For a candidate (one more level), the engine recomputes the state and takes the differences in the
logarithms of the outcomes:

* Extra waves = w·Δln(eDamage) ÷ g_HP + (1−w)·Δln(eHP) ÷ g_DMG. Here g is the per-wave growth of enemy
  health / damage at your wave and tier, and w is 1 (damage-limited), 0 (survival-limited) or 0.5
  (not sure) from your run evidence.
* **Farming:** coin income + UW coins + game speed, plus (if your runs end by death) extra waves ÷ your
  wave, i.e. more coins per run.
* **Tournament:** extra tournament waves (tournament enemy scaling; league conditions not modeled).
* **Milestones:** extra waves on your milestone tier.
* **Balanced:** Farming + purchasing power + research speed (only when research is time-limited) +
  milestone waves ÷ milestone wave.

## 3. Ranking

* Workshop and Enhancements: outcome per coin.
* Labs: outcome per *resource-day*, where resource-days = cost ÷ coins per day + hours ÷ 24 ÷ lab slots.
* Save for: buy the cheaper affordable item A before saving for the best item B only if
  V_A·(C_A + C_B − coins) > V_B·C_A (Smith's sequencing rule with current coins).

## 4. Roadmap

Each of the 20 steps picks the best candidate from the current simulated state, applies it, and
repeats. Workshop and Enhancement steps bundle levels: they keep buying until the per-level cost
reaches the point where the runner-up wins, capped at one day of income. Labs go to the earliest free
slot and never run the same lab twice at once. Coins are spent in order at your measured coins/hour.

## 5. Gems, Ultimate Weapons, cards

* Gem options are valued as outcome × days enjoyed within your horizon. An extra lab slot counts only when
  research is time-limited. A rush counts the earlier benefit plus the freed slot. Rush prices use the
  game's curve.
* Ultimate Weapons: a coin model of Golden Tower, Black Hole and Death Wave, including cooldown sync.
  When cooldowns are equal, affected kills get both multipliers. Weapon choices are ranked by computed
  coin gain first, then by fit to your bottleneck (judgment).
* Cards: the value of each modeled card is the goal outcome of equipping it. Recommended cards fill your
  slots in order of value; remaining slots are your call.

## 6. Limits

See the Sources screen and `docs/RESEARCH_REPORT.md`. In short: regen, thorns, orbs, mines, death defy,
rend, level skips, in-run cash, most UW/card/module/bot/perk/enemy labs, the combat value of Ultimate
Weapons, modules and cells are not computed. The wave conversion is first-order.

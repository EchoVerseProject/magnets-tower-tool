# magnet's Tower Tool

A web app that tells you what to upgrade in **The Tower – Idle Tower Defense**. Drop in the game's
`tool_export.json` and pick a goal (Farming, Tournament, Milestones or Balanced). The app then ranks
every Workshop upgrade, Enhancement and Lab research, plans your next 20 investments, and helps with
gems, Ultimate Weapons, Power Stones and cards.

Everything runs in your browser. Your export is never uploaded anywhere.

## Using it

1. In the game, tap your **Player ID five times** (first time only), then open
   **Settings → Toggles → External Tools Export → Manual Export**. Turn on *Auto Export* to keep the file current.
2. Get `tool_export.json` onto the device you're using. On Android it is in
   `Android/data/com.TechTreeGames.TheTower/files/`.
3. Open the site and drop the file in (or use **Import**).
4. On **Profile → Run evidence**, answer how your runs end and what limits you. This tells the
   tool whether damage or survival is your bottleneck.
5. Pick a goal at the top. Every screen re-ranks immediately.

Import a newer export later. Your answers are kept, and **History** shows what changed and which
recommendations you acted on.

## Screens

| Screen | What it does |
|---|---|
| Dashboard | Buy now, research next, save for, bottlenecks, roadmap preview, gems/UW summary, changes since last import |
| Workshop | All 48 upgrades + 18 enhancements ranked by outcome per coin, with +10-level cost and how many you can buy now |
| Labs | All 234 labs ranked by outcome per resource-day (coins as days of income + slot time) |
| Roadmap | 20 sequential steps (state updated after each), funding times, lab-slot timing, Power Stone track |
| Gems | Lab slots and rushes valued as outcome × days within your horizon; cards and module pulls listed with their prices for your judgment |
| Ultimate Weapons | Ranks the 3 weapons the game offers you, compares buying vs upgrading, ranks stone upgrades, flags cooldown sync breaks |
| Cards & Modules | Best loadout of your owned cards for the goal (modeled cards computed, the rest marked judgment) |
| History | Waves and coins/hour per run, what killed the tower, imports over time |
| Profile | All inputs and levels, editable |
| Sources | Data provenance, model, limitations |

## How it decides

* A goal is an **outcome**, not an upgrade category. Farming measures % more coins, Tournament and
  Milestones measure extra waves, and Balanced combines income, discounts, research speed and progress.
* Damage and health gains are converted to **extra waves** with the game's enemy scaling:
  `waves = ln(1 + gain) / enemy growth per wave`, at your wave and tier.
* Your **bottleneck comes from your run evidence**, never from your levels. Answering "Not sure"
  weights both and marks those picks Low confidence.
* Confidence: **High** means verified costs, a modeled effect and your evidence. **Medium** means the pick
  uses an estimated input. **Low** means it depends on a bottleneck you haven't confirmed.
  **Judgment** means the effect isn't computed; it's listed with the reason.

Details: [docs/MODEL.md](docs/MODEL.md) · research & sources: [docs/RESEARCH_REPORT.md](docs/RESEARCH_REPORT.md).

## Accuracy

* Game data is from [TheTowerSDK](https://github.com/TmRxJD/TheTowerSDK) (MIT), game v29. It was cross-checked
  against the community Effective Paths reference, matching all 5,541 lab cost and time rows, 739 Ultimate
  Weapon rows and 23,286 Workshop values. Wall Health costs were also checked against the v29.1.3 game binary.
* The engine is checked in `tests/` against the original Excel engine (in `legacy-excel/`) in 9 scenarios.
  Every cost, research time, outcome and 20-step roadmap matches.

## Development

There is no build step: it's plain HTML, CSS and ES modules.

```bash
python3 -m http.server 8000
```

Then open http://localhost:8000. Run the tests (Node 20 or later, no dependencies):

```bash
node --test tests/*.test.mjs
```

After a game patch, rebuild the dataset from an updated SDK checkout:

```bash
python3 legacy-excel/build/build_data.py path/to/TheTowerSDK
```

```bash
python3 tools/build_game_data.py legacy-excel/data/tower_data.json path/to/TheTowerSDK
```

Pushing to `main` runs the tests and deploys to GitHub Pages (`.github/workflows/pages.yml`).

## Credits

Game data © Tech Tree Games, compiled by TheTowerSDK (MIT). Formulas follow the community Effective Paths
model. See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This is an unofficial fan tool, not affiliated with
Tech Tree Games.

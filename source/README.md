# source/

The real project behind the app. The deployed page is a single `index.html` at the repo
root, built from the files in here.

## Build

`index.html` is `wc2026_template.html` with the `/*DATA*/` token replaced by
`wc2026_results.json`.

```
python build_app.py          # rebuild ../index.html
python build_app.py --check  # verify ../index.html is in sync (CI runs this)
```

## What each file is

- `wc2026_template.html` - the app source. Edit this for any change to the page. One `/*DATA*/` token.
- `wc2026_results.json` - the 50,000-run simulation output the app renders, with the fixture schedule merged in.
- `wc2026_schedule.json` - the official 72-match group schedule (date, kickoff, home/away, venue), from the public openfootball dataset.
- `merge_schedule.py` - folds the schedule into the results JSON (dates, venues, official home/away). Idempotent, no re-simulation. Run after regenerating the engine output.
- `build_app.py` - the build step above.
- `check_app.js` - CI check: script blocks parse, five models present, build is clean.
- `wc2026_engine.py` - the simulation engine: all five models, market calibration, FIFA Annex C, knockout logic. `python wc2026_engine.py 50000` regenerates the results JSON.
- `model_params.json` - fitted Dixon-Coles parameters plus official Elo for all 48 teams.
- `annexc_data.py` - the official FIFA Annex C round-of-32 table (495 group-finish combinations).
- `fit_dc.py`, `build_params.py` - the fitting pipeline (needs `results.csv`, which is not shipped).
- `val_assess.py`, `val_market.py` - the validation tests (model accuracy, and model vs market).
- `REPORT.md` - the full write-up: the models, the validation, the honest caveats.
- `CLAUDE.md` - handoff doc with the model internals and the gotchas.

Start with [REPORT.md](REPORT.md) for the why, and [CLAUDE.md](CLAUDE.md) for the how.

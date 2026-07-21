# World Cup 2026 forecast, frozen final version

This is the site exactly as it stood live at the end of the tournament. It is kept here so
the root of the repo is free to be reused for another competition without losing the 2026 record.

`index.html` is fully self-contained (the forecast payload is injected into it), so it needs
nothing else to run. Open it directly in a browser.

## What it is

The 2026 World Cup played out 50,000 times, five ways, and shown game by game. The forecast opens
on Pure Market (the bookmakers' pre-tournament ratings, played forward). See `../../REPORT.md` for
the method and `../../source/CLAUDE.md` for the engine.

## Final standings (how the tournament actually finished)

1. Spain (beat Argentina 1-0 after extra time in the final)
2. Argentina
3. England (beat France 6-4 in the third-place play-off)
4. France

The Title Odds tab shows this top-four overview in place of the live title odds, with the
pre-tournament reach-round forecast kept below for the record.

## Files

- `index.html` - the deployed app, self-contained. The complete frozen site.
- `wc2026_results.json` - the live 50,000-run payload injected into the page (conditioned on every
  game played, schedule merged in, each played result embedded).
- `wc2026_baseline.json` - the frozen Day 0 (pre-tournament) snapshot the before/after view compares against.

## Reproducing it

The exact source (template, engine, fitted parameters, played results) lives in the repo at the
commit tagged for this release. From that commit: `python source/make_data.py 50000`, then
`python source/merge_schedule.py`, then `python source/build_app.py` regenerates `index.html`
bit for bit (the engine uses fixed seeds).

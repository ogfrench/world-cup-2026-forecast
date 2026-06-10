# World Cup 2026 Prediction Engine

Who actually wins the World Cup? This plays out all 104 matches and the full knockout bracket 50,000 times over, five different ways, from cold results to the betting market, and shows where they agree and disagree. It opens on the market's view, the smartest single guess.

It is one self-contained `index.html`. No build step, no dependencies, no server. Just static files.

## Put it online in two minutes

**Option A: GitHub, then Netlify (recommended, gives you a repo and auto-updates).**
1. Make a new repository on GitHub and upload everything in this folder (drag the files straight into the "Add file > Upload files" box, or push with git).
2. Go to [app.netlify.com](https://app.netlify.com), "Add new site" > "Import an existing project", and pick the repo.
3. Leave the build command empty and set the publish directory to `.` (a `netlify.toml` here already does this for you). Deploy.
4. You get a live URL. Every push updates it.

**Option B: fastest, no GitHub.**
Drag this whole folder onto [app.netlify.com/drop](https://app.netlify.com/drop). It is live in seconds. (You can claim and rename the site afterwards.)

Either way, Netlify serves `index.html` at the root, so the homepage is the app.

## What's in here

- `index.html` - the app. This is the whole thing.
- `netlify.toml` - tells Netlify to serve the folder as-is.
- `source/` - the full project behind it, so the repo is real and reproducible:
  - `wc2026_engine.py` - the simulation engine (all five models, calibration, the official FIFA bracket).
  - `wc2026_template.html` - the app's source, with a `/*DATA*/` slot where the results get injected.
  - `wc2026_results.json` - the 50,000-run output the app reads.
  - `model_params.json`, `annexc_data.py` - fitted parameters and the official round-of-32 table.
  - `fit_dc.py`, `build_params.py` - the fitting pipeline.
  - `val_assess.py`, `val_market.py` - the validation tests (model accuracy, and model vs market).
  - `REPORT.md`, `CLAUDE.md` - the write-up and a handoff doc.

## Rebuilding it (optional)

1. `python3 source/wc2026_engine.py 50000` regenerates `wc2026_results.json`.
2. Inject it into the template: replace the `/*DATA*/` token in `source/wc2026_template.html` with the contents of the JSON, and save that as `index.html`.

## The honest disclaimer

It is a transparent baseline built from public data, not an oracle, and it has never been tested on a real World Cup. Great for the shape of the tournament. Not betting advice.

made with love by François

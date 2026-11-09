# Product Passport: world-cup-2026-forecast

> Initial documentation-derived navigation map, 9 November 2026. **Not source-verified.** This file is not a release certificate. Inspect current executable source and tests before asserting behavior or changing implementation.

## Purpose
World Cup Monte Carlo forecast dashboard.

## Documented capability areas
- Compare tournament title and stage odds
- view match predictions and actual results
- switch between five forecasting models

## Candidate entry points
- `index.html`
- `model selector`

## Candidate source owners
- `source/wc2026_engine.py`
- `source/make_data.py`
- `source/REPORT.md`

## Technology described in repository documentation
Python; HTML.

## Verification and evidence
**Source inspection:** not completed for this seed map. **Execution:** no commands, real journeys, negative cases, deployment or host acceptance were run for this map. Start with `README.md`, `CLAUDE.md` where present, actual implementation and existing tests. Record concrete paths, commands, assertions, revision, environment and blocked/failed/not_run states here or in dedicated `features/<id>.md` entries as evidence accumulates.

## Required upkeep
When a capability, entry point, ownership boundary or integration changes, update this product map in the same PR after checking code and any executed tests. Do not claim a test passed merely because it is listed here. For recurring architecture faults invoke Architecture Gardener, without duplicating the Product Passport's behavioral scope. See `.claude/rules/product-passport.md`.

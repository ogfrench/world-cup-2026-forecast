# Product Passport: World Cup 2026 forecast

**Source review, 14 November 2026:** inspected the simulation entry point and pipeline test; located the app builder, live-result ingestion and GitHub workflows. This is a code navigation map, not a validation of any predicted result. No commands or browser journeys were run in this review.

## Capability ownership

| User outcome | Owning source | Relevant check |
| --- | --- | --- |
| Generate tournament forecasts across five models | `source/wc2026_engine.py`, `source/model_params.json` | Engine smoke path and Python tests in `source/test_pipeline.py`; account for optional NumPy test skips |
| Update played matches and forecast data | `source/fetch_actuals.py`, `source/make_data.py`, `source/merge_schedule.py`, `source/wc2026_actuals.json` | Feed parsing and played/unplayed regression cases in `source/test_pipeline.py` |
| Render the public prediction dashboard | `source/build_app.py`, `source/wc2026_template.html`, generated `index.html` | `python source/build_app.py --check`, `node source/test_app.js`, actual desktop/mobile browser review |
| Refresh automatically after new results | `.github/workflows/refresh.yml` | Check unchanged-feed no-op, latest-main race safety and eventual published update; a CI green result does not prove the refresh schedule fired |

## Engineering workflow

1. Change the source model or ingestion code, never hand-edit generated odds in `index.html`. Preserve the distinction between forecast probabilities and actual results.
2. During iteration use `python3 -m unittest discover -s source -p 'test_*.py'`; run `python source/build_app.py --check` and `node source/test_app.js` when touching generated markup, scripts, feeds or display.
3. Exercise both a played match and an unplayed/malformed feed record, including home/away orientation, group vs knockout allocation, and idempotent refresh where relevant. A test skipped due to unavailable dependencies is **not** a pass.
4. Review the real rendered dashboard for visual changes. Treat scheduled `refresh.yml` as a publishing workflow and do not replace its triggers or token privileges with PR-only validation to save minutes.
5. Record exact SHA, model inputs, fixture or feed date, command outputs and separately observed deployment/refresh evidence in the PR. Use **passed / failed / blocked / not_run**.

**Review status:** source pointers checked; functional execution, schedule, CI and production deploy **not_run**. See `AGENTS.md` and `source/REPORT.md` for domain cautions.

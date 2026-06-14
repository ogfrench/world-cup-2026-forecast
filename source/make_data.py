#!/usr/bin/env python3
"""Generate the live (conditional) results plus the frozen Day 0 baseline, in one pass.

Runs the engine twice per model from one shared market calibration: unconditioned (Day 0)
and conditioned on the played games (wc2026_actuals.json). Attaches each team's Day 0
values (champ0, advance0, ...) to the live output so the app can show before/after deltas,
then validates and writes both files. Same engine, same seeds, so the only difference
between Day 0 and live is the actual results.

    python3 source/make_data.py [n_sims]     # default 50000

Writes source/wc2026_results.json (live) and source/wc2026_baseline.json (Day 0, frozen).
The recurring refresh (the Action) re-runs only the conditioned half and reuses the
committed baseline; this script is the one-time / full regeneration.
"""
import sys, os, json, math
import wc2026_engine as e

HERE = os.path.dirname(os.path.abspath(__file__))
ORDER = ('elo', 'score', 'hybrid', 'market', 'market_pure')
BK = ('win_group', 'advance', 'r16', 'qf', 'sf', 'final', 'champ')

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50000
    A = e.load_actuals()
    ko_played = e.load_ko_actuals()
    played = sum(len(v) for v in A.values())
    print(f"actuals: {played} played group games, {len(ko_played)} knockout | n={n:,}")

    # market calibration pins the market-implied Elo to the published PRE-TOURNAMENT odds,
    # so it must use the unconditioned model (never conditioned on results)
    elo0, _ = e.run(n, model='elo')
    mE, b = e.market_implied_elo(elo0)
    e.MARKET_ELO.clear(); e.MARKET_ELO.update(mE)
    e.calibrate_market(b)

    base, live = {}, {}
    for key in ORDER:
        print(f"  {e.LABELS[key]}: Day 0 ...", flush=True)
        base[key] = elo0 if key == 'elo' else e.run(n, model=key)[0]
        print(f"  {e.LABELS[key]}: live{' (conditioned)' if played else ''} ...", flush=True)
        live[key] = e.run(n, model=key, actuals=A, ko_played=ko_played)[0]

    for key in ORDER:
        errs = e.validate(live[key])
        if errs:
            sys.exit("VALIDATION FAILED (%s): %s" % (key, errs[:5]))

    # attach Day 0 values to the live output for the before/after deltas
    for key in ORDER:
        for t in e.TEAMS:
            for k in BK:
                live[key][t][k + '0'] = base[key][t][k]

    gm = {key: e.group_match_predictions(key) for key in ORDER}
    # knockout bracket predictions (empty until every group has finished and the R32 is set)
    ko = {key: e.ko_predictions(key, group_actuals=A, ko_played=ko_played) for key in ORDER}
    nko = len(ko[ORDER[0]])
    print(f"  knockout: {nko} known ties" + (" (bracket set)" if nko else " (group stage)"))
    meta = dict(n_sims=n, default_model='market_pure', labels=e.LABELS,
                rho=e.RHO, home_mult=round(math.exp(e.HOME), 3), c=e.C, total=e.TOTAL,
                oos_logloss=dict(pure_dc=0.8558, pure_elo=0.8464, hybrid=0.8409),
                dc_matches=e.PARAMS['meta'].get('dc_matches'),
                live=played > 0, played=played)
    shared = dict(opta=e.OPTA, market=e.MARKET,
                  groups={g: [t[0] for t in e.GROUPS[g]] for g in e.GROUPS},
                  market_implied_elo={t: round(e.MARKET_ELO[t]) for t in e.MARKET_FULL})

    live_data = dict(meta=meta, **shared,
                     models={key: dict(teams=live[key], group_matches=gm[key],
                                       knockout=ko[key]) for key in ORDER})
    base_meta = dict(meta); base_meta['live'] = False; base_meta['played'] = 0
    base_data = dict(meta=base_meta, **shared,
                     models={key: dict(teams=base[key], group_matches=gm[key]) for key in ORDER})

    json.dump(live_data, open(os.path.join(HERE, 'wc2026_results.json'), 'w'), indent=1)
    json.dump(base_data, open(os.path.join(HERE, 'wc2026_baseline.json'), 'w'), indent=1)
    print(f"wrote wc2026_results.json (live={played>0}) and wc2026_baseline.json (Day 0)")
    for key in ('hybrid', 'market_pure'):
        tops = sorted(live[key], key=lambda t: -live[key][t]['champ'])[:4]
        print(f"  {e.LABELS[key]}: " + "  ".join(
            f"{t} {live[key][t]['champ']:.1f}({live[key][t]['champ']-live[key][t]['champ0']:+.1f})" for t in tops))

if __name__ == '__main__':
    main()

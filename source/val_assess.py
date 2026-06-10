"""
Out-of-sample predictive-power assessment of the match models that drive the engine.
Train on internationals before 2025-01-01, test on everything from 2025-01-01 to now.
Elo is frozen at end-2024; Dixon-Coles is refit on <2025; hybrid = 0.5 DC + 0.5 Elo
at the lambda level (exactly as the app). Reports proper scoring rules + accuracy +
a naive base-rate floor + calibration, with paired bootstrap CIs on the gaps.

The 'Model + Market' model is NOT here: it is built from CURRENT (June 2026) market
title odds, and there are no historical odds to backtest it on these matches.
"""
import numpy as np, pandas as pd, math
from val_dc import load, fit, pois, MAXG, NAME_MAP
from val_hybrid import compute_elo, hda_from_lam

rng = np.random.default_rng(7)

def rps3(p, o):
    # ranked probability score for ordered outcomes [home, draw, away]
    c1 = p[0]; c2 = p[0] + p[1]
    e1 = 1.0 if o == 0 else 0.0
    e2 = 1.0 if o <= 1 else 0.0
    return 0.5 * ((c1 - e1) ** 2 + (c2 - e2) ** 2)

if __name__ == '__main__':
    recs, frozen, current = compute_elo()
    rdf = pd.DataFrame(recs, columns=['date','h','a','Rh','Ra','neu','hs','as_'])

    # fit DC on <2025
    tr = load(start='2010-01-01'); tr = tr[tr['date'] < '2025-01-01']
    p = fit(tr); ic, co, idx, T, rho = p['ic'], p['co'], p['idx'], p['T'], p['rho']

    # Elo->goals slope c and mean total, on training matches
    trec = rdf[rdf['date'] < '2025-01-01']
    ed = (trec['Rh'] + np.where(trec['neu'], 0, 100) - trec['Ra']).to_numpy()
    gd = (trec['hs'] - trec['as_']).to_numpy()
    c = float(np.polyfit(ed, gd, 1)[0]); total = float((trec['hs'] + trec['as_']).mean())

    # train base rates (the naive floor)
    bh = float((trec['hs'] > trec['as_']).mean())
    bd = float((trec['hs'] == trec['as_']).mean())
    ba = 1 - bh - bd
    base = [bh, bd, ba]

    test = rdf[rdf['date'] >= '2025-01-01']

    def elo_lam(h, a, neu):
        Rh = frozen.get(h, 1500.0); Ra = frozen.get(a, 1500.0)
        sup = c * ((Rh + (0 if neu else 100)) - Ra)
        return total/2 + sup/2, total/2 - sup/2
    def dc_lam(h, a, neu):
        if h not in idx or a not in idx: return None
        lh = math.exp(ic + co[idx[h]] + co[T+idx[a]] + (0 if neu else co[2*T]))
        la = math.exp(ic + co[idx[a]] + co[T+idx[h]])
        return lh, la

    # per-match probability vectors for each model
    rows = []
    for _, m in test.iterrows():
        h, a, neu = m['h'], m['a'], m['neu']
        dc = dc_lam(h, a, neu)
        if dc is None: continue
        el = elo_lam(h, a, neu)
        def probs(lh, la): return hda_from_lam(max(0.05,lh), max(0.05,la), rho)
        P = {'elo': probs(*el), 'dc': probs(*dc),
             'hybrid': probs(0.5*dc[0]+0.5*el[0], 0.5*dc[1]+0.5*el[1]),
             'base': base}
        o = 0 if m['hs'] > m['as_'] else (1 if m['hs'] == m['as_'] else 2)
        rows.append((P, o))

    n = len(rows)
    models = ['base', 'elo', 'dc', 'hybrid']
    LL = {k: np.array([-math.log(max(P[k][o], 1e-12)) for P, o in rows]) for k in models}
    RP = {k: np.array([rps3(P[k], o) for P, o in rows]) for k in models}
    AC = {k: np.array([1.0 if int(np.argmax(P[k])) == o else 0.0 for P, o in rows]) for k in models}

    print(f"Out-of-sample test: {n} internationals, 2025-01-01 to 2026-06-06")
    print(f"(train: pre-2025; Elo frozen end-2024; DC refit on <2025; hybrid = 0.5 DC + 0.5 Elo)\n")
    print(f"{'model':<10}{'log-loss':>10}{'RPS':>9}{'accuracy':>10}")
    for k in models:
        print(f"{k:<10}{LL[k].mean():>10.4f}{RP[k].mean():>9.4f}{AC[k].mean():>10.3f}")

    # paired bootstrap on the gaps (positive = first model better, i.e. lower loss)
    def boot(metric, x, y, B=4000):
        d = metric[x] - metric[y]
        idxs = rng.integers(0, n, size=(B, n))
        means = d[idxs].mean(axis=1)
        return d.mean(), np.percentile(means, 2.5), np.percentile(means, 97.5)

    print("\nPaired bootstrap, 95% CI on mean difference (positive => first model lower loss = better):")
    for metric, name in [(LL, 'log-loss'), (RP, 'RPS')]:
        print(f"  [{name}]")
        for x, y in [('elo','hybrid'), ('dc','hybrid'), ('dc','elo')]:
            md, lo, hi = boot(metric, x, y)
            sig = 'distinguishable' if (lo > 0 or hi < 0) else 'NOT distinguishable from 0'
            print(f"    {y:<7} vs {x:<7}: {md:+.4f}  CI[{lo:+.4f}, {hi:+.4f}]  ({sig})")

    # calibration of home-win probability (10 bins, weighted mean abs error)
    print("\nCalibration of P(home win)  (mean |predicted - observed|, lower better):")
    homewin = np.array([1.0 if o == 0 else 0.0 for _, o in rows])
    for k in ['elo','dc','hybrid']:
        ph = np.array([P[k][0] for P, _ in rows])
        bins = np.clip((ph*10).astype(int), 0, 9)
        err = w = 0.0
        for b in range(10):
            mask = bins == b
            if mask.sum() == 0: continue
            err += mask.sum() * abs(ph[mask].mean() - homewin[mask].mean()); w += mask.sum()
        print(f"  {k:<7}: {err/w:.4f}")

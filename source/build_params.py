"""Produce model_params.json for the production engine:
- Dixon-Coles attack/defense/home/rho refit on the FULL window (2010 -> Jun 2026)
- official eloratings.net values (from screenshots, carried in the engine's GROUPS)
- Elo->goals slope c and mean total (estimated on the full window)
- blend weight alpha = 0.5  (selected out-of-sample in val_hybrid.py: hybrid 0.8409 beat pure Elo 0.8464 and pure DC 0.8558)
"""
import json, numpy as np, pandas as pd
from val_dc import load, fit
from val_hybrid import compute_elo
from wc2026_engine import GROUPS   # official Elo + group structure

ALPHA = 0.5

# --- DC on the full window ---
df = load(start='2010-01-01')
p = fit(df)
WC = [name for g in GROUPS.values() for name, _ in g]
att = {t: float(p['co'][p['idx'][t]]) for t in WC}
dfn = {t: float(p['co'][p['T'] + p['idx'][t]]) for t in WC}
home = float(p['co'][2*p['T']]); intercept = float(p['ic']); rho = float(p['rho'])

# --- c (goals per Elo pt) and mean total on the full window, via online Elo ---
recs, frozen, current = compute_elo()
rdf = pd.DataFrame(recs, columns=['date','h','a','Rh','Ra','neu','hs','as_'])
sub = rdf[rdf['date'] >= '2010-01-01']
elo_diff = (sub['Rh'] + np.where(sub['neu'], 0, 100) - sub['Ra']).to_numpy()
goal_diff = (sub['hs'] - sub['as_']).to_numpy()
c = float(np.polyfit(elo_diff, goal_diff, 1)[0])
total = float((sub['hs'] + sub['as_']).mean())

elo_official = {name: elo for g in GROUPS.values() for name, elo in g}

params = dict(intercept=intercept, home=home, rho=rho, att=att, dfn=dfn,
              c=c, total=total, alpha=ALPHA, elo=elo_official,
              meta=dict(dc_matches=p_meta if (p_meta:=df.shape[0]) else 0,
                        note="hybrid: lambda = alpha*DC + (1-alpha)*Elo; alpha chosen OOS"))
json.dump(params, open('model_params.json','w'), indent=1)
print("saved model_params.json")
print(f"intercept={intercept:.3f} home={home:+.3f} (x{np.exp(home):.3f}) rho={rho:+.3f}")
print(f"c={c:.5f} goals/Elo-pt  total={total:.3f}  alpha={ALPHA}")
print("sample att/dfn:", {t: (round(att[t],2), round(dfn[t],2)) for t in ['Spain','Brazil','England','Japan','Curacao']})

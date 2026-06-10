"""
Fit a proper Dixon-Coles team-strength model to real international results.

  log E[goals_for]  = intercept + ATT[scoring_team] + DEF[conceding_team] + HOME*home_flag

Attack/Defense per team and the home effect are fit by weighted Poisson regression
(time-decay weights, exponential half-life; ridge shrinkage so sparse minnows revert
to the mean). The Dixon-Coles dependence rho is then estimated by 1-D MLE on the four
low-score cells, holding the fitted means fixed (rho is near-orthogonal to the means,
so this two-step fit is standard and stable).

No Elo. No coefficient tuned to Opta. rho and home advantage are earned from data.
"""
import json, math
import numpy as np, pandas as pd
from scipy import sparse
from scipy.optimize import minimize_scalar
from sklearn.linear_model import PoissonRegressor

NOW = pd.Timestamp('2026-06-06')
WINDOW_START = '2010-01-01'
HALFLIFE_Y = 2.5          # recency half-life
MIN_MATCHES = 15          # team must have >= this many matches in window to be fit
RIDGE_ALPHA = 1e-3        # shrinkage toward league-average

# dataset name -> engine name (only the ones that differ)
NAME_MAP = {
    'United States': 'USA', 'Turkey': 'Turkiye', 'Türkiye': 'Turkiye',
    'Curaçao': 'Curacao', 'Bosnia and Herzegovina': 'Bosnia-Herzegovina',
    'Czech Republic': 'Czechia',
}
WC_TEAMS = {
 'Mexico','South Korea','Czechia','South Africa','Switzerland','Canada','Qatar','Bosnia-Herzegovina',
 'Brazil','Morocco','Scotland','Haiti','Turkiye','Paraguay','Australia','USA','Ecuador','Germany',
 'Ivory Coast','Curacao','Netherlands','Japan','Sweden','Tunisia','Belgium','Iran','Egypt','New Zealand',
 'Spain','Uruguay','Cape Verde','Saudi Arabia','France','Norway','Senegal','Iraq','Argentina','Austria',
 'Algeria','Jordan','Portugal','Colombia','Uzbekistan','England','Croatia','Panama','Ghana','DR Congo'}

def load():
    df = pd.read_csv('results.csv')
    df = df.dropna(subset=['home_score','away_score'])
    df['date'] = pd.to_datetime(df['date'])
    df = df[df['date'] >= WINDOW_START].copy()
    df['home_team'] = df['home_team'].replace(NAME_MAP)
    df['away_team'] = df['away_team'].replace(NAME_MAP)
    df['home_score'] = df['home_score'].astype(int)
    df['away_score'] = df['away_score'].astype(int)
    df['neutral'] = df['neutral'].astype(str).str.upper().eq('TRUE')
    age_y = (NOW - df['date']).dt.days / 365.25
    df['w'] = 0.5 ** (age_y / HALFLIFE_Y)
    return df

def fit():
    df = load()
    # keep teams with enough matches in window
    cnt = pd.concat([df['home_team'], df['away_team']]).value_counts()
    keep = set(cnt[cnt >= MIN_MATCHES].index)
    df = df[df['home_team'].isin(keep) & df['away_team'].isin(keep)].copy()
    teams = sorted(keep)
    idx = {t: i for i, t in enumerate(teams)}
    T = len(teams)
    print(f"Matches used: {len(df):,}  | teams fit: {T}  | window {WINDOW_START}->{NOW.date()}, halflife {HALFLIFE_Y}y")
    missing = WC_TEAMS - keep
    print("WC teams missing from fit (should be empty):", missing or "none")

    # two observations per match: (home scores) and (away scores)
    n = len(df); rows = 2 * n
    # columns: [ATT 0..T-1][DEF T..2T-1][HOME 2T]
    ncol = 2 * T + 1
    r, c, v = [], [], []
    y = np.empty(rows); w = np.empty(rows)
    h_idx = df['home_team'].map(idx).to_numpy()
    a_idx = df['away_team'].map(idx).to_numpy()
    hs = df['home_score'].to_numpy(); as_ = df['away_score'].to_numpy()
    neu = df['neutral'].to_numpy(); ww = df['w'].to_numpy()
    for k in range(n):
        # home-scoring row
        ro = 2*k
        r += [ro, ro]; c += [h_idx[k], T + a_idx[k]]; v += [1.0, 1.0]
        if not neu[k]:
            r.append(ro); c.append(2*T); v.append(1.0)
        y[ro] = hs[k]; w[ro] = ww[k]
        # away-scoring row (away team never has home flag)
        ri = 2*k+1
        r += [ri, ri]; c += [a_idx[k], T + h_idx[k]]; v += [1.0, 1.0]
        y[ri] = as_[k]; w[ri] = ww[k]
    X = sparse.csr_matrix((v, (r, c)), shape=(rows, ncol))

    reg = PoissonRegressor(alpha=RIDGE_ALPHA, fit_intercept=True, max_iter=5000, tol=1e-8)
    reg.fit(X, y, sample_weight=w)
    coef = reg.coef_
    att = {t: float(coef[idx[t]]) for t in teams}
    dfn = {t: float(coef[T + idx[t]]) for t in teams}
    home = float(coef[2*T]); intercept = float(reg.intercept_)

    # --- estimate rho by 1-D MLE on low-score cells, means held fixed ---
    lam_h = np.exp(intercept + coef[h_idx] + coef[T + a_idx] + np.where(neu, 0.0, home))
    lam_a = np.exp(intercept + coef[a_idx] + coef[T + h_idx])
    lam_h = np.clip(lam_h, 1e-6, 8); lam_a = np.clip(lam_a, 1e-6, 8)
    def neg_tau_ll(rho):
        ll = 0.0
        m00 = (hs==0)&(as_==0); m01=(hs==0)&(as_==1); m10=(hs==1)&(as_==0); m11=(hs==1)&(as_==1)
        ll += np.sum(ww[m00]*np.log(np.clip(1 - lam_h[m00]*lam_a[m00]*rho, 1e-9, None)))
        ll += np.sum(ww[m01]*np.log(np.clip(1 + lam_h[m01]*rho, 1e-9, None)))
        ll += np.sum(ww[m10]*np.log(np.clip(1 + lam_a[m10]*rho, 1e-9, None)))
        ll += np.sum(ww[m11]*np.log(np.clip(1 - rho, 1e-9, None)))
        return -ll
    res = minimize_scalar(neg_tau_ll, bounds=(-0.2, 0.2), method='bounded')
    rho = float(res.x)

    params = dict(intercept=intercept, home=home, rho=rho, att=att, dfn=dfn,
                  meta=dict(window=WINDOW_START, halflife_y=HALFLIFE_Y, ridge=RIDGE_ALPHA,
                            n_matches=int(len(df)), n_teams=T))
    json.dump(params, open('dc_params.json', 'w'), indent=1)

    # ---------- validation ----------
    print(f"\nhome advantage (log): {home:+.3f}  -> home side scores x{math.exp(home):.3f}")
    print(f"fitted rho: {rho:+.3f}  (Dixon-Coles found ~ -0.03..-0.16 on club data)")
    avg_def = np.mean(list(dfn.values()))
    # neutral expected goals vs a league-average opponent, and a single 'rating'
    def lam_vs_avg(t):
        lf = math.exp(intercept + att[t] + avg_def)
        la = math.exp(intercept + np.mean(list(att.values())) + dfn[t])
        return lf, la
    rating = {t: (lambda lf_la: lf_la[0]-lf_la[1])(lam_vs_avg(t)) for t in teams}
    order = sorted(WC_TEAMS, key=lambda t: -rating[t])
    print("\nFitted strength of the 48 WC teams (exp goal diff vs an average team, neutral):")
    for i, t in enumerate(order, 1):
        lf, la = lam_vs_avg(t)
        print(f"  {i:2d}. {t:<20} {rating[t]:+5.2f}   (scores {lf:.2f} / concedes {la:.2f})")

    # sanity matchup checks
    def lam(h_, a_, host_home=False):
        lh = math.exp(intercept + att[h_] + dfn[a_] + (home if host_home else 0))
        la2 = math.exp(intercept + att[a_] + dfn[h_])
        return lh, la2
    print("\nsample neutral matchups (lambda_home, lambda_away):")
    for h_, a_ in [('Spain','Curacao'),('Spain','Argentina'),('England','Croatia'),
                   ('Brazil','Haiti'),('USA','Paraguay'),('Germany','Ecuador')]:
        lh, la2 = lam(h_, a_); print(f"  {h_:<10} vs {a_:<12} -> {lh:.2f} : {la2:.2f}")
    return params

if __name__ == '__main__':
    fit()

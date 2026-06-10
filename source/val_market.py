"""
Can the market be beaten? An executable proxy for the claim behind the Model + Market column.
I cannot backtest the World Cup market (no historical international odds), so I test the general
phenomenon on club football, where real closing odds exist on every match.

Same shape as the app: a results-based Elo model vs the market vs their 50/50 blend, scored
out-of-sample. Data: top-5 leagues, real pre-match Elo and de-vigged closing odds. Train the
Elo->goals mapping on pre-2022 matches, test on 2022-07 onward.
"""
import numpy as np, pandas as pd, math

rng = np.random.default_rng(11)
TOP5 = {'E0','SP1','D1','I1','F1'}
SPLIT = pd.Timestamp('2022-07-01')

cols = ['Division','MatchDate','HomeElo','AwayElo','FTHome','FTAway','FTResult',
        'OddHome','OddDraw','OddAway']
df = pd.read_csv('matches.csv', usecols=cols)
df = df[df['Division'].isin(TOP5)].copy()
df['MatchDate'] = pd.to_datetime(df['MatchDate'], errors='coerce')
df = df.dropna(subset=['MatchDate','HomeElo','AwayElo','FTHome','FTAway',
                       'OddHome','OddDraw','OddAway','FTResult'])
for c in ['OddHome','OddDraw','OddAway']:
    df = df[df[c] > 1.01]
df = df.sort_values('MatchDate').reset_index(drop=True)

# de-vig the market (normalize inverse odds)
inv = 1.0/df[['OddHome','OddDraw','OddAway']].to_numpy()
mkt = inv/inv.sum(axis=1, keepdims=True)          # (n,3) home/draw/away
elod = (df['HomeElo'] - df['AwayElo']).to_numpy(float)
gh = df['FTHome'].to_numpy(float); ga = df['FTAway'].to_numpy(float)
out = np.where(gh>ga, 0, np.where(gh==ga, 1, 2))   # 0 home, 1 draw, 2 away
tr = (df['MatchDate'] < SPLIT).to_numpy(); te = ~tr
n_tr, n_te = tr.sum(), te.sum()

# fit Elo->goals on train: goal_diff ~ a + c*elo_diff ; total = mean goals
c, a = np.polyfit(elod[tr], (gh-ga)[tr], 1)
total = float((gh+ga)[tr].mean())
sup = a + c*elod
lamh = np.clip(total/2 + sup/2, 0.05, None)
lama = np.clip(total/2 - sup/2, 0.05, None)

K = np.arange(16)
FACT = np.array([math.factorial(k) for k in K], float)
def pmf(lam):
    lam = lam[:,None]
    m = np.exp(-lam)*lam**K/FACT
    return m/m.sum(axis=1, keepdims=True)
def wda(lamh, lama, rho):
    ph, pa = pmf(lamh), pmf(lama)
    D0 = (ph*pa).sum(axis=1)
    cum_h = np.cumsum(ph, axis=1)
    H0 = (pa*(1 - cum_h)).sum(axis=1)              # P(home > away)
    A0 = 1 - H0 - D0
    c00, c01 = ph[:,0]*pa[:,0], ph[:,0]*pa[:,1]
    c10, c11 = ph[:,1]*pa[:,0], ph[:,1]*pa[:,1]
    d00 = c00*(1-lamh*lama*rho)-c00; d01 = c01*(1+lamh*rho)-c01
    d10 = c10*(1+lama*rho)-c10;      d11 = c11*(1-rho)-c11
    dsum = d00+d01+d10+d11
    H = (H0 + d10)/(1+dsum); D = (D0 + d00 + d11)/(1+dsum); A = (A0 + d01)/(1+dsum)
    P = np.clip(np.stack([H,D,A],axis=1), 1e-9, None)
    return P/P.sum(axis=1, keepdims=True)

# fit rho on train by minimizing log-loss
def ll(P, o, mask): return float(-np.log(P[mask, o[mask]]).mean())
best=(9,0)
for rho in np.linspace(-0.20, 0.05, 26):
    P = wda(lamh, lama, rho)
    l = ll(P, out, tr)
    if l < best[0]: best=(l, rho)
rho = best[1]
elo = wda(lamh, lama, rho)
blend = (elo + mkt); blend = blend/blend.sum(axis=1, keepdims=True)   # 0.5/0.5 probs

# train base-rate floor
br = np.bincount(out[tr], minlength=3)/n_tr
base = np.tile(br, (len(out),1))

def rps(P, o):
    c = np.cumsum(P, axis=1)
    e = np.zeros_like(P); e[np.arange(len(o)), o] = 1; e = np.cumsum(e, axis=1)
    return 0.5*((c[:,0]-e[:,0])**2 + (c[:,1]-e[:,1])**2)

MODELS = {'base rate':base, 'Elo model':elo, 'Market':mkt, 'Elo+Market':blend}
print(f"Top-5 leagues. train {n_tr} matches (<2022-07), test {n_te} (2022-07 to 2025).")
print(f"fitted: c={c:.5f} goals/Elo-pt, home={a:+.3f} goals, total={total:.2f}, rho={rho:+.3f}\n")
LL={}; RP={}
print(f"{'model':<12}{'log-loss':>10}{'RPS':>9}{'accuracy':>10}{'calib(H)':>10}")
for name,P in MODELS.items():
    LL[name]=-np.log(P[te, out[te]]); RP[name]=rps(P[te], out[te])
    acc=(P[te].argmax(1)==out[te]).mean()
    # calibration of home-win prob, 10 bins
    ph=P[te,0]; hw=(out[te]==0).astype(float); b=np.clip((ph*10).astype(int),0,9)
    e=w=0.0
    for k in range(10):
        mk=b==k
        if mk.sum(): e+=mk.sum()*abs(ph[mk].mean()-hw[mk].mean()); w+=mk.sum()
    print(f"{name:<12}{LL[name].mean():>10.4f}{RP[name].mean():>9.4f}{acc:>10.3f}{e/w:>10.4f}")

def boot(x,y,B=4000):
    d=LL[x]-LL[y]; idx=rng.integers(0,len(d),size=(B,len(d)))
    m=d[idx].mean(1); return d.mean(), np.percentile(m,2.5), np.percentile(m,97.5)
print("\nPaired bootstrap on test log-loss (positive => first is better/lower):")
for x,y in [('Elo model','Market'),('Elo+Market','Market'),('Elo+Market','Elo model')]:
    md,lo,hi=boot(x,y); sig='clear' if (lo>0 or hi<0) else 'not distinguishable from 0'
    print(f"  {y:<11} minus {x:<11}: {-md:+.4f}  CI[{-hi:+.4f},{-lo:+.4f}]  ({sig})")

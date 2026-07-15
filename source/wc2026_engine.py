"""
World Cup 2026 prediction engine -- five rating models on a shared fixed-strength Monte Carlo.

Match model (validated out-of-sample, see val_hybrid.py):
    lambda = 0.5 * DixonColes + 0.5 * Elo     (blend weight chosen by held-out log-loss)
  - Dixon-Coles: attack/defense per team + home effect + low-score dependence rho,
    fit by weighted Poisson MLE on 15,751 real internationals (2010-2026). rho and the
    1.31x home advantage are ESTIMATED, not assumed.
  - Elo: official eloratings.net ratings -> goal supremacy via a slope fit to results.
  Pure DC OOS log-loss 0.856, pure Elo 0.846, hybrid 0.841 (beats both).

Variance: this is a FIXED-STRENGTH simulation. Team ratings do not vary between simulated
tournaments, so the only randomness is goal-level (Poisson) variance. There is deliberately NO
per-team rating/form uncertainty. That is the single biggest reason the results-based models lean
top-heavy (they crowd probability onto favourites): a fixed-strength sim cannot see in-tournament
swings (injury, form, a red card). See REPORT.md; adding rating uncertainty would widen the title
race and is the most worthwhile future change. (An earlier docstring claimed a per-team form-noise
offset; that was never implemented, so this note was corrected to match the code.)

The per-match prediction tables use the full Dixon-Coles distribution; the Monte Carlo samples
goals as Poisson (the rho correction is negligible for who-advances).

Run directly for an engine smoke test that prints the title odds:
    python3 wc2026_engine.py [n_sims]
This does NOT write app data. Regenerate that with the full pipeline: make_data.py then merge_schedule.py.
"""
import sys, os, json, math
from itertools import combinations
import numpy as np
from annexc_data import parse_annex_c

_HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS = json.load(open(os.path.join(_HERE, 'model_params.json')))

# ----------------------------------------------------------------------------
# 1. DATA: groups + official eloratings.net "R" values (read off the site, 6 Jun 2026)
# ----------------------------------------------------------------------------
GROUPS = {
    'A': [('Mexico', 1875), ('South Korea', 1758), ('Czechia', 1740), ('South Africa', 1518)],
    'B': [('Switzerland', 1894), ('Canada', 1793), ('Qatar', 1423), ('Bosnia-Herzegovina', 1591)],
    'C': [('Brazil', 1988), ('Morocco', 1824), ('Scotland', 1770), ('Haiti', 1554)],
    'D': [('Turkiye', 1906), ('Paraguay', 1833), ('Australia', 1774), ('USA', 1733)],
    'E': [('Ecuador', 1935), ('Germany', 1925), ('Ivory Coast', 1695), ('Curacao', 1433)],
    'F': [('Netherlands', 1944), ('Japan', 1906), ('Sweden', 1712), ('Tunisia', 1633)],
    'G': [('Belgium', 1888), ('Iran', 1772), ('Egypt', 1699), ('New Zealand', 1563)],
    'H': [('Spain', 2155), ('Uruguay', 1892), ('Cape Verde', 1576), ('Saudi Arabia', 1566)],
    'I': [('France', 2062), ('Norway', 1917), ('Senegal', 1867), ('Iraq', 1618)],
    'J': [('Argentina', 2113), ('Austria', 1830), ('Algeria', 1760), ('Jordan', 1685)],
    'K': [('Portugal', 1984), ('Colombia', 1977), ('Uzbekistan', 1718), ('DR Congo', 1661)],
    'L': [('England', 2020), ('Croatia', 1908), ('Panama', 1734), ('Ghana', 1510)],
}
HOST_TEAMS = {'Mexico', 'USA', 'Canada'}     # home effect applied in their group games

OPTA = {'Spain': 16.1, 'Argentina': 10.4, 'France': 13.0, 'England': 11.2, 'Brazil': 6.6,
        'Portugal': 7.0, 'Germany': 5.1, 'Netherlands': 2.8}
MARKET = {'Spain': 16.0, 'France': 16.0, 'England': 11.3, 'Brazil': 9.0, 'Argentina': 8.3,
          'Portugal': 8.0, 'Germany': 5.0, 'Netherlands': 3.0}

# ----------------------------------------------------------------------------
# 2. FITTED PARAMETERS (from model_params.json)
# ----------------------------------------------------------------------------
INTERCEPT = PARAMS['intercept']; HOME = PARAMS['home']; RHO = PARAMS['rho']
ATT = PARAMS['att']; DFN = PARAMS['dfn']
C = PARAMS['c']; TOTAL = PARAMS['total']; ALPHA = PARAMS['alpha']
ELO = {name: e for teams in GROUPS.values() for name, e in teams}
TEAM_GROUP = {name: g for g, teams in GROUPS.items() for name, _ in teams}
TEAMS = list(ELO); TEAM_IDX = {t: i for i, t in enumerate(TEAMS)}
SHOOTOUT_COEF = 0.0005
KO_SIM_N = 100000; KO_SEED = 8675309     # knockout scoreline simulation: draws, fixed seed (reproducible)
MAXG = 10; NCOL = MAXG + 1

# de-vigged market title odds (June 2026); top 8 firm, tail approximate.
MARKET_FULL = {
    'Spain':16.0,'France':16.0,'England':11.3,'Brazil':9.0,'Argentina':8.3,'Portugal':8.0,
    'Germany':5.0,'Netherlands':3.5,'Belgium':2.5,'Colombia':2.2,'USA':2.0,'Uruguay':2.0,
    'Croatia':1.8,'Morocco':1.8,'Mexico':1.6,'Japan':1.5,'Norway':1.2,'Senegal':1.2,
    'Switzerland':1.1,'Ecuador':1.0,
}
MARKET_ELO = {}                  # market-implied Elo, filled by market_implied_elo()
CURRENT_MODEL = 'hybrid'         # 'elo' | 'score' | 'hybrid' | 'market'

# ----------------------------------------------------------------------------
# 3. HYBRID MATCH MODEL -> Dixon-Coles scoreline matrix (for the display tables)
# ----------------------------------------------------------------------------
_FACT = np.array([math.factorial(k) for k in range(MAXG + 1)], dtype=float)
_K = np.arange(MAXG + 1)
def _pois(lam):
    lam = max(lam, 1e-9)
    return np.exp(-lam) * lam ** _K / _FACT

def _elo_pair(h, a, hh_h, hh_a, elo):
    eh = elo[h] + (100.0 if hh_h else 0.0); ea = elo[a] + (100.0 if hh_a else 0.0)
    sup = C * (eh - ea)
    return TOTAL/2 + sup/2, TOTAL/2 - sup/2

def _dc_pair(h, a, hh_h, hh_a):
    lh = math.exp(INTERCEPT + ATT[h] + DFN[a] + (HOME if hh_h else 0.0))
    la = math.exp(INTERCEPT + ATT[a] + DFN[h] + (HOME if hh_a else 0.0))
    return lh, la

def _hybrid_pair(h, a, hh_h, hh_a):
    e = _elo_pair(h, a, hh_h, hh_a, ELO); d = _dc_pair(h, a, hh_h, hh_a)
    return 0.5*e[0] + 0.5*d[0], 0.5*e[1] + 0.5*d[1]

def lambdas(h, a, hh_h=False, hh_a=False):
    """Expected goals for the currently selected model (CURRENT_MODEL)."""
    m = CURRENT_MODEL
    if m == 'elo':
        lh, la = _elo_pair(h, a, hh_h, hh_a, ELO)
    elif m == 'score':
        lh, la = _dc_pair(h, a, hh_h, hh_a)
    elif m == 'market':                      # 0.5 hybrid + 0.5 (Elo driven by market-implied ratings)
        hy = _hybrid_pair(h, a, hh_h, hh_a); mk = _elo_pair(h, a, hh_h, hh_a, MARKET_ELO)
        lh = 0.5*hy[0] + 0.5*mk[0]; la = 0.5*hy[1] + 0.5*mk[1]
    elif m == 'market_pure':                 # the market's own view: Elo on market-implied ratings
        lh, la = _elo_pair(h, a, hh_h, hh_a, MARKET_ELO)
    else:
        lh, la = _hybrid_pair(h, a, hh_h, hh_a)
    return max(0.05, lh), max(0.05, la)

def dc_matrix(h, a, hh_h=False, hh_a=False):
    la, lb = lambdas(h, a, hh_h, hh_a)
    M = np.outer(_pois(la), _pois(lb))
    M[0, 0] *= 1 - la * lb * RHO
    M[0, 1] *= 1 + la * RHO
    M[1, 0] *= 1 + lb * RHO
    M[1, 1] *= 1 - RHO
    M = np.clip(M, 0, None)
    return M / M.sum()

ANNEX_C = parse_annex_c()
ELIG = {74: set('ABCDF'), 77: set('CDFGH'), 79: set('CEFHI'), 80: set('EHIJK'),
        81: set('BEFIJ'), 82: set('AEHIJ'), 85: set('EFGIJ'), 87: set('DEIJL')}

def assign_thirds(adv_groups):
    key = frozenset(adv_groups)
    mp = ANNEX_C.get(key)
    if mp is not None and all(mp[m] in ELIG[m] for m in ELIG):
        return mp
    slots = list(ELIG); groups = list(adv_groups); res = {}
    def bt(i):
        if i == len(slots): return True
        m = slots[i]
        for gpr in groups:
            if gpr in ELIG[m] and gpr not in res.values():
                res[m] = gpr
                if bt(i + 1): return True
                del res[m]
        return False
    bt(0); return res

# ----------------------------------------------------------------------------
# 4. GROUP STAGE (FIFA 2026 tiebreakers: head-to-head FIRST)
# ----------------------------------------------------------------------------
GROUP_FIXTURES = {g: list(combinations([t[0] for t in teams], 2)) for g, teams in GROUPS.items()}

# build per-group fixture base lambdas for the CURRENT_MODEL (host home applied to host group games)
def build_fx():
    fxd = {}
    for g in GROUPS:
        fx = GROUP_FIXTURES[g]; blh = []; bla = []
        for (h, a) in fx:
            lh, la = lambdas(h, a, h in HOST_TEAMS, a in HOST_TEAMS)
            blh.append(lh); bla.append(la)
        fxd[g] = dict(h=[p[0] for p in fx], a=[p[1] for p in fx],
                      blh=np.array(blh), bla=np.array(bla))
    return fxd

def rank_group(group, results, elo_sign=1):
    teams = [t[0] for t in GROUPS[group]]
    pts = {t: 0 for t in teams}; gf = {t: 0 for t in teams}; ga = {t: 0 for t in teams}
    for h, a, hg, ag in results:
        gf[h] += hg; ga[h] += ag; gf[a] += ag; ga[a] += hg
        if hg > ag: pts[h] += 3
        elif hg < ag: pts[a] += 3
        else: pts[h] += 1; pts[a] += 1
    def h2h(among):
        s = set(among); hp = {t: 0 for t in among}; hgf = {t: 0 for t in among}; hga = {t: 0 for t in among}
        for h, a, hg, ag in results:
            if h in s and a in s:
                hgf[h] += hg; hga[h] += ag; hgf[a] += ag; hga[a] += hg
                if hg > ag: hp[h] += 3
                elif hg < ag: hp[a] += 3
                else: hp[h] += 1; hp[a] += 1
        return hp, hgf, hga
    # FIFA 2026 order with re-application: within a points-tied block, apply head-to-head among the
    # block (points, GD, goals), then overall GD, overall goals, then Elo (a deterministic stand-in
    # for fair play / FIFA ranking / lots, which we have no data for). The first criterion that
    # splits the block partitions it; any subgroup still tied is re-ranked from the top with its
    # head-to-head recomputed among just those teams (this recomputation is what the old flat sort
    # missed). elo_sign flips the Elo tail so callers can detect tail-dependent boundaries.
    def order_block(block):
        if len(block) == 1: return list(block)
        hp, hgf, hga = h2h(block)
        crits = (lambda t: hp[t], lambda t: hgf[t] - hga[t], lambda t: hgf[t],
                 lambda t: gf[t] - ga[t], lambda t: gf[t], lambda t: elo_sign * ELO[t])
        for crit in crits:
            vals = sorted({crit(t) for t in block}, reverse=True)
            if len(vals) > 1:                                  # this criterion separates the block
                out = []
                for v in vals:
                    sub = [t for t in block if crit(t) == v]
                    out.extend(order_block(sub) if len(sub) > 1 else sub)
                return out
        return list(block)                                     # unreachable: the Elo tail is unique
    order = sorted(teams, key=lambda t: -pts[t]); final = []; i = 0
    while i < len(order):
        j = i
        while j < len(order) and pts[order[j]] == pts[order[i]]: j += 1
        final.extend(order_block(order[i:j]))
        i = j
    stats = {t: (pts[t], gf[t] - ga[t], gf[t]) for t in teams}
    return final, stats

# ----------------------------------------------------------------------------
# 5. ONE TOURNAMENT
# ----------------------------------------------------------------------------
def play_ko(a, b, rng):
    lh, la = lambdas(a, b, False, False)        # knockouts neutral
    x, y = rng.poisson(lh), rng.poisson(la)
    if x > y: return a, b
    if y > x: return b, a
    ex, ey = rng.poisson(lh / 3.0), rng.poisson(la / 3.0)    # extra time
    if ex > ey: return a, b
    if ey > ex: return b, a
    p_a = min(0.60, max(0.40, 0.5 + SHOOTOUT_COEF * (ELO[a] - ELO[b])))
    return (a, b) if rng.random() < p_a else (b, a)

# bracket structure, shared by the Monte Carlo and the live bracket derivation below
R16_PAIRS = {89: (74, 77), 90: (73, 75), 91: (76, 78), 92: (79, 80),
             93: (83, 84), 94: (81, 82), 95: (86, 88), 96: (85, 87)}
QF_PAIRS = {97: (89, 90), 98: (93, 94), 99: (91, 92), 100: (95, 96)}
SF_PAIRS = {101: (97, 98), 102: (99, 100)}
FINAL_FEEDERS = (101, 102)

def _r32_map(W, R, T, tmap):
    """The 16 round-of-32 ties as feeder slots, from group winners W, runners R, and
    advancing thirds T (keyed by group) placed by the Annex C map tmap (slot -> group)."""
    return {
        73: (R['A'], R['B']), 74: (W['E'], T[tmap[74]]), 75: (W['F'], R['C']),
        76: (W['C'], R['F']), 77: (W['I'], T[tmap[77]]), 78: (R['E'], R['I']),
        79: (W['A'], T[tmap[79]]), 80: (W['L'], T[tmap[80]]), 81: (W['D'], T[tmap[81]]),
        82: (W['G'], T[tmap[82]]), 83: (R['K'], R['L']), 84: (W['H'], R['J']),
        85: (W['B'], T[tmap[85]]), 86: (W['J'], R['H']), 87: (W['K'], T[tmap[87]]),
        88: (R['D'], R['G']),
    }

def simulate_tournament(group_results, rng, ko_fixed=None):
    ko_fixed = ko_fixed or {}
    def _ko(a, b):                                   # force a known result, else play it out
        w = ko_fixed.get(frozenset((a, b)))
        if w is not None:
            return (w, b if w == a else a)
        return play_ko(a, b, rng)
    winners, runners, thirds, third_stats = {}, {}, {}, {}
    for g in GROUPS:
        order, stats = rank_group(g, group_results[g])
        winners[g], runners[g], thirds[g] = order[0], order[1], order[2]
        third_stats[g] = stats[order[2]]
    ranked_thirds = sorted(GROUPS, key=lambda g: (-third_stats[g][0], -third_stats[g][1],
                                                  -third_stats[g][2], -ELO[thirds[g]]))
    adv_groups = ranked_thirds[:8]
    tmap = assign_thirds(adv_groups)
    T = {g: thirds[g] for g in adv_groups}
    W, R = winners, runners
    r32 = _r32_map(W, R, T, tmap)
    wq = {m: _ko(a, b)[0] for m, (a, b) in r32.items()}
    w16 = {m: _ko(wq[p], wq[q])[0] for m, (p, q) in R16_PAIRS.items()}
    wqf = {m: _ko(w16[p], w16[q])[0] for m, (p, q) in QF_PAIRS.items()}
    wsf = {m: _ko(wqf[p], wqf[q])[0] for m, (p, q) in SF_PAIRS.items()}
    champ, _ = _ko(wsf[101], wsf[102])
    return {'winners': winners, 'runners': runners, 'thirds': T,
            'r32_winners': set(wq.values()), 'r16_winners': set(w16.values()),
            'qf_winners': set(wqf.values()), 'sf_winners': set(wsf.values()),
            'finalists': {wsf[101], wsf[102]}, 'champion': champ}

# ----------------------------------------------------------------------------
# 6. MONTE CARLO  (optionally conditioned on actual results)
# ----------------------------------------------------------------------------
def load_actuals(path=None):
    """Played group results to condition on: a JSON list of
    {group, home, away, hs, as} in engine team names, official home/away."""
    path = path or os.path.join(_HERE, 'wc2026_actuals.json')
    if not os.path.exists(path):
        return {}
    out = {g: [] for g in GROUPS}
    for r in json.load(open(path)):
        out[r['group']].append((r['home'], r['away'], int(r['hs']), int(r['as'])))
    return out

def _fixed_overrides(actuals):
    """Map actual results onto GROUP_FIXTURES order, oriented to each fixture's (h, a)."""
    fixed = {}
    for g, fx in GROUP_FIXTURES.items():
        played = {frozenset((h, a)): (h, hs, ag) for (h, a, hs, ag) in actuals.get(g, [])}
        idx = {}
        for k, (h, a) in enumerate(fx):
            rec = played.get(frozenset((h, a)))
            if rec is None:
                continue
            rh, hs, ag = rec
            idx[k] = (hs, ag) if rh == h else (ag, hs)   # orient to the fixture's home/away
        if idx:
            fixed[g] = idx
    return fixed

def run(n=50000, seed=20260611, model='hybrid', actuals=None, ko_played=None):
    global CURRENT_MODEL; CURRENT_MODEL = model
    rng = np.random.default_rng(seed)
    fx_all = build_fx()
    fixed = _fixed_overrides(actuals or {})
    ko_fixed = {frozenset((p['home'], p['away'])): p['winner']
                for p in (ko_played or []) if p.get('winner')}
    counters = {t: dict(win_group=0, advance=0, r16=0, qf=0, sf=0, final=0, champ=0) for t in TEAMS}
    for _ in range(n):
        group_results = {}
        for g in GROUPS:
            fx = fx_all[g]
            hg = rng.poisson(fx['blh']); ag = rng.poisson(fx['bla'])
            for k, (fh, fa) in fixed.get(g, {}).items():   # lock played games
                hg[k] = fh; ag[k] = fa
            group_results[g] = [(fx['h'][k], fx['a'][k], int(hg[k]), int(ag[k])) for k in range(len(hg))]
        res = simulate_tournament(group_results, rng, ko_fixed)
        for g in GROUPS: counters[res['winners'][g]]['win_group'] += 1
        advancing = set(res['winners'].values()) | set(res['runners'].values()) | set(res['thirds'].values())
        for t in advancing: counters[t]['advance'] += 1
        for t in res['r32_winners']: counters[t]['r16'] += 1
        for t in res['r16_winners']: counters[t]['qf'] += 1
        for t in res['qf_winners']: counters[t]['sf'] += 1
        for t in res['finalists']: counters[t]['final'] += 1
        counters[res['champion']]['champ'] += 1
    probs = {}
    for t in TEAMS:
        probs[t] = {k: 100.0 * v / n for k, v in counters[t].items()}
        probs[t]['elo'] = ELO[t]; probs[t]['group'] = TEAM_GROUP[t]
    return probs, n

def validate(probs):
    """Sanity invariants for a (conditional) run; returns a list of problems."""
    errs = []
    s = sum(probs[t]['champ'] for t in TEAMS)
    if abs(s - 100) > 1.0:
        errs.append(f"champ probs sum to {s:.2f}, not ~100")
    for t in TEAMS:
        p = probs[t]
        for k in ('win_group', 'advance', 'r16', 'qf', 'sf', 'final', 'champ'):
            if not (-0.01 <= p[k] <= 100.01):
                errs.append(f"{t} {k}={p[k]} out of range")
        seq = [p['advance'], p['r16'], p['qf'], p['sf'], p['final'], p['champ']]
        if any(seq[i] + 0.01 < seq[i + 1] for i in range(len(seq) - 1)):
            errs.append(f"{t} reach-round odds not monotonic: {[round(x,1) for x in seq]}")
    return errs


# ----------------------------------------------------------------------------
# 7. DETERMINISTIC PER-MATCH PREDICTIONS (group stage, full Dixon-Coles, no noise)
# ----------------------------------------------------------------------------
def match_report(a, b):
    hh_a = a in HOST_TEAMS; hh_b = b in HOST_TEAMS
    M = dc_matrix(a, b, hh_a, hh_b)
    p_home = float(np.tril(M, -1).sum()); p_draw = float(np.trace(M)); p_away = float(np.triu(M, 1).sum())
    mh, ma = divmod(int(np.argmax(M)), NCOL)
    la, lb = lambdas(a, b, hh_a, hh_b)
    order = np.argsort(M, axis=None)[::-1][:4]
    tops = [(int(s // NCOL), int(s % NCOL), round(float(M.ravel()[s]) * 100, 1)) for s in order]
    return dict(home=a, away=b, p_home=round(p_home*100,1), p_draw=round(p_draw*100,1),
                p_away=round(p_away*100,1), modal=[int(mh), int(ma)],
                xg_home=round(la,2), xg_away=round(lb,2), top_scores=tops)

def group_match_predictions(model='hybrid'):
    global CURRENT_MODEL; CURRENT_MODEL = model
    return {g: [match_report(h, a) for (h, a) in GROUP_FIXTURES[g]] for g in GROUPS}


# ----------------------------------------------------------------------------
# 8. KNOCKOUT BRACKET (live): the actual matchups and a prediction for each tie
# ----------------------------------------------------------------------------
ROUND_OF = {**{s: 'r32' for s in range(73, 89)}, **{s: 'r16' for s in range(89, 97)},
            97: 'qf', 98: 'qf', 99: 'qf', 100: 'qf', 101: 'sf', 102: 'sf', 103: 'final'}

def load_ko_actuals(path=None):
    """Played knockout games: a JSON list of {round, home, away, hs, as, winner} in engine
    team names, where winner is the advancing side (after extra time and any shootout)."""
    path = path or os.path.join(_HERE, 'wc2026_ko_actuals.json')
    return json.load(open(path)) if os.path.exists(path) else []

# Symbolic round-of-32, derived from _r32_map itself so it can never drift from the real bracket:
# each slot's two feeders become tagged tuples ('W',group), ('R',group), or ('3',slot).
R32_SYMBOLIC = _r32_map({g: ('W', g) for g in GROUPS}, {g: ('R', g) for g in GROUPS},
                        {s: ('3', s) for s in ELIG}, {s: s for s in ELIG})

def _third_key(rec, elo_sign=1):
    """Cross-group third-place ranking key (higher better): points, GD, goals, then the Elo tail."""
    p, gd, gf = rec['tstat']
    return (p, gd, gf, elo_sign * ELO[rec['third']])

def _third_qualified(g, settled, elo_sign=1):
    """True iff group g's third is guaranteed among the best 8 thirds: at most 7 others can finish
    above it (settled thirds that outrank it, plus one per still-unsettled group, worst case)."""
    if g not in settled:
        return False
    remaining = len(GROUPS) - len(settled)
    kx = _third_key(settled[g], elo_sign)
    ahead = sum(1 for h, rec in settled.items() if h != g and _third_key(rec, elo_sign) > kx)
    return ahead + remaining <= 7

def _resolve_thirds(settled, elo_sign=1):
    """{slot: team} for third-place slots whose occupant is already determined.

    Full set of 12 settled: rank all thirds, take the top 8, and place them via Annex C.

    Partial: a third's Annex C slot depends on which eight of the twelve groups supply a qualifying
    third, so a slot is placeable early only when it maps to the same group across every still-possible
    qualifying set. Force in the thirds that have clinched a top-8 finish, enumerate the ways the
    remaining qualifying spots can be filled from the open groups, and emit any slot that lands on the
    same clinched (so already known) group in all of them. Enumerating the open groups is a slight
    superset of the genuinely reachable sets (it ignores the fixed ordering among settled non-clinched
    thirds), which only makes the test more conservative, never wrong: an emitted slot is locked under
    the superset, hence under the reachable subset too. This subsumes the old K/L special case (their
    slots are combination-invariant by construction) and generalizes it to any group whose third is
    pinned to a single slot. Runs under each Elo tail via the caller, so a slot whose occupant or
    ordering hangs on the Elo tie-break disagrees between tails and is deferred upstream."""
    out = {}
    if len(settled) == len(GROUPS):
        ranked = sorted(GROUPS, key=lambda g: tuple(-v for v in _third_key(settled[g], elo_sign)))
        for slot, grp in assign_thirds(ranked[:8]).items():
            out[slot] = settled[grp]['third']
        return out
    clinched = [g for g in GROUPS if _third_qualified(g, settled, elo_sign)]
    need = 8 - len(clinched)
    if need < 0:
        return out
    open_pool = [g for g in GROUPS if g not in clinched]
    slot_groups = {}
    for extra in combinations(open_pool, need):
        for slot, grp in assign_thirds(clinched + list(extra)).items():
            slot_groups.setdefault(slot, set()).add(grp)
    for slot, groups in slot_groups.items():
        if len(groups) == 1:
            g = next(iter(groups))
            if g in settled:                  # occupant known: its group has finished
                out[slot] = settled[g]['third']
    return out

def _resolve_feeder(ref, settled, thirds):
    kind, key = ref
    if kind == '3':
        return thirds.get(key)
    return settled[key]['W' if kind == 'W' else 'R'] if key in settled else None

def ko_report(a, b):
    """Neutral-venue knockout prediction. The scoreline is the most common result of SIMULATING the tie
    exactly how it is played: 90 minutes like a group game, then 30 minutes of extra time if it is level,
    then penalties if it is still level. Also returns win/draw/loss over 90, the probability each side
    advances, and p_pens, the share of simulations that go to a shootout."""
    la, lb = lambdas(a, b, False, False)
    rng = np.random.default_rng(KO_SEED); n = KO_SIM_N
    # 1. play 90 minutes (same Poisson goals as a group match)
    h = rng.poisson(la, n); ag = rng.poisson(lb, n)
    level = h == ag
    # 2. if level after 90, play 30 minutes of extra time (a third of the rate) and add it on top
    eh = rng.poisson(la / 3.0, n); ea = rng.poisson(lb / 3.0, n)
    H = np.where(level, h + eh, h); A = np.where(level, ag + ea, ag)
    # 3. if still level after extra time, it is settled on penalties (the score stays as it is)
    pens = H == A
    W = 64                                                # encode each scoreline H-A as one integer
    codes, cnt = np.unique(H * W + A, return_counts=True)
    top = np.argsort(cnt)[::-1][:4]
    tops = [[int(codes[i] // W), int(codes[i] % W), round(float(cnt[i]) / n * 100, 1)] for i in top]
    mh, ma = tops[0][0], tops[0][1]
    p_a = float((h > ag).mean()); p_d = float(level.mean()); p_b = float((ag > h).mean())   # over 90
    sh_a = min(0.60, max(0.40, 0.5 + SHOOTOUT_COEF * (ELO[a] - ELO[b])))                    # shootout edge
    adv_a = float((H > A).mean() + pens.mean() * sh_a)    # win in 90 or extra time, or take the shootout
    return dict(a=a, b=b, p_a=round(p_a * 100, 1), p_draw=round(p_d * 100, 1), p_b=round(p_b * 100, 1),
                modal=[mh, ma], top_scores=tops, p_pens=round(float(pens.mean()) * 100, 1),
                adv_a=round(adv_a * 100, 1), adv_b=round((1 - adv_a) * 100, 1),
                elo_a=ELO[a], elo_b=ELO[b])

def _bracket_core(group_actuals, ko_played, elo_sign):
    """Build the known bracket under one Elo tail. Fills incrementally: each group with all six games
    played is settled (winner, runner-up, third); an R32 tie is emitted once both its feeders resolve,
    and a later-round tie once both its feeder winners are known from played results."""
    settled = {}
    for g in GROUPS:
        res = group_actuals.get(g, [])
        if len(res) >= 6:
            order, stats = rank_group(g, res, elo_sign)
            settled[g] = dict(W=order[0], R=order[1], third=order[2], tstat=stats[order[2]])
    thirds = _resolve_thirds(settled, elo_sign)
    bracket = {}
    for slot, (fa, fb) in R32_SYMBOLIC.items():
        a = _resolve_feeder(fa, settled, thirds); b = _resolve_feeder(fb, settled, thirds)
        if a and b:
            bracket[slot] = dict(round='r32', a=a, b=b, played=None)
    played = {frozenset((p['home'], p['away'])): p for p in (ko_played or [])}
    def fill(slot):
        e = bracket.get(slot)
        if e and frozenset((e['a'], e['b'])) in played:
            pl = played[frozenset((e['a'], e['b']))]
            flip = pl['home'] != e['a']            # orient the feed's home/away to this tie's a/b
            hs, as_ = (pl['as'], pl['hs']) if flip else (pl['hs'], pl['as'])
            pens = pl.get('pens')
            if flip and pens:
                pens = [pens[1], pens[0]]
            e['played'] = dict(hs=hs, as_=as_, winner=pl['winner'],
                               aet=pl.get('aet', False), pens=pens)
    for slot in list(bracket):
        fill(slot)
    def won(slot):
        e = bracket.get(slot)
        return e['played']['winner'] if e and e['played'] else None
    for slot, (p, q) in {**R16_PAIRS, **QF_PAIRS, **SF_PAIRS, 103: FINAL_FEEDERS}.items():
        wp, wq = won(p), won(q)
        if wp and wq:
            bracket[slot] = dict(round=ROUND_OF[slot], a=wp, b=wq, played=None)
            fill(slot)
    # third-place play-off (official match 103, our synthetic slot 104): the two beaten semi-finalists.
    # It sits outside the advancement bracket (nothing progresses from it), so it is emitted separately,
    # but it is an ordinary tie the model can predict, so once both semis are decided we emit it too.
    def lost(slot):
        e = bracket.get(slot)
        if e and e['played'] and e['played']['winner']:
            return e['b'] if e['played']['winner'] == e['a'] else e['a']
        return None
    la, lb = lost(101), lost(102)
    if la and lb:
        bracket[104] = dict(round='third', a=la, b=lb, played=None)
        fill(104)
    return bracket

def actual_bracket(group_actuals, ko_played):
    """Resolve the known bracket from played games, filling ties in as groups finish. Returns
    {slot: {round, a, b, played|None}} for every tie whose two teams are determined by the criteria
    we can compute. A boundary that only the Elo tail would decide (a dead tie that FIFA would settle
    on fair play / ranking / lots, which we have no data for) is left pending instead of guessed: the
    bracket is built under both Elo tails and only slots that agree on both teams are emitted."""
    hi = _bracket_core(group_actuals, ko_played, +1)
    lo = _bracket_core(group_actuals, ko_played, -1)
    return {s: e for s, e in hi.items()
            if s in lo and lo[s]['a'] == e['a'] and lo[s]['b'] == e['b']}

def ko_predictions(model='hybrid', group_actuals=None, ko_played=None):
    """Per-model prediction for every known knockout tie, keyed by slot. Empty until the R32 is set."""
    global CURRENT_MODEL; CURRENT_MODEL = model
    A = group_actuals if group_actuals is not None else load_actuals()
    ko = ko_played if ko_played is not None else load_ko_actuals()
    out = {}
    for slot, e in actual_bracket(A, ko).items():
        rep = ko_report(e['a'], e['b'])
        rep.update(slot=slot, round=e['round'], played=e['played'])
        out[slot] = rep
    return out

def market_implied_elo(probs_elo):
    """Invert the pure-Elo model's log(title%)-vs-Elo line to map market title odds -> implied Elo."""
    ts = [t for t in TEAMS if probs_elo[t]['champ'] > 0.05]
    x = np.array([ELO[t] for t in ts], float)
    y = np.log(np.array([probs_elo[t]['champ'] for t in ts], float))
    b, a = np.polyfit(x, y, 1)               # log p = b*Elo + a
    out = {t: ((math.log(MARKET_FULL[t]) - a) / b if t in MARKET_FULL else ELO[t]) for t in TEAMS}
    return out, b

def calibrate_market(b, iters=4, n=30000, damp=0.8, seed=4242):
    """Nudge MARKET_ELO so a pure-market sim reproduces the published market title odds,
    correcting the group-difficulty bias the global inversion leaves behind."""
    for _ in range(iters):
        pm, _ = run(n, model='market_pure', seed=seed)
        for t in MARKET_FULL:
            s = max(pm[t]['champ'], 0.01)
            MARKET_ELO[t] += damp * (math.log(MARKET_FULL[t]) - math.log(s)) / b

# ----------------------------------------------------------------------------
# 8. MAIN  (four models, all full simulations, sharing the tournament machinery)
# ----------------------------------------------------------------------------
LABELS = {'elo': 'Pure Elo', 'score': 'Pure Goals',
          'hybrid': 'Hybrid', 'market': 'Hybrid + Market', 'market_pure': 'Pure Market'}

if __name__ == '__main__':
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50000
    print(f"Annex C: {len(ANNEX_C)} | rho={RHO:+.3f} home x{math.exp(HOME):.2f} c={C:.4f} total={TOTAL:.2f}")
    out = {}
    for key in ('elo', 'score', 'hybrid'):
        print(f"Running {LABELS[key]} ({n:,} sims) ...")
        out[key], _ = run(n, model=key)
    mE, b = market_implied_elo(out['elo'])
    MARKET_ELO.clear(); MARKET_ELO.update(mE)
    print("Calibrating market-implied ratings to the published odds ...")
    calibrate_market(b)
    for key in ('market', 'market_pure'):
        print(f"Running {LABELS[key]} ({n:,} sims) ...")
        out[key], _ = run(n, model=key)
    resid = max(abs(out['market_pure'][t]['champ'] - MARKET_FULL[t]) for t in MARKET_FULL)
    print(f"  pure-market max error to published odds: {resid:.2f}pp")

    order = ('elo', 'score', 'hybrid', 'market', 'market_pure')
    for key in order:
        top = sorted(out[key], key=lambda t: -out[key][t]['champ'])[:6]
        print(f"  {LABELS[key]:<22}: " + "  ".join(f"{t} {out[key][t]['champ']:.1f}" for t in top))

    # Deliberately does NOT write wc2026_results.json. That file is the product of the full pipeline:
    # make_data.py runs the Day 0 and conditioned passes and the knockout section, then merge_schedule.py
    # folds in dates and official home/away. Running this module is an engine smoke test only; writing a
    # results file here would ship a stale, schedule-less, knockout-less file the app cannot fully render.
    print("\nEngine smoke test only. To regenerate app data: python make_data.py 50000 && python merge_schedule.py")

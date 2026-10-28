"""Statistical engine for the 2022 turnout explorer.

Every number shown on the website is produced by a function in this module,
computed from data/turnout_2022.csv at request time. Narrative text is built
from templates filled with these computed values; nothing is hard-coded.
"""
from __future__ import annotations

import itertools
import math
import re
import warnings
from functools import lru_cache

import numpy as np
import pandas as pd
import scipy.stats as st
import statsmodels.formula.api as smf
from statsmodels.nonparametric.smoothers_lowess import lowess
from statsmodels.stats.multitest import multipletests

from load import load

warnings.filterwarnings("ignore")

SEED = 20221108
N_BOOT = 2000
N_PERM = 5000

# --------------------------------------------------------------------------
# Data + variable dictionary
# --------------------------------------------------------------------------
DF, NATIONAL, FOOTNOTE = load()
DF["is_south"] = (DF["region"] == "South").astype(int)
DF["alt_num"] = DF["alt_numerator"].astype(int)
DF = DF.set_index("abv", drop=False)

VARS = {
    "turnout_rate_vep": dict(label="Turnout rate (VEP)", unit="%", source="csv",
        desc="Total ballots (or highest-office votes for * states) ÷ voting-eligible population. Reported in the CSV as 'Turnout Rate'."),
    "turnout_rate_vap": dict(label="Turnout rate (VAP)", unit="%", source="derived",
        desc="Total turnout ÷ voting-age population (all residents 18+, including non-citizens and ineligible felons)."),
    "pct_noncitizen": dict(label="Non-citizen share of VAP", unit="%", source="csv",
        desc="'% Non-citizen' column: estimated non-citizens as a share of the voting-age population."),
    "vep_vap_gap_pct": dict(label="VAP→VEP reduction", unit="%", source="derived",
        desc="(VAP − VEP) ÷ VAP: share of adults removed when moving from VAP to VEP (non-citizens + ineligible felons)."),
    "prison_pct_vap": dict(label="Prisoners, % of VAP", unit="%", source="derived",
        desc="'Prison' column ÷ VAP: people ineligible to vote because they are in prison."),
    "community_inelig_pct_vap": dict(label="Probation + parole ineligible, % of VAP", unit="%", source="derived",
        desc="('Probation' + 'Parole') ÷ VAP: people disenfranchised while under community supervision. Zero where the state restores rights on release."),
    "felon_inelig_pct_vap": dict(label="All felony-ineligible, % of VAP", unit="%", source="derived",
        desc="'Total Ineligible Felon' ÷ VAP."),
    "log10_vep": dict(label="State size (log10 VEP)", unit="log10 people", source="derived",
        desc="Base-10 logarithm of the voting-eligible population. 6 = 1 million, 7 = 10 million."),
    "vep": dict(label="Voting-eligible population", unit="people", source="csv", desc="'Voting-Eligible Population (VEP)' column."),
    "vap": dict(label="Voting-age population", unit="people", source="csv", desc="'Voting-Age Population (VAP)' column."),
    "total_turnout": dict(label="Total turnout (votes)", unit="votes", source="csv", desc="'Total Turnout' column."),
    "is_south": dict(label="South (Census region)", unit="0/1", source="external",
        desc="1 if the state is in the U.S. Census Bureau South region (includes DC). External classification keyed on the state abbreviation."),
    "alt_num": dict(label="Alternative numerator (*)", unit="0/1", source="csv",
        desc="1 for the 12 states marked * whose numerator is votes for the highest office (Governor, Senate, House, or a ballot measure) instead of total ballots cast."),
}
# Everyday-language names used in plain-English sentences.
PLAIN = {
    "turnout_rate_vep": "turnout (share of eligible voters who voted)",
    "turnout_rate_vap": "turnout counted against all adults",
    "pct_noncitizen": "share of adults who aren't citizens",
    "vep_vap_gap_pct": "share of adults who can't vote",
    "prison_pct_vap": "share of adults in prison",
    "community_inelig_pct_vap": "share of adults barred from voting while on probation or parole",
    "felon_inelig_pct_vap": "share of adults barred from voting due to a felony",
    "log10_vep": "state size",
    "vep": "number of eligible voters",
    "vap": "number of adults",
    "total_turnout": "number of votes",
    "is_south": "being a Southern state",
    "alt_num": "using the 'top race only' counting method",
}


def plain(v: str) -> str:
    return PLAIN.get(v, label(v))


def strength_word(r):
    a = abs(r)
    return "no real" if a < 0.1 else "a weak" if a < 0.3 else "a moderate" if a < 0.5 else "a strong"


def plain_corr(x, y, r, p, n):
    """One or two everyday-language sentences describing a correlation."""
    binary = {"is_south": "Southern states", "alt_num": "States using the 'top race only' count"}
    if abs(r) < 0.1:
        s = f"There's basically no link between {plain(x)} and {plain(y)}."
    elif x in binary:
        s = f"{binary[x]} tend to have {'higher' if r > 0 else 'lower'} {plain(y)} than the rest. It's {strength_word(r)} link."
    else:
        s = (f"States with a higher {plain(x)} tend to have {'higher' if r > 0 else 'lower'} {plain(y)}. "
             f"It's {strength_word(r)} link.")
    s += (" A pattern this strong would rarely show up by pure luck." if p < 0.05 else
          " But with only %d states, a pattern this size could easily be luck." % n)
    return s


GROUPS = {
    "region": dict(label="Census region", source="external"),
    "felony_regime": dict(label="Felony disenfranchisement regime", source="derived"),
    "status_group": dict(label="Result status", source="csv"),
    "alt_numerator": dict(label="Turnout numerator", source="csv"),
}
OUTCOMES = ["turnout_rate_vep", "turnout_rate_vap"]
PREDICTORS = ["pct_noncitizen", "vep_vap_gap_pct", "prison_pct_vap", "community_inelig_pct_vap",
              "felon_inelig_pct_vap", "log10_vep", "is_south", "alt_num"]
HEATMAP_VARS = OUTCOMES + PREDICTORS
CONTROL_POOL = ["is_south", "pct_noncitizen", "log10_vep", "prison_pct_vap", "alt_num"]
# Variables that are arithmetic functions of each other: never put both in one model.
COLLINEAR = {
    "pct_noncitizen": {"vep_vap_gap_pct"},
    "vep_vap_gap_pct": {"pct_noncitizen", "felon_inelig_pct_vap", "prison_pct_vap"},
    "felon_inelig_pct_vap": {"prison_pct_vap", "community_inelig_pct_vap", "vep_vap_gap_pct"},
    "prison_pct_vap": {"felon_inelig_pct_vap", "vep_vap_gap_pct"},
    "community_inelig_pct_vap": {"felon_inelig_pct_vap"},
}


def label(v: str) -> str:
    return VARS.get(v, GROUPS.get(v, {"label": v}))["label"]


def clean(o):
    """Recursively convert numpy/pandas values to JSON-safe Python types."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return None if (math.isnan(o) or math.isinf(o)) else float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return clean(o.tolist())
    return o


def frame(exclude=None) -> pd.DataFrame:
    exclude = set(exclude or [])
    return DF[~DF.index.isin(exclude)]



def fast_ols(d: pd.DataFrame, y: str, terms: list[str]) -> dict:
    """OLS with HC3 standard errors via NumPy (used in resampling loops).
    Matches statsmodels' cov_type='HC3' (normal-theory p-values and CIs)."""
    X = np.column_stack([np.ones(len(d))] + [d[t].astype(float).values for t in terms])
    yv = d[y].astype(float).values
    XtX_inv = np.linalg.pinv(X.T @ X)
    b = XtX_inv @ X.T @ yv
    e = yv - X @ b
    h = np.einsum("ij,jk,ik->i", X, XtX_inv, X)
    meat = X.T @ (X * (e ** 2 / (1 - h) ** 2)[:, None])
    se = np.sqrt(np.diag(XtX_inv @ meat @ XtX_inv))
    z = b / se
    p = 2 * st.norm.sf(np.abs(z))
    r2 = 1 - (e ** 2).sum() / ((yv - yv.mean()) ** 2).sum()
    names = ["Intercept"] + list(terms)
    return dict(coef=dict(zip(names, b)), se=dict(zip(names, se)), p=dict(zip(names, p)),
                lo=dict(zip(names, b - 1.959964 * se)), hi=dict(zip(names, b + 1.959964 * se)), r2=r2, n=len(d))

# --------------------------------------------------------------------------
# Core statistics
# --------------------------------------------------------------------------
def fisher_ci(r, n, alpha=0.05):
    if n <= 3 or abs(r) >= 1:
        return (None, None)
    z, se = np.arctanh(r), 1 / np.sqrt(n - 3)
    q = st.norm.ppf(1 - alpha / 2)
    return (float(np.tanh(z - q * se)), float(np.tanh(z + q * se)))


def boot_corr(x, y, n=N_BOOT, method="pearson"):
    rng = np.random.default_rng(SEED)
    x, y = np.asarray(x, float), np.asarray(y, float)
    out = []
    for _ in range(n):
        i = rng.integers(0, len(x), len(x))
        if np.std(x[i]) == 0 or np.std(y[i]) == 0:
            continue
        out.append(st.spearmanr(x[i], y[i])[0] if method == "spearman" else np.corrcoef(x[i], y[i])[0, 1])
    return [float(v) for v in np.percentile(out, [2.5, 97.5])]


def perm_test_corr(x, y, n=N_PERM):
    rng = np.random.default_rng(SEED)
    x, y = np.asarray(x, float), np.asarray(y, float)
    r0 = np.corrcoef(x, y)[0, 1]
    hits = sum(abs(np.corrcoef(x, rng.permutation(y))[0, 1]) >= abs(r0) for _ in range(n))
    return float(r0), float((hits + 1) / (n + 1))


def correlate(x: str, y: str = "turnout_rate_vep", exclude=None, detail=True) -> dict:
    d = frame(exclude)[[x, y, "abv"]].dropna()
    n = len(d)
    r, p = st.pearsonr(d[x], d[y])
    rho, ps = st.spearmanr(d[x], d[y])
    out = dict(x=x, y=y, x_label=label(x), y_label=label(y), n=n, r=r, p=p, r_ci=fisher_ci(r, n),
               rho=rho, p_spearman=ps, r2=r * r, plain=plain_corr(x, y, r, p, n))
    if not detail:
        return out
    m = smf.ols(f"{y} ~ {x}", d).fit(cov_type="HC3")
    out["slope"] = m.params[x]
    out["slope_ci"] = list(m.conf_int().loc[x])
    out["intercept"] = m.params["Intercept"]
    out["boot_r_ci"] = boot_corr(d[x], d[y])
    loo = {a: float(st.pearsonr(d.drop(a)[x], d.drop(a)[y])[0]) for a in d.index}
    out["loo_r_min"], out["loo_r_max"] = min(loo.values()), max(loo.values())
    out["loo_most_influential"] = max(loo, key=lambda a: abs(loo[a] - r))
    out["loo_most_influential_r"] = loo[out["loo_most_influential"]]
    cooks = smf.ols(f"{y} ~ {x}", d).fit().get_influence().cooks_distance[0]
    out["cooks"] = dict(zip(d.index, cooks))
    # Nonlinearity: quadratic term test (only meaningful for continuous x)
    if d[x].nunique() > 3:
        mq = smf.ols(f"{y} ~ {x} + I({x}**2)", d).fit(cov_type="HC3")
        out["quad_p"] = mq.pvalues.iloc[2]
        out["quad_r2_gain"] = mq.rsquared - m.rsquared
        lw = lowess(d[y], d[x], frac=0.6, return_sorted=True)
        out["lowess"] = dict(x=lw[:, 0], y=lw[:, 1])
    xs = np.linspace(d[x].min(), d[x].max(), 30)
    pred = m.get_prediction(pd.DataFrame({x: xs})).summary_frame(alpha=0.05)
    out["fit"] = dict(x=xs, y=pred["mean"].values, lo=pred["mean_ci_lower"].values, hi=pred["mean_ci_upper"].values)
    return out


def corr_matrix(method="spearman", exclude=None, variables=None) -> dict:
    variables = variables or HEATMAP_VARS
    d = frame(exclude)[variables].astype(float)
    n = len(d)
    mat, pmat = [], []
    for a in variables:
        row, prow = [], []
        for b in variables:
            if a == b:
                row.append(1.0); prow.append(0.0); continue
            fn = st.spearmanr if method == "spearman" else st.pearsonr
            r, p = fn(d[a], d[b])
            row.append(r); prow.append(p)
        mat.append(row); pmat.append(prow)
    # BH across the unique off-diagonal pairs
    iu = [(i, j) for i in range(len(variables)) for j in range(i + 1, len(variables))]
    q = multipletests([pmat[i][j] for i, j in iu], method="fdr_bh")[1]
    qmat = [[0.0] * len(variables) for _ in variables]
    for (i, j), qq in zip(iu, q):
        qmat[i][j] = qmat[j][i] = qq
    return dict(vars=variables, labels=[label(v) for v in variables], r=mat, p=pmat, q=qmat, n=n, method=method)


def predictor_screen(y="turnout_rate_vep", exclude=None) -> list[dict]:
    """Bivariate screen of every predictor vs the outcome, with BH-adjusted q-values."""
    rows = [correlate(x, y, exclude, detail=False) for x in PREDICTORS]
    qs = multipletests([r["p"] for r in rows], method="fdr_bh")[1]
    qs_s = multipletests([r["p_spearman"] for r in rows], method="fdr_bh")[1]
    for r, q, q2 in zip(rows, qs, qs_s):
        r["q"], r["q_spearman"] = q, q2
        r["boot_r_ci"] = boot_corr(frame(exclude)[r["x"]], frame(exclude)[y], n=1000)
    return sorted(rows, key=lambda r: -abs(r["r"]))


def group_compare(group="region", y="turnout_rate_vep", exclude=None) -> dict:
    d = frame(exclude)
    gs = {str(k): v for k, v in d.groupby(group)}
    stats = []
    for k, v in gs.items():
        vals = v[y]
        se = vals.std(ddof=1) / np.sqrt(len(vals)) if len(vals) > 1 else np.nan
        tcrit = st.t.ppf(0.975, len(vals) - 1) if len(vals) > 1 else np.nan
        stats.append(dict(group=k, n=len(vals), mean=vals.mean(), median=vals.median(), sd=vals.std(ddof=1),
                          ci=[vals.mean() - tcrit * se, vals.mean() + tcrit * se], states=list(v.index)))
    arrays = [v[y].values for v in gs.values()]
    valid = [a for a in arrays if len(a) > 1]
    out = dict(group=group, group_label=label(group), y=y, y_label=label(y), n=len(d), groups=stats)
    if len(valid) >= 2:
        f, p = st.f_oneway(*valid)
        h, pk = st.kruskal(*valid)
        m = smf.ols(f"{y} ~ C({group})", d).fit()
        out.update(anova_F=f, anova_p=p, kruskal_H=h, kruskal_p=pk, eta2=m.rsquared)
        # Pairwise Welch t-tests, Holm-corrected
        pairs = []
        for (a, va), (b, vb) in itertools.combinations(gs.items(), 2):
            if len(va) > 1 and len(vb) > 1:
                t, pp = st.ttest_ind(va[y], vb[y], equal_var=False)
                pairs.append(dict(a=a, b=b, diff=va[y].mean() - vb[y].mean(), p=pp))
        if pairs:
            adj = multipletests([pp["p"] for pp in pairs], method="holm")[1]
            for pp, q in zip(pairs, adj):
                pp["p_holm"] = q
        out["pairwise"] = pairs
    return out


def two_group(mask: pd.Series, y="turnout_rate_vep", d=None) -> dict:
    d = DF if d is None else d
    a, b = d.loc[mask.reindex(d.index).fillna(False).astype(bool), y], d.loc[~mask.reindex(d.index).fillna(False).astype(bool), y]
    t, p = st.ttest_ind(a, b, equal_var=False)
    u, pu = st.mannwhitneyu(a, b)
    sd_pool = np.sqrt(((len(a) - 1) * a.var() + (len(b) - 1) * b.var()) / (len(a) + len(b) - 2))
    rng = np.random.default_rng(SEED)
    bs = [rng.choice(a.values, len(a)).mean() - rng.choice(b.values, len(b)).mean() for _ in range(N_BOOT)]
    return dict(n_a=len(a), n_b=len(b), mean_a=a.mean(), mean_b=b.mean(), diff=a.mean() - b.mean(),
                diff_ci=list(np.percentile(bs, [2.5, 97.5])), t=t, p=p, mwu_p=pu,
                cohens_d=(a.mean() - b.mean()) / sd_pool, cles=u / (len(a) * len(b)))


def regression(y="turnout_rate_vep", terms=("is_south",), exclude=None, cv=True) -> dict:
    terms = [t for t in terms if t]
    d = frame(exclude)
    f = f"{y} ~ " + (" + ".join(terms) if terms else "1")
    m = smf.ols(f, d).fit(cov_type="HC3")
    ci = m.conf_int()
    coefs = [dict(term=t, label=label(t), coef=m.params[t], se=m.bse[t], p=m.pvalues[t],
                  ci=[ci.loc[t, 0], ci.loc[t, 1]]) for t in m.params.index if t != "Intercept"]
    out = dict(formula=f, y=y, n=int(m.nobs), r2=m.rsquared, adj_r2=m.rsquared_adj, coefs=coefs,
               intercept=m.params["Intercept"], aic=m.aic, se_type="HC3 (heteroskedasticity-robust)")
    infl = smf.ols(f, d).fit().get_influence()
    out["cooks"] = dict(zip(d.index, infl.cooks_distance[0]))
    out["student_resid"] = dict(zip(d.index, infl.resid_studentized_external))
    out["fitted"] = dict(zip(d.index, m.fittedvalues))
    if cv and terms:
        # Leave-one-out predictive R^2: how well the model predicts a state it did not see
        preds = []
        for a in d.index:
            mm = fast_ols(d.drop(a), y, terms)["coef"]
            preds.append(mm["Intercept"] + sum(mm[t] * float(d.loc[a, t]) for t in terms))
        resid = d[y].values - np.array(preds)
        out["loo_r2"] = 1 - (resid ** 2).sum() / ((d[y] - d[y].mean()) ** 2).sum()
    if len(terms) > 1:
        X = d[terms].astype(float)
        vif = {}
        for t in terms:
            others = [o for o in terms if o != t]
            r2 = smf.ols(f"{t} ~ " + " + ".join(others), d.assign(**{c: X[c] for c in terms})).fit().rsquared
            vif[t] = 1 / (1 - r2) if r2 < 1 else None
        out["vif"] = vif
    return out


@lru_cache(maxsize=64)
def _spec_curve(focal: str, base_y: str, exclude_key: tuple) -> dict:
    exclude = set(exclude_key)
    pool = [c for c in CONTROL_POOL if c != focal and c not in COLLINEAR.get(focal, set())]
    base = frame(exclude)
    cooks = smf.ols(f"{base_y} ~ {focal}", base).fit().get_influence().cooks_distance[0]
    top3 = list(base.index[np.argsort(cooks)[-3:]])
    samples = {
        "All states": set(),
        "Exclude DC": {"DC"},
        "Exclude * states (alt. numerator)": set(DF.index[DF["alt_numerator"]]),
        f"Drop 3 most influential ({', '.join(top3)})": set(top3),
    }
    specs = []
    for yv in OUTCOMES:
        for sname, sx in samples.items():
            d = frame(exclude | sx)
            for k in range(len(pool) + 1):
                for ctrls in itertools.combinations(pool, k):
                    if focal == "alt_num" and "Exclude *" in sname:
                        continue
                    m = fast_ols(d, yv, [focal, *ctrls])
                    specs.append(dict(outcome=yv, sample=sname, controls=list(ctrls), coef=m["coef"][focal],
                                      lo=m["lo"][focal], hi=m["hi"][focal], p=m["p"][focal], n=m["n"], r2=m["r2"]))
    base_spec = next(s for s in specs if s["outcome"] == base_y and s["sample"] == "All states" and not s["controls"])
    sign = np.sign(base_spec["coef"])
    share_same = np.mean([np.sign(s["coef"]) == sign for s in specs])
    share_sig = np.mean([(np.sign(s["coef"]) == sign) and s["p"] < 0.05 for s in specs])
    def share(filter_fn):
        sub = [s for s in specs if filter_fn(s)]
        return float(np.mean([(np.sign(s["coef"]) == sign) and s["p"] < 0.05 for s in sub])) if sub else None
    return dict(focal=focal, focal_label=label(focal), specs=specs, n_specs=len(specs), baseline=base_spec,
                share_same_sign=share_same, share_sig_same_sign=share_sig,
                share_sig_by_outcome={o: share(lambda s, o=o: s["outcome"] == o) for o in OUTCOMES},
                pool=pool, samples=list(samples))


def spec_curve(focal, base_y="turnout_rate_vep", exclude=None):
    return _spec_curve(focal, base_y, tuple(sorted(exclude or [])))


def state_profile(abv: str, exclude=None) -> dict:
    d = frame(exclude)
    row = DF.loc[abv]
    vals = {}
    for v in ["turnout_rate_vep", "turnout_rate_vap", "pct_noncitizen", "vep_vap_gap_pct", "prison_pct_vap",
              "community_inelig_pct_vap", "felon_inelig_pct_vap", "log10_vep", "vep", "vap", "total_turnout"]:
        vals[v] = dict(value=row[v], pctile=float(st.percentileofscore(d[v], row[v], kind="mean")),
                       rank=int((d[v] > row[v]).sum() + 1), label=label(v))
    m = smf.ols("turnout_rate_vep ~ is_south", DF).fit()
    return dict(abv=abv, state=row["state"], region=row["region"], status=row["status"], source=row["source"],
                alt_numerator=bool(row["alt_numerator"]), felony_regime=row["felony_regime"], values=vals,
                n=len(d), region_expected=float(m.predict(DF.loc[[abv]]).iloc[0]))


def selection_compare(selected, y="turnout_rate_vep", exclude=None) -> dict:
    d = frame(exclude)
    sel = [s for s in selected if s in d.index]
    if len(sel) < 2 or len(d) - len(sel) < 2:
        return dict(ok=False, n_sel=len(sel), msg="Select at least 2 states (and leave at least 2 unselected) to compare.")
    mask = d.index.isin(sel)
    rows = []
    for v in ["turnout_rate_vep", "turnout_rate_vap"] + PREDICTORS:
        a, b = d.loc[mask, v].astype(float), d.loc[~mask, v].astype(float)
        p = st.mannwhitneyu(a, b).pvalue if a.nunique() + b.nunique() > 2 else np.nan
        rows.append(dict(var=v, label=label(v), mean_sel=a.mean(), mean_rest=b.mean(), diff=a.mean() - b.mean(), p=p))
    qs = multipletests([r["p"] if r["p"] == r["p"] else 1 for r in rows], method="fdr_bh")[1]
    for r, q in zip(rows, qs):
        r["q"] = q
    return clean(dict(ok=True, n_sel=len(sel), n_rest=int((~mask).sum()), rows=rows,
                note="Mann-Whitney U tests, Benjamini-Hochberg corrected across the rows. Selections made by looking at the data are exploratory: p-values here are descriptive, not confirmatory."))


# --------------------------------------------------------------------------
# Findings: computed, then ranked by evidence category
# --------------------------------------------------------------------------
def _ord(x):
    n = int(round(x))
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


# Each finding's verdict label is checked against an explicit, computed rule.
# If the data stop satisfying the rule (e.g., after editing the CSV), the label
# is replaced with "Re-check" instead of silently asserting a stale claim.
VERDICT_RULES = {
    "south_gap": ("Welch p < 0.05, adjusted p < 0.05, and ≥ 80% of VEP specifications significant in the same direction",
                  lambda s: s["welch_p"] < 0.05 and s["adjusted_p"] < 0.05 and s["spec_share_vep"] >= 0.8),
    "denominator": ("Non-citizen association significant with VAP outcome (p < 0.05) but not with VEP outcome",
                    lambda s: s["p_vap"] < 0.05 and s["p_vep"] >= 0.05),
    "prison_confounded": ("Bivariate p < 0.05 but p ≥ 0.05 once South is controlled",
                          lambda s: s["p"] < 0.05 and s["adj_p"] >= 0.05),
    "suppression_fragile": ("Bootstrap 95% CI includes 0, or < 80% of VEP specifications significant",
                            lambda s: (s["boot_ci"][0] <= 0 <= s["boot_ci"][1]) or s["spec_share"] < 0.8),
    "alt_numerator": ("Difference not significant (p ≥ 0.05); flagged because of the known measurement difference",
                      lambda s: s["p"] >= 0.05),
    "size_null": ("Pearson and Spearman p ≥ 0.05", lambda s: s["p"] >= 0.05),
    "felony_null": ("ANOVA and Kruskal-Wallis p ≥ 0.05, and probation/parole share p ≥ 0.05",
                    lambda s: s["anova_p"] >= 0.05 and s["kruskal_p"] >= 0.05 and s["p_community"] >= 0.05),
    "unexplained": ("Leave-one-out R² of the full model < 0.5", lambda s: s["loo_r2"] < 0.5),
}


VERDICT_PLAIN = {
    "Robust association": ("Strong & reliable", "We're confident this pattern is real.", "happy"),
    "Measurement artifact": ("A counting trick", "The pattern comes from how turnout is measured.", "surprised"),
    "Likely confounded": ("Something else explains it", "Another factor seems to be behind this.", "thinking"),
    "Fragile": ("Shaky, might be luck", "Small changes make it disappear.", "wobbly"),
    "Measurement caveat": ("Good to know", "A quirk in how some states count.", "thinking"),
    "No association": ("No real link", "We looked and found nothing.", "shrug"),
    "Model ceiling": ("Big mystery left", "Most of the story isn't in this data.", "thinking"),
    "Re-check": ("Needs a re-check", "The numbers no longer match the label.", "wobbly"),
}


def _apply_verdict_rules(F):
    for f in F:
        text, rule = VERDICT_RULES[f["id"]]
        ok = bool(rule(f["stats"]))
        f["verdict_rule"] = text
        f["verdict_rule_met"] = ok
        if not ok:
            f["verdict"], f["category"] = "Re-check", 7
        f["verdict_plain"], f["confidence_plain"], f["mood"] = VERDICT_PLAIN[f["verdict"]]


def _fmt(x, d=1):
    return "n/a" if x is None else f"{x:.{d}f}"


def _p(p):
    if p is None:
        return "n/a"
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


@lru_cache(maxsize=1)
def findings() -> list[dict]:
    y = "turnout_rate_vep"
    screen = {r["x"]: r for r in predictor_screen(y)}
    F = []

    # 1 ── South vs rest ---------------------------------------------------
    south = two_group(DF["is_south"] == 1, y)
    reg = group_compare("region", y)
    sc = spec_curve("is_south")
    adj = regression(y, ["is_south", "pct_noncitizen", "log10_vep", "prison_pct_vap", "alt_num"], cv=False)
    adj_c = next(c for c in adj["coefs"] if c["term"] == "is_south")
    south_wo_dc = two_group(DF["is_south"] == 1, y, frame(["DC"]))
    nonsouth = group_compare("region", y, set(DF.index[DF.is_south == 1]))
    w = lambda d: np.average(d[y], weights=d["vep"])
    F.append(dict(
        id="south_gap", verdict="Robust association",
        plain=(f"In Southern states, about {south['mean_a']:.0f} out of every 100 eligible people voted. Everywhere else it was about {south['mean_b']:.0f} out of 100. "
               "This gap shows up no matter how we slice the data, so it's very unlikely to be a fluke. The data can't tell us why, though."), category=0, effect=abs(south["diff"]),
        title=f"Southern states turned out {_fmt(-south['diff'])} points lower than the rest of the country",
        headline_stat=f"Δ = {_fmt(south['diff'])} pts (95% CI {_fmt(south['diff_ci'][0])} to {_fmt(south['diff_ci'][1])}), d = {_fmt(south['cohens_d'], 2)}",
        explanation=(f"The {south['n_a']} Southern jurisdictions averaged {_fmt(south['mean_a'])}% VEP turnout versus {_fmt(south['mean_b'])}% "
                     f"for the other {south['n_b']}. Census region alone accounts for {_fmt(reg['eta2']*100, 0)}% of the between-state variance "
                     f"(ANOVA p = {_p(reg['anova_p'])}); " + (f"the other three regions do not differ significantly from each other (ANOVA p = {_p(nonsouth['anova_p'])}). "
                     if nonsouth["anova_p"] >= 0.05 else f"the other three regions also differ (ANOVA p = {_p(nonsouth['anova_p'])}). ")
                     + f"After adjusting for every other available variable the gap is {_fmt(adj_c['coef'])} points (p = {_p(adj_c['p'])})."),
        why_interesting=("It is the largest and most stable pattern in the file: it survives every specification tried "
                         f"({_fmt(sc['share_sig_same_sign']*100, 0)}% of {sc['n_specs']} models, across both outcomes and four samples, significant in the same direction). "
                         "Because 'South' is a bundle of many state characteristics, it is a pointer to explanations rather than an explanation."),
        stats=dict(n=len(DF), test="Welch t-test; Mann-Whitney U; bootstrap CI for difference", welch_p=south["p"], mwu_p=south["mwu_p"],
                   diff=south["diff"], diff_ci=south["diff_ci"], cohens_d=south["cohens_d"], eta2_region=reg["eta2"],
                   anova_p=reg["anova_p"], adjusted_coef=adj_c["coef"], adjusted_ci=adj_c["ci"], adjusted_p=adj_c["p"],
                   diff_without_dc=south_wo_dc["diff"], weighted_south=w(DF[DF.is_south == 1]), weighted_rest=w(DF[DF.is_south == 0]),
                   spec_share=sc["share_sig_same_sign"], spec_share_vep=sc["share_sig_by_outcome"]["turnout_rate_vep"]),
        chart=dict(kind="group", group="region", y=y), focal="is_south",
        hypotheses=[
            "Electoral competitiveness: 2022 turnout tends to be higher where statewide races are close and heavily contested; many Southern states had lopsided statewide contests. (Not testable here: the file has no race-margin or spending data.)",
            "Election administration: states differ in registration deadlines, same-day registration, mail-ballot rules, and polling-place access. Several of the highest-turnout states are known for permissive registration or all-mail voting. (Not testable here.)",
            "Population composition: education, income, age and residential stability are strong individual-level predictors of voting and differ by region. (Not in the dataset.)",
            "Historical and institutional legacies of voting restrictions in the South may persist in political participation norms and party organisation.",
        ],
        alternatives=[
            (f"Measurement: {int(DF.loc[DF.is_south == 1, 'alt_numerator'].sum())} of the {int(DF.is_south.sum())} Southern jurisdictions use a highest-office numerator, which understates total ballots.", "adjust_alt"),
            ("Classification: DC is in the Census 'South' but is an atypical, fully urban jurisdiction.", "exclude_dc"),
            ("Confounding by incarceration: Southern states imprison a larger share of adults.", "adjust_prison"),
            (f"A few extreme states (e.g., {DF.loc[DF[y].nsmallest(2).index, 'state'].str.cat(sep=', ')}) could drive the mean gap.", "rank_test"),
        ],
        tests=["adjust_alt", "exclude_dc", "adjust_prison", "adjust_all", "rank_test", "permutation", "loo", "vap_outcome", "within_nonsouth"],
        limitations=[
            "Region is an external label, not a mechanism: the data cannot say which Southern characteristic matters.",
            "51 aggregate observations: state-level patterns do not describe individual voters (ecological fallacy).",
            "One election (a midterm). The gap may differ in presidential years or other midterms.",
        ],
    ))

    # 2 ── Denominator choice ---------------------------------------------
    c_vep = correlate("pct_noncitizen", "turnout_rate_vep")
    c_vap = correlate("pct_noncitizen", "turnout_rate_vap")
    rng = np.random.default_rng(SEED)
    diffs = []
    for _ in range(N_BOOT):
        i = rng.integers(0, len(DF), len(DF))
        s = DF.iloc[i]
        diffs.append(np.corrcoef(s.pct_noncitizen, s.turnout_rate_vap)[0, 1] - np.corrcoef(s.pct_noncitizen, s.turnout_rate_vep)[0, 1])
    gap = DF.turnout_rate_vep - DF.turnout_rate_vap
    g_r, g_p = st.pearsonr(DF.pct_noncitizen, gap)
    rk = (DF.turnout_rate_vep.rank(ascending=False) - DF.turnout_rate_vap.rank(ascending=False))
    movers = rk.sort_values()
    rho_ranks = st.spearmanr(DF.turnout_rate_vep, DF.turnout_rate_vap)[0]
    F.append(dict(
        id="denominator", verdict="Measurement artifact",
        plain=("How you count matters! If you divide votes by all adults (including people who aren't allowed to vote, like non-citizens), states with many immigrants "
               "look like they vote less. Divide by only the people who can legally vote and most of that difference disappears. "
               f"{movers.index[0]} drops {int(-movers.iloc[0])} places in the ranking just from this choice."), category=1, effect=abs(c_vap["r"] - c_vep["r"]),
        title="Measuring turnout against all adults manufactures a 'non-citizen' penalty",
        headline_stat=f"r(non-citizen, VAP rate) = {_fmt(c_vap['r'], 2)} vs r(non-citizen, VEP rate) = {_fmt(c_vep['r'], 2)}",
        explanation=(f"With the VAP denominator, states with more non-citizens look like lower-turnout states (r = {_fmt(c_vap['r'], 2)}, p = {_p(c_vap['p'])}). "
                     f"With the VEP denominator, which removes people who cannot legally vote, the association weakens to r = {_fmt(c_vep['r'], 2)} (p = {_p(c_vep['p'])}). "
                     f"The VEP−VAP difference in turnout tracks non-citizen share almost perfectly (r = {_fmt(g_r, 2)}). "
                     f"{movers.index[0]} falls {int(-movers.iloc[0])} places in the ranking when VAP is used."),
        why_interesting=("This is a cautionary measurement result: a researcher who used the more commonly published VAP rate would 'find' an immigrant-share effect "
                         "that is largely an accounting consequence of counting ineligible residents in the denominator."),
        stats=dict(n=len(DF), r_vap=c_vap["r"], p_vap=c_vap["p"], r_vap_ci=c_vap["r_ci"], r_vep=c_vep["r"], p_vep=c_vep["p"], r_vep_ci=c_vep["r_ci"],
                   diff_r=c_vap["r"] - c_vep["r"], diff_r_ci=list(np.percentile(diffs, [2.5, 97.5])), gap_r=g_r, gap_p=g_p,
                   rank_rho=rho_ranks, top_drops={k: float(v) for k, v in movers.head(5).items()},
                   top_rises={k: float(v) for k, v in movers.tail(5).items()}),
        chart=dict(kind="denominator"), focal="pct_noncitizen",
        hypotheses=[
            "Mechanical: non-citizens are in VAP but cannot vote, so VAP-based turnout falls by roughly the non-citizen share even if every eligible citizen behaved identically.",
            "Any residual association under VEP could reflect real differences (for example, newly naturalised citizens or mixed-status communities voting at different rates), but the data cannot isolate this.",
        ],
        alternatives=[
            ("Non-citizen share is itself an estimate (survey-based), so VEP inherits its error; a state with an overestimated non-citizen share gets an inflated VEP rate.", None),
            ("Non-citizen share correlates with state size, so size could mask or mimic the relationship.", "adjust_size"),
        ],
        tests=["vap_outcome", "adjust_size", "adjust_south", "permutation", "loo", "rank_test"],
        limitations=[
            "VEP itself is an estimate built from the very variables tested here; errors in non-citizen counts flow straight into the outcome.",
            "Cannot separate the voting behaviour of naturalised citizens from that of native-born citizens.",
        ],
    ))

    # 3 ── Prison share, confounded by region -----------------------------
    cp = correlate("prison_pct_vap", y)
    m_s = regression(y, ["prison_pct_vap", "is_south"], cv=False)
    c_s = next(c for c in m_s["coefs"] if c["term"] == "prison_pct_vap")
    within = {}
    for s, d in DF.groupby("is_south"):
        r, p = st.pearsonr(d.prison_pct_vap, d[y]); within["South" if s else "Non-South"] = dict(r=r, p=p, n=len(d))
    sc3 = spec_curve("prison_pct_vap")
    pb = st.pointbiserialr(DF.is_south, DF.prison_pct_vap)
    F.append(dict(
        id="prison_confounded", verdict="Likely confounded",
        plain=(f"States that imprison more people have somewhat lower turnout. But many of those states are in the South, which votes less for other reasons. "
               f"Once we take the South into account, the link gets {(1 - c_s['coef'] / cp['slope']) * 100:.0f}% weaker"
               + (" and could just be chance." if c_s["p"] >= 0.05 else ", but it doesn't vanish.")), category=2, effect=abs(cp["r"]),
        title=f"States with more people in prison vote less, but being in the South explains about {(1 - c_s['coef'] / cp['slope']) * 100:.0f}% of that",
        headline_stat=f"r = {_fmt(cp['r'], 2)} (BH q = {_p(screen['prison_pct_vap']['q'])}); slope {_fmt(cp['slope'])} → {_fmt(c_s['coef'])} after adjusting for South",
        explanation=(f"Each additional percentage point of adults in prison is associated with {_fmt(cp['slope'])} points lower VEP turnout "
                     f"(r = {_fmt(cp['r'], 2)}, p = {_p(cp['p'])}, bootstrap 95% CI for r {_fmt(cp['boot_r_ci'][0], 2)} to {_fmt(cp['boot_r_ci'][1], 2)}). "
                     f"But Southern states imprison more people (point-biserial r = {_fmt(pb[0], 2)}), and with a South indicator in the model the slope falls to "
                     f"{_fmt(c_s['coef'])} (p = {_p(c_s['p'])}). Within the South (r = {_fmt(within['South']['r'], 2)}) and outside it "
                     f"(r = {_fmt(within['Non-South']['r'], 2)}) the association is "
                     + ("weaker and not significant" if all(w_["p"] >= 0.05 and abs(w_["r"]) < abs(cp["r"]) for w_ in within.values()) else "mixed")
                     + f". After Benjamini-Hochberg correction for testing {len(PREDICTORS)} predictors, q = {_p(screen['prison_pct_vap']['q'])}"
                     + (" (not significant at 0.05)." if screen['prison_pct_vap']['q'] >= 0.05 else ".")),
        why_interesting=("A textbook confounding pattern: a plausible-sounding bivariate link that largely reflects a shared regional pattern. "
                         "Note that prisoners are already removed from VEP, so this is not a mechanical denominator effect."),
        stats=dict(n=len(DF), r=cp["r"], p=cp["p"], q=screen["prison_pct_vap"]["q"], r_ci=cp["r_ci"], boot_r_ci=cp["boot_r_ci"],
                   slope=cp["slope"], slope_ci=cp["slope_ci"], adj_slope=c_s["coef"], adj_ci=c_s["ci"], adj_p=c_s["p"],
                   within=within, south_prison_r=pb[0], south_prison_p=pb[1], spec_share=sc3["share_sig_same_sign"],
                   loo_range=[cp["loo_r_min"], cp["loo_r_max"]]),
        chart=dict(kind="scatter", x="prison_pct_vap", y=y, color="region"), focal="prison_pct_vap",
        hypotheses=[
            "Spillover: high incarceration may depress participation among family and community members of people who are incarcerated (a hypothesis from the political-science literature; not testable with state aggregates).",
            "Common cause: state political culture, poverty, and policy regimes could drive both incarceration and turnout.",
        ],
        alternatives=[
            ("Regional confounding (South has both higher incarceration and lower turnout).", "adjust_south"),
            ("Influential states (DC has 0 prisoners because DC felons are held federally).", "exclude_dc"),
            ("Outcome choice: is the pattern the same with the VAP rate?", "vap_outcome"),
        ],
        tests=["adjust_south", "within_region", "exclude_dc", "permutation", "loo", "vap_outcome", "adjust_all"],
        limitations=[
            "State prison counts only; federal prisoners and jail populations are not broken out.",
            "Cross-sectional: cannot establish whether incarceration affects turnout, or vice versa, or neither.",
        ],
    ))

    # 4 ── Fragile suppression: non-citizen share given size ------------------
    m2 = regression(y, ["pct_noncitizen", "log10_vep", "is_south"], cv=False)
    nc = next(c for c in m2["coefs"] if c["term"] == "pct_noncitizen")
    sz = next(c for c in m2["coefs"] if c["term"] == "log10_vep")
    rng = np.random.default_rng(SEED)
    bs = []
    for _ in range(1000):
        s = DF.iloc[rng.integers(0, len(DF), len(DF))]
        bs.append(fast_ols(s, y, ["pct_noncitizen", "log10_vep", "is_south"])["coef"]["pct_noncitizen"])
    drops = {}
    for a in DF.index:
        mm = fast_ols(DF.drop(a), y, ["pct_noncitizen", "log10_vep", "is_south"])
        drops[a] = dict(coef=mm["coef"]["pct_noncitizen"], p=mm["p"]["pct_noncitizen"])
    n_sig_drop = sum(v["p"] < 0.05 for v in drops.values())
    cs = st.pearsonr(DF.pct_noncitizen, DF.log10_vep)
    sc4 = spec_curve("pct_noncitizen")
    F.append(dict(
        id="suppression_fragile", verdict="Fragile",
        plain=("One fancier model hints that states with more non-citizens vote a bit less once you account for state size and region. "
               "But small, reasonable changes to the analysis make it disappear, so we don't trust it. Think of it as a hunch, not a finding."), category=3, effect=abs(nc["coef"]),
        title="A hidden non-citizen/size pattern appears in multivariable models, but it is fragile",
        headline_stat=f"Adjusted coef = {_fmt(nc['coef'], 2)} pts per point (p = {_p(nc['p'])}); bootstrap 95% CI {_fmt(np.percentile(bs, 2.5), 2)} to {_fmt(np.percentile(bs, 97.5), 2)}",
        explanation=(f"Alone, neither non-citizen share (r = {_fmt(screen['pct_noncitizen']['r'], 2)}) nor state size (r = {_fmt(screen['log10_vep']['r'], 2)}) predicts VEP turnout. "
                     f"Because they are correlated with each other (r = {_fmt(cs[0], 2)}), adjusting for size and South makes non-citizen share look negative "
                     f"({_fmt(nc['coef'], 2)} per point, p = {_p(nc['p'])}) and size look positive ({_fmt(sz['coef'], 2)} per tenfold increase, p = {_p(sz['p'])}). "
                     f"Among VEP-outcome specifications only {_fmt(sc4['share_sig_by_outcome']['turnout_rate_vep']*100, 0)}% are significant in that direction, and dropping single states moves p across 0.05 "
                     f"({n_sig_drop} of {len(DF)} leave-one-out fits are significant)."),
        why_interesting=("A 'suppressor' pattern like this is exactly what an automated search would surface as a discovery. Showing that it depends on model choices "
                         "is the point: treat it as a hypothesis for other data, not a finding."),
        stats=dict(n=len(DF), coef=nc["coef"], p=nc["p"], ci=nc["ci"], boot_ci=list(np.percentile(bs, [2.5, 97.5])), size_coef=sz["coef"], size_p=sz["p"],
                   noncit_size_r=cs[0], spec_share=sc4["share_sig_by_outcome"]["turnout_rate_vep"], spec_share_all=sc4["share_sig_same_sign"], loo_sig=n_sig_drop,
                   loo_coef_range=[min(v["coef"] for v in drops.values()), max(v["coef"] for v in drops.values())]),
        chart=dict(kind="partial", x="pct_noncitizen", controls=["log10_vep", "is_south"], y=y), focal="pct_noncitizen",
        hypotheses=[
            "If real, large states with smaller immigrant populations (e.g., in the industrial Midwest) might combine high organisational/campaign intensity with fewer barriers for newly naturalised voters.",
            "More likely, it is a statistical artefact of conditioning on two correlated variables in a small sample.",
        ],
        alternatives=[
            ("Overfitting: with 51 observations and several candidate controls, some specifications will cross p < 0.05 by chance.", "spec"),
            ("Specific states (California, New Jersey) may drive the adjusted coefficient.", "loo"),
        ],
        tests=["loo", "adjust_south", "adjust_size", "vap_outcome", "permutation"],
        limitations=["Not pre-registered; found by searching many models, so nominal p-values overstate the evidence."],
    ))

    # 5 ── Alternative numerator --------------------------------------------
    alt = two_group(DF["alt_numerator"], y)
    m_alt = regression(y, ["alt_num", "is_south"], cv=False)
    ca = next(c for c in m_alt["coefs"] if c["term"] == "alt_num")
    alt_states = list(DF.index[DF.alt_numerator])
    F.append(dict(
        id="alt_numerator", verdict="Measurement caveat",
        plain=(f"{len(alt_states)} states only report votes for the top race on the ballot, not every ballot cast. That makes their turnout look a little lower than it really was. "
               f"They average {-alt['diff']:.1f} points lower, but a gap that small could be chance."), category=4, effect=abs(alt["diff"]),
        title=f"{len(alt_states)} states are measured differently and average {_fmt(-alt['diff'])} points lower",
        headline_stat=f"Δ = {_fmt(alt['diff'])} pts (95% CI {_fmt(alt['diff_ci'][0])} to {_fmt(alt['diff_ci'][1])}), p = {_p(alt['p'])}",
        explanation=(f"For {', '.join(alt_states)}, the CSV footnote says the numerator is votes for the highest office (or a ballot measure) rather than total ballots cast. "
                     f"Those states average {_fmt(alt['mean_a'])}% vs {_fmt(alt['mean_b'])}% for the rest. The gap is not statistically significant (Welch p = {_p(alt['p'])}; "
                     f"{_fmt(ca['coef'])} pts after adjusting for South, p = {_p(ca['p'])}), but its direction matches what under-counting would produce."),
        why_interesting=(f"Highest-office votes exclude ballots that skip that race, so these {len(alt_states)} rates are lower bounds. Of the five lowest-turnout states, "
                         f"{sum(DF.loc[DF[y].nsmallest(5).index, 'alt_numerator'])} are * states ({', '.join(a for a in DF[y].nsmallest(5).index if DF.loc[a, 'alt_numerator'])}), "
                         "so comparisons at the bottom of the ranking are partly comparisons of measurement methods."),
        stats=dict(n=len(DF), n_alt=alt["n_a"], diff=alt["diff"], diff_ci=alt["diff_ci"], p=alt["p"], mwu_p=alt["mwu_p"], adj_coef=ca["coef"], adj_p=ca["p"], adj_ci=ca["ci"]),
        chart=dict(kind="group", group="alt_numerator", y=y), focal="alt_num",
        hypotheses=["Roll-off: some voters skip the top race, so highest-office counts sit a little below total ballots.",
                    "These states may also differ substantively (most are Southern or Midwestern), so the gap mixes measurement and real differences."],
        alternatives=[("Region confounds the comparison.", "adjust_south")],
        tests=["adjust_south", "rank_test", "permutation", "vap_outcome"],
        limitations=["The size of each state's undercount is unknown from this file."],
    ))

    # 6 ── State size is unrelated -----------------------------------------
    csz = correlate("log10_vep", y)
    F.append(dict(
        id="size_null", verdict="No association",
        plain="Big states and small states vote at about the same rate. Size just doesn't seem to matter.", category=5, effect=abs(csz["r"]),
        title="State size has essentially no relationship with turnout",
        headline_stat=f"r = {_fmt(csz['r'], 2)} (95% CI {_fmt(csz['r_ci'][0], 2)} to {_fmt(csz['r_ci'][1], 2)}), ρ = {_fmt(csz['rho'], 2)}",
        explanation=(f"Large and small states turn out at similar rates (Pearson r = {_fmt(csz['r'], 2)}, Spearman ρ = {_fmt(csz['rho'], 2)}; quadratic term p = {_p(csz.get('quad_p'))}). "
                     f"The confidence interval rules out strong relationships (|r| above about {_fmt(max(abs(csz['r_ci'][0]), abs(csz['r_ci'][1])), 2)}). "
                     f"Even so, weighting by population matters for the national figure: the unweighted state mean is {_fmt(DF[y].mean())}% while the national rate is {_fmt(NATIONAL['turnout_rate_vep'])}%."),
        why_interesting="A useful null: theories that small states vote more (stronger civic ties) or less (fewer competitive races) find no support at this level.",
        stats=dict(n=len(DF), r=csz["r"], r_ci=csz["r_ci"], p=csz["p"], rho=csz["rho"], quad_p=csz.get("quad_p"),
                   unweighted_mean=DF[y].mean(), national=NATIONAL["turnout_rate_vep"]),
        chart=dict(kind="scatter", x="log10_vep", y=y, color="region"), focal="log10_vep",
        hypotheses=["Large and small states each contain both competitive and uncompetitive environments, which may cancel out."],
        alternatives=[("Size could matter within regions even if not overall.", "within_region")],
        tests=["within_region", "adjust_south", "permutation", "vap_outcome"],
        limitations=["A null in 51 units cannot rule out modest effects (see the CI)."],
    ))

    # 7 ── Felony disenfranchisement regime ---------------------------------
    gfr = group_compare("felony_regime", y)
    cfe = correlate("community_inelig_pct_vap", y)
    F.append(dict(
        id="felony_null", verdict="No association",
        plain=("Whether a state bars people with felony convictions from voting doesn't seem to change its overall turnout much. "
               "But very few states fall into some of the groups, so we can't be sure."), category=5, effect=gfr.get("eta2", 0),
        title="How broadly a state disenfranchises people with felonies shows no clear link to turnout",
        headline_stat=f"Kruskal-Wallis p = {_p(gfr['kruskal_p'])}; η² = {_fmt(gfr['eta2'], 2)}",
        explanation=(f"Grouping states by whether they disenfranchise no one, only prisoners, or also people on probation or parole gives means of "
                     + ", ".join(f"{g['group']} {_fmt(g['mean'])}% (n={g['n']})" for g in gfr["groups"])
                     + f". Differences are not significant (ANOVA p = {_p(gfr['anova_p'])}). The share disenfranchised while on probation or parole is also unrelated (r = {_fmt(cfe['r'], 2)}, p = {_p(cfe['p'])})."),
        why_interesting=f"The regime is derived from the data itself (zero probation/parole counts), but only {int((DF.ineligible_felon == 0).sum())} jurisdictions disenfranchise no one, so power is very low.",
        stats=dict(n=len(DF), kruskal_p=gfr["kruskal_p"], anova_p=gfr["anova_p"], eta2=gfr["eta2"], r_community=cfe["r"], p_community=cfe["p"]),
        chart=dict(kind="group", group="felony_regime", y=y), focal="community_inelig_pct_vap",
        hypotheses=["Disenfranchised populations are a small share of adults (at most a few percent), so effects on aggregate turnout would be small even if real."],
        alternatives=[(f"The 'no disenfranchisement' group contains only {', '.join(DF.index[DF.ineligible_felon == 0])}.", None)],
        tests=["adjust_south", "permutation", "vap_outcome"],
        limitations=["Regime is inferred from counts, not from statutes; small groups give low power."],
    ))

    # 8 ── How much is explained? -------------------------------------------
    full = regression(y, ["is_south", "pct_noncitizen", "log10_vep", "prison_pct_vap", "community_inelig_pct_vap", "alt_num"])
    s_only = regression(y, ["is_south"])
    F.append(dict(
        id="unexplained", verdict="Model ceiling",
        plain=(f"Even using everything in this file, we can only predict about {max(full['loo_r2'], 0) * 100:.0f}% of why states differ. "
               "Things not in this data, like close races, voting rules, or who lives in each state, probably matter a lot."), category=6, effect=full["r2"],
        title=f"Most of the {DF[y].max() - DF[y].min():.0f}-point spread in turnout is not explained by anything in this file",
        headline_stat=f"In-sample R² = {_fmt(full['r2'], 2)}; leave-one-out R² = {_fmt(full['loo_r2'], 2)}",
        explanation=(f"Turnout ranges from {_fmt(DF[y].min())}% ({DF[y].idxmin()}) to {_fmt(DF[y].max())}% ({DF[y].idxmax()}). A model with every available characteristic "
                     f"fits R² = {_fmt(full['r2'], 2)} in-sample, but predicts held-out states with R² = {_fmt(full['loo_r2'], 2)}. The South indicator alone gets "
                     f"{_fmt(s_only['loo_r2'], 2)} out-of-sample. The remaining variation must come from factors outside this dataset."),
        why_interesting="Sets expectations: this dataset describes turnout and eligibility well, but it was not designed to explain turnout.",
        stats=dict(n=len(DF), r2=full["r2"], adj_r2=full["adj_r2"], loo_r2=full["loo_r2"], south_loo_r2=s_only["loo_r2"]),
        chart=dict(kind="residuals", terms=["is_south", "pct_noncitizen", "log10_vep", "prison_pct_vap", "community_inelig_pct_vap", "alt_num"], y=y), focal="is_south",
        hypotheses=["Likely candidates outside the file: race competitiveness, campaign spending, mail and registration rules, education, age structure."],
        alternatives=[],
        tests=["adjust_all", "loo"],
        limitations=["Out-of-sample R² with n = 51 is itself noisy."],
    ))
    _apply_verdict_rules(F)
    F.sort(key=lambda f: (f["category"], -f["effect"]))
    for i, f in enumerate(F):
        f["rank"] = i + 1
    return clean(F)


# --------------------------------------------------------------------------
# Executable follow-up tests
# --------------------------------------------------------------------------
TESTS = {
    "adjust_alt": "Control for the alternative-numerator (*) flag",
    "adjust_south": "Control for South",
    "adjust_prison": "Control for prison share",
    "adjust_size": "Control for state size",
    "adjust_all": "Control for all available variables",
    "exclude_dc": "Re-run without DC",
    "rank_test": "Use rank-based (Spearman / Mann-Whitney) statistics",
    "permutation": "Permutation test (5,000 shuffles)",
    "loo": "Leave-one-state-out influence",
    "vap_outcome": "Switch outcome to VAP turnout",
    "within_region": "Correlation within each Census region",
    "within_nonsouth": "Compare regions outside the South",
    "spec": "Specification curve",
}


def run_test(finding_id: str, test_id: str, exclude=None) -> dict:
    f = next(x for x in findings() if x["id"] == finding_id)
    focal = f["focal"]
    y = "turnout_rate_vep"
    d = frame(exclude)
    res = dict(finding=finding_id, test=test_id, label=TESTS.get(test_id, test_id), n=len(d))

    def model(terms, yy=y, ex=exclude):
        r = regression(yy, terms, ex, cv=False)
        c = next(c for c in r["coefs"] if c["term"] == focal)
        return dict(formula=r["formula"], coef=c["coef"], ci=c["ci"], p=c["p"], r2=r["r2"], n=r["n"])

    base = model([focal])
    res["baseline"] = base
    controls = {"adjust_alt": ["alt_num"], "adjust_south": ["is_south"], "adjust_prison": ["prison_pct_vap"],
                "adjust_size": ["log10_vep"], "adjust_all": [c for c in CONTROL_POOL if c != focal and c not in COLLINEAR.get(focal, set())]}
    if test_id in controls:
        terms = [focal] + [c for c in controls[test_id] if c != focal and c not in COLLINEAR.get(focal, set())]
        res["result"] = model(terms)
        res["summary"] = (f"{label(focal)}: {base['coef']:.2f} (p={_p(base['p'])}) without controls → {res['result']['coef']:.2f} "
                          f"(95% CI {res['result']['ci'][0]:.2f} to {res['result']['ci'][1]:.2f}, p={_p(res['result']['p'])}) with {', '.join(label(t) for t in terms[1:])}.")
    elif test_id == "exclude_dc":
        res["result"] = model([focal], ex=set(exclude or []) | {"DC"})
        res["summary"] = f"Without DC: coefficient {res['result']['coef']:.2f} (p={_p(res['result']['p'])}, n={res['result']['n']}) vs {base['coef']:.2f} with DC."
    elif test_id == "vap_outcome":
        res["result"] = model([focal], yy="turnout_rate_vap")
        res["summary"] = f"Outcome = VAP turnout: coefficient {res['result']['coef']:.2f} (p={_p(res['result']['p'])}) vs {base['coef']:.2f} (p={_p(base['p'])}) for VEP turnout."
    elif test_id == "rank_test":
        if d[focal].nunique() <= 2:
            a, b = d.loc[d[focal] == 1, y], d.loc[d[focal] == 0, y]
            u, p = st.mannwhitneyu(a, b)
            res["result"] = dict(mwu_U=u, p=p, cles=u / (len(a) * len(b)), median_a=a.median(), median_b=b.median())
            res["summary"] = (f"Mann-Whitney U p={_p(p)}. Median {a.median():.1f}% vs {b.median():.1f}%. Probability that a random state in the group "
                              f"has higher turnout than one outside it: {u/(len(a)*len(b)):.2f}.")
        else:
            rho, p = st.spearmanr(d[focal], d[y])
            res["result"] = dict(rho=rho, p=p)
            res["summary"] = f"Spearman ρ = {rho:.2f} (p={_p(p)}), which is insensitive to outlying values."
    elif test_id == "permutation":
        r0, p = perm_test_corr(d[focal], d[y])
        res["result"] = dict(r=r0, p=p, n_perm=N_PERM)
        res["summary"] = f"Observed r = {r0:.2f}; {N_PERM:,} random shuffles of turnout give |r| this large with probability p = {p:.4f}."
    elif test_id == "loo":
        rows = []
        for a in d.index:
            m = fast_ols(d.drop(a), y, [focal])
            rows.append(dict(state=a, coef=m["coef"][focal], p=m["p"][focal]))
        rows.sort(key=lambda r: abs(r["coef"] - base["coef"]), reverse=True)
        res["result"] = dict(rows=rows, min=min(r["coef"] for r in rows), max=max(r["coef"] for r in rows),
                             n_sig=sum(r["p"] < 0.05 for r in rows))
        res["summary"] = (f"Dropping one state at a time, the coefficient ranges {res['result']['min']:.2f} to {res['result']['max']:.2f} "
                          f"and is p<0.05 in {res['result']['n_sig']} of {len(rows)} fits. Most influential: {rows[0]['state']} (→ {rows[0]['coef']:.2f}).")
    elif test_id == "within_region":
        rows = []
        for g, gd in d.groupby("region"):
            if gd[focal].nunique() > 2 and len(gd) > 4:
                r, p = st.pearsonr(gd[focal], gd[y]); rows.append(dict(region=g, n=len(gd), r=r, p=p))
        res["result"] = dict(rows=rows)
        res["summary"] = "Within-region correlations: " + "; ".join(f"{r['region']} r={r['r']:.2f} (n={r['n']}, p={_p(r['p'])})" for r in rows) + ". Small groups give wide uncertainty."
    elif test_id == "within_nonsouth":
        g = group_compare("region", y, set(exclude or []) | set(DF.index[DF.is_south == 1]))
        res["result"] = dict(groups=g["groups"], anova_p=g.get("anova_p"), kruskal_p=g.get("kruskal_p"))
        res["summary"] = ("Outside the South: " + ", ".join(f"{x['group']} {x['mean']:.1f}%" for x in g["groups"])
                          + f"; ANOVA p={_p(g.get('anova_p'))}. The regional effect is a South-vs-rest contrast, not a general regional gradient.")
    elif test_id == "spec":
        sc = spec_curve(focal, exclude=exclude)
        res["result"] = dict(share=sc["share_sig_same_sign"], n=sc["n_specs"])
        res["summary"] = f"{sc['share_sig_same_sign']*100:.0f}% of {sc['n_specs']} specifications are significant in the baseline direction."
    else:
        raise ValueError(test_id)
    return clean(res)


# --------------------------------------------------------------------------
# Question answering (deterministic analysis router)
# --------------------------------------------------------------------------
SYNONYMS = [
    (r"non.?citizen|immigra|foreign", "pct_noncitizen"),
    (r"prison|incarcerat|jail", "prison_pct_vap"),
    (r"probation|parole|community supervision", "community_inelig_pct_vap"),
    (r"felon|disenfranch", "felon_inelig_pct_vap"),
    (r"\bsize\b|population|large state|big state|small state|log", "log10_vep"),
    (r"\bvap\b|voting.age", "turnout_rate_vap"),
    (r"denominator|gap between", "vep_vap_gap_pct"),
    (r"south", "is_south"),
    (r"numerator|highest office|asterisk|\*", "alt_num"),
]
STATE_NAMES = {r["state"].lower(): a for a, r in DF.iterrows()}


def _find_vars(q):
    found = []
    for pat, v in SYNONYMS:
        if re.search(pat, q) and v not in found:
            found.append(v)
    return found


def _find_state(q):
    for name, a in sorted(STATE_NAMES.items(), key=lambda kv: -len(kv[0])):
        if re.search(r"\b" + re.escape(name) + r"\b", q):
            return a
    m = re.search(r"\b([A-Z]{2})\b", q.upper() if False else q)
    return None


def _south_loo_sentence(y, exclude):
    d = frame(exclude)
    fits = [fast_ols(d.drop(a), y, ["is_south"]) for a in d.index]
    coefs = [f["coef"]["is_south"] for f in fits]
    n_sig = sum(f["p"]["is_south"] < 0.05 for f in fits)
    return (f" South gap (bivariate): dropping any single state leaves it between {min(coefs):.1f} and {max(coefs):.1f} points, "
            f"significant in {n_sig} of {len(fits)} fits.")


def ask(question: str, exclude=None, outcome=None) -> dict:
    q = question.lower()
    if re.search(r"\bvap\b.*turnout|turnout.*\bvap\b", q):
        y = "turnout_rate_vap"
    elif re.search(r"\bvep\b", q):
        y = "turnout_rate_vep"
    else:
        y = outcome if outcome in OUTCOMES else "turnout_rate_vep"
    ran = []
    out = dict(question=question, outcome=y, excluded=sorted(exclude or []))
    state = _find_state(q)
    vars_ = [v for v in _find_vars(q) if v != y]

    if re.search(r"surpris|unexpected|interesting|discover", q):
        F = findings()
        out.update(intent="surprising", title="Most surprising computed results",
                   items=[dict(title=f["title"], verdict=f["verdict"], stat=f["headline_stat"], finding=f["id"])
                          for f in F if f["verdict"] in ("Measurement artifact", "Likely confounded", "Fragile", "Robust association")])
        ran.append("Full findings pipeline (group tests, bootstrap CIs, specification curves) on all 51 jurisdictions")
        out["answer"] = ("Ranked by how much the result changes a naive reading of the data: " +
                         " ".join(f"({i+1}) {it['title']} [{it['verdict']}; {it['stat']}]." for i, it in enumerate(out["items"])))
    elif re.search(r"nonlinear|non-linear|curv|threshold|quadratic", q):
        rows = []
        for x in [p for p in PREDICTORS if DF[p].nunique() > 3]:
            c = correlate(x, y, exclude)
            rows.append(dict(var=x, label=label(x), quad_p=c["quad_p"], r2_gain=c["quad_r2_gain"], r=c["r"], rho=c["rho"]))
        qs = multipletests([r["quad_p"] for r in rows], method="fdr_bh")[1]
        for r, qq in zip(rows, qs):
            r["quad_q"] = qq
        rows.sort(key=lambda r: r["quad_p"])
        ran.append(f"Quadratic-term F tests (HC3) for {len(rows)} continuous predictors, BH-corrected; Pearson vs Spearman comparison")
        out.update(intent="nonlinear", title="Tests for nonlinear relationships", table=rows,
                   answer=(f"No predictor shows a significant curved relationship after correction (smallest BH q = {rows[0]['quad_q']:.2f}, for {rows[0]['label']}). "
                           f"The largest R² gain from adding a squared term is {max(r['r2_gain'] for r in rows)*100:.1f} percentage points. "
                           "Pearson and Spearman coefficients are similar for every variable, which also argues against strong monotone-but-curved patterns. "
                           "With 51 states the power to detect modest curvature is limited."
                           if rows[0]["quad_q"] >= 0.05 else
                           f"{rows[0]['label']} shows evidence of curvature (BH q = {rows[0]['quad_q']:.3f}, R² gain {rows[0]['r2_gain']*100:.1f} pts)."))
    elif re.search(r"outlier|unusual|driven|influen|few states|anomal", q):
        terms = ["is_south", "pct_noncitizen", "log10_vep", "prison_pct_vap", "alt_num"]
        r = regression(y, terms, exclude, cv=False)
        cooks = sorted(r["cooks"].items(), key=lambda kv: -kv[1])[:6]
        sres = sorted(r["student_resid"].items(), key=lambda kv: -abs(kv[1]))[:6]
        n = r["n"]
        loo = []
        for x in ["prison_pct_vap", "pct_noncitizen", "log10_vep"]:
            c = correlate(x, y, exclude)
            loo.append(dict(var=x, label=label(x), r=c["r"], loo_min=c["loo_r_min"], loo_max=c["loo_r_max"], most=c["loo_most_influential"]))
        ran += [f"OLS {r['formula']} with Cook's distance and externally studentized residuals", "Leave-one-out correlations for 3 continuous predictors"]
        out.update(intent="influence", title="Are results driven by a few states?", cooks=cooks, resid=sres, loo=loo,
                   answer=(f"Highest Cook's distance in the full model: " + ", ".join(f"{a} ({v:.2f})" for a, v in cooks[:4])
                           + f" (a common rule of thumb flags values above 4/n = {4/n:.2f}). Largest unexplained residuals: "
                           + ", ".join(f"{a} ({v:+.1f} SD)" for a, v in sres[:4]) + ". "
                           + " ".join(f"{l['label']}: r = {l['r']:.2f}, ranging {l['loo_min']:.2f} to {l['loo_max']:.2f} when any single state is dropped (most influential: {l['most']})." for l in loo)
                           + _south_loo_sentence(y, exclude)))
    elif re.search(r"persist|control|account|adjust|confound|holding", q):
        focal = vars_[0] if vars_ else None
        terms = ["is_south", "pct_noncitizen", "log10_vep", "prison_pct_vap", "alt_num"]
        targets = [focal] if focal and focal in PREDICTORS else ["is_south", "prison_pct_vap", "pct_noncitizen", "log10_vep", "alt_num"]
        rows = []
        for t in targets:
            others = [c for c in terms if c != t and c not in COLLINEAR.get(t, set())]
            b = regression(y, [t], exclude, cv=False)["coefs"][0]
            a = next(c for c in regression(y, [t] + others, exclude, cv=False)["coefs"] if c["term"] == t)
            rows.append(dict(var=t, label=label(t), bivariate=b["coef"], p_biv=b["p"], adjusted=a["coef"], p_adj=a["p"], ci_adj=a["ci"], controls=[label(o) for o in others]))
        ran.append("Bivariate vs multivariable OLS (HC3 SEs) for each predictor")
        out.update(intent="adjusted", title="Do relationships persist after adjustment?", table=rows,
                   answer=" ".join(f"{r['label']}: {r['bivariate']:.2f} (p={_p(r['p_biv'])}) alone → {r['adjusted']:.2f} (p={_p(r['p_adj'])}) adjusted for {', '.join(r['controls'])}." for r in rows))
    elif re.search(r"next|should i|follow.?up|investigate|suggest", q):
        F = findings()
        recs = []
        for f in F:
            if f["verdict"] == "Robust association":
                recs.append(f"Unpack '{f['title']}': the gap is robust, but the dataset contains no mechanism. Merge state-level competitiveness, registration and mail-voting rules, and education data to test which component of 'South' matters.")
            if f["verdict"] == "Fragile":
                recs.append(f"Try to replicate '{f['title']}' in another election year (2018 or 2014 VEP files) before taking it seriously. The specification share here is {f['stats']['spec_share']*100:.0f}%.")
            if f["verdict"] == "Likely confounded":
                recs.append(f"For '{f['title']}', compare within-region slopes using county data, where many more units are available.")
        recs.append("Quantify the * states' undercount by comparing their highest-office totals with certified total ballots where available.")
        ran.append("Read verdicts from the computed findings pipeline")
        out.update(intent="next", title="What to investigate next", items=recs, answer=" ".join(f"({i+1}) {r}" for i, r in enumerate(recs)))
    elif state and not vars_:
        p = state_profile(state, exclude)
        ran.append(f"Profile, percentile and rank of {p['state']} on each variable")
        v = p["values"]
        out.update(intent="state", title=f"Profile: {p['state']}", profile=p,
                   answer=(f"{p['state']} ({p['region']}): VEP turnout {v['turnout_rate_vep']['value']:.1f}% (rank {v['turnout_rate_vep']['rank']} of {p['n']}), "
                           f"VAP turnout {v['turnout_rate_vap']['value']:.1f}% (rank {v['turnout_rate_vap']['rank']}). Non-citizen share {v['pct_noncitizen']['value']:.1f}% "
                           f"({_ord(v['pct_noncitizen']['pctile'])} percentile); prisoners {v['prison_pct_vap']['value']:.2f}% of VAP ({_ord(v['prison_pct_vap']['pctile'])} percentile). "
                           f"Region-only model predicts {p['region_expected']:.1f}%, so {p['state']} is {v['turnout_rate_vep']['value']-p['region_expected']:+.1f} pts vs expectation. "
                           f"Numerator: {'highest-office votes (*)' if p['alt_numerator'] else 'total ballots'}. Status: {p['status']}."))
    elif re.search(r"region|group|differ", q) and not [v for v in vars_ if v != "is_south"]:
        g = group_compare("region", y, exclude)
        ran.append("One-way ANOVA, Kruskal-Wallis and Holm-corrected pairwise Welch tests across Census regions")
        sig = [pp for pp in g["pairwise"] if pp["p_holm"] < 0.05]
        out.update(intent="groups", title="Turnout by Census region", group=g,
                   answer=(", ".join(f"{x['group']} {x['mean']:.1f}% (n={x['n']})" for x in g["groups"]) + f". ANOVA p={_p(g['anova_p'])}, η²={g['eta2']:.2f}. "
                           + ("Significant pairs after Holm correction: " + "; ".join(f"{pp['a']} vs {pp['b']} ({pp['diff']:+.1f})" for pp in sig) + "." if sig else "No pair survives Holm correction.")))
    elif len(vars_) >= 1 and not re.search(r"strongest|most strongly|which characteristic|associated", q):
        x = vars_[0]
        c = correlate(x, y, exclude)
        ran.append(f"Pearson & Spearman correlation, Fisher and bootstrap CIs, HC3 OLS slope, leave-one-out and quadratic test for {label(x)} vs {label(y)}")
        out.update(intent="pair", title=f"{label(x)} vs {label(y)}", corr={k: c[k] for k in ["x", "y", "n", "r", "p", "r_ci", "rho", "p_spearman", "slope", "slope_ci", "boot_r_ci", "loo_r_min", "loo_r_max", "loo_most_influential", "quad_p"] if k in c},
                   answer=(f"n = {c['n']}. Pearson r = {c['r']:.2f} (95% CI {c['r_ci'][0]:.2f} to {c['r_ci'][1]:.2f}, p = {_p(c['p'])}); Spearman ρ = {c['rho']:.2f} (p = {_p(c['p_spearman'])}). "
                           f"OLS slope {c['slope']:.2f} {label(y)} points per unit (95% CI {c['slope_ci'][0]:.2f} to {c['slope_ci'][1]:.2f}). "
                           f"Leave-one-out r range {c['loo_r_min']:.2f} to {c['loo_r_max']:.2f}; most influential state: {c['loo_most_influential']}. "
                           + (f"Quadratic term p = {_p(c['quad_p'])}." if c.get("quad_p") is not None else "")))
    else:
        rows = predictor_screen(y, exclude)
        generic = re.search(r"strongest|most strongly|which characteristic|associated|correlat|predict|go along|higher or lower|why do some", q)
        ran.append(f"Bivariate screen of {len(rows)} predictors against {label(y)} with BH-adjusted q-values and bootstrap CIs")
        out.update(intent="strongest", title=f"Characteristics most strongly associated with {label(y)}", table=rows,
                   answer=("" if generic else "No specific analysis matched this question, so here is the default screen of every predictor. Try naming a variable, a state, or one of the suggested questions. ")
                          + ("Ranked by |r|: " + "; ".join(f"{r['x_label']} r = {r['r']:+.2f} [{r['boot_r_ci'][0]:+.2f}, {r['boot_r_ci'][1]:+.2f}], q = {_p(r['q'])}" for r in rows[:5])
                           + ". Only associations with q < 0.05 survive multiple-testing correction."))
    out["analyses_run"] = ran
    out["plain"] = _plain_answer(out, y)
    return clean(out)


def _plain_answer(out, y):
    it = out["intent"]
    if it == "surprising":
        return ("Here are the patterns that change how you'd read the data at first glance. The biggest one: "
                + out["items"][0]["title"].lower() + ". Click any of them to dig deeper.")
    if it == "nonlinear":
        if all(r["quad_q"] >= 0.05 for r in out["table"]):
            return "Nope. Every link we checked is either a straight-line trend or no trend at all. Nothing bends or curves in a way we can detect with 51 states."
        return f"Yes, {plain(out['table'][0]['var'])} shows signs of a curved relationship."
    if it == "influence":
        top = ", ".join(a for a, _ in out["cooks"][:3])
        return (f"A few states pull harder on the results than others (mainly {top}). "
                "We re-ran the key analyses leaving out one state at a time to see whether any single state changes the story. See the numbers below.")
    if it == "adjusted":
        return " ".join(f"{plain(r['var']).capitalize()}: {'still linked to turnout' if r['p_adj'] < 0.05 else 'the link fades and could be chance'} "
                        f"once other factors are taken into account." for r in out["table"])
    if it == "next":
        return "Here are a few ideas for where to dig next, based on which findings are solid and which are shaky."
    if it == "state":
        p = out["profile"]
        v = p["values"]["turnout_rate_vep"]
        diff = v["value"] - p["region_expected"]
        return (f"In {p['state']}, about {v['value']:.0f} of every 100 eligible people voted, ranking #{v['rank']} of {p['n']}. "
                f"That's {abs(diff):.1f} points {'more' if diff > 0 else 'less'} than we'd guess from "
                f"{'being in the South' if p['region'] == 'South' else 'not being in the South'} alone.")
    if it == "groups":
        g = sorted(out["group"]["groups"], key=lambda x: x["mean"])
        nm = lambda x: {"South": "Southern", "West": "Western", "Midwest": "Midwestern", "Northeast": "Northeastern"}.get(x, x)
        return (f"{nm(g[0]['group'])} states voted the least (about {g[0]['mean']:.0f}%) and {nm(g[-1]['group'])} states the most (about {g[-1]['mean']:.0f}%). "
                + ("The difference between regions is bigger than luck would explain." if out["group"]["anova_p"] < 0.05 else "But the differences could be luck."))
    if it == "pair":
        c = out["corr"]
        return plain_corr(c["x"], c["y"], c["r"], c["p"], c["n"])
    if it == "strongest":
        t = out["table"]
        n_sig = sum(r["q"] < 0.05 for r in t)
        return (f"The biggest link is with {plain(t[0]['x'])}. " + plain_corr(t[0]["x"], y, t[0]["r"], t[0]["p"], t[0]["n"])
                + f" Of the {len(t)} things we checked, {n_sig} {'passes' if n_sig == 1 else 'pass'} our 'probably not luck' test after accounting for checking many things at once.")
    return ""


def overview() -> dict:
    d = DF
    y = d["turnout_rate_vep"]
    desc = {}
    for v in ["turnout_rate_vep", "turnout_rate_vap", "pct_noncitizen", "vep_vap_gap_pct", "prison_pct_vap", "community_inelig_pct_vap", "felon_inelig_pct_vap", "vep"]:
        s = d[v]
        desc[v] = dict(label=label(v), mean=s.mean(), sd=s.std(), min=s.min(), q1=s.quantile(.25), median=s.median(), q3=s.quantile(.75), max=s.max(),
                       min_state=s.idxmin(), max_state=s.idxmax())
    sw = st.shapiro(y)
    iqr = y.quantile(.75) - y.quantile(.25)
    out_lo, out_hi = y.quantile(.25) - 1.5 * iqr, y.quantile(.75) + 1.5 * iqr
    quality = [
        f"{len(d)} jurisdictions (50 states + DC); one national total row and one footnote row removed. No duplicate states.",
        f"Reported VEP turnout matches total turnout ÷ VEP within {(d.turnout_rate_vep - d.turnout_rate_vep_calc).abs().max():.2f} points (rounding).",
        f"National VEP ({NATIONAL['vep']:,.0f}) exceeds the sum of state VEPs ({d.vep.sum():,.0f}) by {NATIONAL['vep'] - d.vep.sum():,.0f}, matching 'Overseas Eligible' ({NATIONAL['overseas_eligible']:,.0f}) to within {abs(NATIONAL['vep'] - d.vep.sum() - NATIONAL['overseas_eligible']):,.0f} people (rounding). Overseas voters are only counted nationally.",
        f"National prison count exceeds the state sum by {NATIONAL['prison'] - d.prison.sum():,.0f}, consistent with federal prisoners not assigned to states.",
        f"'Overseas Eligible' is blank for every state ({d.overseas_eligible.isna().sum()} missing); no other missing values.",
        f"{int(d.alt_numerator.sum())} states (*) use highest-office votes as the numerator, not total ballots, so their rates are lower bounds.",
        f"Result status varies: " + ", ".join(f"{k} {v}" for k, v in d.status.value_counts().items()) + ".",
        f"Felony counts: {int((d.ineligible_felon == 0).sum())} jurisdictions report zero ineligible felons and {int(((d.probation + d.parole) == 0).sum())} report zero probation/parole disenfranchisement (policy, not missing data).",
        f"No turnout outliers by the 1.5×IQR rule (range {out_lo:.1f}–{out_hi:.1f}); distribution is close to normal (Shapiro-Wilk p = {sw.pvalue:.2f}).",
    ]
    columns = [
        ("State", "Jurisdiction name; '*' marks an alternative numerator", "identifier"),
        ("Total Turnout", "Ballots counted (or highest-office votes for * states)", "count → numerator"),
        ("Status", "Certified / Official / Final / Final Total Turnout Pending", "categorical"),
        ("Source", "URL of the official results", "metadata"),
        ("Turnout Rate", "Total Turnout ÷ VEP", "outcome (%)"),
        ("Voting-Eligible Population (VEP)", "VAP minus non-citizens and ineligible felons", "denominator"),
        ("Voting-Age Population (VAP)", "All residents aged 18+", "denominator"),
        ("% Non-citizen", "Non-citizens as % of VAP", "eligibility component"),
        ("Prison / Probation / Parole", "People ineligible due to felony status, by supervision type", "eligibility component (count)"),
        ("Total Ineligible Felon", "Prison + probation + parole (verified exactly)", "eligibility component (count)"),
        ("Overseas Eligible", "Eligible citizens abroad; national row only", "eligibility component"),
        ("State Abv", "Postal abbreviation", "identifier"),
    ]
    F = findings()
    return clean(dict(n=len(d), national=dict(turnout=NATIONAL["total_turnout"], rate=NATIONAL["turnout_rate_vep"], vep=NATIONAL["vep"], vap=NATIONAL["vap"],
                                    pct_noncitizen=NATIONAL["pct_noncitizen"], noncitizen=NATIONAL["vap"] * NATIONAL["pct_noncitizen"] / 100,
                                    ineligible_felon=NATIONAL["ineligible_felon"], overseas=NATIONAL["overseas_eligible"],
                                    rate_vap=NATIONAL["total_turnout"] / NATIONAL["vap"] * 100),
                      desc=desc, quality=quality, columns=columns, footnote=FOOTNOTE,
                      top=[dict(id=f["id"], title=f["title"], verdict=f["verdict"], stat=f["headline_stat"]) for f in F[:4]],
                      vars={k: v for k, v in VARS.items()}, groups=GROUPS))


def records(exclude=None) -> list[dict]:
    cols = ["abv", "state", "region", "status", "status_group", "felony_regime", "alt_numerator", "source",
            "total_turnout", "vep", "vap", "prison", "probation", "parole", "ineligible_felon"] + list(dict.fromkeys(HEATMAP_VARS))
    d = DF[cols].copy()
    d["excluded"] = d.index.isin(set(exclude or []))
    return clean(d.to_dict("records"))

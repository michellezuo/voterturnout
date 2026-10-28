"""Write a reproducible record of the analysis.

    python analysis/report.py

Produces analysis/output/findings.json (everything the website shows) and
analysis/output/REPORT.md (a readable summary). Re-running regenerates both
from data/turnout_2022.csv; numbers in the report are never typed by hand.
"""
import json
from pathlib import Path

import engine

OUT = Path(__file__).resolve().parent / "output"


def main():
    OUT.mkdir(exist_ok=True)
    ov = engine.overview()
    F = engine.findings()
    screen = engine.clean(engine.predictor_screen())
    heat = engine.clean(engine.corr_matrix("spearman"))
    region = engine.clean(engine.group_compare("region"))
    full = engine.clean(engine.regression("turnout_rate_vep", ["is_south", "pct_noncitizen", "log10_vep", "prison_pct_vap", "community_inelig_pct_vap", "alt_num"]))
    for k in ("cooks", "student_resid", "fitted"):
        full.pop(k, None)
    (OUT / "findings.json").write_text(json.dumps(dict(overview=ov, findings=F, predictor_screen=screen, spearman_matrix=heat,
                                                       region=region, full_model=full, seed=engine.SEED), indent=1), encoding="utf-8")

    L = ["# 2022 turnout: analysis record", "",
         f"Source: `data/turnout_2022.csv` · unit: state (50 + DC) · n = {ov['n']} · random seed {engine.SEED}", "",
         "## Data quality", *[f"- {q}" for q in ov["quality"]], "",
         "## Bivariate screen (VEP turnout)", "",
         "| Predictor | r | bootstrap 95% CI | p | BH q | Spearman ρ |", "|---|---|---|---|---|---|",
         *[f"| {r['x_label']} | {r['r']:.2f} | {r['boot_r_ci'][0]:.2f} to {r['boot_r_ci'][1]:.2f} | {r['p']:.3f} | {r['q']:.3f} | {r['rho']:.2f} |" for r in screen], "",
         "## Region", "",
         *[f"- {g['group']}: {g['mean']:.1f}% (n={g['n']})" for g in region["groups"]],
         f"- ANOVA p = {region['anova_p']:.4f}, η² = {region['eta2']:.2f}", "",
         "## Full model (HC3 SEs)", "", f"`{full['formula']}` · R² = {full['r2']:.3f} · leave-one-out R² = {full['loo_r2']:.3f}", "",
         "| Term | coef | 95% CI | p |", "|---|---|---|---|",
         *[f"| {c['label']} | {c['coef']:.3f} | {c['ci'][0]:.2f} to {c['ci'][1]:.2f} | {c['p']:.3f} |" for c in full["coefs"]], "",
         "## Ranked findings", ""]
    for f in F:
        L += [f"### {f['rank']}. {f['title']}", f"**Verdict:** {f['verdict']} (rule: {f['verdict_rule']}; met: {f['verdict_rule_met']})", "",
              f"**Key statistic:** {f['headline_stat']}", "", f["explanation"], "", f"*Why it matters:* {f['why_interesting']}", "",
              "*Limitations:* " + " ".join(f["limitations"]), ""]
    (OUT / "REPORT.md").write_text("\n".join(L), encoding="utf-8")
    print(f"Wrote {OUT / 'findings.json'} and {OUT / 'REPORT.md'}")


if __name__ == "__main__":
    main()

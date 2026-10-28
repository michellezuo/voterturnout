# 2022 turnout: analysis record

Source: `data/turnout_2022.csv` · unit: state (50 + DC) · n = 51 · random seed 20221108

## Data quality
- 51 jurisdictions (50 states + DC); one national total row and one footnote row removed. No duplicate states.
- Reported VEP turnout matches total turnout ÷ VEP within 0.05 points (rounding).
- National VEP (242,690,810) exceeds the sum of state VEPs (239,561,653) by 3,129,157, matching 'Overseas Eligible' (3,129,152) to within 5 people (rounding). Overseas voters are only counted nationally.
- National prison count exceeds the state sum by 131,109, consistent with federal prisoners not assigned to states.
- 'Overseas Eligible' is blank for every state (51 missing); no other missing values.
- 12 states (*) use highest-office votes as the numerator, not total ballots, so their rates are lower bounds.
- Result status varies: Official 29, Certified 16, Final 3, Final Total Turnout Pending 3.
- Felony counts: 3 jurisdictions report zero ineligible felons and 24 report zero probation/parole disenfranchisement (policy, not missing data).
- No turnout outliers by the 1.5×IQR rule (range 27.8–66.4); distribution is close to normal (Shapiro-Wilk p = 0.42).

## Bivariate screen (VEP turnout)

| Predictor | r | bootstrap 95% CI | p | BH q | Spearman ρ |
|---|---|---|---|---|---|
| South (Census region) | -0.51 | -0.65 to -0.32 | 0.000 | 0.001 | -0.51 |
| Prisoners, % of VAP | -0.34 | -0.58 to -0.10 | 0.013 | 0.053 | -0.27 |
| Alternative numerator (*) | -0.20 | -0.47 to 0.14 | 0.153 | 0.403 | -0.18 |
| All felony-ineligible, % of VAP | -0.17 | -0.42 to 0.09 | 0.229 | 0.403 | -0.14 |
| VAP→VEP reduction | -0.16 | -0.41 to 0.09 | 0.252 | 0.403 | -0.16 |
| Non-citizen share of VAP | -0.11 | -0.35 to 0.15 | 0.426 | 0.525 | -0.10 |
| Probation + parole ineligible, % of VAP | -0.11 | -0.38 to 0.15 | 0.459 | 0.525 | -0.10 |
| State size (log10 VEP) | -0.01 | -0.26 to 0.22 | 0.968 | 0.968 | 0.05 |

## Region

- Midwest: 50.1% (n=12)
- Northeast: 50.2% (n=9)
- South: 42.1% (n=17)
- West: 49.2% (n=13)
- ANOVA p = 0.0024, η² = 0.26

## Full model (HC3 SEs)

`turnout_rate_vep ~ is_south + pct_noncitizen + log10_vep + prison_pct_vap + community_inelig_pct_vap + alt_num` · R² = 0.430 · leave-one-out R² = 0.252

| Term | coef | 95% CI | p |
|---|---|---|---|
| South (Census region) | -8.148 | -12.08 to -4.21 | 0.000 |
| Non-citizen share of VAP | -0.801 | -1.46 to -0.14 | 0.018 |
| State size (log10 VEP) | 4.430 | -0.20 to 9.06 | 0.061 |
| Prisoners, % of VAP | -11.595 | -23.86 to 0.67 | 0.064 |
| Probation + parole ineligible, % of VAP | 2.652 | -0.10 to 5.41 | 0.059 |
| Alternative numerator (*) | -3.392 | -7.53 to 0.74 | 0.108 |

## Ranked findings

### 1. Southern states turned out 7.7 points lower than the rest of the country
**Verdict:** Robust association (rule: Welch p < 0.05, adjusted p < 0.05, and ≥ 80% of VEP specifications significant in the same direction; met: True)

**Key statistic:** Δ = -7.7 pts (95% CI -11.1 to -4.4), d = -1.23

The 17 Southern jurisdictions averaged 42.1% VEP turnout versus 49.8% for the other 34. Census region alone accounts for 26% of the between-state variance (ANOVA p = 0.002); the other three regions do not differ significantly from each other (ANOVA p = 0.917). After adjusting for every other available variable the gap is -7.2 points (p = < 0.001).

*Why it matters:* It is the largest and most stable pattern in the file: it survives every specification tried (100% of 128 models, across both outcomes and four samples, significant in the same direction). Because 'South' is a bundle of many state characteristics, it is a pointer to explanations rather than an explanation.

*Limitations:* Region is an external label, not a mechanism: the data cannot say which Southern characteristic matters. 51 aggregate observations: state-level patterns do not describe individual voters (ecological fallacy). One election (a midterm). The gap may differ in presidential years or other midterms.

### 2. Measuring turnout against all adults manufactures a 'non-citizen' penalty
**Verdict:** Measurement artifact (rule: Non-citizen association significant with VAP outcome (p < 0.05) but not with VEP outcome; met: True)

**Key statistic:** r(non-citizen, VAP rate) = -0.29 vs r(non-citizen, VEP rate) = -0.11

With the VAP denominator, states with more non-citizens look like lower-turnout states (r = -0.29, p = 0.039). With the VEP denominator, which removes people who cannot legally vote, the association weakens to r = -0.11 (p = 0.426). The VEP−VAP difference in turnout tracks non-citizen share almost perfectly (r = 0.93). CA falls 10 places in the ranking when VAP is used.

*Why it matters:* This is a cautionary measurement result: a researcher who used the more commonly published VAP rate would 'find' an immigrant-share effect that is largely an accounting consequence of counting ineligible residents in the denominator.

*Limitations:* VEP itself is an estimate built from the very variables tested here; errors in non-citizen counts flow straight into the outcome. Cannot separate the voting behaviour of naturalised citizens from that of native-born citizens.

### 3. States with more people in prison vote less, but being in the South explains about 52% of that
**Verdict:** Likely confounded (rule: Bivariate p < 0.05 but p ≥ 0.05 once South is controlled; met: True)

**Key statistic:** r = -0.34 (BH q = 0.053); slope -13.2 → -6.3 after adjusting for South

Each additional percentage point of adults in prison is associated with -13.2 points lower VEP turnout (r = -0.34, p = 0.013, bootstrap 95% CI for r -0.58 to -0.08). But Southern states imprison more people (point-biserial r = 0.41), and with a South indicator in the model the slope falls to -6.3 (p = 0.192). Within the South (r = -0.23) and outside it (r = -0.15) the association is weaker and not significant. After Benjamini-Hochberg correction for testing 8 predictors, q = 0.053 (not significant at 0.05).

*Why it matters:* A textbook confounding pattern: a plausible-sounding bivariate link that largely reflects a shared regional pattern. Note that prisoners are already removed from VEP, so this is not a mechanical denominator effect.

*Limitations:* State prison counts only; federal prisoners and jail populations are not broken out. Cross-sectional: cannot establish whether incarceration affects turnout, or vice versa, or neither.

### 4. A hidden non-citizen/size pattern appears in multivariable models, but it is fragile
**Verdict:** Fragile (rule: Bootstrap 95% CI includes 0, or < 80% of VEP specifications significant; met: True)

**Key statistic:** Adjusted coef = -0.59 pts per point (p = 0.070); bootstrap 95% CI -1.24 to 0.02

Alone, neither non-citizen share (r = -0.11) nor state size (r = -0.01) predicts VEP turnout. Because they are correlated with each other (r = 0.50), adjusting for size and South makes non-citizen share look negative (-0.59 per point, p = 0.070) and size look positive (3.43 per tenfold increase, p = 0.122). Among VEP-outcome specifications only 34% are significant in that direction, and dropping single states moves p across 0.05 (7 of 51 leave-one-out fits are significant).

*Why it matters:* A 'suppressor' pattern like this is exactly what an automated search would surface as a discovery. Showing that it depends on model choices is the point: treat it as a hypothesis for other data, not a finding.

*Limitations:* Not pre-registered; found by searching many models, so nominal p-values overstate the evidence.

### 5. 12 states are measured differently and average 3.4 points lower
**Verdict:** Measurement caveat (rule: Difference not significant (p ≥ 0.05); flagged because of the known measurement difference; met: True)

**Key statistic:** Δ = -3.4 pts (95% CI -8.4 to 1.8), p = 0.221

For AL, ID, KS, MS, MO, OK, PA, RI, SD, TN, TX, WI, the CSV footnote says the numerator is votes for the highest office (or a ballot measure) rather than total ballots cast. Those states average 44.6% vs 48.0% for the rest. The gap is not statistically significant (Welch p = 0.221; -2.6 pts after adjusting for South, p = 0.214), but its direction matches what under-counting would produce.

*Why it matters:* Highest-office votes exclude ballots that skip that race, so these 12 rates are lower bounds. Of the five lowest-turnout states, 3 are * states (MS, TN, AL), so comparisons at the bottom of the ranking are partly comparisons of measurement methods.

*Limitations:* The size of each state's undercount is unknown from this file.

### 6. How broadly a state disenfranchises people with felonies shows no clear link to turnout
**Verdict:** No association (rule: ANOVA and Kruskal-Wallis p ≥ 0.05, and probation/parole share p ≥ 0.05; met: True)

**Key statistic:** Kruskal-Wallis p = 0.495; η² = 0.05

Grouping states by whether they disenfranchise no one, only prisoners, or also people on probation or parole gives means of No felony disenfranchisement 52.5% (n=3), Prison + probation/parole 46.0% (n=27), Prison only 48.0% (n=21). Differences are not significant (ANOVA p = 0.270). The share disenfranchised while on probation or parole is also unrelated (r = -0.11, p = 0.459).

*Why it matters:* The regime is derived from the data itself (zero probation/parole counts), but only 3 jurisdictions disenfranchise no one, so power is very low.

*Limitations:* Regime is inferred from counts, not from statutes; small groups give low power.

### 7. State size has essentially no relationship with turnout
**Verdict:** No association (rule: Pearson and Spearman p ≥ 0.05; met: True)

**Key statistic:** r = -0.01 (95% CI -0.28 to 0.27), ρ = 0.05

Large and small states turn out at similar rates (Pearson r = -0.01, Spearman ρ = 0.05; quadratic term p = 0.676). The confidence interval rules out strong relationships (|r| above about 0.28). Even so, weighting by population matters for the national figure: the unweighted state mean is 47.2% while the national rate is 46.2%.

*Why it matters:* A useful null: theories that small states vote more (stronger civic ties) or less (fewer competitive races) find no support at this level.

*Limitations:* A null in 51 units cannot rule out modest effects (see the CI).

### 8. Most of the 30-point spread in turnout is not explained by anything in this file
**Verdict:** Model ceiling (rule: Leave-one-out R² of the full model < 0.5; met: True)

**Key statistic:** In-sample R² = 0.43; leave-one-out R² = 0.25

Turnout ranges from 32.5% (MS) to 62.3% (OR). A model with every available characteristic fits R² = 0.43 in-sample, but predicts held-out states with R² = 0.25. The South indicator alone gets 0.20 out-of-sample. The remaining variation must come from factors outside this dataset.

*Why it matters:* Sets expectations: this dataset describes turnout and eligibility well, but it was not designed to explain turnout.

*Limitations:* Out-of-sample R² with n = 51 is itself noisy.

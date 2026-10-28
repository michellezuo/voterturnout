# Who Showed Up? · 2022 voter turnout explorer

A friendly, interactive website about one dataset: **`2022 November General Election - Turnout Rates.csv`** (stored as `data/turnout_2022.csv`). It covers how many people voted in each U.S. state (plus DC) in November 2022, and what might explain the differences.

Every number on the site is calculated from that CSV by the Python code in `analysis/`. Nothing is typed in by hand, and there are no placeholder results. Plain-English summaries come first, and the technical statistics sit behind "Show the numbers" toggles.

## Two ways to run it

### 1. Hosted on GitHub Pages (static)

The `docs/` folder is a fully static build:

- **Default views load instantly:** every chart, finding and test for the default view is precomputed into `docs/precomputed.json` by the real Python engine.
- **Anything else runs in your browser:** hiding states, typing your own question, or building custom models runs the **same Python code** in the browser via [Pyodide](https://pyodide.org) (`docs/worker.js`). The first time takes about 20 seconds while Pyodide downloads.
- **The optional AI explainer is off on the hosted version,** because it needs a secret API key that can't live on a public site.

To publish: in the repository's **Settings → Pages**, set **Source** to *Deploy from a branch*, branch `main`, folder `/docs`.

After changing anything in `analysis/` or `web/`, rebuild with:

```bash
python build_static.py
```

### 2. Locally with the Python server

```bash
pip install -r requirements.txt
python server.py            # → http://127.0.0.1:8050
```

Startup takes about 10 seconds while findings are computed. To use the optional **AI explainer** in the Ask tab, run `pip install anthropic`, set `ANTHROPIC_API_KEY`, and restart. The AI only sees results that were already computed, and its text is shown separately from the computed answer.

## What's in the data

51 rows (50 states + DC) with votes cast, two population counts, the share of adults who aren't citizens, and the number of people barred from voting due to a felony (in prison, on probation, on parole).

- **VAP (voting-age population):** everyone 18+ living in the state.
- **VEP (voting-eligible population):** VAP minus non-citizens and people barred by a felony conviction, plus Americans abroad. The site uses VEP by default because it only counts people who could vote.

Census region is the only label added from outside the file.

## Site tour

| Tab | What you can do |
|---|---|
| **Hello!** | What turnout means (VEP vs VAP explained with a picture), headline stats, a stats cheat sheet |
| **Discoveries** | 8 findings ranked from most solid to least certain, each with a plain-English summary and a "how much to trust it" label |
| **Explore** | Linked map, dot chart (draw a loop to pick states), distribution, group comparison, ranking, "what goes with what" grid, data table, state profile |
| **Dig deeper** | Per finding: what we saw → educated guesses → other explanations (with "Test it!" buttons) → your own checks → a 128-version robustness chart and a model builder → what the data can't tell us |
| **Ask Ballo** | Questions in your own words, answered by running real analyses. Three suggested questions to get started. |

## Project layout

```
data/turnout_2022.csv     the dataset (unchanged copy)
analysis/load.py          parsing, cleaning, derived variables
analysis/engine.py        all statistics, findings, plain-English text, tests, question router
analysis/api.py           routes shared by the server and the in-browser worker
analysis/ai.py            optional AI explainer (local server only)
analysis/report.py        writes analysis/output/REPORT.md + findings.json
server.py                 local server
build_static.py           builds docs/ for GitHub Pages
web/                      the site (index.html, app.js, style.css, worker.js)
docs/                     generated static site (do not edit by hand)
```

## Methods notes

- Regressions use heteroskedasticity-robust (HC3) standard errors. Bootstraps use 2,000 resamples (seed 20221108) and permutation tests use 5,000 shuffles.
- Benjamini–Hochberg correction is used for the many-variable screens, and Holm correction for pairwise group tests.
- Robustness charts vary the control variables, the outcome (VEP/VAP) and the sample (all states, without DC, without the 12 "top race only" states, without the 3 most influential states).
- 51 states in one midterm election: patterns are associations, not causes, and say nothing about individual voters.

The mascots (Ballo, Bloo and Rosie) are original drawings made for this project.

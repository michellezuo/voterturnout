"""Load and clean the 2022 November General Election turnout CSV.

The raw file has a two-row header (a group row and a column-name row), a
national total row, 51 state/DC rows and a trailing footnote row.
"""
from pathlib import Path
import numpy as np
import pandas as pd

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "turnout_2022.csv"

RAW_COLS = [
    "state_raw", "total_turnout", "status", "source", "turnout_rate_vep",
    "vep", "vap", "pct_noncitizen", "prison", "probation", "parole",
    "ineligible_felon", "overseas_eligible", "abv",
]

# U.S. Census Bureau regions. This is an external, standard classification
# keyed on the state abbreviation; it is NOT in the CSV.
CENSUS_REGION = {
    **dict.fromkeys(["CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"], "Northeast"),
    **dict.fromkeys(["IL", "IN", "MI", "OH", "WI", "IA", "KS", "MN", "MO", "NE", "ND", "SD"], "Midwest"),
    **dict.fromkeys(["DE", "DC", "FL", "GA", "MD", "NC", "SC", "VA", "WV", "AL", "KY", "MS", "TN",
                     "AR", "LA", "OK", "TX"], "South"),
    **dict.fromkeys(["AZ", "CO", "ID", "MT", "NV", "NM", "UT", "WY", "AK", "CA", "HI", "OR", "WA"], "West"),
}


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.replace("%", "").str.strip()
                         .replace({"": np.nan, "nan": np.nan}), errors="coerce")


def load_raw() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, header=None, skiprows=2, names=RAW_COLS, dtype=str)
    return df


def load() -> tuple[pd.DataFrame, pd.Series, str]:
    """Return (states_df, national_row, footnote)."""
    raw = load_raw()
    footnote = raw.iloc[-1]["state_raw"]
    raw = raw.iloc[:-1]
    for c in ["total_turnout", "turnout_rate_vep", "vep", "vap", "pct_noncitizen", "prison",
              "probation", "parole", "ineligible_felon", "overseas_eligible"]:
        raw[c] = _num(raw[c])
    national = raw.iloc[0].copy()
    df = raw.iloc[1:].copy().reset_index(drop=True)
    df["alt_numerator"] = df["state_raw"].str.endswith("*")
    df["state"] = df["state_raw"].str.rstrip("*").str.strip()
    df["region"] = df["abv"].map(CENSUS_REGION)

    # Derived variables (all computed from CSV columns)
    df["turnout_rate_vep_calc"] = df["total_turnout"] / df["vep"] * 100
    df["turnout_rate_vap"] = df["total_turnout"] / df["vap"] * 100
    df["vep_vap_gap_pct"] = (df["vap"] - df["vep"]) / df["vap"] * 100
    df["felon_inelig_pct_vap"] = df["ineligible_felon"] / df["vap"] * 100
    df["prison_pct_vap"] = df["prison"] / df["vap"] * 100
    df["community_inelig_pct_vap"] = (df["probation"] + df["parole"]) / df["vap"] * 100
    df["log10_vep"] = np.log10(df["vep"])
    df["disenfranchises_community"] = (df["probation"] + df["parole"]) > 0
    df["felony_regime"] = np.select(
        [df["ineligible_felon"] == 0, ~df["disenfranchises_community"]],
        ["No felony disenfranchisement", "Prison only"],
        "Prison + probation/parole",
    )
    df["status_group"] = df["status"].replace({"Final Total Turnout Pending": "Pending"})
    return df, national, footnote


if __name__ == "__main__":
    df, nat, fn = load()
    pd.set_option("display.width", 220, "display.max_columns", 40)
    print(df.dtypes)
    print(df.describe().T)

"""
Auto-profiler for interactive exploration.

Given a DataFrame, infer each column's *role* and emit an "exploration plan":
what is worth slicing by, what is worth measuring and filtering, and which view
archetype fits. This is the "auto-magically determine what's possible to
explore" core of the exploring skill.

It is the piece that would have told the HourApp that `value` (transaction
amount), `gas`, and `gas_price` are filterable continuous measures — not just
`hour`. The app only explored time because nothing profiled the columns first.

Roles inferred:
  temporal     -> date-range filter; resample trend; hour/weekday rhythm
  measure      -> distribution + RANGE FILTER; aggregate (sum/mean)
  categorical  -> multiselect / facet / bar  (low-cardinality)
  id           -> top-N / search / join key  (high-cardinality, not a facet)
  geo          -> map (lat/lon)

Pure pandas/numpy. No plotting, no Panel.
"""

# /// script
# requires-python = ">=3.9"
# dependencies = ["pandas", "numpy"]
# ///
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

# Heuristic thresholds (deliberately conservative; tune per domain).
MAX_CATEGORICAL = 20  # <= this many distinct values -> a categorical dimension
ORDINAL_INT_MAX = 15  # small-integer range -> ordinal/categorical, not a measure
ID_UNIQUE_FRAC = 0.5  # uniques / rows above this -> identifier-like
TEMPORAL_PARSE_MIN = 0.8  # fraction of a sample that must parse as dates


@dataclass
class Col:
    name: str
    role: str
    dtype: str
    n_unique: int
    n_missing: int
    detail: str = ""
    interaction: str = ""


def _looks_temporal(s: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(s):
        return True
    if s.dtype == object:
        sample = s.dropna().astype(str).head(50)
        if len(sample) == 0:
            return False
        # Skip obvious non-dates (hashes / hex addresses) before trying dateutil.
        if sample.str.match(r"^0x[0-9a-fA-F]+$").mean() > 0.5:
            return False
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            parsed = pd.to_datetime(sample, errors="coerce")
        return parsed.notna().mean() >= TEMPORAL_PARSE_MIN
    return False


def _is_geo(name: str) -> bool:
    n = name.lower()
    return any(k in n for k in ("latitude", "longitude", "lat", "lon", "lng"))


def profile_columns(df: pd.DataFrame) -> list[Col]:
    # A datetime (or named, non-default) index carries a real dimension — surface
    # it as a column so time is profiled even when it's the index, which is the
    # common case for timeseries data.
    if isinstance(df.index, pd.DatetimeIndex) or (
        df.index.name and not isinstance(df.index, pd.RangeIndex)
    ):
        df = df.reset_index()
    n = len(df)
    out: list[Col] = []
    for c in df.columns:
        s = df[c]
        nu = int(s.nunique(dropna=True))
        nm = int(s.isna().sum())
        dt = str(s.dtype)

        if _is_geo(c):
            out.append(Col(c, "geo", dt, nu, nm, "lat/lon-like", "map / coordinated view"))
        elif _looks_temporal(s):
            ts = pd.to_datetime(s, errors="coerce")
            span = f"{ts.min():%Y-%m-%d} -> {ts.max():%Y-%m-%d}"
            out.append(
                Col(
                    c,
                    "temporal",
                    dt,
                    nu,
                    nm,
                    span,
                    "date-range filter; resample trend; hour/weekday rhythm",
                )
            )
        elif pd.api.types.is_bool_dtype(s):
            out.append(Col(c, "categorical", dt, nu, nm, "boolean", "toggle / multiselect"))
        elif pd.api.types.is_numeric_dtype(s):
            vals = s.dropna()
            is_intish = pd.api.types.is_integer_dtype(s) or bool((vals % 1 == 0).all())
            if nu <= ORDINAL_INT_MAX and is_intish:
                out.append(
                    Col(
                        c,
                        "categorical",
                        dt,
                        nu,
                        nm,
                        f"{nu} levels (small int)",
                        "multiselect / facet / bar",
                    )
                )
            else:
                lo, hi, med = float(vals.min()), float(vals.max()), float(vals.median())
                out.append(
                    Col(
                        c,
                        "measure",
                        dt,
                        nu,
                        nm,
                        f"range [{lo:.4g}, {hi:.4g}], median {med:.4g}",
                        "histogram + RANGE FILTER; aggregate (sum/mean)",
                    )
                )
        else:
            if nu > max(MAX_CATEGORICAL, ID_UNIQUE_FRAC * n):
                out.append(
                    Col(
                        c,
                        "id",
                        dt,
                        nu,
                        nm,
                        f"{nu} uniques (~{nu / max(n,1):.0%} of rows)",
                        "top-N / search / join key (not a facet)",
                    )
                )
            elif nu <= MAX_CATEGORICAL:
                out.append(
                    Col(c, "categorical", dt, nu, nm, f"{nu} levels", "multiselect / facet / bar")
                )
            else:
                out.append(Col(c, "id", dt, nu, nm, f"{nu} uniques (high-card)", "top-N / search"))
    return out


def recommend(df: pd.DataFrame) -> dict:
    cols = profile_columns(df)
    by_role: dict[str, list[str]] = {}
    for col in cols:
        by_role.setdefault(col.role, []).append(col.name)

    measures = by_role.get("measure", [])
    cats = by_role.get("categorical", [])
    temporal = by_role.get("temporal", [])
    geo = by_role.get("geo", [])

    archetypes = []
    if temporal:
        archetypes.append(
            "Rhythm of an ordered axis (time): resampled trend + hour x weekday heatmap"
        )
    if cats and (measures or True):
        archetypes.append("Facet & compare: distributions/measures split across categories")
    if len(measures) >= 2:
        archetypes.append("Relationship: scatter / scatter_matrix (rasterize for big N)")
    if len(geo) >= 2:
        archetypes.append("Coordinated map: geo points linked to distributions")

    return {
        "columns": cols,
        "measures": measures,
        "categoricals": cats,
        "temporal": temporal,
        "geo": geo,
        "ids": by_role.get("id", []),
        "archetypes": archetypes,
        # The auto-magic the HourApp lacked: every measure earns a range filter.
        "suggested_filters": (
            [f"date-range on {t}" for t in temporal]
            + [f"multiselect on {c}" for c in cats]
            + [f"range slider on {m}" for m in measures]
        ),
    }


def story_outline(df: pd.DataFrame) -> list[str]:
    """Turn a profile into an ordered EDA narrative — the practitioner ladder:
    start small (one variable), then condition on one dimension, then two, then
    reduce. The profiler decides which rungs exist for THIS dataset, so the same
    arc generalizes across temporal, categorical, measure-heavy, geo, and graph
    data without being hand-written per dataset."""
    p = recommend(df)
    meas, cats, temporal, geo, ids = (
        p["measures"],
        p["categoricals"],
        p["temporal"],
        p["geo"],
        p["ids"],
    )
    m0 = meas[0] if meas else "count"
    beats = ["Acquaint & profile — classify columns, find measures vs dimensions"]

    # Level 1 — one variable at a time
    if meas:
        beats.append(f"Distributions of the measures ({', '.join(meas[:3])}) + their ranges")
    if temporal:
        beats.append(f"{m0} over {temporal[0]} — resample to the scale where the trend lives")

    # Level 2 — condition on one dimension
    if temporal:
        beats.append(f"Rhythm: {m0} by hour-of-day / weekday (the ordered-axis profile)")
    if cats:
        beats.append(f"{m0} across {cats[0]} (bars / box) — does one average hide subgroups?")

    # Level 3 — two dimensions on one panel
    if temporal and cats:
        beats.append(f"{m0} by time × {cats[0]} (heatmap / small multiples)")
    elif temporal and meas:
        beats.append(f"{m0} by hour × weekday (the weekly-fingerprint heatmap)")
    if len(cats) >= 2:
        beats.append(f"Facet across {cats[0]} × {cats[1]} (small multiples)")
    if len(meas) >= 2:
        beats.append(f"Relationship: {meas[0]} vs {meas[1]} (scatter; rasterize if big)")

    # Level 4 — many dimensions: reduce / cluster / seriate
    if len(meas) >= 3:
        beats.append("Reduce & cluster: PCA/SVD across the measures, color by a dimension")
    if temporal:
        beats.append("Reduce period-shapes: PCA of each day's profile — find regimes unsupervised")
    if ids:
        beats.append(f"High-cardinality {ids[0]}: top-N, flows, or co-occurrence seriation")
    if geo:
        beats.append("Map view, coordinated (brushed) with the distributions")

    # Level 5 — escalate
    beats.append("Make it live: defer to Panel when one control must drive every view")
    return beats


def render_plan(df: pd.DataFrame, title: str = "Dataset") -> str:
    plan = recommend(df)
    lines = [
        f"\n{'='*70}",
        f"EXPLORATION PLAN — {title}  ({len(df):,} rows x {len(df.columns)} cols)",
        "=" * 70,
    ]
    lines.append(f"{'column':<22}{'role':<13}{'detail'}")
    lines.append("-" * 70)
    for col in plan["columns"]:
        lines.append(f"{col.name:<22}{col.role:<13}{col.detail}")
    lines.append("-" * 70)
    lines.append(f"measures (filter + aggregate): {plan['measures'] or '—'}")
    lines.append(f"dimensions (slice/facet):      {plan['categoricals'] or '—'}")
    lines.append(f"temporal:                      {plan['temporal'] or '—'}")
    lines.append(f"ids / high-card:               {plan['ids'] or '—'}")
    lines.append("\nsuggested interactions:")
    for f in plan["suggested_filters"]:
        lines.append(f"  • {f}")
    lines.append("\nsuggested layout archetype(s):")
    for a in plan["archetypes"]:
        lines.append(f"  → {a}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Demo: run the profiler on two very different datasets and print the plans.
# ---------------------------------------------------------------------------
def _synthetic_bike(n_hours=2000):
    rng = np.random.default_rng(0)
    idx = pd.date_range("2013-01-01", periods=n_hours, freq="h")
    hour = idx.hour.values
    base = 60 * (np.exp(-((hour - 8) ** 2) / 4) + np.exp(-((hour - 17) ** 2) / 4) + 0.2)
    east = rng.poisson(np.clip(base * 0.6, 0, None))
    west = rng.poisson(np.clip(base * 0.4, 0, None))
    return pd.DataFrame({"Date": idx, "East": east, "West": west, "Total": east + west})


def _synthetic_eth(n=5000):
    rng = np.random.default_rng(1)
    ts = pd.Timestamp("2024-06-01", tz="UTC") + pd.to_timedelta(
        rng.integers(0, 7 * 24 * 3600, n), "s"
    )
    hexes = ["0x" + "".join(rng.choice(list("0123456789abcdef"), 40)) for _ in range(800)]
    return pd.DataFrame(
        {
            "block_timestamp": ts,
            "block_number": rng.integers(20_000_000, 20_050_000, n),
            "value": rng.exponential(0.4, n),  # ETH amount  <-- the missed filter
            "gas": rng.integers(21_000, 500_000, n),
            "gas_price": rng.integers(1, 200, n) * 10**9,
            "receipt_gas_used": rng.integers(21_000, 480_000, n),
            "transaction_type": rng.choice([0, 2], n),
            "receipt_status": rng.choice([0, 1], n, p=[0.03, 0.97]),
            "from_address": rng.choice(hexes, n),
            "to_address": rng.choice(hexes, n),
        }
    )


def sample_fremont(seed=42):
    """Faithful synthetic Fremont Bridge hourly counts (commute peaks, weekday/
    weekend regimes, summer seasonality, multi-year uptick, weather, direction)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2014-01-01", "2018-12-31 23:00", freq="h")
    hour, dow, doy, year = (
        idx.hour.values,
        idx.dayofweek.values,
        idx.dayofyear.values,
        idx.year.values,
    )
    weekend = dow >= 5
    commute = np.exp(-((hour - 8) ** 2) / (2 * 1.4**2)) + np.exp(
        -((hour - 17.5) ** 2) / (2 * 1.4**2)
    )
    midday = np.exp(-((hour - 13) ** 2) / (2 * 3.0**2))
    shape = np.where(weekend, 0.8 * midday, commute + 0.12 * midday)
    seasonal = 0.70 + 0.30 * np.cos(2 * np.pi * (doy - 200) / 365)
    trend = 1 + 0.07 * (year - 2014)
    daykey = idx.normalize().asi8
    r2 = np.random.default_rng(seed + 1)
    rain = np.array(
        [{d: (0.5 if r2.random() < 0.28 else 1.0) for d in np.unique(daykey)}[d] for d in daykey]
    )
    total = rng.poisson(np.clip(75 * shape * seasonal * trend * rain, 0, None))
    east = rng.binomial(total, np.where(hour < 12, 0.63, 0.37))
    df = pd.DataFrame({"East": east, "West": total - east, "Total": total}, index=idx)
    df.index.name = "Date"
    return df


def _synthetic_penguins(n=344):
    rng = np.random.default_rng(2)
    species = rng.choice(["Adelie", "Gentoo", "Chinstrap"], n, p=[0.44, 0.36, 0.20])
    return pd.DataFrame(
        {
            "species": species,
            "island": rng.choice(["Biscoe", "Dream", "Torgersen"], n),
            "sex": rng.choice(["male", "female"], n),
            "bill_length_mm": rng.normal(
                np.where(species == "Gentoo", 47, np.where(species == "Chinstrap", 49, 39)), 3
            ).round(1),
            "bill_depth_mm": rng.normal(np.where(species == "Gentoo", 15, 18), 1).round(1),
            "flipper_length_mm": rng.normal(np.where(species == "Gentoo", 217, 193), 7).astype(int),
            "body_mass_g": rng.normal(np.where(species == "Gentoo", 5000, 3700), 400).astype(int),
            "year": rng.choice([2007, 2008, 2009], n),
        }
    )


def _load_any(path):
    if path.endswith(".parquet"):
        return pd.read_parquet(path)
    if path.endswith((".csv", ".tsv")):
        return pd.read_csv(path, sep="\t" if path.endswith(".tsv") else ",")
    raise SystemExit(f"unsupported file type: {path} (use .csv / .tsv / .parquet)")


if __name__ == "__main__":
    import argparse
    import json as _json

    ap = argparse.ArgumentParser(
        description="Profile a dataset: classify column roles, propose an exploration plan and story outline.",
        epilog="Examples:\n  python exploration_profiler.py data.parquet\n"
        "  python exploration_profiler.py data.csv --json\n"
        "  python exploration_profiler.py --demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("data", nargs="?", help="path to a .csv / .tsv / .parquet file")
    ap.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON (plan + outline) to stdout"
    )
    ap.add_argument(
        "--demo", action="store_true", help="run built-in synthetic demos (bike / penguins / eth)"
    )
    args = ap.parse_args()

    if args.demo:
        for label, d in [
            ("Fremont bikes (temporal + measures)", sample_fremont()),
            ("Penguins (categorical + measures)", _synthetic_penguins()),
            ("Ethereum txns (temporal + measures + ids)", _synthetic_eth()),
        ]:
            print(f"\n### {label} ###")
            for i, beat in enumerate(story_outline(d), 1):
                print(f"  {i:2}. {beat}")
    elif not args.data:
        ap.print_help()
    else:
        df = _load_any(args.data)
        if args.json:
            plan = recommend(df)
            plan["columns"] = [vars(c) for c in plan["columns"]]
            plan["outline"] = story_outline(df)
            print(_json.dumps(plan, indent=2, default=str))
        else:
            print(render_plan(df, args.data))
            print("\nstory outline:")
            for i, beat in enumerate(story_outline(df), 1):
                print(f"  {i:2}. {beat}")

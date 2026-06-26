"""
nb_from_spec.py — deterministic builder: a declarative story-spec (JSON) -> .ipynb

The LLM authors a compact JSON spec (story arc + narration + which columns), and
this script renders it to a valid notebook. The vetted hvPlot/HoloViews code for
each view archetype lives HERE, so the model never hand-writes plotting code (and
can't get the responsive/width idioms wrong). `kind: "code"` is the escape hatch
for bespoke steps.

Usage:  python nb_from_spec.py bike_story.spec.json  ->  bike_story.ipynb
"""

import json

# --- vetted view renderers: params -> Python source string -------------------


def r_profile(p):
    # Self-contained: the delivered notebook must not depend on the skill's
    # profiler at runtime. The roles the profiler found go into the narration.
    return "df.info()\ndf.describe(include='all').T"


def r_resample(p):
    return (
        f"df[{p['cols']!r}].resample({p.get('freq', 'W')!r}).{p.get('agg', 'sum')}().hvplot.line(\n"
        f"    responsive=True, height=300, yformatter=NumeralTickFormatter(format='0,0'),\n"
        f"    value_label={p.get('ylabel', 'value')!r}, title={p['title']!r})"
    )


def r_rhythm(p):
    src = {"hour": "df.index.hour", "weekday": "df.index.dayofweek"}[p.get("by", "hour")]
    m = p["measure"]
    return (
        f"by = df.groupby({src})[{m!r}].mean().rename('mean {m}')\n"
        f"by.hvplot.line(responsive=True, height=300, xlabel={p.get('by', 'hour')!r},\n"
        f"    yformatter=NumeralTickFormatter(format='0,0'), title={p['title']!r}) * by.hvplot.scatter(size=25)"
    )


def r_split(p):
    m = p["measure"]
    return (
        f"prof = (df.assign(hour=df.index.hour,\n"
        f"                  daytype=np.where(df.index.dayofweek < 5, 'weekday', 'weekend'))\n"
        f"          .groupby(['daytype', 'hour'])[{m!r}].mean().reset_index())\n"
        f"prof.hvplot.line(x='hour', y={m!r}, by='daytype', responsive=True, height=300,\n"
        f"    yformatter=NumeralTickFormatter(format='0,0'), title={p['title']!r})"
    )


def r_heatmap(p):
    m = p["measure"]
    return (
        f"fp = (df.assign(hour=df.index.hour, day=df.index.day_name())\n"
        f"        .groupby(['day', 'hour'])[{m!r}].mean().reset_index())\n"
        f"order = ['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']\n"
        f"fp['day'] = pd.Categorical(fp['day'], categories=order, ordered=True)\n"
        f"hv.HeatMap(fp, kdims=['hour', 'day'], vdims=[{m!r}]).opts(\n"
        f"    responsive=True, height=320, cmap='viridis', colorbar=True, tools=['hover'],\n"
        f"    xlabel='hour of day', ylabel='', title={p['title']!r})"
    )


def r_facet(p):
    return f"df.hvplot.box(y={p['measure']!r}, by={p['by']!r}, responsive=True, height=320, title={p['title']!r})"


def r_scatter(p):
    return (
        f"df.hvplot.scatter(x={p['x']!r}, y={p['y']!r}, by={p.get('by')!r},\n"
        f"    responsive=True, height=340, alpha=0.6, title={p['title']!r})"
    )


def r_pca_dayshape(p):
    m = p["measure"]
    return (
        f"mat = df[{m!r}].groupby([df.index.normalize(), df.index.hour]).sum().unstack().dropna()\n"
        f"mat = mat[mat.sum(1) > 50]\n"
        f"X = mat.values.astype(float); X = X / X.sum(1, keepdims=True)\n"
        f"U, S, Vt = np.linalg.svd(X - X.mean(0), full_matrices=False)\n"
        f"pcs = U[:, :2] * S[:2]\n"
        f"pcdf = pd.DataFrame({{'PC1': pcs[:, 0], 'PC2': pcs[:, 1], 'date': mat.index.astype(str),\n"
        f"    'daytype': np.where(mat.index.dayofweek < 5, 'weekday', 'weekend')}})\n"
        f"pcdf.hvplot.scatter('PC1', 'PC2', by='daytype', hover_cols=['date'],\n"
        f"    responsive=True, height=360, alpha=0.6, size=30, title={p['title']!r})"
    )


def r_code(p):
    return p["code"]


RENDERERS = {
    "profile": r_profile,
    "resample": r_resample,
    "rhythm": r_rhythm,
    "split": r_split,
    "heatmap": r_heatmap,
    "facet": r_facet,
    "scatter": r_scatter,
    "pca_dayshape": r_pca_dayshape,
    "code": r_code,
}

IMPORTS = (
    "import numpy as np\n"
    "import pandas as pd\n"
    "import hvplot.pandas  # noqa: activates the .hvplot accessor (Bokeh)\n"
    "import holoviews as hv\n"
    "from bokeh.models import NumeralTickFormatter"
)


def _md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": text}


def _code(text):
    return {
        "cell_type": "code",
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": text,
    }


def build(spec):
    cells = [_md(f"# {spec['title']}\n\n{spec.get('intro', '')}"), _code(IMPORTS)]
    if spec.get("setup"):
        cells.append(_code(spec["setup"]))
    for b in spec["beats"]:
        if b.get("narrate"):
            cells.append(_md(b["narrate"]))
        if b["kind"] not in RENDERERS:
            raise SystemExit(f"unknown beat kind: {b['kind']!r}")
        src = RENDERERS[b["kind"]](b.get("params", {}))
        if src.strip():
            cells.append(_code(src))
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(
        description="Render a declarative story-spec (JSON) into a Jupyter notebook.",
        epilog="Example: python build_notebook.py bike_story.spec.json -o bike_story.ipynb",
    )
    ap.add_argument("spec", help="path to a .spec.json story spec")
    ap.add_argument("--output", "-o", help="output .ipynb path (default: alongside the spec)")
    args = ap.parse_args()

    out = args.output or args.spec.replace(".spec.json", ".ipynb").replace(".json", ".ipynb")
    spec = json.load(open(args.spec))
    nb = build(spec)
    json.dump(nb, open(out, "w"), indent=1)
    print(f"wrote {out}  ({len(nb['cells'])} cells from {len(spec['beats'])} beats)")

# %% [markdown]
# # Exploring the Fremont Bridge bike counts
#
# A practitioner's walk through an unfamiliar dataset. The shape of the walk is
# the point: **profile first to decide what is worth asking, then proceed one
# question at a time** — each section poses a question (and what we'd expect to
# see if a hunch is right), runs *one* view, reads the answer off it, and lets
# that answer pick the next question. We follow the surprises rather than a
# pre-planned tour.
#
# Render to a notebook with: `jupytext --to notebook seattle_bikes.py`
#
# > **Grounding.** The findings narrated below were read off the real outputs
# > after running this notebook against the public CSV (see §0). They are
# > reported as findings *because the cells ran* — not because the pattern is
# > "well known". Re-run it on a fresh export and read the numbers off your own
# > plots; where a sentence and a plot disagree, trust the plot.

# %%
import holoviews as hv  # for the hour × weekday HeatMap
import numpy as np
import pandas as pd
from bokeh.models import NumeralTickFormatter

# Fremont Bridge Hourly Bicycle Counts — data.seattle.gov (dataset 65db-xm6k).
# Export the CSV as FremontHourly.csv next to this file, then load it:
raw = pd.read_csv("FremontHourly.csv", parse_dates=[0], index_col=0)
raw.index.name = "Date"
east = next(c for c in raw.columns if "east" in c.lower())
west = next(c for c in raw.columns if "west" in c.lower())
df = pd.DataFrame({"East": raw[east], "West": raw[west]})
df["Total"] = df["East"] + df["West"]
df.head()

# %% [markdown]
# ## 0. Profile first — what are we holding, and what does each column earn?
#
# Before any plot, classify every column by role, because the roles decide which
# questions are even askable. We look at shape, types, missingness and — the key
# signal — cardinality.

# %%
profile = pd.DataFrame(
    {
        "dtype": df.dtypes.astype(str),
        "n_unique": df.nunique(),
        "pct_missing": (df.isna().mean() * 100).round(1),
    }
)
profile

# %% [markdown]
# Reading that off:
#
# - The **index is temporal** (a `DatetimeIndex`) — our one dimension to slice
#   by. Everything interesting will be "measure *conditioned on* some slice of
#   time": hour, weekday, month.
# - **`East` and `West` are measures**, and not redundant ones — they encode
#   *direction*. That is a column begging to be split on, so it earns its own
#   question later (§5), not just a `Total`.
# - **`Total`** is the headline measure we'll lead with.
#
# So the profile hands us a short list of questions worth asking: is there a
# trend over time, a within-day rhythm, does that rhythm differ by day or season,
# and is the East/West split telling us something. We take them in the order the
# data forces (you can't read a weekday split before you know the daily rhythm
# exists).

# %% [markdown]
# ## 1. First look at the raw signal — and why it fails
#
# Start naive: just plot the hourly `Total`. **Hypothesis:** maybe the trend is
# visible directly. We run it mainly to *rule it out* and motivate the next move.

# %%
df["Total"].hvplot.line(
    responsive=True,
    height=260,
    alpha=0.5,
    yformatter=NumeralTickFormatter(format="0,0"),
    title="Raw hourly counts — too dense to read",
)

# %% [markdown]
# That answers its own question by failing: hourly resolution is a solid smear of
# ink, no structure visible. The fix is to **aggregate up** until structure
# appears — which is itself the next question: at what timescale does this data
# have a shape?

# %% [markdown]
# ## 2. Zoom out to weekly totals — trend and season appear
#
# Resample to weekly sums. **What we'd expect** if ridership is weather-driven: a
# summer/winter swing; any real growth would show as a slow climb under it.

# %%
weekly = df[["East", "West", "Total"]].resample("W").sum()
weekly.hvplot.line(
    responsive=True,
    height=300,
    value_label="weekly riders",
    yformatter=NumeralTickFormatter(format="0,0"),
    title="Weekly ridership — trend, seasonality, weather wobble",
)

# %% [markdown]
# Both show up: a strong seasonal swing and a slow multi-year climb. So *some*
# uptick is real growth, but much of any short window is just season and weather.
# The seasonal swing raises the next question — that within-year variation has to
# come from *somewhere* in the day. What does a typical day look like?

# %% [markdown]
# ## 3. The daily rhythm — is this a commuter route?
#
# Average `Total` over hour-of-day. **Hypothesis:** if these are commuters we
# should see two sharp peaks (morning and evening) and a quiet midday; if it's
# leisure riding, a single midday hump instead.

# %%
by_hour = df.groupby(df.index.hour)["Total"].mean().rename("mean riders")
by_hour.hvplot.line(
    responsive=True,
    height=300,
    xlabel="hour of day",
    yformatter=NumeralTickFormatter(format="0,0"),
    title="The daily rhythm: two commute peaks",
) * by_hour.hvplot.scatter(size=25)

# %% [markdown]
# The commuter hypothesis holds: sharp peaks around 8am and 5pm, a midday lull,
# near-zero overnight. But an average over *all* days is suspicious — it could be
# blending two different kinds of day into one curve. That's the next question.

# %% [markdown]
# ## 4. Is one average hiding two populations? — weekday vs weekend
#
# Split the same rhythm by weekday vs weekend. **Hypothesis:** if §3's peaks are
# commuting, they should belong to weekdays only, and weekends should look like
# leisure (one midday hump).

# %%
prof = (
    df.assign(hour=df.index.hour, daytype=np.where(df.index.dayofweek < 5, "weekday", "weekend"))
    .groupby(["daytype", "hour"])["Total"]
    .mean()
    .reset_index()
)
prof.hvplot.line(
    x="hour",
    y="Total",
    by="daytype",
    responsive=True,
    height=300,
    yformatter=NumeralTickFormatter(format="0,0"),
    title="Weekday commute vs weekend leisure",
)

# %% [markdown]
# Confirmed, and it *was* two populations: weekdays keep the bimodal commute;
# weekends collapse to a single lower midday hump. The single curve in §3 was an
# average of two genuinely different days. Now two questions branch off — does the
# commute rhythm also shift across the *seasons* we saw in §2, and does the
# East/West direction (flagged in the profile) carry its own story? Take them in
# turn.

# %% [markdown]
# ## 5. Does direction matter? — the profile's unanswered column
#
# §0 flagged `East`/`West` as a split we hadn't used. **Hypothesis:** if people
# ride one way to work and the other way home, the two directions should peak at
# *different* hours and trade places at midday.

# %%
by_dir = df.assign(hour=df.index.hour).groupby("hour")[["East", "West"]].mean()
by_dir.hvplot.line(
    responsive=True,
    height=300,
    xlabel="hour of day",
    value_label="mean riders",
    title="Direction flips at midday: morning one way, evening the other",
)

# %% [markdown]
# The two directions are near mirror images: one leads in the morning, the other
# in the evening — the same commuters, outbound and back. The `East`/`West`
# columns weren't redundant after all; reading the profile carefully is what put
# this question on the list.

# %% [markdown]
# ## 6. Does the rhythm change across seasons? — hand the reader the knob
#
# `month` is a free dimension: rather than freeze one month or fan out twelve
# static facets, pass `groupby="month"` and hvPlot builds a month slider for free
# (a `HoloMap`, no server, no callback). This is interactivity where it *earns*
# its place — the reader drives the one dimension worth sweeping.

# %%
by_month_hour = (
    df.assign(hour=df.index.hour, month=df.index.month)
    .groupby(["month", "hour"])["Total"]
    .mean()
    .reset_index()
)
by_month_hour.hvplot.line(
    x="hour",
    y="Total",
    groupby="month",
    responsive=True,
    height=300,
    xlabel="hour of day",
    ylim=(0, None),
    yformatter=NumeralTickFormatter(format="0,0"),
    title="Daily rhythm, month by month (drag the slider)",
)

# %% [markdown]
# Drag the slider: the commute peaks stay put in clock time but fatten in the
# light summer months and thin in the dark ones — the seasonal swing from §2,
# now located *inside* the daily rhythm.

# %% [markdown]
# ## 7. The whole week on one panel — a summary view
#
# We've answered the questions one at a time; close by putting two dimensions on
# one panel — hour × weekday as a heatmap — as a compact summary of everything
# above, useful to hand to someone who didn't walk through it.

# %%
fp = (
    df.assign(hour=df.index.hour, day=df.index.day_name())
    .groupby(["day", "hour"])["Total"]
    .mean()
    .reset_index()
)
order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
fp["day"] = pd.Categorical(fp["day"], categories=order, ordered=True)
hv.HeatMap(fp, kdims=["hour", "day"], vdims=["Total"]).opts(
    responsive=True,
    height=320,
    cmap="viridis",
    colorbar=True,
    tools=["hover"],
    xlabel="hour of day",
    ylabel="",
    title="Mean riders by hour × weekday (the weekly fingerprint)",
)

# %% [markdown]
# The commute ridge glows Mon–Fri at 8 and 17; the weekend is a soft midday smear
# — §3 through §6 in a single frame. The story the profile pointed us at —
# a directional commuter route with a daily rhythm that breathes with the seasons
# — is now visible top to bottom, each claim read off a cell that ran.

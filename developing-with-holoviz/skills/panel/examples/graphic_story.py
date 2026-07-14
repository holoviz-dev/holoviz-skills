"""A NYT-style graphic story built with panel-material-ui.

A scrollable editorial article: a masthead, a narrow reading column, and prose
interleaved with explanatory charts (takeaway titles, one highlight color, direct
inline labels, annotations, no toolbars). Each chart follows the hvplot
`distilling-explanatory-plots` reference; this file is the Panel shell that stacks them into
a narrative.

Run with:  panel serve graphic_story.py --show
"""

import holoviews as hv
import numpy as np
import pandas as pd
import panel as pn
import panel_material_ui as pmui

hv.extension("bokeh")
pn.extension()

df = pd.read_csv("https://raw.githubusercontent.com/mwaskom/seaborn-data/master/mpg.csv")
df["year"] = 1900 + df["model_year"]
df["origin_name"] = df["origin"].map({"usa": "American", "europe": "European", "japan": "Japanese"})

RED, BLUE, GRAY, GRAYLINE = "#c0392b", "#2c7fb8", "#cfcfcf", "#9e9e9e"
W, H = 620, 320
FS = {"title": 14, "labels": 11, "ticks": 10}


def style(el, title, xlabel=""):
    """Shared styling so every chart in the piece reads as one visual family."""
    return el.opts(
        toolbar=None,
        show_grid=False,
        width=W,
        height=H,
        title=title,
        fontsize=FS,
        xlabel=xlabel,
        ylabel="miles per gallon",
    )


# 1 — the trend, with the oil shocks annotated in place
yr = df.groupby("year")["mpg"].median().reset_index()
c1 = (
    hv.Curve(yr, "year", "mpg").opts(color=RED, line_width=3)
    * hv.Scatter(yr, "year", "mpg").opts(color=RED, size=6)
    * hv.VLine(1973).opts(color=GRAY, line_dash="dashed")
    * hv.VLine(1979).opts(color=GRAY, line_dash="dashed")
    * hv.Text(1973, 33, "1973 oil crisis").opts(
        text_font_size="8pt", text_color="#888", text_align="left"
    )
    * hv.Text(1979, 19, "1979 oil crisis").opts(
        text_font_size="8pt", text_color="#888", text_align="left"
    )
)
c1 = style(c1, "Fuel economy nearly doubled in a decade").opts(ylim=(10, 38))

# 2 — the mechanism: the whole cloud, with a trend line
d2 = df.dropna(subset=["weight", "mpg"])
m, b = np.polyfit(d2["weight"], d2["mpg"], 1)
xs = np.array([d2["weight"].min(), d2["weight"].max()])
c2 = hv.Scatter(d2, "weight", "mpg").opts(color=GRAY, size=4, alpha=0.6) * hv.Curve(
    (xs, m * xs + b)
).opts(color=RED, line_width=3)
c2 = style(c2, "The lever was weight: heavier cars were thirstier", xlabel="weight (lbs)")

# 3 — three series, identified by direct inline labels instead of a legend
yo = df.groupby(["year", "origin_name"])["mpg"].median().reset_index()


def oline(name, color, width, dy=0):
    d = yo[yo.origin_name == name].sort_values("year")
    lab = hv.Text(d.iloc[-1].year + 0.25, d.iloc[-1].mpg + dy, name).opts(
        text_font_size="9pt", text_color=color, text_align="left", text_font_style="bold"
    )
    return hv.Curve(d, "year", "mpg").opts(color=color, line_width=width) * lab


c3 = (
    oline("European", GRAYLINE, 2, dy=1.2)
    * oline("Japanese", BLUE, 2.5, dy=-1.2)
    * oline("American", RED, 3)
)
c3 = style(c3, "American cars started far behind, then closed the gap").opts(
    show_legend=False, xlim=(1970, 1985), ylim=(12, 42)
)


def prose(text):
    # Markdown, not Typography, so inline **bold** and `code` render.
    return pn.pane.Markdown(text, styles={"font-size": "16px", "line-height": "1.6"})


article = pmui.Column(
    pmui.Typography("The Great American Car Diet", variant="h3", sx={"fontWeight": 700, "mt": 2}),
    pmui.Typography(
        "How the oil shocks of the 1970s remade the automobile",
        variant="subtitle1",
        sx={"color": "text.secondary", "mb": 1},
    ),
    prose(
        "In 1970 the typical new car managed about **17 miles per gallon**. By 1982 that had "
        "climbed past **30**. Two oil shocks, a decade apart, turned fuel economy from an "
        "afterthought into the number that sold cars."
    ),
    pn.pane.HoloViews(c1),
    prose(
        "The lever was weight. Plot every car and the trade-off is nearly a straight line: the "
        "heavier the car, the fewer the miles per gallon. The efficiency gains came from making "
        "cars lighter."
    ),
    pn.pane.HoloViews(c2),
    prose(
        "Not everyone started in the same place. American cars were the heaviest and thirstiest "
        "in 1970, while Japanese imports were already frugal. The gap narrowed as "
        "Detroit caught up."
    ),
    pn.pane.HoloViews(c3),
    prose("_Source: UCI / seaborn `mpg` sample dataset, model years 1970–1982._"),
    sizing_mode="stretch_width",
)

THEME = {
    "palette": {"primary": {"main": "#1a1a1a"}},  # dark, understated masthead
    "typography": {"fontFamily": "Georgia, 'Times New Roman', serif"},  # editorial serif
}

pmui.Page(
    title="The Upshot",
    theme_config=THEME,
    main=[pmui.Container(article, width_option="md")],  # clamp to a readable column
).servable()

# Distilling Explanatory Plots

An explanatory plot is for an audience: it makes one point and strips away everything that
doesn't serve it — the opposite of [Composing Exploratory Plots](composing-exploratory-plots.md),
which shows everything and invites interaction.

## Contents

- [Lead with the takeaway](#lead-with-the-takeaway)
- [Subtract to one message](#subtract-to-one-message)
- [Direct labels, not a legend](#direct-labels-not-a-legend)
- [Gray context, one highlight](#gray-context-one-highlight)
- [Annotate in the static view](#annotate-in-the-static-view)
- [Kill chart junk](#kill-chart-junk)
- [Show uncertainty](#show-uncertainty)
- [Example](#example)

## Lead with the takeaway

The title is the finding, not the variable: `"Skills cut output tokens 38%"`, not
`"Tokens by variant"`. The chart proves a sentence the reader has already read.

## Subtract to one message

Keep the single mark that makes the point and drop the rest — where the exploratory view
layered violin, box, and scatter across facets, the explanatory version is usually one series
or one comparison. Pick the encoding that makes it trivial: sorted bars for a ranking, a line
for a trend, a slope or dumbbell for before/after.

## Direct labels, not a legend

Label the series on the mark itself with `hv.Text` at the line end (or `hv.Labels`) and set
`show_legend=False`, so the eye never leaves the data to decode a color key.

## Gray context, one highlight

Mute everything to gray and give the highlight color only to the series that
carries the message. One focus, one color encoding per figure.

## Annotate in the static view

Mark the point with `hv.Text`, `hv.VLine`/`hv.HLine`, or an arrow — the event, the threshold,
the delta. Assume no interaction: readers won't hover, so the static view must carry the whole
message. Set `toolbar=None`, or control which tools appear via `default_tools=[]` / `tools=[]`, rather than relying on hover tooltips — see [Decluttering Plots](../decluttering-plots/SKILL.md) for the full toolbar/tools guidance.

## Kill chart junk

Pin the axis range to the data (`ylim=`/`xlim=`); an auto-range that pads to round
numbers leaves dead whitespace. Drop gridlines (`show_grid=False`), thin the
ticks, and remove the toolbar.

## Show uncertainty

When the point rests on noisy estimates, show the spread (a band, error bars, a
range) rather than rounding to a single confident number.

## Example

Median fuel economy over time, with the takeaway as the title, the oil shocks
annotated in place, one highlight color, and no toolbar:

```python
import hvplot.pandas  # noqa
import holoviews as hv

trend = df.hvplot.line("year", "mpg", color="#c0392b", line_width=3)
shock = hv.VLine(1979).opts(color="#bbbbbb", line_dash="dashed")
note = hv.Text(1979, 19, "1979 oil crisis").opts(text_align="left", text_color="#888")

(trend * shock * note).opts(
    title="Fuel economy nearly doubled in a decade",
    toolbar=None, show_grid=False, show_legend=False, ylim=(10, 38),
)
```

To assemble several explanatory charts into a scrollable narrative, see
[Data Storytelling](../panel/data-storytelling.md).

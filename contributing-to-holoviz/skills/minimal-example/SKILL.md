---
name: minimal-example
description: Write a minimal, self-contained, reproducible example for a HoloViz behavior or bug. Use when drafting a bug report, an issue reproducer, a PR "How to test" snippet, or any code sample a maintainer must be able to paste and run unchanged.
metadata:
  version: "0.1.0"
  author: holoviz
---

# Minimal Examples

A reproducer a tester pastes and runs unchanged to check a fix, so keep it short
enough to skim, not study. These are the traps specific to HoloViz reproducers.

- Render explicitly with `pn.serve(obj)`; don't end on the bare object. In a
  script the notebook `_repr_html_` never fires, so `obj` alone does nothing and
  any render-time error (layout sizing, projection, aspect, colorbar) stays
  hidden. `pn.serve` renders any HoloViews/hvPlot/Panel object and surfaces it.
- Declare the backend the behavior depends on (`hv.extension('bokeh')` vs
  `'matplotlib'`). The same code renders through different code paths per
  backend, so an implicit backend makes the report ambiguous.
- Generate data inline and seed it (`rng = np.random.default_rng(0)`), or load a
  dataset the reader can fetch too, e.g. a URL, `xr.tutorial.open_dataset`, or
  `bokeh.sampledata`. Just don't `read_csv` a local path only you have.
- For a bug, paste the versions that matter (`hv.__version__`, `pn.__version__`,
  and the backend: bokeh/matplotlib/cartopy). HoloViz bugs are usually
  version-specific.
- End with a one-line comment on the before behavior (what a tester sees without
  the fix) and the after (what a correct run should show), so they know what to
  look for without studying the code.

```python
import numpy as np, pandas as pd, holoviews as hv, panel as pn
hv.extension('bokeh')                       # backend the behavior depends on

rng = np.random.default_rng(0)
df = pd.DataFrame({'x': rng.normal(size=20), 'y': rng.normal(size=20)})
pn.serve(hv.Scatter(df, 'x', 'y'))          # force render; raises the error if present
# Before: raises ValueError / renders blank.
# After:  shows a scatter of 20 points.
```

# Using Tabulator

Tabulator is the preferred widget for displaying DataFrames in Panel apps — sortable, filterable, paginated. Requires `pn.extension("tabulator")`.

## Contents

- [Basic Setup](#basic-setup)
- [Widget-Based Filtering with `add_filter`](#widget-based-filtering-with-add_filter)
  - [Function-Based Filtering](#function-based-filtering)
- [Checkbox Selection](#checkbox-selection)
- [Row Content (Expandable Details)](#row-content-expandable-details)

## Basic Setup

```python
self._table = pn.widgets.Tabulator(
    value=df,
    sizing_mode="stretch_width",
    layout="fit_columns",
    disabled=True,            # prevent cell editing
    show_index=False,
    theme="materialize",
    pagination="remote",
    page_size=15,
    formatters={
        "Revenue": {"type": "money", "symbol": "$", "precision": 0},
        "Cost": {"type": "money", "symbol": "$", "precision": 0},
    },
)
```

- `layout="fit_columns"` fills available width. Best option for responsive layouts.
- `disabled=True` prevents editing — set `False` for editable tables.
- Prefer Tabulator formatters/editors over Bokeh types.

## Widget-Based Filtering with `add_filter`

Wire sidebar widgets directly as table filters — Tabulator watches widget values and shows/hides rows automatically. No manual filtering needed.

```python
region_filter = pmui.CheckBoxGroup(value=list(REGIONS), options=REGIONS)
product_filter = pmui.CheckBoxGroup(value=list(PRODUCTS), options=PRODUCTS)

# Must be called AFTER table has data (value is set),
# otherwise raises AttributeError: 'NoneType' has no attribute 'columns'
table.add_filter(region_filter, "Region")
table.add_filter(product_filter, "Product")
```

Filter behavior depends on the widget value type: a **list** matches any item in the list, a **tuple** is interpreted as a range (inclusive), a **scalar** checks for equality.

Use `table.current_view` to inspect the currently visible (filtered + sorted) DataFrame.

### Function-Based Filtering

For complex filtering, pass a bound function:

```python
search = pn.widgets.TextInput(name="Search", value="")

def contains_filter(df, pattern, column):
    if not pattern:
        return df
    return df[df[column].str.contains(pattern, case=False)]

table.add_filter(pn.bind(contains_filter, pattern=search, column="Name"))
```

## Checkbox Selection

Use `selectable="checkbox"` for row selection with checkboxes. Watch the `selection` parameter for changes and read `selected_dataframe` for the selected rows.

```python
self._table = pn.widgets.Tabulator(
    ...,
    selectable="checkbox",
)
self._table.param.watch(self._on_selection, "selection")

def _on_selection(self, event):
    selected = self._table.selected_dataframe
    if selected is not None and not selected.empty:
        # Use selected rows to filter charts, update KPIs, etc.
        ...
```

## Row Content (Expandable Details)

Use `row_content` to render an expandable detail region below each row. Pass a function that receives a `pandas.Series` (the row) and returns a Panel object.

```python
def row_detail(row):
    return pn.Column(
        f"**{row['Name']}** — {row['Region']}",
        pn.pane.HoloViews(
            df[df["Name"] == row["Name"]].hvplot.line(x="date", y="revenue"),
            height=200,
        ),
    )

self._table = pn.widgets.Tabulator(
    value=df,
    row_content=row_detail,
    sizing_mode="stretch_width",
)
```

- The function is called lazily when the user expands a row (clicks the `+` icon).
- Set `embed_content=True` to pre-render all row content on load instead of lazily — useful when there are few rows and you want instant expansion, but expensive with many rows.

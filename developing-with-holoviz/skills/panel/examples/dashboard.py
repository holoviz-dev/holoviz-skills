"""
KPI dashboard example using panel-material-ui and HoloViews.

Trend indicators for KPI cards, DynamicMap charts that preserve zoom/pan,
Tabulator checkbox selection that cross-filters charts, and a responsive
pmui.Grid layout. Demonstrates pn.indicators.Trend, DynamicMap with trigger
pattern, Tabulator selection-driven filtering, param.DataFrame as single
source of truth, and pmui.Page template with sidebar filters.

Run: panel serve examples/dashboard.py --dev --show
"""

import numpy as np
import pandas as pd
import panel as pn
import panel_material_ui as pmui
import param

from bokeh.models import NumeralTickFormatter
import holoviews as hv

pn.extension("tabulator", throttled=True, defer_load=True, loading_indicator=True)

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

THEME_CONFIG = {
    "light": {
        "palette": {
            "primary": {"main": "#1565c0"},
            "secondary": {"main": "#26a69a"},
            "success": {"main": "#2e7d32"},
            "warning": {"main": "#f57c00"},
            "error": {"main": "#c62828"},
        },
        "typography": {
            "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            "h4": {"fontWeight": 600, "letterSpacing": "-0.02em"},
            "h6": {"fontWeight": 600},
            "body1": {"lineHeight": 1.6},
        },
        "shape": {"borderRadius": 12},
        "components": {
            "MuiPaper": {
                "styleOverrides": {
                    "root": {"boxShadow": "0 2px 12px rgba(0,0,0,0.06)"},
                },
            },
        },
    },
    "dark": {
        "palette": {
            "primary": {"main": "#5c9ce6"},
            "secondary": {"main": "#4db6ac"},
            "success": {"main": "#66bb6a"},
            "warning": {"main": "#ffa726"},
            "error": {"main": "#ef5350"},
        },
        "typography": {
            "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            "h4": {"fontWeight": 600, "letterSpacing": "-0.02em"},
            "h6": {"fontWeight": 600},
            "body1": {"lineHeight": 1.6},
        },
        "shape": {"borderRadius": 12},
    },
}

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

REGIONS = ["North", "South", "East", "West"]
PRODUCTS = ["Widget A", "Widget B", "Widget C", "Widget D"]
np.random.seed(42)


def generate_sales_data():
    """Generate 12 months of daily sales data."""
    dates = pd.date_range("2025-01-01", periods=365, freq="D")
    rows = []
    for date in dates:
        for region in REGIONS:
            for product in PRODUCTS:
                base = {"North": 120, "South": 95, "East": 110, "West": 85}[region]
                seasonal = 1 + 0.3 * np.sin(2 * np.pi * date.dayofyear / 365)
                product_factor = {"Widget A": 1.2, "Widget B": 0.9, "Widget C": 1.0, "Widget D": 0.7}[product]
                revenue = base * seasonal * product_factor * (0.8 + 0.4 * np.random.random())
                units = int(revenue / (15 + 5 * np.random.random()))
                rows.append({
                    "date": date,
                    "region": region,
                    "product": product,
                    "revenue": round(revenue, 2),
                    "units": units,
                    "cost": round(revenue * (0.55 + 0.1 * np.random.random()), 2),
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

REGION_COLORS = {"North": "#ff7f0e", "South": "#2ca02c", "East": "#1f77b4", "West": "#d62728"}


class SalesDashboard(pn.viewable.Viewer):
    """KPI dashboard with Tabulator selection-driven chart filtering."""

    _base_df = param.DataFrame(doc="""
        Full dataset — generated once, never changes.""")

    _filtered_df = param.DataFrame(doc="""
        Single source of truth — _base_df narrowed by sidebar filters
        and Tabulator selection. KPIs, charts, and table all consume this.""")

    _trigger = param.Integer(default=0, doc="""
        Signal for DynamicMap — increment to refresh charts while preserving zoom.""")

    def __init__(self, df=None, **params):
        if df is None:
            df = generate_sales_data()
        params["_base_df"] = df

        # KPI Trend indicators — create once, update data via watcher
        trend_opts = dict(sizing_mode="stretch_width", height=120, plot_type="area")
        self._revenue_trend = pn.indicators.Trend(
            name="Revenue", plot_color="#1565c0", **trend_opts,
        )
        self._units_trend = pn.indicators.Trend(
            name="Units Sold", plot_color="#26a69a", **trend_opts,
        )
        self._margin_trend = pn.indicators.Trend(
            name="Gross Margin %", plot_color="#2e7d32", **trend_opts,
        )
        self._aov_trend = pn.indicators.Trend(
            name="Avg Order Value", plot_color="#f57c00", **trend_opts,
        )

        # Data table — select rows to cross-filter charts
        self._table = pn.widgets.Tabulator(
            sizing_mode="stretch_width",
            layout="fit_columns",
            disabled=True,
            selectable="checkbox",
            theme="materialize",
            pagination="remote",
            page_size=15,
            show_index=False,
            formatters={
                "Revenue": {"type": "money", "symbol": "$", "precision": 0},
                "Cost": {"type": "money", "symbol": "$", "precision": 0},
            },
        )
        self._table.param.watch(self._on_table_selection, "selection")

        # Sidebar widgets
        self._date_picker = pmui.DateRangeSlider(
            start=pd.Timestamp("2025-01-01"),
            end=pd.Timestamp("2025-12-31"),
            value=(pd.Timestamp("2025-01-01"), pd.Timestamp("2025-12-31")),
            sizing_mode="stretch_width",
            margin=(5, 16),
        )
        self._region_filter = pmui.CheckBoxGroup(
            value=list(REGIONS),
            options=REGIONS,
            label="Regions",
        )
        self._product_filter = pmui.CheckBoxGroup(
            value=list(PRODUCTS),
            options=PRODUCTS,
            label="Products",
        )

        super().__init__(**params)

        # Wire sidebar widgets → _update_all
        pn.bind(
            self._update_all,
            self._date_picker.param.value,
            self._region_filter.param.value,
            self._product_filter.param.value,
            watch=True,
        )
        self._update_all()  # initial render — populates table data

        # Wire checkbox widgets as Tabulator filters — must come after
        # _update_all so the table has data for add_filter to inspect.
        self._table.add_filter(self._region_filter, "Region")
        self._table.add_filter(self._product_filter, "Product")

        # DynamicMaps created after super — lazily render with current data,
        # preserve zoom/pan on subsequent filter changes via _trigger.
        curves_dmap = hv.DynamicMap(pn.bind(self._render_curves, self.param._trigger))
        cumulative_dmap = hv.DynamicMap(pn.bind(self._render_cumulative, self.param._trigger))
        self._chart_pane = pn.pane.HoloViews(
            (curves_dmap + cumulative_dmap).opts(shared_axes=False),
            sizing_mode="stretch_width",
            height=400,
            linked_axes=False,
            theme="light_minimal",
        )

    # -- Data --

    def _apply_sidebar_filters(self):
        """Apply sidebar filters to _base_df."""
        df = self._base_df
        start, end = self._date_picker.value
        start = pd.Timestamp(start)
        end = pd.Timestamp(end)
        mask = (
            (df["date"] >= start)
            & (df["date"] <= end)
            & (df["region"].isin(self._region_filter.value))
            & (df["product"].isin(self._product_filter.value))
        )
        return df[mask]

    def _apply_table_selection(self, df):
        """Narrow df by Tabulator checkbox selection, if any."""
        if self._table.selection and self._table.value is not None:
            selected = self._table.selected_dataframe
            if selected is not None and not selected.empty:
                keys = selected[["Region", "Product"]].rename(
                    columns={"Region": "region", "Product": "product"},
                )
                return df.merge(keys, on=["region", "product"])
        return df

    # -- Chart rendering (DynamicMap callbacks) --

    def _render_curves(self, trigger):
        """Return NdOverlay of weekly revenue curves by region."""
        df = self._filtered_df
        if df is None or df.empty:
            return hv.NdOverlay({"(none)": hv.Curve([], kdims=["date"], vdims=["revenue"])}, kdims=["Region"]).opts(
                "Curve", responsive=True, height=350,
            )
        weekly = df.groupby([pd.Grouper(key="date", freq="W"), "region"]).agg(
            revenue=("revenue", "sum"),
        ).reset_index()

        region_curves = {}
        for region_name, region_df in weekly.groupby("region"):
            region_curves[region_name] = hv.Curve(
                region_df, kdims=["date"], vdims=["revenue"],
            ).opts(
                color=REGION_COLORS.get(region_name, "#999"),
                line_width=2,
            )
        if not region_curves:
            region_curves["(none)"] = hv.Curve([], kdims=["date"], vdims=["revenue"])

        return hv.NdOverlay(region_curves, kdims=["Region"]).opts(
            "NdOverlay",
            legend_position="top_left",
            title="Weekly Revenue by Region",
        ).opts(
            "Curve",
            responsive=True,
            height=350,
            tools=["hover", "xwheel_zoom"],
            active_tools=["xwheel_zoom"],
            default_tools=["reset"],
            hover_tooltips=[
                ("Region", "$name"),
                ("Week", "@{date}"),
                ("Revenue", "@revenue{$0,0}"),
            ],
            xlabel="Date",
            ylabel="Revenue ($)",
            yformatter=NumeralTickFormatter(format="$0,0"),
            gridstyle={"grid_line_alpha": 0.3},
            show_grid=True,
        )

    def _render_cumulative(self, trigger):
        """Return cumulative total revenue curve."""
        df = self._filtered_df
        if df is None or df.empty:
            return hv.Curve([], kdims=["date"], vdims=["cumulative_revenue"]).opts(
                responsive=True, height=350,
            )

        weekly = df.groupby(pd.Grouper(key="date", freq="W")).agg(
            revenue=("revenue", "sum"),
        ).reset_index().sort_values("date")
        weekly["cumulative_revenue"] = weekly["revenue"].cumsum()

        return hv.Curve(
            weekly, kdims=["date"], vdims=["cumulative_revenue"],
        ).opts(
            responsive=True,
            height=350,
            title="Cumulative Revenue",
            color="#1565c0",
            line_width=2.5,
            tools=["hover", "xwheel_zoom"],
            active_tools=["xwheel_zoom"],
            default_tools=["reset"],
            hover_mode="vline",
            hover_tooltips=[
                ("Date", "@{date}"),
                ("Cumulative", "@{cumulative_revenue}{$0,0}"),
            ],
            xlabel="Date",
            ylabel="Cumulative Revenue ($)",
            yformatter=NumeralTickFormatter(format="$0,0"),
            gridstyle={"grid_line_alpha": 0.3},
            show_grid=True,
        )

    # -- Updates --

    def _on_table_selection(self, event):
        """Re-render charts when table selection changes."""
        sidebar_df = self._apply_sidebar_filters()
        self._filtered_df = self._apply_table_selection(sidebar_df)
        self._trigger += 1

    def _update_all(self, *args):
        sidebar_df = self._apply_sidebar_filters()
        self._filtered_df = self._apply_table_selection(sidebar_df)
        with pn.io.hold():
            self._update_kpis(self._filtered_df)
            self._update_table()
            self._trigger += 1  # signal DynamicMaps to re-render

    def _update_kpis(self, df):
        monthly = df.groupby(df["date"].dt.to_period("M")).agg(
            revenue=("revenue", "sum"),
            units=("units", "sum"),
            cost=("cost", "sum"),
        ).reset_index()
        monthly["date"] = monthly["date"].dt.to_timestamp()
        monthly["margin"] = ((monthly["revenue"] - monthly["cost"]) / monthly["revenue"] * 100).round(1)
        monthly["aov"] = (monthly["revenue"] / monthly["units"]).round(2)

        self._revenue_trend.data = {"x": monthly["date"], "y": monthly["revenue"]}
        self._revenue_trend.value = int(df["revenue"].sum())

        self._units_trend.data = {"x": monthly["date"], "y": monthly["units"]}
        self._units_trend.value = int(df["units"].sum())

        total_rev = df["revenue"].sum()
        total_cost = df["cost"].sum()
        margin_pct = ((total_rev - total_cost) / total_rev * 100) if total_rev else 0
        self._margin_trend.data = {"x": monthly["date"], "y": monthly["margin"]}
        self._margin_trend.value = round(margin_pct, 1)

        aov = total_rev / len(df) if len(df) else 0
        self._aov_trend.data = {"x": monthly["date"], "y": monthly["aov"]}
        self._aov_trend.value = round(aov, 2)

    def _update_table(self):
        """Recompute summary for current date range (all regions/products).
        Region and Product filtering is handled by Tabulator's add_filter."""
        df = self._base_df
        start, end = self._date_picker.value
        start, end = pd.Timestamp(start), pd.Timestamp(end)
        df = df[(df["date"] >= start) & (df["date"] <= end)]
        summary = (
            df.groupby(["region", "product"])
            .agg(revenue=("revenue", "sum"), units=("units", "sum"), cost=("cost", "sum"))
            .reset_index()
        )
        summary["margin"] = ((summary["revenue"] - summary["cost"]) / summary["revenue"] * 100).round(1)
        summary["revenue"] = summary["revenue"].round(0)
        summary["cost"] = summary["cost"].round(0)
        summary.columns = ["Region", "Product", "Revenue", "Units", "Cost", "Margin %"]
        self._table.value = summary

    # -- Layout --

    def __panel__(self):
        kpi_row = pmui.Grid(
            pmui.Grid(
                pmui.Paper(self._revenue_trend, sx={"p": 1.5}, sizing_mode="stretch_width"),
                size={"xs": 12, "sm": 6, "md": 3},
            ),
            pmui.Grid(
                pmui.Paper(self._units_trend, sx={"p": 1.5}, sizing_mode="stretch_width"),
                size={"xs": 12, "sm": 6, "md": 3},
            ),
            pmui.Grid(
                pmui.Paper(self._margin_trend, sx={"p": 1.5}, sizing_mode="stretch_width"),
                size={"xs": 12, "sm": 6, "md": 3},
            ),
            pmui.Grid(
                pmui.Paper(self._aov_trend, sx={"p": 1.5}, sizing_mode="stretch_width"),
                size={"xs": 12, "sm": 6, "md": 3},
            ),
            container=True,
            spacing=2,
            sizing_mode="stretch_width",
        )
        charts_section = pmui.Paper(
            self._chart_pane,
            sx={"p": 2},
            sizing_mode="stretch_width",
        )
        table_section = pmui.Paper(
            pmui.Column(
                pmui.Typography("Sales summary", variant="h6", sx={"mb": 1}),
                pmui.Typography(
                    "Select rows to filter the charts above.",
                    sx={"color": "text.secondary", "fontSize": 13, "mb": 1},
                ),
                self._table,
                sizing_mode="stretch_width",
            ),
            sx={"p": 2},
            sizing_mode="stretch_width",
        )

        main_content = pmui.Column(
            kpi_row,
            charts_section,
            table_section,
            sizing_mode="stretch_width",
            margin=(10, 0),
        )

        if pn.state.served:
            return pmui.Page(
                title="Sales Dashboard",
                sidebar=[
                    pmui.Typography("Filters", variant="h6", sx={"mb": 1}),
                    self._date_picker,
                    pn.layout.Divider(margin=(16, 0)),
                    self._region_filter,
                    pn.layout.Divider(margin=(16, 0)),
                    self._product_filter,
                ],
                sidebar_width=260,
                theme_config=THEME_CONFIG,
                main=[
                    pmui.Container(
                        main_content,
                        width_option="xl",
                    )
                ],
            )
        return main_content


SalesDashboard().servable()

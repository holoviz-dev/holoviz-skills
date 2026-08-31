#!/usr/bin/env python3
"""Historical evaluation dashboard for trend analysis across runs.

Usage:
    panel serve scripts/compare_history.py --show --args eval_results/
"""

# pyright: reportAssignmentType=false

import html
import json
import sys
from pathlib import Path

import holoviews as hv
import hvplot.pandas  # noqa: F401
import pandas as pd
import panel as pn
import panel_material_ui as pmui
import param

pn.extension("tabulator", "echarts", throttled=True, sizing_mode="stretch_width")

_DEFAULT_RESULTS_DIR = Path(__file__).parent.parent / "eval_results"
_RESULTS_DIR = next((Path(a) for a in sys.argv[1:] if Path(a).is_dir()), _DEFAULT_RESULTS_DIR)

_METRICS = ("tokens_output", "tokens_input", "execution_time")
_LABELS = {
    "execution_success": "Execution success",
    "tokens_output": "Tokens (output)",
    "tokens_input": "Tokens (input)",
    "execution_time": "Response Time (s)",
}
_HEATMAP = {
    "execution_success": ("{:.0%}", "RdYlGn"),
    "tokens_output": ("{:,.0f}", "RdYlGn_r"),
    "tokens_input": ("{:,.0f}", "RdYlGn_r"),
    "execution_time": ("{:.1f}", "RdYlGn_r"),
}
_CONDITIONS = ("with_skills", "without_skills")
_CONDITION_ABBR = {"with_skills": "on", "without_skills": "off"}
GREEN, RED = "#2ca02c", "#d62728"
GRADE_STYLE = {
    True: "background-color: #e6f4ea; font-weight: 600",
    False: "background-color: #fdecea",
}

_CHART = dict(
    toolbar=None,
    active_tools=[],
    show_grid=True,
    gridstyle={"xgrid_line_alpha": 0, "ygrid_line_alpha": 0.35, "ygrid_line_dash": "dotted"},
)
hv.opts.defaults(
    *[
        opt(**_CHART)
        for opt in (
            hv.opts.Overlay,
            hv.opts.Curve,
            hv.opts.Scatter,
            hv.opts.Violin,
            hv.opts.HeatMap,
        )
    ]
)
pn.indicators.Number.param.font_size.default = "24pt"
pn.indicators.Number.param.title_size.default = "10pt"

# Button and iframe share one pane so the handler can find the iframe inside Panel's
# shadow root. Writes srcdoc into a new tab.
_OPEN_PLOT_JS = (
    "var f=this.getRootNode().querySelector('iframe');"
    "var w=window.open('','_blank');"
    "if(w&&f){w.document.write(f.srcdoc);w.document.close();}"
)


def chart_pane(obj):
    """HoloViews pane with unlinked axes (metrics are in different units)."""
    return pn.pane.HoloViews(obj, linked_axes=False, sizing_mode="stretch_width")


def stack_xaxis(i, last):
    """Put x-tick labels only on the top and bottom panels of a stack."""
    if last == 0:
        return "bottom"
    if i == 0:
        return "top"
    return "bottom" if i == last else None


def no_rows_notice(df):
    if df is None or df.empty:
        return pmui.Alert(
            "Nothing matches the current filters — pick at least one run, model and query "
            "in the sidebar.",
            severity="info",
        )
    return None


def donut(pairs, title):
    data = [{"value": int(v), "name": n, "itemStyle": {"color": c}} for n, v, c in pairs if v]
    return pn.pane.ECharts(
        {
            "title": {"text": title, "left": "center", "textStyle": {"fontSize": 14}},
            "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
            "legend": {"bottom": 0},
            "series": [
                {
                    "type": "pie",
                    "radius": ["45%", "70%"],
                    "avoidLabelOverlap": True,
                    "label": {"formatter": "{b}: {c}"},
                    "data": data,
                }
            ],
        },
        height=300,
    )


def _section(title, plot):
    return pmui.Column(
        pmui.Typography(title, variant="h6"),
        chart_pane(plot),
        sx={"gap": "8px"},
    )


class HistoricalDashboard(pn.viewable.Viewer):
    selected_conditions = param.ListSelector(default=list(_CONDITIONS), objects=list(_CONDITIONS))
    selected_models = param.ListSelector(default=[], objects=[])
    selected_queries = param.ListSelector(default=[], objects=[])
    selected_runs = param.ListSelector(default=[], objects=[])
    df = param.DataFrame()

    def __init__(self, results_dir: Path, **params):
        self._results_dir = results_dir
        self._history_df = self._load_history(results_dir)

        all_runs = (
            sorted(self._history_df["run_id"].unique(), reverse=True)
            if not self._history_df.empty
            else []
        )
        all_models = (
            sorted(self._history_df["model"].unique()) if not self._history_df.empty else []
        )
        all_queries = (
            sorted(self._history_df["query_id"].unique()) if not self._history_df.empty else []
        )
        params.setdefault("selected_runs", all_runs[: min(5, len(all_runs))])
        params.setdefault("selected_models", all_models)
        params.setdefault("selected_queries", all_queries)

        self._no_data_alert = pmui.Alert(
            "No historical summary found. Run eval first to generate ``history_summary.json``.",
            alert_type="warning",
            visible=self._history_df.empty,
        )
        super().__init__(**params)
        self.param.selected_runs.objects = all_runs
        self.param.selected_models.objects = all_models
        self.param.selected_queries.objects = all_queries

        self._run_filter = pmui.MultiSelect.from_param(
            self.param.selected_runs, label="Runs", sizing_mode="stretch_width"
        )
        self._model_filter = self._check_group("selected_models", label="Models")
        self._query_filter = self._check_group("selected_queries", label="Queries")
        self._condition_filter = self._check_group("selected_conditions", label="Conditions")

    def _check_group(self, name, **kw):
        return pmui.CheckButtonGroup.from_param(
            self.param[name],
            orientation="vertical",
            button_style="outlined",
            sizing_mode="stretch_width",
            **kw,
        )

    def _load_history(self, results_dir: Path) -> pd.DataFrame:
        history_file = results_dir / "history_summary.json"
        if not history_file.exists():
            return pd.DataFrame()
        rows = json.loads(history_file.read_text()).get("rows", [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
        return df.sort_values(["created_at", "run_id", "model", "condition", "query_id"])

    def _filtered_df(self) -> pd.DataFrame:
        df = self._history_df
        if df.empty:
            return df.copy()
        for col, values in (
            ("run_id", self.selected_runs),
            ("model", self.selected_models),
            ("query_id", self.selected_queries),
            ("condition", self.selected_conditions),
        ):
            df = df[df[col].isin(values or [])]
        return df

    @param.depends(
        "selected_runs",
        "selected_models",
        "selected_queries",
        "selected_conditions",
        watch=True,
        on_init=True,
    )
    def _update_df(self):
        self.df = self._filtered_df()

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------

    @param.depends("df")
    def _overview(self):
        df = self.df
        if (notice := no_rows_notice(df)) is not None:
            return notice

        with_df = df[df["condition"] == "with_skills"]
        without_df = df[df["condition"] == "without_skills"]

        def rate(sub):
            values = sub["execution_success"].dropna().astype(float)
            return float(values.mean()) if not values.empty else None

        def counts(sub):
            ok = sub["execution_success"].fillna(False).astype(bool)
            return int(ok.sum()), int((~ok).sum())

        with_rate, without_rate = rate(with_df), rate(without_df)
        lift = None if None in (with_rate, without_rate) else with_rate - without_rate
        cards = [
            ("runs shown", df["run_id"].nunique(), "{value}"),
            ("queries × models", df["query_id"].nunique(), f"{{value}} × {df['model'].nunique()}"),
            ("success with skills", with_rate, "{value:.0%}"),
            ("success without skills", without_rate, "{value:.0%}"),
            ("pass-rate lift", lift, "{value:+.0%}"),
            ("avg response time", df["execution_time"].mean(), "{value:.1f} s"),
            ("avg tokens", df["tokens_output"].mean(), "{value:,.0f}"),
        ]
        kpis = pmui.Grid(
            *[
                pmui.Grid(
                    pn.indicators.Number(label=text, value=value, format=fmt),
                    size={"xs": 6, "md": 4},
                )
                for text, value, fmt in cards
            ],
            container=True,
            spacing=2,
        )
        ws_ok, ws_fail = counts(with_df)
        wo_ok, wo_fail = counts(without_df)
        impact = self._skills_impact(df)
        return pmui.Column(
            kpis,
            pmui.Row(
                donut(
                    [("Success", ws_ok, GREEN), ("Failure", ws_fail, RED)],
                    "Execution success — with skills",
                ),
                donut(
                    [("Success", wo_ok, GREEN), ("Failure", wo_fail, RED)],
                    "Execution success — without skills",
                ),
            ),
            impact
            if impact is not None
            else pmui.Alert(
                "Select both conditions to see the skills-impact chart.", severity="info"
            ),
            sx={"gap": "16px"},
        )

    def _skills_impact(self, df: pd.DataFrame):
        """Cumulative +1/−1 effect of skills per model over runs."""
        if not set(_CONDITIONS) <= set(df["condition"]):
            return None
        piv = df.pivot_table(
            index=["run_id", "model", "query_id"],
            columns="condition",
            values="execution_success",
            aggfunc="first",
        )
        forward = piv["with_skills"].fillna(False).astype(bool)
        baseline = piv["without_skills"].fillna(False).astype(bool)
        effect = pd.Series(0, index=piv.index, dtype=int)
        effect.loc[forward & ~baseline] = 1
        effect.loc[baseline & ~forward] = -1
        impact = effect.groupby(["run_id", "model"]).sum().rename("impact").reset_index()
        run_order = df.drop_duplicates("run_id").set_index("run_id")["created_at"]
        impact["created_at"] = impact["run_id"].map(run_order)
        impact = impact.sort_values(["created_at", "run_id", "model"])
        if impact.empty:
            return None
        impact["score"] = impact.groupby("model")["impact"].cumsum()
        lines = (
            hv.Dataset(impact, ["run_id", "model"], "score")
            .to(hv.Curve, "run_id", "score")
            .overlay("model")
        )
        return chart_pane(
            (lines * hv.HLine(0))
            .opts("Curve", line_width=2, tools=["hover"])
            .opts("HLine", color="#999", line_dash="dashed", line_width=1)
            .opts(
                "Overlay",
                title="Skills impact over runs  (+1 with-skills ran, −1 without-skills ran)",
                xlabel="run",
                ylabel="cumulative impact",
                responsive=True,
                height=320,
                legend_position="right",
            )
        )

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------

    def _heatmap_pair(self, df: pd.DataFrame, metric: str, fmt: str, cmap: str):
        work = df.copy()
        if metric == "execution_success":
            work[metric] = work[metric].astype(float)
        work = work[work[metric].notna()]
        if work.empty:
            return None
        clim = (0, 1) if metric == "execution_success" else (work[metric].min(), work[metric].max())
        label = _LABELS[metric]
        panels = []
        for condition in _CONDITIONS:
            d = (
                work[work["condition"] == condition]
                .groupby(["query_id", "model"], as_index=False)[metric]
                .mean()
            )
            d = d[d[metric].notna()].copy()
            if d.empty:
                continue
            d["label"] = d[metric].map(fmt.format)
            hm = hv.HeatMap(d, ["query_id", "model"], [metric, "label"]).opts(
                cmap=cmap,
                colorbar=True,
                clim=clim,
                xlabel="",
                ylabel="model",
                responsive=True,
                height=250,
                xrotation=30,
                tools=["hover"],
                hover_tooltips=[("Query", "@query_id"), ("Model", "@model"), (label, "@label")],
                shared_axes=False,
                title=f"{label} — {condition}",
            )
            labels = hv.Labels(d, ["query_id", "model"], "label").opts(
                text_color="#111", text_font_size="9pt"
            )
            panels.append(hm * labels)
        return chart_pane(hv.Layout(panels).cols(2)) if panels else None

    @param.depends("df")
    def _heatmaps(self):
        df = self.df
        if (notice := no_rows_notice(df)) is not None:
            return notice
        caption = pmui.Typography(
            "Cell = mean across selected runs · green is better · both conditions share a scale",
            variant="caption",
            sx={"color": "text.secondary"},
        )
        sections = [caption]
        for metric, (fmt, cmap) in _HEATMAP.items():
            pair = self._heatmap_pair(df, metric, fmt, cmap)
            if pair is None:
                continue
            sections.append(
                pmui.Column(pmui.Typography(_LABELS[metric], variant="h6"), pair, sx={"gap": "8px"})
            )
        if len(sections) == 1:
            return pmui.Alert("No numeric data for the selected filters yet.", severity="info")
        return pmui.Column(*sections, sx={"gap": "20px"})

    # ------------------------------------------------------------------
    # Distributions
    # ------------------------------------------------------------------

    def _build_metric_violin(self, df: pd.DataFrame, metric: str, *, i: int, n: int):
        xaxis = stack_xaxis(i, n - 1)
        violin = hv.Violin(df, kdims=["model", "condition"], vdims=[metric]).opts(
            responsive=True,
            height=320,
            show_legend=(i == 0),
            ylabel=_LABELS[metric],
            xlabel="model" if xaxis else "",
            xaxis=xaxis,
            split="condition",
            tools=["hover"],
            legend_position="top",
        )
        status = df["execution_success"].fillna(False).astype(bool)
        scatter_kw = dict(
            x="model",
            y=metric,
            by="condition",
            alpha=0.45,
            size=14,
            xlabel="model" if xaxis else "",
            responsive=True,
            height=320,
            legend=False,
        )
        over = df[status].hvplot.scatter(color=GREEN, **scatter_kw)
        under = df[~status].hvplot.scatter(color=RED, **scatter_kw)
        return (violin * over * under).opts(
            xaxis=xaxis,
            tools=["hover"],
            backend_opts={"plot.min_border_left": 85},
        )

    @param.depends("df")
    def _distributions(self):
        df = self.df
        if (notice := no_rows_notice(df)) is not None:
            return notice
        return pmui.Column(
            *[
                _section(_LABELS[m], self._build_metric_violin(df, m, i=i, n=len(_METRICS)))
                for i, m in enumerate(_METRICS)
            ],
            sx={"gap": "20px"},
        )

    # ------------------------------------------------------------------
    # Trends
    # ------------------------------------------------------------------

    def _build_trend(
        self, df: pd.DataFrame, metric: str, ylabel: str, *, i: int, n: int, ylim=None
    ):
        work = df.copy()
        if metric == "execution_success":
            work[metric] = work[metric].astype(float)
        agg = (
            work.groupby(["run_id", "model", "condition"], as_index=False)
            .agg(**{metric: (metric, "mean"), "created_at": ("created_at", "first")})
            .sort_values(["created_at", "run_id", "model", "condition"])
        )
        # Short combined series label ("model · on"/"off") — one legend column instead
        # of "model, condition", so a vertical right-side legend stays narrow and the
        # color swatches line up in a single readable list.
        agg["series"] = agg["model"] + " · " + agg["condition"].map(_CONDITION_ABBR)
        xaxis = stack_xaxis(i, n - 1)
        if agg.empty:
            return hv.Curve([], kdims=["run_id"], vdims=[metric]).opts(
                responsive=True, height=280, title="No data for selected filters."
            )
        kw = dict(
            x="run_id",
            y=metric,
            by="series",
            xlabel="run" if xaxis else "",
        )
        line = agg.hvplot.line(
            ylabel=ylabel,
            responsive=True,
            height=300,
            legend="right" if i == 0 else False,
            line_width=2,
            **({"ylim": ylim} if ylim else {}),
            **kw,
        )
        scatter = agg.hvplot.scatter(legend=False, **kw)
        return (line * scatter).opts(
            xaxis=xaxis,
            tools=["hover"],
            backend_opts={"plot.min_border_left": 85, "plot.min_border_right": 230},
        )

    @param.depends("df")
    def _trends(self):
        df = self.df
        if (notice := no_rows_notice(df)) is not None:
            return notice
        n = len(_METRICS) + 1
        success = self._build_trend(
            df, "execution_success", "Execution success rate", i=0, n=n, ylim=(-0.1, 1.1)
        )
        sections = [_section("Execution success rate", success)]
        for i, metric in enumerate(_METRICS, start=1):
            plot = self._build_trend(df, metric, _LABELS[metric], i=i, n=n)
            sections.append(_section(_LABELS[metric], plot))
        return pmui.Column(*sections, sx={"gap": "20px"})

    # ------------------------------------------------------------------
    # Details
    # ------------------------------------------------------------------

    @param.depends("df")
    def _details(self):
        df = self.df
        if (notice := no_rows_notice(df)) is not None:
            return notice
        table = df.copy().sort_values(["created_at", "query_id", "model", "condition"])[
            [
                "run_id",
                "created_at",
                "query_id",
                "model",
                "condition",
                "tokens_output",
                "tokens_input",
                "execution_time",
                "execution_success",
            ]
        ]
        table["created_at"] = pd.to_datetime(table["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
        for col in ("tokens_output", "tokens_input"):
            table[col] = table[col].fillna(0).astype(int)
        tabulator = pn.widgets.Tabulator(
            table,
            disabled=True,
            show_index=False,
            layout="fit_columns",
            theme="materialize",
            header_filters=True,
            selectable=False,
            titles={
                "run_id": "Run",
                "created_at": "Created",
                "query_id": "Query",
                "model": "Model",
                "condition": "Condition",
                "tokens_output": "Tokens (out)",
                "tokens_input": "Tokens (in)",
                "execution_time": "Response time (s)",
                "execution_success": "Status",
            },
        )
        tabulator.style.map(lambda g: GRADE_STYLE.get(g, ""), subset=["execution_success"])
        return tabulator

    # ------------------------------------------------------------------
    # Plot Outputs
    # ------------------------------------------------------------------

    def _output_card(self, query: str, model: str, condition: str, kind: str, path: Path):
        title = pmui.Typography(query, variant="subtitle2", sx={"fontWeight": 600})
        kind_label = "screenshot" if kind == "screenshot" else "saved plot"
        caption = pmui.Typography(
            f"{model} · {condition} · {kind_label}",
            variant="caption",
            sx={"color": "text.secondary"},
        )
        if kind == "screenshot":
            body = pn.pane.PNG(path, sizing_mode="stretch_width", height=460)
        else:
            escaped = html.escape(path.read_text())
            body = pn.pane.HTML(
                f'<iframe srcdoc="{escaped}" sandbox="allow-scripts" '
                f'style="width:100%;height:430px;border:1px solid #e0e0e0;border-radius:4px">'
                f"</iframe>"
                f'<div style="margin-top:4px">'
                f'<button type="button" onclick="{_OPEN_PLOT_JS}" '
                f'style="background:none;border:none;padding:0;color:#1976d2;'
                f"text-decoration:underline;cursor:pointer;font-size:12px;"
                f'font-family:inherit">Open the full plot in a new tab</button>'
                f"</div>",
                sizing_mode="stretch_width",
            )
        return pmui.Paper(
            pmui.Column(title, caption, body, sx={"gap": "8px"}),
            sx={"p": 2},
            elevation=1,
        )

    def _iter_query_dirs(self):
        for model in self.selected_models:
            for condition in self.selected_conditions:
                for query in self.selected_queries:
                    query_dir = self._results_dir / model / condition / query
                    if query_dir.is_dir():
                        yield query, model, condition, query_dir

    @param.depends("selected_models", "selected_queries", "selected_conditions")
    def _plots_outputs(self):
        cards = []
        for query, model, condition, query_dir in self._iter_query_dirs():
            plot_html = query_dir / "plot_output.html"
            screenshot = query_dir / "screenshot.png"
            if plot_html.exists():
                cards.append(self._output_card(query, model, condition, "plot", plot_html))
            elif screenshot.exists():
                cards.append(self._output_card(query, model, condition, "screenshot", screenshot))
        if not cards:
            return pmui.Alert(
                "No saved plots or screenshots found for the selected filters.",
                severity="info",
            )
        grid = pmui.Grid(
            *(pmui.Grid(card, size={"xs": 12, "md": 6, "lg": 4}) for card in cards),
            container=True,
            spacing=2,
            sizing_mode="stretch_width",
        )
        return pmui.Column(
            pmui.Typography(
                "Saved plot per model / condition / query (screenshot if no plot). "
                "Most recent artifacts on disk — overwritten each run.",
                variant="caption",
                sx={"color": "text.secondary"},
            ),
            grid,
            sx={"gap": "12px"},
        )

    def __panel__(self):
        empty = self._history_df.empty
        n_runs = 0 if empty else self._history_df["run_id"].nunique()
        latest = None
        if not empty:
            latest = pd.to_datetime(self._history_df["created_at"]).max()
            latest = latest.strftime("%Y-%m-%d %H:%M")
        sidebar = pmui.Column(
            pmui.Typography("Filters", variant="h6"),
            self._run_filter,
            pmui.Divider(),
            self._model_filter,
            pmui.Divider(),
            self._query_filter,
            pmui.Divider(),
            self._condition_filter,
            pn.pane.HTML(
                f'<div style="font-size:12px;display:flex;gap:10px">'
                f'<span style="color:{GREEN}">●</span> success'
                f'<span style="color:{RED}">●</span> failure</div>'
            ),
            pmui.Typography(
                f"{n_runs} run(s) · latest {latest or '—'}",
                variant="caption",
                sx={"color": "text.secondary", "mt": 2},
            ),
            sx={"gap": "12px"},
            margin=10,
        )
        main = pmui.Column(
            self._no_data_alert,
            pmui.Typography("Historical Evaluation Trends", variant="h4"),
            pmui.Typography(
                f"Results directory: {self._results_dir}",
                variant="body2",
                sx={"color": "text.secondary"},
            ),
            pmui.Tabs(
                ("Overview", self._overview),
                ("Comparison", self._heatmaps),
                ("Distributions", self._distributions),
                ("Trends", self._trends),
                ("Details", self._details),
                ("Plot Outputs", self._plots_outputs),
            ),
            sx={"gap": "16px"},
            margin=10,
        )
        return pmui.Page(
            title="HoloViz Skills - Eval Trends",
            sidebar=[sidebar],
            main=[main],
        )


dashboard = HistoricalDashboard(results_dir=_RESULTS_DIR)
dashboard.servable()

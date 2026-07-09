#!/usr/bin/env python3
"""Historical evaluation dashboard for trend analysis across runs.

Usage:
    panel serve scripts/compare_history.py --show --args eval_results/
"""

# pyright: reportAssignmentType=false

import json
import sys
from pathlib import Path

import holoviews as hv
import hvplot.pandas  # noqa: F401
import pandas as pd
import panel as pn
import panel_material_ui as pmui
import param

pn.extension("tabulator", throttled=True)

_DEFAULT_RESULTS_DIR = Path(__file__).parent.parent / "eval_results"
_RESULTS_DIR = next((Path(a) for a in sys.argv[1:] if Path(a).is_dir()), _DEFAULT_RESULTS_DIR)
_METRICS = ["tokens_output", "tokens_input", "execution_time", "execution_success", "has_code"]
_METRIC_LABELS = {
    "tokens_output": "Tokens (output)",
    "tokens_input": "Tokens (input)",
    "execution_time": "Response Time (s)",
    "execution_success": "Execution Success Rate",
    "has_code": "Code Generation Rate",
}

_CONDITION_DASH = {"with_skills": "solid", "without_skills": "dashed"}
_CONDITION_MARKER = {"with_skills": "circle", "without_skills": "x"}
_MODEL_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
]


class HistoricalDashboard(pn.viewable.Viewer):
    selected_runs = param.ListSelector(default=[], objects=[])
    selected_models = param.ListSelector(default=[], objects=[])
    selected_queries = param.ListSelector(default=[], objects=[])
    selected_conditions = param.ListSelector(
        default=["with_skills", "without_skills"],
        objects=["with_skills", "without_skills"],
    )
    selected_metric = param.Selector(default="tokens_output", objects=_METRICS)

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
        default_runs = all_runs[: min(5, len(all_runs))]

        params.setdefault("selected_runs", default_runs)
        params.setdefault("selected_models", all_models)
        params.setdefault("selected_queries", all_queries)

        self._model_color = {
            m: _MODEL_COLORS[i % len(_MODEL_COLORS)] for i, m in enumerate(all_models)
        }

        self._trend_pane = pn.pane.HoloViews(None, sizing_mode="stretch_width", linked_axes=False)
        self._delta_pane = pn.pane.HoloViews(None, sizing_mode="stretch_width", linked_axes=False)
        self._table_pane = pn.widgets.Tabulator(
            pd.DataFrame(),
            theme="materialize",
            sizing_mode="stretch_width",
            show_index=False,
        )
        self._no_data_alert = pmui.Alert(
            "No historical summary found. Run eval first to generate history_summary.json.",
            alert_type="warning",
            visible=self._history_df.empty,
        )

        self._run_filter = pmui.MultiSelect(
            label="Runs",
            options=all_runs,
            value=default_runs,
            sizing_mode="stretch_width",
        )
        self._model_filter = pmui.CheckButtonGroup(
            label="Models",
            options=all_models,
            value=all_models,
            orientation="vertical",
            color="secondary",
            button_style="outlined",
            sizing_mode="stretch_width",
        )
        self._query_filter = pmui.CheckButtonGroup(
            label="Queries",
            options=all_queries,
            value=all_queries,
            orientation="vertical",
            color="primary",
            button_style="outlined",
            sizing_mode="stretch_width",
        )
        self._condition_filter = pmui.CheckButtonGroup(
            label="Conditions",
            options=["with_skills", "without_skills"],
            value=["with_skills", "without_skills"],
            orientation="vertical",
            color="primary",
            button_style="outlined",
            sizing_mode="stretch_width",
        )
        self._metric_select = pmui.Select(
            label="Metric",
            options=_METRICS,
            value="tokens_output",
            sizing_mode="stretch_width",
        )

        super().__init__(**params)

        self.param["selected_runs"].objects = all_runs
        self.param["selected_models"].objects = all_models
        self.param["selected_queries"].objects = all_queries

        self._run_filter.param.watch(lambda e: setattr(self, "selected_runs", e.new), "value")
        self._model_filter.param.watch(lambda e: setattr(self, "selected_models", e.new), "value")
        self._query_filter.param.watch(lambda e: setattr(self, "selected_queries", e.new), "value")
        self._condition_filter.param.watch(
            lambda e: setattr(self, "selected_conditions", e.new), "value"
        )
        self._metric_select.param.watch(lambda e: setattr(self, "selected_metric", e.new), "value")

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _load_history(self, results_dir: Path) -> pd.DataFrame:
        history_file = results_dir / "history_summary.json"
        if not history_file.exists():
            return pd.DataFrame()
        payload = json.loads(history_file.read_text())
        rows = payload.get("rows", [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
        df = df.sort_values(["created_at", "run_id", "model", "condition", "query_id"])
        return df

    def _filtered_df(self) -> pd.DataFrame:
        if self._history_df.empty:
            return self._history_df
        df = self._history_df
        if self.selected_runs:
            df = df[df["run_id"].isin(self.selected_runs)]
        if self.selected_models:
            df = df[df["model"].isin(self.selected_models)]
        if self.selected_queries:
            df = df[df["query_id"].isin(self.selected_queries)]
        if self.selected_conditions:
            df = df[df["condition"].isin(self.selected_conditions)]
        return df

    def _run_order(self, df: pd.DataFrame) -> dict[str, int]:
        """Chronological run → x-index (oldest = 0)."""
        order = df[["run_id", "created_at"]].drop_duplicates("run_id").sort_values("created_at")
        return {row.run_id: i for i, row in enumerate(order.itertuples())}

    # ------------------------------------------------------------------
    # Plot 1 — Line + Scatter trend
    # ------------------------------------------------------------------

    def _build_trend(self, df: pd.DataFrame):
        metric = self.selected_metric
        label = _METRIC_LABELS[metric]

        if metric in ("execution_success", "has_code"):
            df = df.copy()
            df[metric] = df[metric].astype(float)

        run_to_x = self._run_order(df)
        xticks = [(v, k) for k, v in run_to_x.items()]
        # Tight x range: small left margin, half-unit right margin
        n_runs = len(run_to_x)
        xlim = (-0.1, n_runs - 0.5)

        grouped = (
            df.groupby(["run_id", "model", "condition"], as_index=False)
            .agg(**{metric: (metric, "mean"), "created_at": ("created_at", "first")})
            .sort_values("created_at")
        )
        grouped["x"] = grouped["run_id"].map(run_to_x)
        grouped["series"] = grouped["model"] + " / " + grouped["condition"]

        hover_spec = [
            ("Series", "$name"),
            ("Run", "@run_id"),
            (label, f"@{{{metric}}}{{0.2f}}"),
        ]

        line_plots = {}
        scatter_plots = {}
        for series_key, grp in grouped.groupby("series"):
            model = grp["model"].iloc[0]
            condition = grp["condition"].iloc[0]
            color = self._model_color.get(model, "#333333")
            dash = _CONDITION_DASH.get(condition, "solid")
            marker = _CONDITION_MARKER.get(condition, "circle")
            grp = grp.sort_values("x")

            line_plots[series_key] = grp.hvplot.line(
                x="x",
                y=metric,
                color=color,
                line_dash=dash,
                line_width=2,
                hover_cols=["run_id", metric],
                hover_tooltips=hover_spec,
                responsive=True,
                height=340,
            )
            scatter_plots[series_key] = grp.hvplot.scatter(
                x="x",
                y=metric,
                color=color,
                marker=marker,
                size=80,
                hover_cols=["run_id", metric],
                hover_tooltips=hover_spec,
                responsive=True,
                height=340,
            )

        if not line_plots:
            return hv.Curve([], kdims=["x"], vdims=[metric]).opts(
                responsive=True, height=340, title="No data for selected filters."
            )

        overlay = hv.NdOverlay(line_plots) * hv.NdOverlay(scatter_plots)

        extra = {"ylim": (-0.1, 1.1)} if metric in ("execution_success", "has_code") else {}
        overlay = overlay.opts(
            hv.opts.NdOverlay(
                title=f"Metric Trend: {label}",
                legend_position="top_right",
                xticks=xticks,
                xrotation=30,
                xlabel="Run (chronological)",
                ylabel=label,
                xlim=xlim,
                responsive=True,
                height=340,
                **extra,
            ),
        )
        return overlay

    # ------------------------------------------------------------------
    # Plot 3 — Skills Advantage Δ
    # ------------------------------------------------------------------

    def _build_delta(self, df: pd.DataFrame):
        metric = self.selected_metric
        label = _METRIC_LABELS[metric]
        delta_col = "delta"

        if metric in ("execution_success", "has_code"):
            df = df.copy()
            df[metric] = df[metric].astype(float)

        run_to_x = self._run_order(df)
        xticks = [(v, k) for k, v in run_to_x.items()]
        n_runs = len(run_to_x)
        xlim = (-0.1, n_runs - 0.5)

        agg = df.groupby(["run_id", "model", "query_id", "condition"], as_index=False).agg(
            **{metric: (metric, "mean"), "created_at": ("created_at", "first")}
        )
        pivot = agg.pivot_table(
            index=["run_id", "model", "query_id", "created_at"],
            columns="condition",
            values=metric,
        ).reset_index()
        pivot.columns.name = None

        if "with_skills" not in pivot.columns or "without_skills" not in pivot.columns:
            msg = "Delta requires both conditions present in data."
            return hv.Curve([], kdims=["x"], vdims=[delta_col]).opts(
                responsive=True, height=280, title=msg
            )

        pivot = pivot.dropna(subset=["with_skills", "without_skills"])
        if pivot.empty:
            return hv.Curve([], kdims=["x"], vdims=[delta_col]).opts(
                responsive=True, height=280, title="No paired rows for delta."
            )

        pivot[delta_col] = pivot["with_skills"] - pivot["without_skills"]
        pivot["x"] = pivot["run_id"].map(run_to_x)
        pivot["series"] = pivot["model"] + " / " + pivot["query_id"]

        hover_spec = [
            ("Series", "$name"),
            ("Run", "@run_id"),
            (f"Δ {label}", f"@{{{delta_col}}}{{0.3f}}"),
        ]

        line_plots = {}
        scatter_plots = {}
        for series_key, grp in pivot.groupby("series"):
            model = grp["model"].iloc[0]
            color = self._model_color.get(model, "#333333")
            grp = grp.sort_values("x")

            line_plots[series_key] = grp.hvplot.line(
                x="x",
                y=delta_col,
                color=color,
                line_width=2,
                hover_cols=["run_id", delta_col],
                hover_tooltips=hover_spec,
                responsive=True,
                height=280,
            )
            scatter_plots[series_key] = grp.hvplot.scatter(
                x="x",
                y=delta_col,
                color=color,
                size=70,
                hover_cols=["run_id", delta_col],
                hover_tooltips=hover_spec,
                responsive=True,
                height=280,
            )

        if not line_plots:
            return hv.Curve([], kdims=["x"], vdims=[delta_col]).opts(
                responsive=True, height=280, title="No data for selected filters."
            )

        zero_line = hv.HLine(0).opts(color="gray", line_dash="dashed", line_width=1.5)

        overlay = hv.NdOverlay(line_plots) * hv.NdOverlay(scatter_plots) * zero_line
        overlay = overlay.opts(
            hv.opts.NdOverlay(
                title=f"Skills Advantage (Δ): {label}",
                legend_position="top_right",
                xticks=xticks,
                xrotation=30,
                xlabel="Run (chronological)",
                ylabel=f"Δ {label}",
                xlim=xlim,
                responsive=True,
                height=280,
            ),
        )
        return overlay

    # ------------------------------------------------------------------
    # Reactive update — fires whenever any filter param changes
    # ------------------------------------------------------------------

    @param.depends(
        "selected_runs",
        "selected_models",
        "selected_queries",
        "selected_conditions",
        "selected_metric",
        watch=True,
        on_init=True,
    )
    def _update_views(self):
        df = self._filtered_df()
        with pn.io.hold():
            if df.empty:
                self._trend_pane.object = hv.Curve([], kdims=["x"], vdims=["y"]).opts(
                    responsive=True, height=340, title="No data for selected filters."
                )
                self._delta_pane.object = hv.Curve([], kdims=["x"], vdims=["y"]).opts(
                    responsive=True, height=280, title="No data for selected filters."
                )
                self._table_pane.value = pd.DataFrame()
                return

            self._trend_pane.object = self._build_trend(df)

            delta_df = self._history_df.copy()
            if self.selected_runs:
                delta_df = delta_df[delta_df["run_id"].isin(self.selected_runs)]
            if self.selected_models:
                delta_df = delta_df[delta_df["model"].isin(self.selected_models)]
            if self.selected_queries:
                delta_df = delta_df[delta_df["query_id"].isin(self.selected_queries)]
            self._delta_pane.object = self._build_delta(delta_df)

            display_cols = [
                "run_id",
                "created_at",
                "query_id",
                "model",
                "condition",
                "tokens_output",
                "tokens_input",
                "execution_time",
                "execution_success",
                "has_code",
            ]
            self._table_pane.value = (
                df[display_cols]
                .copy()
                .sort_values(["created_at", "query_id", "model", "condition"])
            )

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def __panel__(self):
        with pn.config.set(sizing_mode="stretch_width"):
            sidebar = pmui.Column(
                pmui.Typography("Filters", variant="h6"),
                self._metric_select,
                pmui.Divider(),
                self._run_filter,
                pmui.Divider(),
                self._model_filter,
                pmui.Divider(),
                self._query_filter,
                pmui.Divider(),
                self._condition_filter,
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
                pmui.Paper(
                    pmui.Column(
                        pmui.Typography("Metric Trend by Run", variant="h6"),
                        self._trend_pane,
                    ),
                    sx={"p": 2},
                    elevation=1,
                ),
                pmui.Paper(
                    pmui.Column(
                        pmui.Typography("Skills Advantage (Δ) by Run", variant="h6"),
                        pmui.Typography(
                            "Δ > 0: with_skills outperforms without_skills",
                            variant="caption",
                            sx={"color": "text.secondary"},
                        ),
                        self._delta_pane,
                    ),
                    sx={"p": 2},
                    elevation=1,
                ),
                pmui.Paper(self._table_pane, sx={"p": 2}, elevation=1),
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

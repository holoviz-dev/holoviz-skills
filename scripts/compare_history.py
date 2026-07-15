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

_BINARY_METRICS = {"execution_success", "has_code"}


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
    # Plot 1 — Violin trend (distribution per model, split by condition)
    # ------------------------------------------------------------------

    def _build_trend(self, df: pd.DataFrame):
        metric = self.selected_metric
        label = _METRIC_LABELS[metric]

        if metric in ("execution_success", "has_code"):
            df = df.copy()
            df[metric] = df[metric].astype(float)

        plot_df = df.copy().sort_values(["model", "condition", "created_at", "run_id", "query_id"])

        models = sorted(plot_df["model"].unique())

        if not models:
            return hv.Curve([], kdims=["run_id"], vdims=[metric]).opts(
                responsive=True, height=400, title="No data for selected filters."
            )

        vdim = hv.Dimension(metric, label=label)
        violin = hv.Violin(plot_df, kdims=["model", "condition"], vdims=[vdim])
        return violin.opts(
            responsive=True,
            height=400,
            show_legend=True,
            title=f"Metric Distribution: {label}",
            ylabel=label,
            xlabel="Model",
            violin_width=0.6,
            fontscale=1.1,
            split="condition",
            xrotation=20,
            toolbar=None,
        )

    # ------------------------------------------------------------------
    # Plot 1b — Grouped bar for binary metrics (execution_success, has_code)
    # ------------------------------------------------------------------

    def _build_binary_trend(self, df: pd.DataFrame):
        metric = self.selected_metric
        label = _METRIC_LABELS[metric]

        df = df.copy()
        df[metric] = df[metric].astype(float)

        run_to_x = self._run_order(df)

        # Mean rate per (run, model, condition); preserve chronological order
        agg = (
            df.groupby(["run_id", "model", "condition"], as_index=False)
            .agg(**{metric: (metric, "mean"), "created_at": ("created_at", "first")})
            .sort_values(["model", "created_at"])
        )
        agg["run_order"] = agg["run_id"].map(run_to_x)

        models = sorted(agg["model"].unique())
        if not models:
            return hv.Curve([], kdims=["run_id"], vdims=[metric]).opts(
                responsive=True, height=340, title="No data for selected filters."
            )

        bar_plots = {}
        for model in models:
            mdf = agg[agg["model"] == model].sort_values("run_order")
            bar = mdf.hvplot.bar(
                x="run_id",
                y=metric,
                by="condition",
                ylabel=label,
                xlabel="Run (chronological)",
                title=f"{label} — {model}",
                ylim=(0, 1.05),
                responsive=True,
                height=340,
                legend="top_right",
                fontscale=1.1,
            ).opts(default_tools=[])
            bar_plots[model] = bar

        if len(bar_plots) == 1:
            return next(iter(bar_plots.values()))

        return hv.Layout(list(bar_plots.values())).cols(1)

    # ------------------------------------------------------------------
    # Plot 2b — Skills Advantage Δ for binary metrics (stacked bar of outcomes)
    # ------------------------------------------------------------------

    def _build_binary_delta(self, df: pd.DataFrame):
        metric = self.selected_metric
        label = _METRIC_LABELS[metric]

        df = df.copy()
        df[metric] = df[metric].astype(float)

        run_to_x = self._run_order(df)

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
            return hv.Curve([], kdims=["run_id"], vdims=["count"]).opts(
                responsive=True, height=340, title="Delta requires both conditions present in data."
            )

        pivot = pivot.dropna(subset=["with_skills", "without_skills"])
        if pivot.empty:
            return hv.Curve([], kdims=["run_id"], vdims=["count"]).opts(
                responsive=True, height=340, title="No paired rows for delta."
            )

        pivot["delta"] = (pivot["with_skills"] - pivot["without_skills"]).round().astype(int)
        pivot["outcome"] = pivot["delta"].map({1: "helped", 0: "no change", -1: "hurt"})
        pivot["run_order"] = pivot["run_id"].map(run_to_x)

        _OUTCOME_COLORS = {"helped": "#2ca02c", "no change": "#aec7e8", "hurt": "#d62728"}
        _OUTCOME_ORDER = ["helped", "no change", "hurt"]

        models = sorted(pivot["model"].unique())
        if not models:
            return hv.Curve([], kdims=["run_id"], vdims=["count"]).opts(
                responsive=True, height=340, title="No data for selected filters."
            )

        bar_plots = {}
        for model in models:
            mdf = (
                pivot[pivot["model"] == model]
                .groupby(["run_id", "outcome", "run_order"], as_index=False)
                .size()
                .rename(columns={"size": "count"})
                .sort_values("run_order")
            )
            # Ensure all outcome categories present for consistent stacking
            all_runs = mdf[["run_id", "run_order"]].drop_duplicates().set_index("run_id")
            full = pd.MultiIndex.from_product(
                [all_runs.index, _OUTCOME_ORDER], names=["run_id", "outcome"]
            )
            mdf = (
                mdf.drop(columns="run_order")
                .set_index(["run_id", "outcome"])
                .reindex(full, fill_value=0)
                .reset_index()
                .merge(all_runs, on="run_id")
                .sort_values("run_order")
            )
            bar = mdf.hvplot.bar(
                x="run_id",
                y="count",
                by="outcome",
                stacked=True,
                color=[_OUTCOME_COLORS[o] for o in _OUTCOME_ORDER],
                ylabel="Query count",
                xlabel="Run (chronological)",
                title=f"Skills Advantage (Δ): {label} — {model}",
                responsive=True,
                height=340,
                legend="top_right",
                fontscale=1.1,
            ).opts(default_tools=[])
            bar_plots[model] = bar

        if len(bar_plots) == 1:
            return next(iter(bar_plots.values()))

        return hv.Layout(list(bar_plots.values())).cols(2)

    # ------------------------------------------------------------------
    # Plot 2 — Skills Advantage Δ (violin of per-query deltas per model)
    # ------------------------------------------------------------------

    def _build_delta(self, df: pd.DataFrame):
        metric = self.selected_metric
        label = _METRIC_LABELS[metric]
        delta_col = "delta"

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
            return hv.Curve([], kdims=["run_id"], vdims=[delta_col]).opts(
                responsive=True, height=340, title="Delta requires both conditions present in data."
            )

        pivot = pivot.dropna(subset=["with_skills", "without_skills"])
        if pivot.empty:
            return hv.Curve([], kdims=["run_id"], vdims=[delta_col]).opts(
                responsive=True, height=340, title="No paired rows for delta."
            )

        pivot[delta_col] = pivot["with_skills"] - pivot["without_skills"]

        models = sorted(pivot["model"].unique())
        if not models:
            return hv.Curve([], kdims=["run_id"], vdims=[delta_col]).opts(
                responsive=True, height=340, title="No data for selected filters."
            )

        vdim = hv.Dimension(delta_col, label=f"Δ {label}")
        violin = hv.Violin(pivot, kdims=["model"], vdims=[vdim])
        zero_line = hv.HLine(0).opts(color="gray", line_dash="dashed", line_width=1.5)
        return (
            violin.opts(
                responsive=True,
                height=340,
                show_legend=False,
                title=f"Skills Advantage (Δ): {label}",
                ylabel=f"Δ {label}",
                xlabel="Model",
                violin_width=0.6,
                fontscale=1.1,
                xrotation=20,
                toolbar=None,
            )
            * zero_line
        )

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
                    responsive=True, height=400, title="No data for selected filters."
                )
                self._delta_pane.object = hv.Curve([], kdims=["x"], vdims=["y"]).opts(
                    responsive=True, height=280, title="No data for selected filters."
                )
                self._table_pane.value = pd.DataFrame()
                return

            if self.selected_metric in _BINARY_METRICS:
                self._trend_pane.object = self._build_binary_trend(df)
            else:
                self._trend_pane.object = self._build_trend(df)

            delta_df = self._history_df.copy()
            if self.selected_runs:
                delta_df = delta_df[delta_df["run_id"].isin(self.selected_runs)]
            if self.selected_models:
                delta_df = delta_df[delta_df["model"].isin(self.selected_models)]
            if self.selected_queries:
                delta_df = delta_df[delta_df["query_id"].isin(self.selected_queries)]
            if self.selected_metric in _BINARY_METRICS:
                self._delta_pane.object = self._build_binary_delta(delta_df)
            else:
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

#!/usr/bin/env python3
"""Historical evaluation dashboard for trend analysis across runs.

This dashboard is intentionally separate from compare_results.py.

Usage:
    panel serve scripts/compare_history.py --show --args eval_results/
    panel serve scripts/compare_history.py --args eval_results/
"""

# pyright: reportAssignmentType=false

import json
import sys
from pathlib import Path

import hvplot.pandas  # noqa: F401
import pandas as pd
import panel as pn
import panel_material_ui as pmui
import param

pn.extension("tabulator", throttled=True)

_DEFAULT_RESULTS_DIR = Path(__file__).parent.parent / "eval_results"
_RESULTS_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_RESULTS_DIR
_METRICS = ["tokens_output", "tokens_input", "execution_time", "execution_success", "has_code"]
_METRIC_LABELS = {
    "tokens_output": "Tokens (output)",
    "tokens_input": "Tokens (input)",
    "execution_time": "Response Time (s)",
    "execution_success": "Execution Success Rate",
    "has_code": "Code Generation Rate",
}


class HistoryState(param.Parameterized):
    selected_runs = param.ListSelector(default=[], objects=[])
    selected_models = param.ListSelector(default=[], objects=[])
    selected_queries = param.ListSelector(default=[], objects=[])
    selected_conditions = param.ListSelector(
        default=["with_skills", "without_skills"], objects=["with_skills", "without_skills"]
    )
    selected_metric = param.Selector(default="tokens_output", objects=_METRICS)


class HistoricalDashboard(pn.viewable.Viewer):
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
        self._state = HistoryState(
            selected_runs=default_runs,
            selected_models=all_models,
            selected_queries=all_queries,
        )
        self._state.param["selected_runs"].objects = all_runs
        self._state.param["selected_models"].objects = all_models
        self._state.param["selected_queries"].objects = all_queries

        self._run_filter = pmui.MultiSelect(
            label="Runs",
            options=all_runs,
            value=default_runs,
            helper_text="Hold CMD to select multiple",
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

        self._trend_pane = pn.pane.HoloViews(height=380, sizing_mode="stretch_width")
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

        super().__init__(**params)

        self._run_filter.param.watch(
            lambda e: setattr(self._state, "selected_runs", e.new), "value"
        )
        self._model_filter.param.watch(
            lambda e: setattr(self._state, "selected_models", e.new), "value"
        )
        self._query_filter.param.watch(
            lambda e: setattr(self._state, "selected_queries", e.new), "value"
        )
        self._condition_filter.param.watch(
            lambda e: setattr(self._state, "selected_conditions", e.new), "value"
        )
        self._metric_select.param.watch(
            lambda e: setattr(self._state, "selected_metric", e.new), "value"
        )

        self._state.param.watch(
            lambda _: self._refresh_views(),
            [
                "selected_runs",
                "selected_models",
                "selected_queries",
                "selected_conditions",
                "selected_metric",
            ],
        )

        self._refresh_views()

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
        if self._state.selected_runs:
            df = df[df["run_id"].isin(self._state.selected_runs)]
        if self._state.selected_models:
            df = df[df["model"].isin(self._state.selected_models)]
        if self._state.selected_queries:
            df = df[df["query_id"].isin(self._state.selected_queries)]
        if self._state.selected_conditions:
            df = df[df["condition"].isin(self._state.selected_conditions)]
        return df

    def _build_trend(self, df: pd.DataFrame):
        metric = self._state.selected_metric
        label = _METRIC_LABELS.get(metric, metric)

        metric_df = df.copy()
        if metric in ("execution_success", "has_code"):
            metric_df[metric] = metric_df[metric].astype(float)

        grouped = (
            metric_df.groupby(["created_at", "run_id", "model", "condition"], as_index=False)
            .agg({metric: "mean"})
            .sort_values(by=["created_at", "model", "condition"])
        )
        grouped["series"] = grouped["model"] + " | " + grouped["condition"]
        grouped["run_label"] = grouped["run_id"]

        return grouped.hvplot.bar(
            x="run_label",
            y=metric,
            by="series",
            stacked=False,
            height=360,
            responsive=True,
            ylabel=label,
            xlabel="Run ID",
            title=f"Grouped Comparison: {label}",
            legend="top_left",
            rot=45,
        )

    def _refresh_views(self):
        with pn.io.hold():
            df = self._filtered_df()
            if df.empty:
                self._trend_pane.object = pn.pane.Markdown("No data for selected filters.")
                self._table_pane.value = pd.DataFrame()
                return

            self._trend_pane.object = self._build_trend(df)

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
            table_df = (
                df[display_cols]
                .copy()
                .sort_values(["created_at", "query_id", "model", "condition"])
            )
            self._table_pane.value = table_df

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
                pmui.Paper(self._trend_pane, sx={"p": 2}, elevation=1),
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

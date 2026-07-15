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
_METRICS = ["tokens_output", "tokens_input", "execution_time"]
_METRIC_LABELS = {
    "tokens_output": "Tokens (output)",
    "tokens_input": "Tokens (input)",
    "execution_time": "Response Time (s)",
}


class HistoricalDashboard(pn.viewable.Viewer):
    selected_runs = param.ListSelector(default=[], objects=[])
    selected_models = param.ListSelector(default=[], objects=[])
    selected_queries = param.ListSelector(default=[], objects=[])
    selected_conditions = param.ListSelector(
        default=["with_skills", "without_skills"],
    )

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

        self._plots_container = pmui.Column(sizing_mode="stretch_width")
        self._status_legend = self._build_status_legend()
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

    def _build_status_legend(self):
        legend = hv.NdOverlay(
            {
                "Success": hv.Scatter([(0, 0)], kdims=["x"], vdims=["y"]),
                "Failure": hv.Scatter([(1, 0)], kdims=["x"], vdims=["y"]),
            },
            kdims="status",
        ).opts(
            show_legend=True,
            legend_position="right",
            width=180,
            height=90,
            xaxis=None,
            yaxis=None,
            toolbar=None,
            default_tools=[],
            fontscale=0.9,
        )
        return pn.pane.HoloViews(legend, sizing_mode="fixed", width=180, height=90)

    # ------------------------------------------------------------------
    # Plots
    # ------------------------------------------------------------------

    def _build_history_trend(
        self,
        df: pd.DataFrame,
        metric: str,
        *,
        show_legend: bool = True,
        axis_visible: bool = True,
    ):
        label = _METRIC_LABELS[metric]

        if metric == "execution_success":
            df = df.copy()
            df[metric] = df[metric].astype(float)

        agg = (
            df.groupby(["run_id", "model", "condition"], as_index=False)
            .agg(**{metric: (metric, "mean"), "created_at": ("created_at", "first")})
            .sort_values(["created_at", "run_id", "model", "condition"])
        )
        if agg.empty:
            return hv.Curve([], kdims=["run_id"], vdims=[metric]).opts(
                responsive=True, height=340, title="No data for selected filters."
            )

        line = agg.hvplot.line(
            x="run_id",
            y=metric,
            by=["model", "condition"],
            ylabel=label,
            xlabel="Run" if axis_visible else "",
            responsive=True,
            height=400,
            legend="right" if show_legend else False,
            fontscale=1.1,
            line_width=2,
        )

        scatter = agg.hvplot.scatter(
            x="run_id",
            y=metric,
            by=["model", "condition"],
            xlabel="Run" if axis_visible else "",
            legend=False,
        )

        return (line * scatter).opts(
            legend_position="top_right",
            xaxis="bottom" if axis_visible else None,
            default_tools=["reset"],
            tools=["hover"],
            toolbar=None,
        )

    def _centered_footer(self, text: str):
        return pn.Row(
            pn.Spacer(),
            pmui.Typography(
                text, variant="caption", align="center", sx={"color": "text.secondary"}
            ),
            pn.Spacer(),
            sizing_mode="stretch_width",
        )

    def _build_metric_violin(
        self,
        df: pd.DataFrame,
        metric: str,
        *,
        show_legend: bool = True,
        axis_visible: bool = True,
    ):
        metric_df = df.copy()
        if metric == "execution_success":
            metric_df[metric] = metric_df[metric].astype(float)

        violin = hv.Violin(metric_df, kdims=["model", "condition"], vdims=[metric]).opts(
            responsive=True,
            height=400,
            show_legend=show_legend,
            ylabel=_METRIC_LABELS[metric],
            xlabel="Model" if axis_visible else "",
            fontscale=1.1,
            split="condition",
            legend_position="top_right",
        )
        status = metric_df["execution_success"].astype(bool)
        success_points = metric_df[status].hvplot.scatter(
            x="model",
            y=metric,
            by="condition",
            color="#2ca02c",
            alpha=0.45,
            size=18,
            jitter=0.25,
            responsive=True,
            height=400,
            legend=False,
        )
        failure_points = metric_df[~status].hvplot.scatter(
            x="model",
            y=metric,
            by="condition",
            color="#d62728",
            alpha=0.45,
            size=18,
            jitter=0.25,
            responsive=True,
            height=400,
            legend=False,
        )
        return (violin * success_points * failure_points).opts(
            default_tools=["reset"],
            tools=["hover"],
            xaxis="bottom" if axis_visible else None,
            toolbar=None,
        )

    def _build_metric_trend(
        self,
        df: pd.DataFrame,
        metric: str,
        *,
        show_legend: bool = True,
        axis_visible: bool = True,
    ):
        return self._build_history_trend(
            df, metric, show_legend=show_legend, axis_visible=axis_visible
        )

    # ------------------------------------------------------------------
    # Reactive update — fires whenever any filter param changes
    # ------------------------------------------------------------------

    @param.depends(
        "selected_runs",
        "selected_models",
        "selected_queries",
        "selected_conditions",
        watch=True,
        on_init=True,
    )
    def _update_views(self):
        df = self._filtered_df()
        with pn.io.hold():
            if df.empty:
                self._plots_container.objects = [
                    pmui.Paper(
                        pmui.Typography("No data for selected filters.", variant="body2"),
                        sx={"p": 2},
                        elevation=1,
                    )
                ]
                self._table_pane.value = pd.DataFrame()
                return

            violin_sections = []
            trend_sections = []
            for i, metric in enumerate(_METRICS):
                is_last = i == len(_METRICS) - 1
                violin_sections.append(
                    pmui.Column(
                        self._build_metric_violin(
                            df,
                            metric,
                            show_legend=(i == 0),
                            axis_visible=is_last,
                        ),
                        sx={"gap": "6px"},
                    )
                )
                trend_sections.append(
                    pmui.Column(
                        self._build_metric_trend(
                            df,
                            metric,
                            show_legend=(i == 0),
                            axis_visible=is_last,
                        ),
                        sx={"gap": "6px"},
                    )
                )

            self._plots_container.objects = [
                pmui.Grid(
                    pmui.Grid(
                        pmui.Paper(
                            pmui.Column(
                                pmui.Typography("Metric Distribution", variant="h5"),
                                *violin_sections,
                                self._centered_footer("Model"),
                                sx={"gap": "16px"},
                            ),
                            sx={"p": 2},
                            styles={"height": "100%"},
                            elevation=1,
                        ),
                        size={"xs": 12, "lg": 6},
                    ),
                    pmui.Grid(
                        pmui.Paper(
                            pmui.Column(
                                pmui.Typography("Historical Run Trend", variant="h5"),
                                *trend_sections,
                                self._centered_footer("Run"),
                                sx={"gap": "16px"},
                            ),
                            sx={"p": 2},
                            styles={"height": "100%"},
                            elevation=1,
                        ),
                        size={"xs": 12, "lg": 6},
                    ),
                    container=True,
                    spacing=2,
                    sizing_mode="stretch_width",
                )
            ]

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
                self._run_filter,
                pmui.Divider(),
                self._model_filter,
                pmui.Divider(),
                self._query_filter,
                pmui.Divider(),
                self._condition_filter,
                self._status_legend,
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
                self._plots_container,
                pmui.Paper(self._table_pane, sx={"p": 2}, elevation=1),
                sx={"gap": "16px"},
                margin=10,
            )

        return pmui.Page(
            title="HoloViz Skills - Eval Trends",
            sidebar=[sidebar],
            sidebar_open=False,
            main=[main],
        )


dashboard = HistoricalDashboard(results_dir=_RESULTS_DIR)
dashboard.servable()

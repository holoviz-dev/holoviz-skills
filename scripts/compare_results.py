#!/usr/bin/env python3
"""
HoloViz Skills Evaluation — Comparison Dashboard.

Read-only Panel dashboard that loads evaluation_results.json and renders
side-by-side comparisons of model performance across queries and conditions.

Usage:
    panel serve scripts/compare_results.py --show --args eval_results/
    panel serve scripts/compare_results.py --args eval_results/
    panel serve scripts/compare_results.py  # defaults to ../eval_results
"""

import json
import sys
from pathlib import Path

import pandas as pd
import panel as pn
import panel_material_ui as pmui
import param

pn.extension("tabulator", throttled=True)

# ── Resolve eval results path from CLI args ────────────────────────────────
_default_results_dir = Path(__file__).parent.parent / "eval_results"
_results_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else _default_results_dir

_METRICS = [
    "tokens_output",
    "tokens_input",
    "tokens_cached",
    "execution_time",
    "execution_success",
    "has_code",
]

_METRIC_LABELS = {
    "tokens_output": "Tokens (output)",
    "tokens_input": "Tokens (input)",
    "tokens_cached": "Tokens (cached)",
    "execution_time": "Response Time (s)",
    "execution_success": "Execution Success",
    "has_code": "Code Generated",
}

CONDITIONS = ("with_skills", "without_skills")
CONDITION_LABELS = {
    "with_skills": "With Skills",
    "without_skills": "Without Skills",
}


# ── Screenshot helper ──────────────────────────────────────────────────────


def _ensure_screenshot(query_dir: Path) -> Path | None:
    """Return path to screenshot.png for a query run, generating it if needed.

    - If screenshot.png already exists, returns it immediately (cached).
    - If plot_output.png exists (matplotlib), copies it to screenshot.png.
    - If plot_output.html exists, uses Playwright headless to render it.
    - Returns None if no output file exists or rendering fails.
    """
    screenshot_path = query_dir / "screenshot.png"
    if screenshot_path.exists():
        return screenshot_path

    png_file = query_dir / "plot_output.png"
    if png_file.exists():
        import shutil

        shutil.copy(png_file, screenshot_path)
        return screenshot_path

    html_file = query_dir / "plot_output.html"
    if html_file.exists():
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1200, "height": 800})
                page.goto(f"file://{html_file.absolute()}")
                page.wait_for_timeout(2000)
                page.screenshot(path=str(screenshot_path), full_page=False)
                browser.close()
            return screenshot_path
        except Exception:
            return None

    return None


# ── Data loading ───────────────────────────────────────────────────────────


def _load_results(results_dir: Path) -> dict | None:
    """Load evaluation_results.json from results_dir. Returns None if missing."""
    json_file = results_dir / "evaluation_results.json"
    if not json_file.exists():
        return None
    with open(json_file) as f:
        return json.load(f)


def _build_dataframe(summary: dict) -> pd.DataFrame:
    """Flatten the nested summary JSON into a tidy DataFrame.

    Columns: query, model, condition, <metric>...
    """
    rows = []
    for query_id, query_data in summary.get("queries", {}).items():
        for model, model_data in query_data.get("models", {}).items():
            for condition in CONDITIONS:
                metrics = model_data.get(condition, {})
                if not metrics:
                    continue
                row = {
                    "query": query_id,
                    "model": model,
                    "condition": condition,
                    "condition_label": CONDITION_LABELS[condition],
                }
                for m in _METRICS:
                    row[m] = metrics.get(m)
                rows.append(row)
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ── State ──────────────────────────────────────────────────────────────────


class EvalState(param.Parameterized):
    """Shared filter state for the dashboard."""

    selected_queries = param.ListSelector(default=[], objects=[])
    selected_models = param.ListSelector(default=[], objects=[])
    selected_conditions = param.ListSelector(
        default=list(CONDITIONS),
        objects=list(CONDITIONS),
    )


# ── Dashboard app ──────────────────────────────────────────────────────────


class ComparisonDashboard(pn.viewable.Viewer):
    """Read-only dashboard for comparing model evaluation results."""

    def __init__(self, results_dir: Path, **params):
        self._results_dir = results_dir
        self._summary = _load_results(results_dir)
        self._df_full = _build_dataframe(self._summary) if self._summary else pd.DataFrame()

        # Populate selector objects from data
        all_queries = sorted(self._df_full["query"].unique()) if not self._df_full.empty else []
        all_models = sorted(self._df_full["model"].unique()) if not self._df_full.empty else []

        self._state = EvalState(
            selected_queries=all_queries,
            selected_models=all_models,
        )
        self._state.param["selected_queries"].objects = all_queries
        self._state.param["selected_models"].objects = all_models

        # Build all components before super().__init__ so watchers work correctly
        self._query_filter = pmui.CheckButtonGroup(
            label="Queries",
            options=all_queries,
            value=all_queries,
            orientation="vertical",
            color="primary",
            button_style="outlined",
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
        self._condition_filter = pmui.CheckButtonGroup(
            label="Conditions",
            options=list(CONDITIONS),
            value=list(CONDITIONS),
            orientation="vertical",
            color="primary",
            button_style="outlined",
            sizing_mode="stretch_width",
        )

        # Reactive content panes — created once, updated in-place
        self._gallery_pane = pn.Column(sizing_mode="stretch_width")
        self._table_pane = pn.widgets.Tabulator(
            pd.DataFrame(),
            theme="materialize",
            sizing_mode="stretch_width",
            show_index=False,
        )
        self._no_data_alert = pmui.Alert(
            "No evaluation results found. "
            f"Run `python eval.py` to generate results in `{results_dir}`.",
            alert_type="warning",
            visible=self._summary is None or self._df_full.empty,
        )

        super().__init__(**params)

        # Wire filters — explicit watchers (CheckButtonGroup.from_param write-back gap)
        self._query_filter.param.watch(
            lambda e: setattr(self._state, "selected_queries", e.new), "value"
        )
        self._model_filter.param.watch(
            lambda e: setattr(self._state, "selected_models", e.new), "value"
        )
        self._condition_filter.param.watch(
            lambda e: setattr(self._state, "selected_conditions", e.new), "value"
        )

        # Initial render
        self._refresh_views()

        # Wire state changes to refresh
        self._state.param.watch(
            lambda _: self._refresh_views(),
            ["selected_queries", "selected_models", "selected_conditions"],
        )

    # ── Data helpers ───────────────────────────────────────────────────────

    def _filtered_df(self) -> pd.DataFrame:
        if self._df_full.empty:
            return self._df_full
        df = self._df_full
        if self._state.selected_queries:
            df = df[df["query"].isin(self._state.selected_queries)]
        if self._state.selected_models:
            df = df[df["model"].isin(self._state.selected_models)]
        if self._state.selected_conditions:
            df = df[df["condition"].isin(self._state.selected_conditions)]
        return df

    # ── View update ────────────────────────────────────────────────────────

    def _refresh_views(self):
        with pn.io.hold():
            df = self._filtered_df()
            if df.empty:
                self._gallery_pane.objects = []
                self._table_pane.value = pd.DataFrame()
                return

            # ── Screenshot gallery ─────────────────────────────────────────
            # Group rows by query; within each query build one card per
            # (model, condition) combination that survived the filters.
            # Cards are laid out in a responsive row per query.

            query_sections = []
            for query_id in sorted(df["query"].unique()):
                query_df = df[df["query"] == query_id]
                cards = []
                for _, row in query_df.sort_values(["model", "condition"]).iterrows():
                    label = f"{row['model']} — {row['condition_label']}"
                    query_dir = self._results_dir / row["model"] / row["condition"] / query_id
                    screenshot = _ensure_screenshot(query_dir)
                    if screenshot is not None:
                        img = pn.pane.PNG(
                            str(screenshot),
                            sizing_mode="scale_width",
                            height=500,
                        )
                    else:
                        img = pmui.Alert(
                            "No plot output available.",
                            alert_type="info",
                            sizing_mode="stretch_width",
                        )
                    card = pmui.Paper(
                        pmui.Typography(
                            label, variant="subtitle2", sx={"mb": 1, "color": "text.secondary"}
                        ),
                        img,
                        elevation=2,
                        sx={"p": 2, "flex": "1 1 320px", "minWidth": "280px"},
                    )
                    cards.append(card)

                query_row = pn.Column(
                    pmui.Typography(query_id, variant="h6"),
                    pn.FlexBox(*cards, flex_wrap="wrap", gap="16px", sizing_mode="stretch_width"),
                    sizing_mode="stretch_width",
                )
                query_sections.append(query_row)

            self._gallery_pane.objects = query_sections

            # ── Summary table — all metrics as columns ─────────────────────
            display_cols = ["query", "model", "condition_label"] + _METRICS
            rename_map = {"condition_label": "condition", **_METRIC_LABELS}
            table_df = (
                df[display_cols]
                .rename(columns=rename_map)
                .sort_values(["query", "model", "condition"])
                .reset_index(drop=True)
            )
            self._table_pane.value = table_df

    # ── Layout ─────────────────────────────────────────────────────────────

    def __panel__(self):
        with pn.config.set(sizing_mode="stretch_width"):
            sidebar = pmui.Column(
                pmui.Typography("Filters", variant="h6"),
                self._query_filter,
                pmui.Divider(),
                self._model_filter,
                pmui.Divider(),
                self._condition_filter,
                sx={"gap": "12px"},
                margin=10,
            )
            main = pmui.Column(
                self._no_data_alert,
                pmui.Typography(
                    "Model Comparison",
                    variant="h4",
                ),
                pmui.Typography(
                    f"Results directory: `{self._results_dir}`",
                    variant="body2",
                    sx={"color": "text.secondary"},
                ),
                pmui.Paper(
                    self._gallery_pane,
                    sx={"p": 2},
                    elevation=1,
                ),
                pmui.Paper(
                    self._table_pane,
                    sx={"p": 2},
                    elevation=1,
                ),
                sx={"gap": "16px"},
                margin=10,
            )

        return pmui.Page(
            title="HoloViz Skills — Eval Comparison",
            sidebar=[sidebar],
            main=[main],
        )


# ── Entry point ────────────────────────────────────────────────────────────

dashboard = ComparisonDashboard(results_dir=_results_dir)
dashboard.servable()

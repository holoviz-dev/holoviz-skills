"""Tests for layout_lint.py.

Fixtures are hand-built HTML with a known, deliberately-planted violation
(WRONG) and its fix (CORRECT) — there's no Panel/panel-material-ui available
in this test environment to serve a real app against, but layout_lint.py has
no Panel-specific knowledge: it only inspects live DOM/CSSOM through a real
browser, so a plain static HTML page exercises exactly the same code path a
served Panel app would. Fixtures load via `file://` (no HTTP server needed).

`clean_realistic` is a small dashboard-shaped page (header, sidebar, KPI row,
button) checked across all three default widths — it must come back
violation-free, since a false positive on ordinary-looking content is the
failure mode that trains agents to ignore this tool.

Run from this directory: `python test_layout_lint.py` (imports the sibling
`layout_lint` module by plain name; requires `playwright install chromium`
to have been run once).
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import layout_lint
from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# Fixtures — one deliberately-planted violation per check, plus its fix
# ---------------------------------------------------------------------------

CASES: dict[str, dict] = {
    "overflow": {
        "check": "VIEWPORT_OVERFLOW",
        "width": 1400,
        "wrong": """<!doctype html><html><body style="margin:0">
            <div style="width:2000px; height:200px; background:#eee;">too wide</div>
            </body></html>""",
        "correct": """<!doctype html><html><body style="margin:0">
            <div style="max-width:100%; height:200px; background:#eee;">fits fine</div>
            </body></html>""",
    },
    "touch_target": {
        "check": "TOUCH_TARGET_TOO_SMALL",
        "width": 1400,
        "wrong": """<!doctype html><html><body style="margin:0; padding:40px;">
            <button style="width:20px; height:20px; padding:0;">x</button>
            </body></html>""",
        "correct": """<!doctype html><html><body style="margin:0; padding:40px;">
            <button style="width:48px; height:48px;">x</button>
            </body></html>""",
    },
    "contrast": {
        "check": "LOW_CONTRAST",
        "width": 1400,
        "wrong": """<!doctype html><html>
            <body style="margin:0; padding:40px; background:#ffffff;">
            <p style="color:#cccccc; font-size:16px;">Hard to read text</p>
            </body></html>""",
        "correct": """<!doctype html><html>
            <body style="margin:0; padding:40px; background:#ffffff;">
            <p style="color:#222222; font-size:16px;">Easy to read text</p>
            </body></html>""",
    },
    "overlap": {
        "check": "ELEMENT_OVERLAP",
        "width": 1400,
        "wrong": """<!doctype html><html><body style="margin:0; padding:40px;">
            <div style="position:relative;">
              <div style="width:200px; height:100px; background:#ffcccc; position:relative;">A</div>
              <div style="width:200px; height:100px; background:#ccccff; position:relative;
                          margin-top:-60px; margin-left:80px;">B</div>
            </div></body></html>""",
        "correct": """<!doctype html><html><body style="margin:0; padding:40px;">
            <div style="position:relative;">
              <div style="width:200px; height:100px; background:#ffcccc; position:relative;">A</div>
              <div style="width:200px; height:100px; background:#ccccff; position:relative;
                          margin-top:10px;">B</div>
            </div></body></html>""",
    },
    "misaligned_left_edge": {
        "check": "MISALIGNED_LEFT_EDGE",
        "width": 1400,
        "wrong": """<!doctype html><html><body style="margin:0; padding:40px;"><div>
            <div class="card" style="width:300px; height:60px; background:#eee;
                        margin-bottom:8px; margin-left:0px;">Row 1</div>
            <div class="card" style="width:300px; height:60px; background:#eee;
                        margin-bottom:8px; margin-left:24px;">Row 2</div>
            <div class="card" style="width:300px; height:60px; background:#eee;
                        margin-bottom:8px; margin-left:0px;">Row 3</div>
            </div></body></html>""",
        "correct": """<!doctype html><html><body style="margin:0; padding:40px;"><div>
            <div class="card" style="width:300px; height:60px; background:#eee;
                        margin-bottom:8px;">Row 1</div>
            <div class="card" style="width:300px; height:60px; background:#eee;
                        margin-bottom:8px;">Row 2</div>
            <div class="card" style="width:300px; height:60px; background:#eee;
                        margin-bottom:8px;">Row 3</div>
            </div></body></html>""",
    },
    "font_scale": {
        "check": "FONT_SCALE_SPRAWL",
        "width": 1400,
        "wrong": """<!doctype html><html><body style="margin:0; padding:20px;">
            <p style="font-size:11px;">a</p><p style="font-size:13px;">b</p>
            <p style="font-size:15px;">c</p><p style="font-size:17px;">d</p>
            <p style="font-size:19px;">e</p><p style="font-size:21px;">f</p>
            <p style="font-size:23px;">g</p><p style="font-size:27px;">h</p>
            </body></html>""",
        "correct": """<!doctype html><html><body style="margin:0; padding:20px;">
            <p style="font-size:14px;">a</p><p style="font-size:14px;">b</p>
            <p style="font-size:16px;">c</p><p style="font-size:16px;">d</p>
            <p style="font-size:24px;">e</p>
            </body></html>""",
    },
}

# A small dashboard-shaped page — header, sidebar (collapses under 600px),
# a 3-card KPI row, a button, body text — checked across ALL default widths.
# Must stay completely clean; this is the primary anti-false-positive guard.
CLEAN_REALISTIC_HTML = """<!doctype html>
<html><head><style>
  body { margin:0; font-family: sans-serif; background:#fafafa; color:#1a1a1a; }
  .header { height:56px; background:#1565c0; color:#fff; display:flex;
            align-items:center; padding:0 16px; font-size:18px; }
  .layout { display:flex; }
  .sidebar { width:220px; padding:16px; box-sizing:border-box; }
  .main { flex:1; padding:16px; box-sizing:border-box; max-width:100%; min-width:0; }
  .kpi-row { display:flex; gap:16px; flex-wrap:wrap; }
  .kpi-card { flex:1; min-width:100px; background:#fff; border-radius:8px; padding:16px;
              box-sizing:border-box; box-shadow:0 1px 3px rgba(0,0,0,0.1); }
  .kpi-card h3 { margin:0 0 8px 0; font-size:14px; color:#555; }
  .kpi-card .value { font-size:24px; font-weight:600; }
  .btn { display:inline-block; padding:10px 16px; min-width:44px; min-height:44px;
         box-sizing:border-box; background:#1565c0; color:#fff; border:none;
         border-radius:6px; font-size:14px; cursor:pointer; }
  p { font-size:14px; line-height:1.6; color:#333; }
  @media (max-width: 600px) {
    .layout { flex-direction: column; }
    .sidebar { width:100%; }
  }
</style></head>
<body>
  <div class="header">Sales Dashboard</div>
  <div class="layout">
    <div class="sidebar"><p>Filters</p><button class="btn">Apply</button></div>
    <div class="main">
      <div class="kpi-row">
        <div class="kpi-card"><h3>Revenue</h3><div class="value">$12,400</div></div>
        <div class="kpi-card"><h3>Units</h3><div class="value">340</div></div>
        <div class="kpi-card"><h3>Margin</h3><div class="value">28%</div></div>
      </div>
      <p>Select rows to filter the charts above.</p>
    </div>
  </div>
</body></html>
"""


# ---------------------------------------------------------------------------
# Regressions — edge cases validated manually during development, locked in
# ---------------------------------------------------------------------------

# position:absolute overlays (Tooltip/Dialog/SpeedDial-shaped elements) must
# NOT trigger ELEMENT_OVERLAP — check_overlap only considers static/relative.
ABSOLUTE_OVERLAY_HTML = """<!doctype html><html><body style="margin:0; padding:40px;">
    <div style="position:relative; width:300px; height:100px; background:#eee;">Card content</div>
    <div style="position:absolute; top:50px; left:250px; background:#333; color:#fff;
                padding:4px 8px; border-radius:4px; font-size:12px;">Tooltip</div>
    </body></html>"""

# A .pn-loading overlay that never clears must produce a LOAD_TIMEOUT
# violation and let the run continue to other widths, not crash and discard
# everything already collected.
STUCK_SPINNER_HTML = """<!doctype html><html><body>
    <div class="pn-loading" style="width:100px;height:100px;">stuck spinner, never clears</div>
    </body></html>"""


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _lint_html(browser, html: str, width: int) -> list[layout_lint.Violation]:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(html)
        path = f.name
    page = browser.new_page()
    try:
        page.goto(f"file://{path}")
        page.set_viewport_size({"width": width, "height": layout_lint.VIEWPORT_HEIGHT})
        page.wait_for_function("() => !document.querySelector('.pn-loading')", timeout=5000)
        page.wait_for_timeout(50)
        dom = page.evaluate(layout_lint.DOM_EXTRACT_JS)
        return layout_lint.run_checks(dom, width)
    finally:
        page.close()
        Path(path).unlink(missing_ok=True)


def run() -> int:
    failures: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()

        for name, case in CASES.items():
            check = case["check"]
            width = case["width"]

            wrong_hits = {v.check for v in _lint_html(browser, case["wrong"], width)}
            if check not in wrong_hits:
                failures.append(
                    f"[{name}] WRONG fixture did not trigger {check} "
                    f"(got {wrong_hits or 'nothing'})"
                )

            correct_hits = {v.check for v in _lint_html(browser, case["correct"], width)}
            if check in correct_hits:
                failures.append(f"[{name}] CORRECT fixture incorrectly triggered {check}")

        clean_hits: set[str] = set()
        for width in layout_lint.DEFAULT_WIDTHS:
            clean_hits |= {v.check for v in _lint_html(browser, CLEAN_REALISTIC_HTML, width)}
        if clean_hits:
            failures.append(
                f"[clean_realistic] expected no violations across default widths, got {clean_hits}"
            )

        overlay_hits = {v.check for v in _lint_html(browser, ABSOLUTE_OVERLAY_HTML, 1400)}
        if "ELEMENT_OVERLAP" in overlay_hits:
            failures.append(
                "[absolute_overlay_not_flagged] a position:absolute overlay (Tooltip/Dialog-"
                f"shaped) incorrectly triggered ELEMENT_OVERLAP (got {overlay_hits})"
            )

        browser.close()

    # LOAD_TIMEOUT: a stuck .pn-loading overlay must be reported per width and
    # must not crash the run or discard results from other widths.
    with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as f:
        f.write(STUCK_SPINNER_HTML)
        stuck_path = f.name
    try:
        timeout_violations = layout_lint.lint_url(
            f"file://{stuck_path}", widths=[1400, 768], timeout=1000
        )
        timeout_checks = [v.check for v in timeout_violations]
        if timeout_checks != ["LOAD_TIMEOUT", "LOAD_TIMEOUT"]:
            failures.append(
                f"[load_timeout_resilience] expected a LOAD_TIMEOUT per width (2 total), "
                f"got {timeout_checks}"
            )
    finally:
        Path(stuck_path).unlink(missing_ok=True)

    # Unreachable URL: must raise ConnectionError with a clear message, not an
    # unhandled Playwright traceback.
    try:
        layout_lint.lint_url("http://localhost:1/nope", widths=[1400])
        failures.append("[unreachable_url] expected ConnectionError, none was raised")
    except ConnectionError:
        pass
    except Exception as e:  # noqa: BLE001 - deliberately broad: any other
        # exception type here means the error wasn't translated to
        # ConnectionError as intended.
        failures.append(f"[unreachable_url] expected ConnectionError, got {type(e).__name__}: {e}")

    # Each case contributes a WRONG and a CORRECT assertion; the extras are
    # clean_realistic, absolute_overlay, load_timeout, and unreachable_url.
    total = len(CASES) * 2 + 4
    passed = total - len(failures)
    print(f"{passed}/{total} passed")
    for f in failures:
        print(f"  FAIL: {f}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run())

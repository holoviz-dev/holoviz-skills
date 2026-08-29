"""An explorable guide to context: why long AI chats get expensive.

A worked example of the pattern in ``../building-slides.md``.
The subject is an *idea*, not a dataset — the numbers are a model, not a
measurement — which is what separates this genre from ``data-storytelling``.

Six things to notice, because they are the pattern rather than the topic:

1. ``SlidesTemplate`` supplies navigation.  reveal.js gives arrow keys, the
   ``#/2`` URL hash, and progress for free; each object in ``main`` is one
   slide.
2. **"Words" not "tokens."**  The audience is non-technical; every
   user-facing string avoids jargon per the vocabulary table in
   ``building-slides.md``.
3. The interaction on slide 3 is *load-bearing*.  Dragging ``messages``
   redraws the curve **and** rewrites the stat cards, so the reader derives
   the acceleration instead of being told it.  No formula is shown.
4. The axes are fixed, not autoscaled.  This is the single most common
   mistake in an explorable and it silently destroys the lesson.
5. Slides 2, 4, and 5 default to a state that already shows something
   (``turn=1``, ``shown=5``, ``stage=1``), so the reader lands on a
   populated view rather than a blank widget.
6. The opening slide is static — no Python interaction — so Pyodide is warm
   by the time the reader reaches a widget under ``panel convert``.

Run:   panel serve context_explainer.py --show
Ship:  panel convert context_explainer.py --to pyodide-worker --out dist --index
"""

import holoviews as hv
import numpy as np
import panel as pn
import param
from bokeh.core.properties import value
from bokeh.models import NumeralTickFormatter
from panel.template import SlidesTemplate

hv.extension("bokeh")
pn.extension()

# ── Theme (see developing-with-holoviz/skills/hvplot/distilling-explanatory-plots.md) ──
DISPLAY = "Verdana, sans-serif"
BODY = "Verdana, sans-serif"
INK, MUTED, HAIRLINE = "#1a1a1a", "#6b7280", "#d1d5db"
ACCENT, ACCENT_SOFT = "#2563eb", "#dbeafe"
DANGER, DANGER_SOFT = "#dc2626", "#fee2e2"


def font_hook(plot, element):
    """Apply consistent typography to every Bokeh chart."""
    fig = plot.state
    if fig.title is not None:
        fig.title.text_font = DISPLAY
        fig.title.text_font_style = "bold"
        fig.title.text_font_size = "15pt"
        fig.title.text_color = INK
    for axis in fig.axis:
        axis.axis_label_text_font = BODY
        axis.axis_label_text_font_style = "normal"
        axis.axis_label_text_color = MUTED
        axis.major_label_text_font = BODY
        axis.major_label_text_color = MUTED
        axis.axis_line_color = HAIRLINE
        axis.major_tick_line_color = HAIRLINE
        axis.minor_tick_line_color = None
    fig.outline_line_color = None
    for r in fig.renderers:
        glyph = getattr(r, "glyph", None)
        if glyph is not None and hasattr(glyph, "text_font"):
            glyph.text_font = value(BODY)


BASE = dict(toolbar=None, show_grid=False, show_legend=False, hooks=[font_hook], fontscale=1.05)

# ── Model ───────────────────────────────────────────────────────
# All user-facing numbers derive from these two constants.
SYS = 3000  # setup instructions, re-sent every turn
TURN = 650  # one exchange: user message + AI reply
MAX_TURNS = 60


def total_read(n):
    """Words the AI reads across *n* messages — the accelerating sum."""
    return n * SYS + TURN * (n * (n + 1)) // 2


def thread_len(n):
    """Words the conversation actually contains — the linear sum."""
    return n * TURN


def fmt(n):
    return f"{round(n):,}"


# ── Centred slide helpers ───────────────────────────────────────
CSS = f"font-family:{BODY};color:{INK};text-align:center;max-width:800px;margin:0 auto"


def headline(title, dek, label=None):
    """Slide title + subtitle, centred in the reveal.js stage."""
    label_html = ""
    if label:
        label_html = (
            f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:.08em;color:{ACCENT};margin-bottom:6px">{label}</div>'
        )
    return pn.pane.HTML(
        f'<div style="{CSS}">'
        f"{label_html}"
        f'<h1 style="font-size:42px;font-weight:800;margin:0 0 10px;line-height:1.15">{title}</h1>'
        f'<p style="font-size:17px;color:{MUTED};margin:0;line-height:1.5">{dek}</p>'
        f"</div>",
        sizing_mode="stretch_width",
    )


# ═══════════════════════════════════════════════════════════════════
# Slide 1 — What Really Happens When You Chat with AI
# Static.  No interaction, so Pyodide warms up in the background.
# ═══════════════════════════════════════════════════════════════════

slide_hook = pn.Column(
    headline(
        "What Really Happens When You Chat with AI",
        "A 40-message conversation feels like 40 short exchanges.<br>"
        "Behind the scenes, it's <b>much</b> more work than that.",
        label="The big picture",
    ),
    pn.pane.HTML(
        f"""<div style="{CSS}">
<div style="display:flex;gap:40px;justify-content:center;margin:20px 0 16px">
  <div>
    <div style="font-size:36px;font-weight:700">{40}</div>
    <div style="font-size:11px;color:{MUTED}">messages you sent</div></div>
  <div>
    <div style="font-size:36px;font-weight:700;color:{ACCENT}">{fmt(total_read(40))}</div>
    <div style="font-size:11px;color:{MUTED}">words the AI processed</div></div>
  <div>
    <div style="font-size:36px;font-weight:700;color:{DANGER}">{total_read(40)//thread_len(40)}x
    </div>
    <div style="font-size:11px;color:{MUTED}">more than you'd expect</div></div>
</div>
<div style="max-width:360px;margin:0 auto">
  <div style="display:flex;align-items:center;gap:8px;margin:5px 0">
    <div style="width:90px;text-align:right;font-size:11px;font-weight:600">Your messages</div>
    <div style="flex:1;height:14px;border-radius:3px;background:#f0f0f0;overflow:hidden">
      <div style="height:100%;width:4%;background:{ACCENT};opacity:.45;
           border-radius:3px;min-width:3px"></div></div></div>
  <div style="display:flex;align-items:center;gap:8px;margin:5px 0">
    <div style="width:90px;text-align:right;font-size:11px;font-weight:600">AI's workload</div>
    <div style="flex:1;height:14px;border-radius:3px;background:#f0f0f0;overflow:hidden">
      <div style="height:100%;width:100%;background:{ACCENT};border-radius:3px"></div>
    </div></div>
</div>
<p style="margin:16px auto 0;max-width:480px;font-size:13px;color:{MUTED};line-height:1.5">
  <b style="color:{INK}">Why the gap?</b> The AI has no memory between messages.
  Every time you hit send, it <em>re-reads the entire conversation from the
  beginning</em>.</p>
</div>""",
        sizing_mode="stretch_width",
    ),
)


# ═══════════════════════════════════════════════════════════════════
# Slide 2 — Every Message Starts from Scratch
# The exchange column stays small; the payload bar grows.
# ═══════════════════════════════════════════════════════════════════


class PayloadDemo(pn.viewable.Viewer):
    """Statelessness, shown rather than asserted.

    Each round shows the exchange alongside a growing bar representing
    the full payload the AI received — dramatic contrast instead of the
    mirrored-columns pattern that looks too similar to convey the point.
    Defaults to ``turn=1`` so the first round is already visible.
    """

    turn = param.Integer(default=1, bounds=(0, 4))

    CHAT = [
        ("why is this environment failing?", "the lockfile is out of date"),
        ("how do I regenerate it?", "delete it and reinstall"),
        ("that broke two packages", "pin the majors and retry"),
        ("still broken", "the channel mirror is stale"),
    ]

    def __init__(self, **params):
        self._view = pn.pane.HTML("", sizing_mode="stretch_width")
        self._summary = pn.pane.HTML("", sizing_mode="stretch_width")
        # Button before super — on_init=True fires _update during super,
        # which sets _btn.name and _btn.disabled.
        self._btn = pn.widgets.Button(
            name="Send message 2", button_type="primary", width=180, align="center"
        )
        super().__init__(**params)
        self._btn.on_click(self._on_advance)
        self._layout = pn.Column(
            self._view,
            self._btn,
            self._summary,
            align="center",
            styles={"max-width": "620px", "margin": "0 auto"},
        )

    def _on_advance(self, event):
        if self.turn < len(self.CHAT):
            self.turn += 1

    @param.depends("turn", watch=True, on_init=True)
    def _update(self):
        self._view.object = self._render_table()
        done = self.turn >= len(self.CHAT)
        self._btn.name = "That's the pattern" if done else f"Send message {self.turn + 1}"
        self._btn.disabled = done
        self._summary.object = self._render_summary()

    def _render_table(self):
        max_pay = SYS + TURN * len(self.CHAT)
        header = (
            f'<tr><th style="padding:0 8px 4px;font-size:9px;font-weight:700;'
            f"color:{MUTED};text-transform:uppercase;letter-spacing:.06em;"
            f'text-align:left"></th>'
            f'<th style="text-align:left;font-size:9px;font-weight:700;'
            f'color:{MUTED};text-transform:uppercase;letter-spacing:.06em">'
            f"Exchange</th>"
            f'<th style="text-align:left;font-size:9px;font-weight:700;'
            f'color:{MUTED};text-transform:uppercase;letter-spacing:.06em">'
            f"What the AI received</th></tr>"
        )
        rows = []
        for i in range(self.turn):
            msg, reply = self.CHAT[i]
            pay = SYS + TURN * (i + 1)
            pct = max(4, round(100 * pay / max_pay))
            note = "setup included" if i == 0 else "all prior rounds re-sent"
            rows.append(
                f'<tr style="border-top:1px solid #f0f0f0">'
                f'<td style="padding:5px 8px;font-size:12px;font-weight:600;'
                f'color:{MUTED};white-space:nowrap">Round {i+1}</td>'
                f'<td style="padding:5px 4px;font-size:11px">'
                f'<div style="background:{ACCENT_SOFT};border-radius:4px;'
                f"padding:2px 6px;display:inline-block;max-width:140px;"
                f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
                f"{msg}</div></td>"
                f'<td style="padding:5px 4px;width:55%">'
                f'<div style="height:16px;border-radius:3px;background:#f0f0f0;'
                f'overflow:hidden"><div style="height:100%;width:{pct}%;'
                f'background:{ACCENT};border-radius:3px"></div></div>'
                f'<div style="font-size:10px;margin-top:1px;text-align:left">'
                f'<b style="color:{ACCENT}">{fmt(pay)}</b> '
                f'<span style="color:{MUTED}">· {note}</span></div></td></tr>'
            )
        table = (
            f'<table style="width:100%;border-collapse:collapse;'
            f'font-family:{BODY}">{header}{"".join(rows)}</table>'
        )
        if self.turn == 0:
            table += (
                f'<p style="text-align:center;color:{MUTED};'
                f'font-size:12px;margin:12px 0">'
                f"Press the button to watch the right column grow</p>"
            )
        return table

    def _render_summary(self):
        if self.turn < len(self.CHAT):
            return ""
        typed = thread_len(self.turn)
        rd = sum(SYS + TURN * (i + 1) for i in range(self.turn))
        return (
            f'<p style="text-align:center;font-family:{BODY};font-size:13px;'
            f'color:#1e40af;margin:8px 0"><b>You typed {fmt(typed)} words.</b> '
            f"The AI processed <b>{fmt(rd)}</b> — "
            f"<b>{rd // typed}x</b> what you wrote.</p>"
        )

    def __panel__(self):
        return self._layout


# ═══════════════════════════════════════════════════════════════════
# Slide 3 — The Longer You Go, the Worse It Gets
# The slider drives the chart AND the stat line — one parameter,
# two views, so the reader derives the acceleration.
# ═══════════════════════════════════════════════════════════════════


class CostCurve(pn.viewable.Viewer):
    """The load-bearing interaction.

    ``messages`` drives the chart *and* the stat line, so the reader
    watches the same change expressed geometrically and numerically.
    No formula is shown — the slider derives the growth.
    Continuous updates (no throttling) — the redraw is cheap and
    direct manipulation makes the acceleration feel visceral.
    """

    messages = param.Integer(default=20, bounds=(1, MAX_TURNS), label="messages in the chat")

    def __init__(self, **params):
        self._stats = pn.pane.HTML("", sizing_mode="stretch_width")
        self._plot_pane = pn.pane.HoloViews(None, sizing_mode="stretch_width", height=280)
        super().__init__(**params)
        self._slider = pn.widgets.IntSlider.from_param(
            self.param.messages, width=300, align="center"
        )
        self._layout = pn.Column(
            self._slider,
            self._plot_pane,
            self._stats,
            align="center",
            styles={"max-width": "700px", "margin": "0 auto"},
        )

    @param.depends("messages", watch=True, on_init=True)
    def _update(self):
        self._plot_pane.object = self._make_plot()
        self._stats.object = self._render_stats()

    def _make_plot(self):
        n = self.messages
        x = np.arange(0, n + 1)
        read = np.array([total_read(i) for i in x])
        typed = np.array([thread_len(i) for i in x])

        gap = hv.Area((x, typed, read), vdims=["y", "y2"]).opts(
            color=ACCENT, alpha=0.12, line_alpha=0
        )
        c_read = hv.Curve((x, read)).opts(color=ACCENT, line_width=3)
        c_typed = hv.Curve((x, typed)).opts(color=MUTED, line_width=2, line_dash="dashed")

        lbl_read = hv.Text(n, total_read(n), " AI's workload", halign="left", valign="bottom").opts(
            color=ACCENT, text_font_size="9pt"
        )
        lbl_typed = hv.Text(
            n, total_read(MAX_TURNS) * 0.045, " your messages", halign="left", valign="bottom"
        ).opts(color=MUTED, text_font_size="9pt")

        return (gap * c_typed * c_read * lbl_read * lbl_typed).opts(
            width=580,
            height=260,
            **BASE,
            xlim=(0, MAX_TURNS * 1.35),
            ylim=(0, total_read(MAX_TURNS) * 1.05),
            yformatter=NumeralTickFormatter(format="0.0a"),
            xlabel="messages",
            ylabel="words",
        )

    def _render_stats(self):
        n = self.messages
        typed, read = thread_len(n), total_read(n)
        return (
            f'<div style="font-family:{BODY};display:flex;gap:16px;'
            f'justify-content:center;margin-top:4px">'
            f'<div style="text-align:center">'
            f'<div style="font-size:11px;color:{MUTED}">What you wrote</div>'
            f'<div style="font-size:18px;font-weight:600">{fmt(typed)}</div></div>'
            f'<div style="color:{HAIRLINE};font-size:24px;line-height:1">·</div>'
            f'<div style="text-align:center">'
            f'<div style="font-size:11px;color:#1e40af">AI processed</div>'
            f'<div style="font-size:18px;font-weight:600;color:{ACCENT}">'
            f"{fmt(read)}</div></div>"
            f'<div style="color:{HAIRLINE};font-size:24px;line-height:1">·</div>'
            f'<div style="text-align:center">'
            f'<div style="font-size:11px;color:{MUTED}">Multiplier</div>'
            f'<div style="font-size:18px;font-weight:600;color:{DANGER}">'
            f"{read / typed:.1f}x</div></div></div>"
        )

    def __panel__(self):
        return self._layout


# ═══════════════════════════════════════════════════════════════════
# Slide 4 — Mistakes Never Go Away
# Step-through showing a wrong answer re-read on every turn.
# Defaults to shown=5 so the mistake and first correction are visible.
# ═══════════════════════════════════════════════════════════════════


class MistakeDemo(pn.viewable.Viewer):
    """The wrong answer stays; corrections pile up beside it."""

    shown = param.Integer(default=5, bounds=(4, 12))

    TALK = [
        ("you", "set up the training pipeline", False),
        ("ai", "sure, here is a pipeline config", False),
        ("you", "it needs to checkpoint every epoch", False),
        ("ai", "I'll assume you have a GPU", True),  # the mistake
        ("you", "no, this runs on CPU only", False),
        ("ai", "understood, switching to CPU", False),
        ("you", "the setup still references GPU software", False),
        ("ai", "fixed that", False),
        ("you", "the memory settings are wrong too", False),
        ("ai", "updated for CPU", False),
        ("you", "and the file sizes", False),
        ("ai", "adjusted", False),
    ]

    def __init__(self, **params):
        self._chat = pn.pane.HTML("", sizing_mode="stretch_width")
        self._sidebar = pn.pane.HTML("", sizing_mode="stretch_width")
        self._btn = pn.widgets.Button(
            name="Next message", button_type="primary", width=150, align="center"
        )
        super().__init__(**params)
        self._btn.on_click(self._on_advance)
        self._layout = pn.Column(
            pn.Row(
                self._chat,
                self._sidebar,
                align="center",
                styles={"max-width": "580px", "margin": "0 auto"},
            ),
            self._btn,
            align="center",
        )

    def _on_advance(self, event):
        if self.shown < len(self.TALK):
            self.shown += 1

    @param.depends("shown", watch=True, on_init=True)
    def _update(self):
        self._chat.object = self._render_chat()
        self._sidebar.object = self._render_sidebar()
        done = self.shown >= len(self.TALK)
        self._btn.name = "And it's still there" if done else "Next message"
        self._btn.disabled = done

    def _render_chat(self):
        bubbles = []
        for i in range(self.shown):
            who, text, bad = self.TALK[i]
            bg = ACCENT_SOFT if who == "you" else "#f5f5f5"
            align = "flex-end" if who == "you" else "flex-start"
            if bad:
                bg = DANGER_SOFT
            bubbles.append(
                f'<div style="align-self:{align};max-width:82%;padding:4px 8px;'
                f"border-radius:6px;background:{bg};font-size:11.5px;"
                f'line-height:1.35">{text}</div>'
            )
        return (
            f'<div style="font-family:{BODY};display:flex;flex-direction:column;'
            f'gap:3px;max-height:220px;overflow-y:auto;min-width:260px">'
            + "".join(bubbles)
            + "</div>"
        )

    def _render_sidebar(self):
        rereads = max(0, self.shown - 4)
        return (
            f'<div style="font-family:{BODY};padding:10px 12px;background:#fafafa;'
            f'border-radius:8px;min-width:190px;text-align:center">'
            f'<div style="font-size:9px;font-weight:700;text-transform:uppercase;'
            f'color:{MUTED};letter-spacing:.06em;margin-bottom:6px">'
            f"The wrong answer</div>"
            f'<div style="background:{DANGER_SOFT};border-radius:6px;padding:4px 8px;'
            f'font-size:11.5px;display:inline-block">'
            f'<em>"I\'ll assume you have a GPU"</em></div>'
            f'<div style="margin-top:8px;font-size:13px;display:flex;'
            f'justify-content:center;gap:20px">'
            f'<div><span style="color:{MUTED}">Re-read</span> '
            f'<b style="color:{DANGER}">{rereads}x</b></div>'
            f'<div><span style="color:{MUTED}">Corrections</span> '
            f"<b>{rereads}</b></div></div>"
            f'<p style="margin:8px 0 0;font-size:11.5px;color:{MUTED};'
            f'line-height:1.45;text-align:left">'
            f'<b style="color:{INK}">The AI re-reads the mistake</b> alongside '
            f"every correction, making it more likely to get confused again.</p>"
            f"</div>"
        )

    def __panel__(self):
        return self._layout


# ═══════════════════════════════════════════════════════════════════
# Slide 5 — Go Back and Edit, Don't Keep Talking
# Side-by-side: keep correcting vs. edit the original.
# Defaults to stage=1 so the wrong answer is visible on arrival.
# ═══════════════════════════════════════════════════════════════════


class FixComparison(pn.viewable.Viewer):
    """Two paths diverge from the same mistake."""

    stage = param.Integer(default=1, bounds=(0, 2))

    _BASE = [
        ("you", "set up the training pipeline"),
        ("ai", "here is a pipeline config"),
        ("you", "it needs to checkpoint every epoch"),
    ]
    _BAD = "added a step — assuming you have a GPU"
    _CORRECTIONS = [
        ("you", "no, CPU only"),
        ("ai", "switching"),
        ("you", "still references GPU"),
        ("ai", "fixed"),
        ("you", "memory settings wrong"),
        ("ai", "updating"),
        ("you", "file sizes too"),
        ("ai", "adjusted"),
    ]

    def __init__(self, **params):
        self._view = pn.pane.HTML("", sizing_mode="stretch_width")
        self._result = pn.pane.HTML("", sizing_mode="stretch_width")
        self._btn = pn.widgets.Button(
            name="Run both", button_type="primary", width=160, align="center"
        )
        super().__init__(**params)
        self._btn.on_click(self._on_advance)
        self._layout = pn.Column(
            self._view,
            self._btn,
            self._result,
            align="center",
            styles={"max-width": "680px", "margin": "0 auto"},
        )

    def _on_advance(self, event):
        if self.stage < 2:
            self.stage += 1

    def _bubble(self, who, text, bad=False, edited=False):
        bg = ACCENT_SOFT if who == "you" else "#f5f5f5"
        if bad:
            bg = DANGER_SOFT
        if edited:
            bg = "#dcfce7"
        icon = " ✏️" if edited else ""
        return (
            f'<div style="padding:3px 7px;border-radius:5px;background:{bg};'
            f'font-size:11px;line-height:1.3">{text}{icon}</div>'
        )

    @param.depends("stage", watch=True, on_init=True)
    def _update(self):
        s = self.stage

        a = [self._bubble(w, t) for w, t in self._BASE]
        b = [self._bubble(w, t) for w, t in self._BASE]

        if s >= 1:
            a.append(self._bubble("ai", self._BAD, bad=True))
            b.append(self._bubble("ai", self._BAD, bad=True))

        if s >= 2:
            for w, t in self._CORRECTIONS:
                a.append(self._bubble(w, t))
            b = [
                self._bubble("you", self._BASE[0][1]),
                self._bubble("ai", self._BASE[1][1]),
                self._bubble("you", "checkpoint every epoch — CPU only, no GPU", edited=True),
                self._bubble("ai", "added a CPU-safe checkpoint step"),
            ]

        stats_a = stats_b = ""
        if s >= 2:
            kA = total_read(12)
            kB = total_read(3) + (SYS + TURN * 3) + (SYS + TURN * 4)
            stats_a = (
                f'<div style="margin-top:5px;font-size:11px;color:{MUTED}">'
                f"<b>{len(a)}</b> messages · "
                f'<b style="color:{DANGER}">{fmt(kA)}</b> words</div>'
            )
            stats_b = (
                f'<div style="margin-top:5px;font-size:11px;color:{MUTED}">'
                f"<b>{len(b)}</b> messages · "
                f'<b style="color:{ACCENT}">{fmt(kB)}</b> words</div>'
            )

        self._view.object = (
            f'<div style="font-family:{BODY};display:flex;gap:20px;'
            f'justify-content:center">'
            f'<div style="flex:1;max-width:300px">'
            f'<div style="font-size:9px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:.06em;color:{DANGER};margin-bottom:5px;'
            f'text-align:center">A — Keep correcting</div>'
            f'<div style="display:flex;flex-direction:column;gap:2px;'
            f'max-height:180px;overflow-y:auto">{"".join(a)}</div>{stats_a}</div>'
            f'<div style="width:1px;background:{HAIRLINE};align-self:stretch"></div>'
            f'<div style="flex:1;max-width:300px">'
            f'<div style="font-size:9px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:.06em;color:{ACCENT};margin-bottom:5px;'
            f'text-align:center">B — Edit the original</div>'
            f'<div style="display:flex;flex-direction:column;gap:2px;'
            f'max-height:180px;overflow-y:auto">{"".join(b)}</div>{stats_b}</div>'
            f'</div>'
        )

        labels = ["Run both", "See what happens", "Done"]
        self._btn.name = labels[s]
        self._btn.disabled = s >= 2

        if s >= 2:
            kA = total_read(12)
            kB = total_read(3) + (SYS + TURN * 3) + (SYS + TURN * 4)
            pct = round(100 * (1 - kB / kA))
            self._result.object = (
                f'<p style="text-align:center;font-family:{BODY};font-size:13px;'
                f'color:#1e40af;margin:6px 0"><b>{pct}% less work for the AI</b>'
                f" — and the wrong answer is gone, not buried.</p>"
            )
        else:
            self._result.object = ""

    def __panel__(self):
        return self._layout


# ═══════════════════════════════════════════════════════════════════
# Slide 6 — Three Things to Remember
# Bold-lead bullets: the bold phrase carries the point on its own.
# ═══════════════════════════════════════════════════════════════════


def _card(title, bullets):
    items = "".join(
        f'<div style="margin:2px 0"><b>{bold}</b> {rest}</div>' for bold, rest in bullets
    )
    return (
        f'<div style="background:#fafafa;border-radius:8px;padding:12px 16px;'
        f'text-align:left"><div style="font-size:14px;font-weight:600;'
        f'margin-bottom:4px">{title}</div>'
        f'<div style="font-size:12.5px;color:{MUTED};line-height:1.5">'
        f"{items}</div></div>"
    )


slide_takeaways = pn.Column(
    headline(
        "Three Things to Remember",
        "You don't need to understand the technology. Just keep these in mind.",
        label="Takeaways",
    ),
    pn.pane.HTML(
        f"""<div style="font-family:{BODY};display:flex;flex-direction:column;
gap:8px;max-width:600px;margin:0 auto">
{_card("1. Long chats get worse, not just longer", [
    ("The AI re-reads everything", "every time you send a message."),
    ("Responses slow down", "as the conversation grows."),
    ("Quality drops —", "important details get buried in the noise."),
])}
{_card("2. When it goes wrong, go back — don't pile on", [
    ("Find the message that caused it", "and use the pencil icon to rewrite."),
    ("Sending more corrections", "leaves the original mistake in place forever."),
    ("Editing removes the problem", "instead of arguing with it."),
])}
{_card("3. Fresh starts are free — use them", [
    ("Start a new chat", "when the topic changes or things feel off."),
    ("Copy any useful results first,", "then open a fresh conversation."),
    ("A clean slate", "means the AI focuses only on what matters now."),
])}
</div>""",
        sizing_mode="stretch_width",
    ),
)


# ═══════════════════════════════════════════════════════════════════
# Assemble
# ═══════════════════════════════════════════════════════════════════

slides = [
    slide_hook,
    pn.Column(
        headline(
            "Every Message Starts from Scratch",
            "There's no memory. Each time you press send, the AI "
            "receives <b>the entire conversation again</b>.",
            label="How it works",
        ),
        PayloadDemo(),
    ),
    pn.Column(
        headline(
            "The Longer You Go, the Worse It Gets",
            "Each new message re-reads <em>all</em> the previous ones. "
            "The total work <b>accelerates</b>.",
            label="The cost",
        ),
        CostCurve(),
        pn.pane.HTML(
            f'<p style="font-family:{BODY};text-align:center;font-size:12.5px;'
            f'color:{MUTED};margin:4px 0">'
            f'<b style="color:{INK}">Slower responses</b> · '
            f'<b style="color:{INK}">Lower quality</b> · '
            f'<b style="color:{INK}">Higher cost</b> — every message costs '
            f"more than the last</p>",
            sizing_mode="stretch_width",
        ),
    ),
    pn.Column(
        headline(
            "Mistakes Never Go Away",
            "When the AI guesses wrong, that wrong answer <b>stays "
            "forever</b>. Correcting it doesn't remove it.",
            label="The problem",
        ),
        MistakeDemo(),
    ),
    pn.Column(
        headline(
            "Go Back and Edit, Don't Keep Talking",
            "Most chat apps have a pencil icon next to your messages. "
            "<b>Go back to the message that caused the problem</b> "
            "and rewrite it.",
            label="The fix",
        ),
        FixComparison(),
    ),
    slide_takeaways,
]

pn.config.raw_css.append(f"""
#header {{ font-family: {BODY}; }}
""")

SlidesTemplate(
    title="An explorable guide to context",
    main=slides,
    reveal_config={
        "width": 1100,
        "height": 720,
        "hash": True,
        "margin": 0.04,
        "center": True,
    },
).servable()

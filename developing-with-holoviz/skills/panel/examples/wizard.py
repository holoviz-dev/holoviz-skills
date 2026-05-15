"""
Wizard/stepper layout example using panel-material-ui.

Multi-step wizard with one action per page, breadcrumb navigation, sidebar
menu, and a progress bar. Demonstrates Viewer class pattern, Placeholder
swapping, pn.io.hold() batching, shared disabled state, and pmui.Page template.

Run: panel serve examples/wizard.py --dev --show
"""

import panel as pn
import panel_material_ui as pmui
import param

pn.extension(throttled=True, defer_load=True, loading_indicator=True)

# Professional theme - refined indigo/teal palette
THEME_CONFIG = {
    "light": {
        "palette": {
            "primary": {"main": "#1e3a5f"},  # Deep navy blue
            "secondary": {"main": "#2e7d6f"},  # Teal accent
            "success": {"main": "#2e7d6f"},
        },
        "typography": {
            "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            "h4": {"fontWeight": 600, "letterSpacing": "-0.02em"},
            "h5": {"fontWeight": 600, "letterSpacing": "-0.01em"},
            "body1": {"lineHeight": 1.6},
        },
        "shape": {"borderRadius": 12},
        "components": {
            "MuiButton": {
                "styleOverrides": {
                    "root": {"textTransform": "none", "fontWeight": 600},
                },
            },
            "MuiPaper": {
                "styleOverrides": {
                    "root": {"boxShadow": "0 4px 20px rgba(0,0,0,0.08)"},
                },
            },
        },
    },
    "dark": {
        "palette": {
            "primary": {"main": "#5c8fc2"},
            "secondary": {"main": "#4db6a4"},
            "success": {"main": "#4db6a4"},
        },
        "typography": {
            "fontFamily": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
            "h4": {"fontWeight": 600, "letterSpacing": "-0.02em"},
            "h5": {"fontWeight": 600, "letterSpacing": "-0.01em"},
            "body1": {"lineHeight": 1.6},
        },
        "shape": {"borderRadius": 12},
        "components": {
            "MuiButton": {
                "styleOverrides": {
                    "root": {"textTransform": "none", "fontWeight": 600},
                },
            },
        },
    },
}


class WizardStep(pn.viewable.Viewer):
    """Base class for wizard steps."""

    complete = param.Boolean(default=False, doc="""
        Whether this step has valid data and can proceed.""")

    disabled = param.Boolean(default=False, doc="""
        Whether this step's widgets are disabled (e.g., after submit).""")

    icon = param.String(default="circle", doc="""
        Material icon name for breadcrumbs and sidebar.""")

    title = param.String(doc="""
        Display title for this step.""")

    def __panel__(self):
        raise NotImplementedError("Subclasses must implement __panel__")


class FilingStatusStep(WizardStep):
    """Step 1: Filing status selection."""

    complete = param.Boolean(default=True)

    filing_status = param.Selector(
        default="Single",
        objects=["Single", "Married filing jointly", "Married filing separately", "Head of household"],
        doc="""
        Your tax filing status.""",
    )

    icon = param.String(default="person")

    title = param.String(default="Filing Status")

    def __panel__(self):
        return pmui.Column(
            pmui.Typography("What is your filing status?", variant="h4", sx={"fontWeight": 700, "mb": 1}),
            pmui.Typography(
                "This determines your tax brackets and standard deduction.",
                sx={"color": "text.secondary", "mb": 4},
            ),
            pmui.RadioBoxGroup.from_param(
                self.param.filing_status,
                label="",  # Remove redundant label
                options=["Single", "Married filing jointly", "Married filing separately", "Head of household"],
                disabled=self.param.disabled,
            ),
            sizing_mode="stretch_width",
        )


class IncomeStep(WizardStep):
    """Step 2: Income input."""

    icon = param.String(default="attach_money")

    interest = param.Number(default=0, bounds=(0, None), doc="""
        Interest and dividend income from 1099 forms.""")

    title = param.String(default="Income")

    wages = param.Number(default=0, bounds=(0, None), doc="""
        W-2 wages from Box 1.""")

    @param.depends("wages", "interest", watch=True)
    def _on_income_change(self):
        self.complete = (self.wages + self.interest) > 0

    def __panel__(self):
        return pmui.Column(
            pmui.Typography("What did you earn this year?", variant="h4", sx={"fontWeight": 600, "mb": 1}),
            pmui.Typography(
                "Enter your total income from all sources. We'll use this to calculate your tax bracket.",
                sx={"color": "text.secondary", "mb": 4},
            ),
            pmui.Column(
                pmui.Typography("W-2 Wages", sx={"fontWeight": 500, "mb": 1}),
                pmui.FloatInput.from_param(self.param.wages, label="$ Wages", sizing_mode="stretch_width", disabled=self.param.disabled),
                pmui.Typography("From Box 1 of your W-2 form", sx={"color": "text.secondary", "fontSize": 13, "mt": 0.5}),
                sizing_mode="stretch_width",
                margin=(0, 0, 24, 0),
            ),
            pmui.Column(
                pmui.Typography("Interest & Dividends", sx={"fontWeight": 500, "mb": 1}),
                pmui.FloatInput.from_param(self.param.interest, label="$ Interest", sizing_mode="stretch_width", disabled=self.param.disabled),
                pmui.Typography("From 1099-INT and 1099-DIV forms", sx={"color": "text.secondary", "fontSize": 13, "mt": 0.5}),
                sizing_mode="stretch_width",
            ),
            sizing_mode="stretch_width",
        )


class DeductionsStep(WizardStep):
    """Step 3: Deductions."""

    complete = param.Boolean(default=True)

    deduction_type = param.Selector(
        default="Standard",
        objects=["Standard", "Itemized"],
        doc="""
        Standard or itemized deduction.""",
    )

    icon = param.String(default="receipt_long")

    itemized_amount = param.Number(default=0, bounds=(0, None), doc="""
        Total itemized deductions if not using standard.""")

    title = param.String(default="Deductions")

    def __init__(self, **params):
        self._itemized_input = pmui.FloatInput.from_param(
            self.param.itemized_amount,
            label="Itemized Amount ($)",
            sizing_mode="stretch_width",
            disabled=self.param.disabled,
        )
        self._standard_info = pmui.Paper(
            pmui.Typography(
                "Standard deduction: $14,600 (Single) / $29,200 (Married)",
                sx={"color": "text.secondary"},
            ),
            sx={"p": 2, "mt": 2, "backgroundColor": "rgba(0,0,0,0.02)"},
        )
        self._deduction_details = pn.pane.Placeholder(sizing_mode="stretch_width")
        super().__init__(**params)

    @param.depends("deduction_type", watch=True, on_init=True)
    def _update_deduction_details(self):
        if self.deduction_type == "Itemized":
            self._deduction_details.update(self._itemized_input)
        else:
            self._deduction_details.update(self._standard_info)

    def __panel__(self):
        return pmui.Column(
            pmui.Typography("Choose your deduction", variant="h4", sx={"fontWeight": 600, "mb": 1}),
            pmui.Typography(
                "Most filers benefit from the standard deduction.",
                sx={"color": "text.secondary", "mb": 4},
            ),
            pmui.RadioButtonGroup.from_param(self.param.deduction_type, disabled=self.param.disabled),
            self._deduction_details,
            sizing_mode="stretch_width",
        )


class ReviewStep(WizardStep):
    """Step 4: Review and submit."""

    complete = param.Boolean(default=True)

    icon = param.String(default="check_circle")

    title = param.String(default="Review")

    def __init__(self, steps, **params):
        super().__init__(**params)
        self._steps = steps

    def __panel__(self):
        filing = self._steps[0]
        income = self._steps[1]
        deductions = self._steps[2]

        total_income = income.wages + income.interest
        deduction_amount = 14600 if filing.filing_status == "Single" else 29200
        if deductions.deduction_type == "Itemized":
            deduction_amount = deductions.itemized_amount
        taxable = max(0, total_income - deduction_amount)

        return pmui.Column(
            pmui.Typography("Review your return", variant="h4", sx={"fontWeight": 600, "mb": 1}),
            pmui.Typography(
                "Please confirm your information before submitting.",
                sx={"color": "text.secondary", "mb": 3},
            ),
            pmui.Paper(
                pmui.Column(
                    pmui.Row(
                        pmui.Typography("Filing Status", sx={"color": "text.secondary", "minWidth": 140}),
                        pmui.Typography(filing.filing_status or "Not selected", sx={"fontWeight": 500}),
                    ),
                    pmui.Row(
                        pmui.Typography("W-2 Wages", sx={"color": "text.secondary", "minWidth": 140}),
                        pmui.Typography(f"${income.wages:,.2f}", sx={"fontWeight": 500}),
                    ),
                    pmui.Row(
                        pmui.Typography("Interest Income", sx={"color": "text.secondary", "minWidth": 140}),
                        pmui.Typography(f"${income.interest:,.2f}", sx={"fontWeight": 500}),
                    ),
                    pmui.Row(
                        pmui.Typography("Deduction", sx={"color": "text.secondary", "minWidth": 140}),
                        pmui.Typography(f"{deductions.deduction_type} (${deduction_amount:,.0f})", sx={"fontWeight": 500}),
                    ),
                    pn.layout.Divider(margin=(16, 0)),
                    pmui.Row(
                        pmui.Typography("Taxable Income", sx={"fontWeight": 600, "minWidth": 140}),
                        pmui.Typography(f"${taxable:,.2f}", sx={"fontWeight": 600, "color": "primary.main"}),
                    ),
                    sizing_mode="stretch_width",
                ),
                sx={"p": 3},
            ),
            sizing_mode="stretch_width",
        )


class TaxWizard(pn.viewable.Viewer):
    """TurboTax-style wizard with one action per page."""

    active_step = param.Integer(default=0, bounds=(0, None), doc="""
        Current step index (0-based).""")

    submitted = param.Boolean(default=False, doc="""
        Whether the wizard has been submitted.""")

    def __init__(self, **params):
        # Step instances
        self._filing_step = FilingStatusStep()
        self._income_step = IncomeStep()
        self._deductions_step = DeductionsStep()
        self._review_step = ReviewStep(
            steps=[self._filing_step, self._income_step, self._deductions_step]
        )
        self._steps = [
            self._filing_step,
            self._income_step,
            self._deductions_step,
            self._review_step,
        ]

        # Components
        self._breadcrumb_items = [
            {"label": step.title, "icon": step.icon, "view": step}
            for step in self._steps
        ]
        self._breadcrumbs = pmui.Breadcrumbs(
            items=self._breadcrumb_items,
            active=0,
            color="primary",
            separator="›",
            sizing_mode="stretch_width",
        )
        self._back_btn = pmui.Button(
            label="Back",
            icon="arrow_back",
            variant="outlined",
            visible=False,
        )
        self._next_btn = pmui.Button(
            label="Continue",
            icon="arrow_forward",
            variant="contained",
            color="primary",
        )
        self._content = pn.pane.Placeholder(sizing_mode="stretch_width", min_height=450, margin=20)
        self._progress_bar = pmui.LinearProgress(
            value=25,
            sizing_mode="stretch_width",
            margin=(12, 0, 0, 0),
            sx={
                "height": 4,
                "borderRadius": 2,
                "backgroundColor": "rgba(0,0,0,0.08)",
            },
        )
        self._nav_menu = pmui.MenuList(
            items=[{"label": step.title, "icon": step.icon} for step in self._steps],
            active=0,
            color="primary",
            highlight=True,
        )
        self._nav_row = pmui.Row(
            self._back_btn,
            pn.layout.HSpacer(),
            self._next_btn,
            sizing_mode="stretch_width",
        )
        self._step_text = pmui.Typography(
            f"Step 1 of {len(self._steps)}",
            sx={"color": "primary.contrastText"},
        )

        # Wire up events and syncs
        self._breadcrumbs.on_click(self._on_breadcrumb_click)
        self._back_btn.on_click(self._on_back)
        self._next_btn.on_click(self._on_advance)
        self._nav_menu.param.watch(self._on_menu_select, "active")
        for step in self._steps:
            step.param.watch(self._update_button_state, "complete")

        super().__init__(**params)

    def _on_menu_select(self, event):
        active = event.new
        if active and active[0] != self.active_step:
            self.active_step = active[0]

    def _on_breadcrumb_click(self, event):
        clicked_label = event.get("label") if isinstance(event, dict) else getattr(event, "label", None)
        if not clicked_label:
            return
        for i, item in enumerate(self._breadcrumb_items):
            if item["label"] == clicked_label:
                self.active_step = i
                return

    def _on_back(self, event=None):
        if self.active_step > 0:
            self.active_step = self.active_step - 1

    def _on_advance(self, event=None):
        if self.active_step < len(self._steps) - 1:
            self.active_step = self.active_step + 1
        else:
            self._submit()

    def _submit(self):
        self.submitted = True
        self._content.update(
            pmui.Column(
                pmui.Typography("Your return has been submitted!", variant="h4", sx={"fontWeight": 700, "mb": 2}),
                pmui.Typography(
                    "Thank you for using Tax Wizard. You will receive a confirmation email shortly.",
                    sx={"color": "text.secondary"},
                ),
                sizing_mode="stretch_width",
            )
        )
        with pn.io.hold():
            self._next_btn.visible = False
            self._back_btn.visible = False
            self._breadcrumbs.visible = False
            for step in self._steps:
                step.disabled = True

    def _update_button_state(self, *args):
        current_step = self._steps[self.active_step]
        self._next_btn.disabled = not current_step.complete

    @param.depends("active_step", watch=True, on_init=True)
    def _update_view(self):
        with pn.io.hold():
            self._breadcrumbs.active = self.active_step

            current_step = self._steps[self.active_step]
            is_first = self.active_step == 0
            is_last = self.active_step == len(self._steps) - 1

            self._back_btn.visible = not is_first and not self.submitted
            self._next_btn.label = "Submit" if is_last else "Continue"
            self._next_btn.disabled = not current_step.complete

            self._content.update(current_step)
            self._nav_menu.active = (self.active_step,)
            self._progress_bar.value = int(((self.active_step + 1) / len(self._steps)) * 100)
            self._step_text.object = f"Step {self.active_step + 1} of {len(self._steps)}"

    def __panel__(self):
        if pn.state.served:
            return pmui.Page(
                title="Tax Wizard",
                header=[self._step_text],
                sidebar=[
                    pmui.Typography("Steps", variant="h6", sx={"mb": 1}),
                    pmui.Column(self._nav_menu, sizing_mode="stretch_width"),
                    pn.layout.Divider(margin=(20, 0)),
                    pmui.Typography("Need Help?", variant="h6", sx={"mb": 1}),
                    pmui.Typography(
                        "Have questions about filing? Visit our FAQ or contact support.",
                        sx={"color": "text.secondary", "fontSize": 13},
                    ),
                    pmui.Button(
                        label="View FAQ",
                        icon="help_outline",
                        variant="outlined",
                        sizing_mode="stretch_width",
                        margin=(15, 10, 0, 10),
                    ),
                ],
                sidebar_width=280,
                theme_config=THEME_CONFIG,
                main=[
                    pmui.Container(
                        pmui.Column(
                            self._breadcrumbs,
                            self._progress_bar,
                            pmui.Paper(
                                pmui.Column(
                                    self._content,
                                    self._nav_row,
                                    sizing_mode="stretch_width",
                                    margin=(0, 0, 30, 0),
                                ),
                                sx={"p": 5, "mt": 2},
                                sizing_mode="stretch_width",
                            ),
                            sizing_mode="stretch_width",
                            margin=(40, 0, 0, 0),
                        ),
                        width_option="md",
                    )
                ],
            )
        return pmui.Column(self._breadcrumbs, self._content, self._nav_row)


TaxWizard().servable()

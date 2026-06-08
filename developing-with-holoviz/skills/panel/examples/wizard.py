"""
Wizard/stepper layout example using panel-material-ui.

Multi-step wizard with one action per page, driven by a `pmui.StepperMenu`
that shows live step state (completed / error / active), supports non-linear
navigation, and reports position via its `active` parameter. Also demonstrates
the Viewer class pattern, `pn.pane.Placeholder` step swapping, `pn.io.hold()`
batching, shared `disabled` state, inline `pmui.Alert` validation, a
`pmui.Tooltip`, and the `pmui.Page` template.

Run: panel serve examples/wizard.py --dev --show
"""

import panel as pn
import panel_material_ui as pmui
import param

pn.extension(throttled=True)

# Professional theme - refined navy/teal palette
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

    complete = param.Boolean(
        default=False,
        doc="""
        Whether this step has valid data and can proceed.""",
    )

    disabled = param.Boolean(
        default=False,
        doc="""
        Whether this step's widgets are disabled (e.g., after submit).""",
    )

    icon = param.String(
        default="circle",
        doc="""
        Material icon name for the stepper.""",
    )

    title = param.String(
        doc="""
        Display title for this step."""
    )

    def __panel__(self):
        raise NotImplementedError("Subclasses must implement __panel__")


class FilingStatusStep(WizardStep):
    """Step 1: Filing status selection."""

    complete = param.Boolean(default=True)

    filing_status = param.Selector(
        default="Single",
        objects=[
            "Single",
            "Married filing jointly",
            "Married filing separately",
            "Head of household",
        ],
        doc="""
        Your tax filing status.""",
    )

    icon = param.String(default="person")

    title = param.String(default="Filing Status")

    def __panel__(self):
        return pmui.Column(
            pmui.Typography(
                "What is your filing status?", variant="h4", sx={"fontWeight": 700, "mb": 1}
            ),
            pmui.Typography(
                "This determines your tax brackets and standard deduction.",
                sx={"color": "text.secondary", "mb": 4},
            ),
            pmui.RadioBoxGroup.from_param(
                self.param.filing_status,
                label="",  # Remove redundant label
                options=[
                    "Single",
                    "Married filing jointly",
                    "Married filing separately",
                    "Head of household",
                ],
                disabled=self.param.disabled,
            ),
            sizing_mode="stretch_width",
        )


class IncomeStep(WizardStep):
    """Step 2: Income input."""

    icon = param.String(default="attach_money")

    interest = param.Number(
        default=0,
        bounds=(0, None),
        doc="""
        Interest and dividend income from 1099 forms.""",
    )

    title = param.String(default="Income")

    wages = param.Number(
        default=0,
        bounds=(0, None),
        doc="""
        W-2 wages from Box 1.""",
    )

    @param.depends("wages", "interest", watch=True)
    def _on_income_change(self):
        self.complete = (self.wages + self.interest) > 0

    def __panel__(self):
        return pmui.Column(
            pmui.Typography(
                "What did you earn this year?", variant="h4", sx={"fontWeight": 600, "mb": 1}
            ),
            pmui.Typography(
                "Enter your total income from all sources. "
                "We'll use this to calculate your tax bracket.",
                sx={"color": "text.secondary", "mb": 4},
            ),
            pmui.Column(
                pmui.Typography("W-2 Wages", sx={"fontWeight": 500, "mb": 1}),
                pmui.FloatInput.from_param(
                    self.param.wages,
                    label="$ Wages",
                    sizing_mode="stretch_width",
                    disabled=self.param.disabled,
                ),
                pmui.Typography(
                    "From Box 1 of your W-2 form",
                    sx={"color": "text.secondary", "fontSize": 13, "mt": 0.5},
                ),
                sizing_mode="stretch_width",
                margin=(0, 0, 24, 0),
            ),
            pmui.Column(
                pmui.Typography("Interest & Dividends", sx={"fontWeight": 500, "mb": 1}),
                pmui.FloatInput.from_param(
                    self.param.interest,
                    label="$ Interest",
                    sizing_mode="stretch_width",
                    disabled=self.param.disabled,
                ),
                pmui.Typography(
                    "From 1099-INT and 1099-DIV forms",
                    sx={"color": "text.secondary", "fontSize": 13, "mt": 0.5},
                ),
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

    itemized_amount = param.Number(
        default=0,
        bounds=(0, None),
        doc="""
        Total itemized deductions if not using standard.""",
    )

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
            pmui.RadioButtonGroup.from_param(
                self.param.deduction_type, disabled=self.param.disabled
            ),
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
                        pmui.Typography(
                            "Filing Status", sx={"color": "text.secondary", "minWidth": 140}
                        ),
                        pmui.Typography(
                            filing.filing_status or "Not selected", sx={"fontWeight": 500}
                        ),
                    ),
                    pmui.Row(
                        pmui.Typography(
                            "W-2 Wages", sx={"color": "text.secondary", "minWidth": 140}
                        ),
                        pmui.Typography(f"${income.wages:,.2f}", sx={"fontWeight": 500}),
                    ),
                    pmui.Row(
                        pmui.Typography(
                            "Interest Income", sx={"color": "text.secondary", "minWidth": 140}
                        ),
                        pmui.Typography(f"${income.interest:,.2f}", sx={"fontWeight": 500}),
                    ),
                    pmui.Row(
                        pmui.Typography(
                            "Deduction", sx={"color": "text.secondary", "minWidth": 140}
                        ),
                        pmui.Typography(
                            f"{deductions.deduction_type} (${deduction_amount:,.0f})",
                            sx={"fontWeight": 500},
                        ),
                    ),
                    pn.layout.Divider(margin=(16, 0)),
                    pmui.Row(
                        pmui.Typography("Taxable Income", sx={"fontWeight": 600, "minWidth": 140}),
                        pmui.Typography(
                            f"${taxable:,.2f}", sx={"fontWeight": 600, "color": "primary.main"}
                        ),
                    ),
                    sizing_mode="stretch_width",
                ),
                sx={"p": 3},
            ),
            sizing_mode="stretch_width",
        )


class TaxWizard(pn.viewable.Viewer):
    """TurboTax-style wizard with one action per page, driven by StepperMenu."""

    active_step = param.Integer(
        default=0,
        bounds=(0, None),
        doc="""
        Current step index (0-based).""",
    )

    submitted = param.Boolean(
        default=False,
        doc="""
        Whether the wizard has been submitted.""",
    )

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
        self._visited = {0}

        # StepperMenu replaces the old Breadcrumbs + sidebar MenuList +
        # LinearProgress — it conveys order, progress, and per-step state in
        # one component. non_linear=True lets users click a step to jump to it.
        self._stepper = pmui.StepperMenu(
            items=self._build_items(),
            active=0,
            non_linear=True,
            alternative_label=True,
            color="primary",
            sizing_mode="stretch_width",
            margin=(0, 0, 8, 0),
        )

        # Inline validation banner shown when the current step is incomplete.
        self._alert = pmui.Alert(
            object="",
            severity="warning",
            variant="outlined",
            visible=False,
            sizing_mode="stretch_width",
            margin=(0, 0, 16, 0),
        )

        # Navigation
        self._back_btn = pmui.Button(
            label="Back", icon="arrow_back", variant="outlined", visible=False
        )
        self._next_btn = pmui.Button(
            label="Continue", icon="arrow_forward", variant="contained", color="primary"
        )
        self._nav_row = pmui.Row(
            self._back_btn, pn.layout.HSpacer(), self._next_btn, sizing_mode="stretch_width"
        )
        self._content = pn.pane.Placeholder(sizing_mode="stretch_width", min_height=420, margin=20)
        self._step_text = pmui.Typography(
            f"Step 1 of {len(self._steps)}", sx={"color": "primary.contrastText"}
        )

        # Wire up events and syncs
        self._stepper.param.watch(self._on_stepper, "active")
        self._back_btn.on_click(self._on_back)
        self._next_btn.on_click(self._on_advance)
        for step in self._steps:
            step.param.watch(self._refresh_state, "complete")

        super().__init__(**params)

    # -- Stepper items reflect live completion / error state --

    def _build_items(self):
        items = []
        for i, step in enumerate(self._steps):
            item = {"label": step.title, "icon": step.icon, "tooltip": step.title}
            # The active step keeps the active highlight (no flag). Only steps
            # the user has actually visited and left get a completed/error flag;
            # unvisited future steps stay pending/grey. `step.complete` means
            # "has valid data" — not "the user has finished this step" — so it
            # must be gated on visitation or every default-valid step would
            # render in the completed color and the active step wouldn't stand out.
            if i != self.active_step and i in self._visited:
                if step.complete:
                    item["completed"] = True
                else:
                    item["error"] = True
            items.append(item)
        return items

    # -- Navigation handlers --

    def _on_stepper(self, event):
        if event.new is None or event.new == self.active_step:
            return
        self.active_step = event.new

    def _on_back(self, event=None):
        if self.active_step > 0:
            self.active_step -= 1

    def _on_advance(self, event=None):
        if self.active_step < len(self._steps) - 1:
            self.active_step += 1
        else:
            self._submit()

    def _submit(self):
        self.submitted = True
        with pn.io.hold():
            for step in self._steps:
                step.disabled = True
            self._stepper.items = [
                {"label": s.title, "icon": s.icon, "completed": True} for s in self._steps
            ]
            self._next_btn.visible = False
            self._back_btn.visible = False
            self._alert.visible = False
            self._content.update(
                pmui.Column(
                    pmui.Typography(
                        "Your return has been submitted!",
                        variant="h4",
                        sx={"fontWeight": 700, "mb": 2},
                    ),
                    pmui.Typography(
                        "Thank you for using Tax Wizard. You will receive a confirmation shortly.",
                        sx={"color": "text.secondary"},
                    ),
                    sizing_mode="stretch_width",
                )
            )

    # -- State sync --

    def _refresh_state(self, *events):
        with pn.io.hold():
            self._stepper.items = self._build_items()
            self._update_controls()

    def _update_controls(self):
        current = self._steps[self.active_step]
        is_first = self.active_step == 0
        is_last = self.active_step == len(self._steps) - 1
        self._back_btn.visible = not is_first and not self.submitted
        self._next_btn.label = "Submit" if is_last else "Continue"
        self._next_btn.disabled = not current.complete
        if not current.complete and not self.submitted:
            self._alert.object = "Complete this step before continuing."
            self._alert.visible = True
        else:
            self._alert.visible = False
        self._step_text.object = f"Step {self.active_step + 1} of {len(self._steps)}"

    @param.depends("active_step", watch=True, on_init=True)
    def _update_view(self):
        with pn.io.hold():
            self._visited.add(self.active_step)
            if self._stepper.active != self.active_step:
                self._stepper.active = self.active_step
            self._stepper.items = self._build_items()
            self._content.update(self._steps[self.active_step])
            self._update_controls()

    def __panel__(self):
        if pn.state.served:
            return pmui.Page(
                title="Tax Wizard",
                header=[self._step_text],
                sidebar=[
                    pmui.Typography("Need Help?", variant="h6", sx={"mb": 1}),
                    pmui.Typography(
                        "Have questions about filing? Visit our FAQ or contact support.",
                        sx={"color": "text.secondary", "fontSize": 13},
                    ),
                    pmui.Tooltip(
                        pmui.Button(
                            label="View FAQ",
                            icon="help_outline",
                            variant="outlined",
                            sizing_mode="stretch_width",
                            margin=(15, 10, 0, 10),
                        ),
                        title="Browse frequently asked questions about filing",
                    ),
                ],
                sidebar_width=280,
                theme_config=THEME_CONFIG,
                main=[
                    pmui.Container(
                        pmui.Column(
                            self._stepper,
                            pmui.Paper(
                                pmui.Column(
                                    self._alert,
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
        return pmui.Column(self._stepper, self._alert, self._content, self._nav_row)


TaxWizard().servable()

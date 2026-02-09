from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Button, Input, Label, Static

from bagels.config import CONFIG, write_state
from bagels.managers.currency import get_main_currency
from bagels.managers.utils import (
    dynamic_cache,
    get_income_to_use,
    get_period_figures,
    try_method_query_one,
)
from bagels.models.category import Nature
from bagels.utils.money import format_amount


class Budgets(Static):
    can_focus = True

    def __init__(self, page_parent, *args, **kwargs) -> None:
        super().__init__(
            *args, **kwargs, id="budgets-container", classes="module-container"
        )
        super().__setattr__("border_title", "Budgeting")
        self.page_parent = page_parent

    # --------------- Hooks -------------- #

    def on_mount(self) -> None:
        self.rebuild()

    def _write_state(self, key: str, value: str, typing=None) -> bool:
        current_value = CONFIG.state
        for part in key.split("."):
            current_value = getattr(current_value, part)
        if value != "":
            typed_val = value
            if typing:
                typed_val = typing(value)
            if current_value != typed_val:
                write_state(key, typed_val)
            return True
        return False

    def on_input_changed(self, event: Input.Changed) -> None:
        updated = False
        if event.input.id == "savings-input":
            if self.savings_assess_metric.startswith("percentage"):
                updated = self._write_state(
                    "budgeting.savings_percentage", event.value, float
                )
            else:
                updated = self._write_state(
                    "budgeting.savings_amount", event.value, float
                )

        elif event.input.id == "wants-input":
            if self.wants_spending_assess_metric.startswith("percentage"):
                updated = self._write_state(
                    "budgeting.wants_spending_percentage", event.value, float
                )
            else:
                updated = self._write_state(
                    "budgeting.wants_spending_amount", event.value, float
                )
        if updated:
            self.rebuild()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id.startswith("savings-"):
            metric = event.button.id.replace("savings-", "")
            self._write_state("budgeting.savings_assess_metric", metric)
        elif event.button.id.startswith("wants-"):
            metric = event.button.id.replace("wants-", "")
            self._write_state("budgeting.wants_spending_assess_metric", metric)
        self.rebuild()

    # region Builders
    # ------------- Builders ------------- #

    def rebuild(self) -> None:
        self.savings_assess_metric = CONFIG.state.budgeting.savings_assess_metric
        try_method_query_one(self, "#savings-row > .selected", "set_classes", [""])
        try_method_query_one(
            self, f"#savings-{self.savings_assess_metric}", "set_classes", ["selected"]
        )
        restrict_percentage = r"0\.([0-9]){0,2}"
        restrict_amount = r"\d*\.?\d{0,2}"
        input = self.query_one("#savings-input")
        if self.savings_assess_metric.startswith("percentage"):
            input.value = str(CONFIG.state.budgeting.savings_percentage)
            input.restrict = restrict_percentage
        else:
            input.value = str(CONFIG.state.budgeting.savings_amount)
            input.restrict = restrict_amount

        self.wants_spending_assess_metric = (
            CONFIG.state.budgeting.wants_spending_assess_metric
        )
        input = self.query_one("#wants-input")
        try_method_query_one(self, "#wants-row > .selected", "set_classes", [""])
        try_method_query_one(
            self,
            f"#wants-{self.wants_spending_assess_metric}",
            "set_classes",
            ["selected"],
        )
        if self.wants_spending_assess_metric.startswith("percentage"):
            input.value = str(CONFIG.state.budgeting.wants_spending_percentage)
            input.restrict = restrict_percentage
        else:
            input.value = str(CONFIG.state.budgeting.wants_spending_amount)
            input.restrict = restrict_amount
        self._rebuild_income_bar()

    def _rebuild_income_bar(self) -> None:
        offset = self.page_parent.offset
        main_currency = get_main_currency()
        net_income = dynamic_cache(get_income_to_use, offset)
        net_expenses = dynamic_cache(
            get_period_figures, isIncome=False, offset=offset, offset_type="month"
        )
        amount_to_save = round(
            net_income * CONFIG.state.budgeting.savings_percentage
            if self.savings_assess_metric.startswith("percentage")
            else CONFIG.state.budgeting.savings_amount,
            CONFIG.defaults.round_decimals,
        )
        want_quota = round(
            (net_income - amount_to_save)
            * CONFIG.state.budgeting.wants_spending_percentage
            if self.wants_spending_assess_metric.startswith("percentage")
            else CONFIG.state.budgeting.wants_spending_amount,
            CONFIG.defaults.round_decimals,
        )
        expenses_must = round(
            dynamic_cache(
                get_period_figures,
                isIncome=False,
                offset=offset,
                offset_type="month",
                nature=Nature.MUST,
            ),
            CONFIG.defaults.round_decimals,
        )
        expenses_need = round(
            dynamic_cache(
                get_period_figures,
                isIncome=False,
                offset=offset,
                offset_type="month",
                nature=Nature.NEED,
            ),
            CONFIG.defaults.round_decimals,
        )
        expenses_want = round(
            net_expenses - expenses_must - expenses_need,
            CONFIG.defaults.round_decimals,
        )

        self.app.log(
            f"Data: net_income={net_income}, net_expenses={net_expenses}, amount_to_save={amount_to_save}, expenses_must={expenses_must}, expenses_need={expenses_need}, expenses_want={expenses_want}"
        )

        income_bar_container = self.query_one("#income-bar")
        empty_bar = self.query_one(".empty-bar")

        income_bar_container.display = not not net_income
        empty_bar.display = not net_income

        if not net_income:
            return

        row1 = income_bar_container.query_one("#row-1")
        p_expenses = round(net_expenses / net_income * 100)
        p_saving = round(amount_to_save / net_income * 100)
        row1_columns = f"{p_expenses}% {p_saving}% 1fr"
        self.app.log(row1_columns)
        row1.styles.grid_columns = row1_columns

        row2 = income_bar_container.query_one("#row-2")
        row2.styles.grid_columns = f"{p_expenses}% 1fr"

        label_spent_amount = income_bar_container.query_one("#label-spent-amount")
        label_spent_amount.update(format_amount(net_expenses, main_currency))
        label_save_amount = income_bar_container.query_one("#label-save-amount")
        label_save_amount.update(format_amount(amount_to_save, main_currency))
        label_remaining_amount = income_bar_container.query_one(
            "#label-remaining-amount"
        )
        remaining = round(
            net_income - net_expenses - amount_to_save, CONFIG.defaults.round_decimals
        )
        label_remaining_amount.update(format_amount(remaining, main_currency))

        row3 = income_bar_container.query_one("#row-3")
        row3.display = not not net_expenses  # only display if there are expenses

        row4 = income_bar_container.query_one("#row-4")
        row4.display = not not net_expenses

        row5 = income_bar_container.query_one("#row-5")
        row5.display = not not net_expenses

        if not not net_expenses:
            p_tospend = round(100 - p_saving)
            row3.styles.width = f"{p_tospend}%"

            p_quota = round(100 - p_saving - p_expenses)
            p_must = round(expenses_must / net_expenses * p_expenses)
            p_need = round(expenses_need / net_expenses * p_expenses)
            p_want = round(expenses_want / net_expenses * p_expenses)
            row4_columns = f"{p_must}% {p_need}% {p_quota}% {p_want}% 1fr"
            self.app.log(row4_columns)
            row4.styles.grid_columns = row4_columns

            row3.styles.grid_columns = f"{p_must}% {p_need}% 1fr"
            label_spent_must_amount = row3.query_one("#label-spent-must-amount")
            label_spent_must_amount.update(format_amount(expenses_must, main_currency))
            label_spent_need_amount = row3.query_one("#label-spent-need-amount")
            label_spent_need_amount.update(format_amount(expenses_need, main_currency))
            label_spent_want_amount = row3.query_one("#label-want-remaining-amount")
            label_spent_want_amount.update(
                f"{format_amount(expenses_want, main_currency)} / {format_amount(want_quota, main_currency)}"
            )

            row5.styles.width = f"{p_tospend}%"
            bar_want_quota = row5.query_one("#bar-must-quota")
            p_want_quota = round(want_quota / (net_income - amount_to_save) * 100)
            bar_want_quota.styles.width = f"{p_want_quota}%"

    # region View
    # --------------- View --------------- #
    def compose(self) -> ComposeResult:
        with Horizontal(id="savings-row", classes="config-rows"):
            yield Label("Savings: ", id="savings-label")
            yield Button(
                "% Period Income",
                tooltip="Save a percentage of this period's income. Will temporarily use last period's value if income not yet recorded this period. Will use fallback value otherwise.\n\nValue: \"percentagePeriodIncome\"",
                id="savings-percentagePeriodIncome",
            )
            yield Button(
                "Set amount",
                tooltip='Save a set amount each period.\n\nValue: "setAmount"',
                id="savings-setAmount",
            )
            yield Input(placeholder="0.0", id="savings-input")
        with Horizontal(id="wants-row", classes="config-rows"):
            yield Label("Wants: ", id="wants-label")
            yield Button(
                "% Quota",
                tooltip='Limit spending on WANTs each period by a percentage of the amount left after savings.\n\nValue: "percentage"',
                id="wants-percentageQuota",
            )
            yield Button(
                "Set amount",
                tooltip='Limit spending on WANTs each period by a set amount.\n\nValue: "setAmount"',
                id="wants-setAmount",
            )
            yield Input(
                placeholder="0.0",
                id="wants-input",
            )
        with Container(id="income-bar"):
            with Container(id="row-0"):
                with Horizontal():
                    yield Label("╭ Spent: ")
                    yield Label("0.0", id="label-spent-amount")
                with Horizontal(id="remaining"):
                    yield Label("Remaining: ")
                    yield Label("0.0", id="label-remaining-amount")
                    yield Label(" ╮")
            with Container(id="row-1"):
                yield Static(id="bar-spent")
                yield Static(id="bar-saving")
                yield Static(id="bar-remaining")
            with Container(id="row-2"):
                yield Static()
                with Horizontal():
                    yield Label("╰ Save: ")
                    yield Label("0.0", id="label-save-amount")
            with Container(id="row-3"):
                with Horizontal():
                    yield Label("╭ Must: ")
                    yield Label("0.0", id="label-spent-must-amount")
                with Horizontal():
                    yield Label("╭ Need: ")
                    yield Label("0.0", id="label-spent-need-amount")
                with Horizontal(id="want"):
                    yield Label("Want: ")
                    yield Label("(0.0 / 0.0)", id="label-want-remaining-amount")
                    yield Label(" ╮")
            with Container(id="row-4"):
                yield Static(id="bar-spent-must")
                yield Static(id="bar-spent-need")
                yield Static(id="bar-spent-quota")
                yield Static(id="bar-spent-want")
                yield Label("Saved")
            with Container(id="row-5"):
                yield Static(id="bar-must-quota")
        with Container(classes="empty-bar"):
            yield Label("Nothing to display. Budgeting depends on your income!")

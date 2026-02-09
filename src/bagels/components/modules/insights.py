from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.widgets import Label, Static

from bagels.components.percentage_bar import PercentageBar, PercentageBarItem
from bagels.config import CONFIG
from bagels.managers.accounts import get_account_by_id
from bagels.managers.categories import get_all_categories_records
from bagels.managers.currency import get_main_currency
from bagels.managers.utils import (
    get_period_average,
    get_period_figures,
)
from bagels.utils.money import format_amount


class Insights(Static):
    can_focus = True

    def __init__(self, parent: Static, *args, **kwargs) -> None:
        super().__init__(
            *args, **kwargs, id="insights-container", classes="module-container"
        )
        super().__setattr__("border_title", "Insights")
        super().__setattr__("border_subtitle", CONFIG.hotkeys.home.toggle_use_account)
        self.page_parent = parent

    def on_mount(self) -> None:
        self.rebuild()

    # region Builder
    # -------------- Builder ------------- #

    def rebuild(self) -> None:
        self.use_account = self.page_parent.filter["byAccount"]
        period_net = self._update_labels()
        items = self.get_percentage_bar_items(period_net)
        self.percentage_bar.set_total(period_net, False)
        self.percentage_bar.set_items(items)
        # data = self.get_period_barchart_data()
        # self.period_barchart.set_data(data)

    def _update_labels(self) -> None:
        current_filter_label = self.query_one(".current-filter-label")
        period_net_label = self.query_one(".period-net")
        period_average_label = self.query_one(".period-average")
        average_label = self.query_one(".average-label")

        mode_isIncome = self.page_parent.mode["isIncome"]
        label = "Income" if mode_isIncome else "Expense"
        display_currency = get_main_currency()
        if self.use_account and self.page_parent.mode["accountId"]["default_value"] is not None:
            account = get_account_by_id(self.page_parent.mode["accountId"]["default_value"])
            if account is not None:
                display_currency = account.currencyCode

        if self.use_account:
            current_filter_label.update(
                f"{self.page_parent.mode['accountId']['default_value_text']} {label} of {self.page_parent.get_filter_label()}"
            )
        else:
            current_filter_label.update(
                f"{label} of {self.page_parent.get_filter_label()}"
            )
        average_label.update(f"{label} per day")

        if self.use_account:
            params = {
                "offset": self.page_parent.filter["offset"],
                "offset_type": self.page_parent.filter["offset_type"],
                "accountId": self.page_parent.mode["accountId"]["default_value"],
                "isIncome": mode_isIncome,
            }
        else:
            params = {
                "offset": self.page_parent.filter["offset"],
                "offset_type": self.page_parent.filter["offset_type"],
                "isIncome": mode_isIncome,
            }

        period_net = get_period_figures(**params)
        period_average = get_period_average(
            period_net,
            offset=self.page_parent.filter["offset"],
            offset_type=self.page_parent.filter["offset_type"],
        )
        period_net_label.update(format_amount(period_net, display_currency))
        period_average_label.update(format_amount(period_average, display_currency))

        return period_net

    def get_percentage_bar_items(
        self, period_net=1, limit: int = 5
    ) -> list[PercentageBarItem]:
        if period_net == 0:
            return []
        if self.use_account:
            category_records = get_all_categories_records(
                offset=self.page_parent.filter["offset"],
                offset_type=self.page_parent.filter["offset_type"],
                is_income=self.page_parent.mode["isIncome"],
                account_id=self.page_parent.mode["accountId"]["default_value"],
            )
        else:
            category_records = get_all_categories_records(
                offset=self.page_parent.filter["offset"],
                offset_type=self.page_parent.filter["offset_type"],
                is_income=self.page_parent.mode["isIncome"],
            )

        # Sort categories by percentage in descending order
        items = []
        if len(category_records) <= limit:
            # If we have 5 or fewer categories, show them all
            for category in category_records:
                items.append(
                    PercentageBarItem(
                        name=category.name,
                        count=int(category.amount),
                        color=category.color,
                    )
                )
        else:
            # Show top 4 categories and group the rest as "Others"
            for category in category_records[:limit]:
                items.append(
                    PercentageBarItem(
                        name=category.name,
                        count=int(category.amount),
                        color=category.color,
                    )
                )

            # Sum up the amounts of remaining categories
            others_amount = int(sum(cat.amount for cat in category_records[limit:]))
            items.append(
                PercentageBarItem(name="Others", count=others_amount, color="white")
            )

        return items

    # def get_period_barchart_data(self) -> BarchartData:
    #     offset_type = self.page_parent.filter["offset_type"]
    #     offset = self.page_parent.filter["offset"]
    #     if offset_type == "day":
    #         return BarchartData(amounts=[], labels=[])

    #     # Get data for each sub-period
    #     amounts = []
    #     labels = []

    #     match offset_type:
    #         case "year":
    #             # Get start of the target year
    #             start_date = datetime.now().replace(
    #                 month=1, day=1, year=datetime.now().year + offset
    #             )
    #             for i in range(12):
    #                 # Calculate month offset relative to today
    #                 target_date = start_date.replace(month=i + 1)
    #                 month_offset = (target_date.year - datetime.now().year) * 12 + (
    #                     target_date.month - datetime.now().month
    #                 )

    #                 amount = get_period_figures(
    #                     offset_type="month",
    #                     offset=month_offset,
    #                     isIncome=self.page_parent.mode["isIncome"],
    #                 )
    #                 amounts.append(abs(amount))
    #                 labels.append(target_date.strftime("%b"))
    #         case "week":
    #             start_date, end_date = get_start_end_of_period(offset, offset_type)

    #             for i in range(7):
    #                 current_date = start_date + timedelta(days=i)
    #                 day_offset = (current_date - datetime.now()).days + 1

    #                 amount = get_period_figures(
    #                     offset_type="day",
    #                     offset=day_offset,
    #                     isIncome=self.page_parent.mode["isIncome"],
    #                 )
    #                 amounts.append(abs(amount))
    #                 labels.append(current_date.strftime("%d"))

    #     return BarchartData(amounts=amounts, labels=labels)

    # region View
    # --------------- View --------------- #

    def compose(self) -> ComposeResult:
        with Horizontal(classes="figures-container"):
            with Container(classes="net container"):
                yield Label(classes="current-filter-label title")  # dynamic
                yield Label("Loading...", classes="period-net amount")  # dynamic
            with Container(classes="average container"):
                yield Label("<> per day", classes="average-label title")  # dynamic
                yield Label("Loading...", classes="period-average amount")  # dynamic

        self.percentage_bar = PercentageBar()
        # self.period_barchart = Barchart()
        yield self.percentage_bar
        # yield self.period_barchart

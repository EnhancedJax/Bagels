from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Center, Container
from textual.widgets import Static

from bagels.components.bagel import Bagel
from bagels.components.modules.budgets import Budgets
from bagels.components.modules.categories import Categories
from bagels.components.modules.people import People
from bagels.components.modules.spending import Spending
from bagels.managers.accounts import get_accounts_count
from bagels.managers.categories import get_categories_count


class Manager(Static):
    offset = 0

    BINDINGS = [
        Binding("left", "dec_offset", "Shift back", show=True),
        Binding("right", "inc_offset", "Shift front", show=True),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, id="manager-page")
        self.isReady = get_accounts_count() and get_categories_count()
        self.spendings_module = Spending(page_parent=self)
        self.categories_module = Categories()
        self.budgets_module = Budgets(page_parent=self)
        self.people_module = People()

    def on_mount(self) -> None:
        pass

    # -------------- Helpers ------------- #

    def rebuild(self) -> None:
        if self.isReady:
            self.spendings_module.rebuild()
            self.categories_module.rebuild()
            self.budgets_module.rebuild()
            self.people_module.rebuild()

    # region Callbacks
    # ------------- Callbacks ------------ #

    def action_inc_offset(self) -> None:
        if self.offset < 0:
            self.offset += 1
            self.spendings_module.rebuild()
            self.budgets_module.rebuild()

    def action_dec_offset(self) -> None:
        self.offset -= 1
        self.spendings_module.rebuild()
        self.budgets_module.rebuild()

    # region View
    # --------------- View --------------- #

    def compose(self) -> ComposeResult:
        if self.isReady:
            with Static(classes="manager-modules-container"):
                with Container(classes="left"):
                    yield self.spendings_module
                    yield self.budgets_module
                with Container(classes="right"):
                    yield self.categories_module
                    yield self.people_module
        else:
            with Center():
                yield Bagel()

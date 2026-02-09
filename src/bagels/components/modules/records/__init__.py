from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.events import DescendantBlur, DescendantFocus
from textual.reactive import reactive
from textual.widgets import Button, Input, Static, Switch

from bagels.components.datatable import DataTable
from bagels.components.indicators import EmptyIndicator
from bagels.components.modules.records._cud import RecordCUD
from bagels.components.modules.records._table_builder import RecordTableBuilder
from bagels.config import CONFIG
from bagels.forms.person_forms import PersonForm


class DisplayMode:
    DATE = "d"
    PERSON = "p"


class Records(RecordCUD, RecordTableBuilder, Static):
    DEFAULT_CSS = """\
Records .label-highlight-match {
    color: $accent-lighten-2;
    text-style: bold;
}
    """

    COMPONENT_CLASSES: ClassVar[set[str]] = {
        "label-highlight-match",
    }

    BINDINGS = [
        (CONFIG.hotkeys.new, "new", "Add"),
        (CONFIG.hotkeys.delete, "delete", "Delete"),
        (CONFIG.hotkeys.edit, "edit", "Edit"),
        (CONFIG.hotkeys.home.new_transfer, "new_transfer", "Transfer/Exchange"),
        (CONFIG.hotkeys.home.toggle_splits, "toggle_splits", "Toggle Splits"),
        Binding(
            CONFIG.hotkeys.home.display_by_person,
            "display_by_person",
            "Display by Person",
            show=False,
        ),
        Binding(
            CONFIG.hotkeys.home.display_by_date,
            "display_by_date",
            "Display by Date",
            show=False,
        ),
    ]

    can_focus = True
    show_splits = True
    displayMode = reactive(DisplayMode.DATE)
    FILTERS = {}
    FILTER_LABEL_TIPS = {
        "filter-category": "Shopping|Food|Dining",
        "filter-amount": ">=123.45",
        "filter-label": "Dinner with friends",
    }

    def __init__(self, parent: Static, *args, **kwargs) -> None:
        super().__init__(
            *args, **kwargs, id="records-container", classes="module-container"
        )
        super().__setattr__("border_title", "Records")
        self.page_parent = parent
        self.person_form = PersonForm()
        self.FILTERS = {
            "category": lambda: self.query_one("#filter-category").value,
            "amount": lambda: self.query_one("#filter-amount").value,
            "label": lambda: self.query_one("#filter-label").value,
            "enabled": lambda: self.query_one("#toggle-filter").value,
        }

    def on_mount(self) -> None:
        self.rebuild()

    # region Callbacks
    # ------------- Callbacks ------------ #

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        current_row_index = event.cursor_row
        if event.row_key and event.row_key.value:
            self.current_row = event.row_key.value
            self.current_row_index = current_row_index
        else:
            self.current_row = None
            self.current_row_index = None

    def watch_displayMode(self, displayMode: DisplayMode) -> None:
        self.query_one("#display-date").classes = (
            "selected" if displayMode == DisplayMode.DATE else ""
        )
        self.query_one("#display-person").classes = (
            "selected" if displayMode == DisplayMode.PERSON else ""
        )

    def action_toggle_splits(self) -> None:
        self.show_splits = not self.show_splits
        self.rebuild()

    def action_display_by_person(self) -> None:
        self.displayMode = DisplayMode.PERSON
        self.rebuild()

    def action_display_by_date(self) -> None:
        self.displayMode = DisplayMode.DATE
        self.rebuild()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "prev-month":
                self.page_parent.action_prev_month()
            case "next-month":
                self.page_parent.action_next_month()
            case "display-date":
                self.action_display_by_date()
            case "display-person":
                self.action_display_by_person()
            case _:
                pass

    def on_input_changed(self, event: Input.Changed) -> None:
        if self.FILTERS["enabled"]():
            self.rebuild(focus=False)

    def on_switch_changed(self, event: Switch.Changed) -> None:
        self.rebuild(focus=False)

    def on_descendant_focus(self, event: DescendantFocus) -> None:
        if event.widget.id.startswith("filter-"):
            event.widget.placeholder = self.FILTER_LABEL_TIPS[event.widget.id]

    def on_descendant_blur(self, event: DescendantBlur) -> None:
        if event.widget.id.startswith("filter-"):
            event.widget.placeholder = "Filter " + event.widget.id.split("-")[1]

    # region View
    # --------------- View --------------- #

    def compose(self) -> ComposeResult:
        with Container(classes="selectors"):
            with Container(id="display-selector"):
                yield Button(
                    f"Date ({CONFIG.hotkeys.home.display_by_date})", id="display-date"
                )
                yield Button(
                    f"Person ({CONFIG.hotkeys.home.display_by_person})",
                    id="display-person",
                )
            with Container(classes="filtering", id="filter-container"):
                yield Input(id="filter-category", placeholder="Filter category")
                yield Input(
                    id="filter-amount",
                    placeholder="Filter amount",
                    restrict=r"^(>=|>|=|<=|<)?\d*\.?\d*$",
                )
                yield Input(id="filter-label", placeholder="Filter label")
                yield Switch(id="toggle-filter", animate=False)
        self.table = DataTable(
            id="records-table",
            cursor_type="row",
            cursor_foreground_priority=True,
            zebra_stripes=True,
        )
        yield self.table
        yield EmptyIndicator("No entries")

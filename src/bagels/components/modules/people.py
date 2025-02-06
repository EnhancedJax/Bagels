from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Static

from bagels.components.datatable import DataTable
from bagels.components.indicators import EmptyIndicator
from bagels.config import CONFIG
from bagels.forms.person_forms import PersonForm
from bagels.managers.persons import (
    delete_person,
    get_person_by_id,
    get_persons_with_net_due,
    update_person,
)
from bagels.modals.confirmation import ConfirmationModal
from bagels.modals.input import InputModal


class People(Static):
    COLUMNS = ("Name", "Net due")

    BINDINGS = [
        Binding(CONFIG.hotkeys.edit, "edit_person", "Edit"),
        Binding(CONFIG.hotkeys.delete, "delete_person", "Delete"),
    ]

    can_focus = True

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(
            *args, **kwargs, id="people-container", classes="module-container"
        )
        super().__setattr__("border_title", "People")
        self.current_row = None

    # --------------- Hooks -------------- #

    def on_mount(self) -> None:
        self.rebuild()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key:
            self.current_row = event.row_key.value

    # region Builders
    # ------------- Builders ------------- #

    def rebuild(self) -> None:
        table: DataTable = self.query_one("#people-table")
        empty_indicator: Static = self.query_one(".empty-indicator")

        table.clear()
        if not table.columns:
            table.add_columns(*self.COLUMNS)

        people = get_persons_with_net_due()
        if people:
            for person in people:
                table.add_row(person.name, person.due, key=person.id)
            table.zebra_stripes = True

        empty_indicator.display = not people

    # region Helpers
    # -------------- Helpers ------------- #

    def _notify_no_select(self) -> None:
        self.app.notify(
            title="Error",
            message="A person must be selected for this action.",
            severity="error",
            timeout=2,
        )

    # region callbacks
    # ------------- Callbacks ------------ #

    def action_delete_person(self) -> None:
        if not self.current_row:
            self._notify_no_select()
            return

        def check_delete(result) -> None:
            if result:
                try:
                    delete_person(self.current_row)
                except Exception as e:
                    self.app.notify(
                        title="Error", message=f"{e}", severity="error", timeout=10
                    )
                self.rebuild()

        person = get_person_by_id(self.current_row)

        self.app.push_screen(
            ConfirmationModal(
                f"Are you sure you want to delete person '{person.name}'? Existing records with this person will not be affected."
            ),
            check_delete,
        )

    def action_edit_person(self) -> None:
        if not self.current_row:
            self._notify_no_select()
            return

        def check_result(result) -> None:
            if result:
                try:
                    update_person(self.current_row, result)
                except Exception as e:
                    self.app.notify(
                        title="Error", message=f"{e}", severity="error", timeout=10
                    )
                else:
                    self.app.notify(
                        title="Success",
                        message=f"Person {result['name']} updated",
                        severity="information",
                        timeout=3,
                    )
                    self.rebuild()

        filled_form = PersonForm().get_filled_form(self.current_row)
        self.app.push_screen(
            InputModal("Edit Person", filled_form), callback=check_result
        )

    # region View
    # --------------- View --------------- #
    def compose(self) -> ComposeResult:
        yield DataTable(
            id="people-table",
            cursor_type="row",
            cursor_foreground_priority=True,
        )
        yield EmptyIndicator("No people")

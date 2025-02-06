from textual.app import ComposeResult
from textual.binding import Binding
from textual.widgets import Static

from bagels.components.datatable import DataTable
from bagels.config import CONFIG
from bagels.forms.category_form import CategoryForm
from bagels.managers.categories import (
    create_category,
    delete_category,
    get_all_categories_tree,
    get_category_by_id,
    update_category,
)
from bagels.modals.confirmation import ConfirmationModal
from bagels.modals.input import InputModal


class Categories(Static):
    can_focus = True

    COLUMNS = ("", "Name", "Nature")

    BINDINGS = [
        Binding(
            CONFIG.hotkeys.categories.browse_defaults,
            "browse_defaults",
            "Browse",
            False,
        ),
        Binding(CONFIG.hotkeys.new, "new_category", "Add"),
        Binding(
            CONFIG.hotkeys.categories.new_subcategory,
            "new_subcategory",
            "Add Subcategory",
        ),
        Binding(CONFIG.hotkeys.edit, "edit_category", "Edit"),
        Binding(CONFIG.hotkeys.delete, "delete_category", "Delete"),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(
            *args, **kwargs, id="categories-container", classes="module-container"
        )
        super().__setattr__("border_title", "Categories")

    # --------------- Hooks -------------- #

    def on_mount(self) -> None:
        self.rebuild()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key:
            self.current_row = event.row_key.value

    # region Builders
    # ------------- Builders ------------- #

    def rebuild(self) -> None:
        table: DataTable = self.query_one("#categories-table")
        # empty_indicator: Static = self.query_one(".empty-indicator")

        table.clear()
        if not table.columns:
            table.add_columns(*self.COLUMNS)

        categories = get_all_categories_tree()
        if categories:
            for category, node, depth in categories:
                char = " "
                nature = category.nature.value
                if depth == 0:
                    char = ""
                table.add_row(
                    node,
                    char + category.name,
                    nature,
                    key=category.id,
                )
            table.zebra_stripes = True
        else:
            self.current_row = None

        # empty_indicator.display = not categories

    # region Helpers
    # -------------- Helpers ------------- #

    def _notify_no_categories(self) -> None:
        self.app.notify(
            title="Error",
            message="Category must be selected for this action.",
            severity="error",
            timeout=2,
        )

    # region callbacks
    # ------------- Callbacks ------------ #

    def action_new_category(self) -> None:
        def check_result(result) -> None:
            if result:
                try:
                    create_category(result)
                except Exception as e:
                    self.app.notify(
                        title="Error", message=f"{e}", severity="error", timeout=10
                    )
                else:
                    self.app.notify(
                        title="Success",
                        message="Category created",
                        severity="information",
                        timeout=3,
                    )
                    self.rebuild()

        self.app.push_screen(
            InputModal("New Category", CategoryForm().get_form()), callback=check_result
        )

    def action_new_subcategory(self) -> None:
        if not self.current_row:
            self._notify_no_categories()
            return

        def check_result(result) -> None:
            if result:
                try:
                    create_category(result)
                except Exception as e:
                    self.app.notify(
                        title="Error", message=f"{e}", severity="error", timeout=10
                    )
                else:
                    self.app.notify(
                        title="Success",
                        message="Subcategory created",
                        severity="information",
                        timeout=3,
                    )
                    self.rebuild()

        parent_category_id = self.current_row
        subcategory_form = CategoryForm().get_subcategory_form(parent_category_id)
        parent_category = get_category_by_id(parent_category_id)
        self.app.push_screen(
            InputModal(f"New Subcategory of {parent_category.name}", subcategory_form),
            callback=check_result,
        )

    def action_delete_category(self) -> None:
        if not self.current_row:
            self._notify_no_categories()
            return

        def check_delete(result) -> None:
            if result:
                try:
                    delete_category(self.current_row)
                except Exception as e:
                    self.app.notify(
                        title="Error", message=f"{e}", severity="error", timeout=10
                    )
                self.rebuild()

        category = get_category_by_id(self.current_row)

        self.app.push_screen(
            ConfirmationModal(
                f"Are you sure you want to delete category '[{category.color}]●[/{category.color}] {category.name}'?"
            ),
            check_delete,
        )

    def action_edit_category(self) -> None:
        if not self.current_row:
            self._notify_no_categories()
            return

        def check_result(result) -> None:
            if result:
                try:
                    update_category(self.current_row, result)
                except Exception as e:
                    self.app.notify(
                        title="Error", message=f"{e}", severity="error", timeout=10
                    )
                else:
                    self.app.notify(
                        title="Success",
                        message=f"Category {result['name']} updated",
                        severity="information",
                        timeout=3,
                    )
                    self.rebuild()

        filled_form = CategoryForm().get_filled_form(self.current_row)
        self.app.push_screen(
            InputModal("Edit Category", filled_form), callback=check_result
        )

    # region View
    # --------------- View --------------- #
    def compose(self) -> ComposeResult:
        yield DataTable(
            id="categories-table",
            cursor_type="row",
            cursor_foreground_priority=True,
        )
        # yield EmptyIndicator("No categories")

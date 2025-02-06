from textual import events
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import Label, Static

from bagels.modals.confirmation import ConfirmationModal
from bagels.modals.input import InputModal
from bagels.config import CONFIG
from bagels.modals.transfer import TransferModal
from bagels.models.record_template import RecordTemplate
from bagels.managers.record_templates import (
    create_template,
    delete_template,
    get_adjacent_template,
    get_all_templates,
    get_template_by_id,
    swap_template_order,
    update_template,
)
from bagels.managers.records import create_record
from bagels.forms.recordtemplate_forms import RecordTemplateForm


class Templates(Static):
    can_focus = True

    BINDINGS = [
        Binding(CONFIG.hotkeys.new, "new_template", "New"),
        Binding(
            CONFIG.hotkeys.home.new_transfer, "new_transfer", "New Transfer Template"
        ),
        Binding(CONFIG.hotkeys.edit, "edit_template", "Edit"),
        Binding(CONFIG.hotkeys.delete, "delete_template", "Delete"),
        Binding("left", "swap_previous", "Swap left"),
        Binding("right", "swap_next", "Swap right"),
    ]

    def __init__(self, parent: Static, *args, **kwargs) -> None:
        super().__init__(
            *args, **kwargs, id="templates-container", classes="module-container"
        )
        super().__setattr__("border_title", "Templates")
        super().__setattr__("border_subtitle", "1 - 9")
        self.page_parent = parent
        self.templates: list[RecordTemplate] = []
        self.template_form = RecordTemplateForm()
        self.selected_template_id = None

    def on_mount(self) -> None:
        self.rebuild()

    # region Builder
    # -------------- Builder ------------- #

    def _create_templates_widgets(self, container: Container) -> None:
        if len(self.templates) == 0:
            widget = Label("No templates. Jump here to create one.", classes="empty")
            container.compose_add_child(widget)
            return container
        for index, template in enumerate(self.templates):
            if index > 8:
                break
            if template.isTransfer:
                widget = Container(
                    Label(f"{template.label}", classes="label"),
                    id=f"template-{template.id}",
                    classes="template-item",
                )
            else:
                color = template.category.color
                widget = Container(
                    Label(
                        f"[{color}]{CONFIG.symbols.category_color}[/{color}]",
                        classes="dot",
                    ),
                    Label(f"{template.label}", classes="label"),
                    id=f"template-{template.id}",
                    classes="template-item",
                )
            widget.border_subtitle = str(index + 1)
            widget.can_focus = True
            container.compose_add_child(widget)
        return container

    def rebuild(self, reset_state=False) -> None:
        self.templates = get_all_templates()
        container = self.query(".templates")
        if len(container) > 0:
            container[0].remove()
        container = Horizontal(classes="templates")
        container = self._create_templates_widgets(container)
        self.mount(container)
        if reset_state:
            self.selected_template_id = None
        if self.selected_template_id:
            self.call_after_refresh(
                lambda: self.query_one(f"#template-{self.selected_template_id}").focus()
            )

    # helper
    # -------------- Helper -------------- #

    def _notify_no_selected_template(self) -> None:
        self.app.notify(
            title="Error",
            message="No template selected",
            severity="error",
            timeout=3,
        )

    # region Callback
    # ------------- Callback ------------- #

    def on_descendant_focus(self, event: events.DescendantFocus):
        id = event.widget.id
        if id:
            template_id = id.split("-")[1]
            self.selected_template_id = template_id

    def select_template(self, index: int) -> None:
        if index > len(self.templates):
            self.app.notify(
                title="Error",
                message=f"Template slot {index} is empty",
                severity="error",
                timeout=3,
            )
            return
        template = self.templates[index - 1]
        record_data = template.to_dict()
        record_data["date"] = self.page_parent.mode["date"]
        create_record(record_data)
        self.app.notify(
            title="Success",
            message=f"Created new record with {template.label}",
            severity="information",
            timeout=3,
        )
        self.page_parent.rebuild()

    # region CRUD
    # ----------------- - ---------------- #

    def action_new_template(self) -> None:
        def check_result(result) -> None:
            if result:
                create_template(result)
                self.app.notify(
                    title="Success",
                    message="Template created",
                    severity="information",
                    timeout=3,
                )
                self.rebuild()

        self.app.push_screen(
            InputModal("New Template", form=self.template_form.get_form()),
            callback=check_result,
        )

    def action_new_transfer(self) -> None:
        def check_result(result) -> None:
            if result:
                create_template(result)
                self.app.notify(
                    title="Success",
                    message="Template created",
                    severity="information",
                    timeout=3,
                )
                self.rebuild()

        self.app.push_screen(
            TransferModal(title="New Transfer Template", isTemplate=True),
            callback=check_result,
        )

    def action_edit_template(self) -> None:
        if not self.selected_template_id:
            self._notify_no_selected_template()
            return

        # ----------------- - ---------------- #
        def check_result(result) -> None:
            if result:
                try:
                    update_template(self.selected_template_id, result)
                except Exception as e:
                    self.app.notify(
                        title="Error", message=f"{e}", severity="error", timeout=10
                    )
                else:
                    self.app.notify(
                        title="Success",
                        message="Template edited",
                        severity="information",
                        timeout=3,
                    )
                    self.rebuild()

        # ----------------- - ---------------- #
        template = get_template_by_id(self.selected_template_id)
        if template.isTransfer:
            self.app.push_screen(
                TransferModal(
                    title="Edit Transfer Template",
                    record=template,
                    isTemplate=True,
                ),
                callback=check_result,
            )
        else:
            self.app.push_screen(
                InputModal(
                    "Edit Template",
                    form=self.template_form.get_filled_form(self.selected_template_id),
                ),
                callback=check_result,
            )

    def action_delete_template(self) -> None:
        if not self.selected_template_id:
            self._notify_no_selected_template()
            return

        # ----------------- - ---------------- #
        def check_delete(result) -> None:
            if result:
                delete_template(self.selected_template_id)
                self.app.notify(
                    title="Success",
                    message="Template deleted",
                    severity="information",
                    timeout=3,
                )
                self.selected_template_id = None
                self.rebuild()

        template = get_template_by_id(self.selected_template_id)

        # ----------------- - ---------------- #
        self.app.push_screen(
            ConfirmationModal(
                f"Are you sure you want to delete template '{template.label}'?"
            ),
            check_delete,
        )

    def _swap_template(self, direction: str) -> None:
        if not self.selected_template_id:
            self._notify_no_selected_template()
            return
        if get_adjacent_template(self.selected_template_id, direction) == -1:
            self.app.notify(
                title="Error",
                message=f"No {direction} template",
                severity="error",
                timeout=3,
            )
            self.app.bell()
            return
        else:
            swap_template_order(self.selected_template_id, direction)
            self.rebuild()

    def action_swap_previous(self) -> None:
        self._swap_template("previous")

    def action_swap_next(self) -> None:
        self._swap_template("next")

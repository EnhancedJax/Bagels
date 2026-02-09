from datetime import datetime

from bagels.forms.form import Form
from bagels.forms.record_forms import RecordForm
from bagels.managers.persons import (
    get_person_by_id,
    update_person,
)
from bagels.managers.record_templates import create_template_from_record
from bagels.managers.records import (
    create_record,
    create_record_and_splits,
    delete_record,
    get_record_by_id,
    update_record,
    update_record_and_splits,
)
from bagels.managers.splits import get_split_by_id, update_split
from bagels.modals.confirmation import ConfirmationModal
from bagels.modals.input import InputModal
from bagels.modals.record import RecordModal
from bagels.modals.transfer import TransferModal


class RecordCUD:
    def action_new(self) -> None:
        def check_result(result) -> None:
            if result:
                try:
                    create_record_and_splits(result["record"], result["splits"])
                    if result["createTemplate"]:
                        create_template_from_record(result["record"])
                except Exception as e:
                    self.app.notify(
                        title="Error", message=f"{e}", severity="error", timeout=10
                    )
                else:
                    self.app.notify(
                        title="Success",
                        message=f"Record created {'and template created' if result['createTemplate'] else ''}",
                        severity="information",
                        timeout=3,
                    )
                    self.page_parent.rebuild(templates=result["createTemplate"])

        self.app.push_screen(
            RecordModal(
                "New Record",
                form=RecordForm().get_form(default_values=self.page_parent.mode),
                splitForm=Form(),
                date=self.page_parent.mode["date"],
            ),
            callback=check_result,
        )

    def action_edit(self) -> None:
        if not (hasattr(self, "current_row") and self.current_row):
            self.app.notify(
                title="Error", message="Nothing selected", severity="error", timeout=2
            )
            self.app.bell()
            return
        # ----------------- - ---------------- #
        type = self.current_row.split("-")[0]
        id = self.current_row.split("-")[1]

        # ----------------- - ---------------- #
        def check_result_records(result) -> None:
            if result:
                try:
                    if result.get("record"):  # if not editing a transfer:
                        update_record_and_splits(id, result["record"], result["splits"])
                    else:
                        update_record(id, result)
                except Exception as e:
                    self.app.notify(
                        title="Error", message=f"{e}", severity="error", timeout=10
                    )
                else:
                    self.app.notify(
                        title="Success",
                        message="Record updated",
                        severity="information",
                        timeout=3,
                    )
                    self.page_parent.rebuild()
            else:
                self.app.notify(
                    title="Discarded",
                    message="Record not updated",
                    severity="warning",
                    timeout=3,
                )

        def check_result_person(result) -> None:
            if result:
                try:
                    update_person(id, result)
                except Exception as e:
                    self.app.notify(
                        title="Error", message=f"{e}", severity="error", timeout=10
                    )
                else:
                    self.app.notify(
                        title="Success",
                        message="Person updated",
                        severity="information",
                        timeout=3,
                    )
                    self.page_parent.rebuild()
            else:
                self.app.notify(
                    title="Discarded",
                    message="Person not updated",
                    severity="warning",
                    timeout=3,
                )

        # ----------------- - ---------------- #
        match type:
            case "r":
                record = get_record_by_id(id)
                if not record:
                    self.app.notify(
                        title="Error",
                        message="Record not found",
                        severity="error",
                        timeout=2,
                    )
                    return
                if record.isTransfer:
                    self.app.push_screen(
                        TransferModal(title="Edit transfer", record=record),
                        callback=check_result_records,
                    )
                else:
                    filled_form, filled_splits = RecordForm().get_filled_form(record.id)
                    self.app.push_screen(
                        RecordModal(
                            "Edit Record",
                            form=filled_form,
                            splitForm=filled_splits,
                            isEditing=True,
                        ),
                        callback=check_result_records,
                    )
            case "s":
                split = get_split_by_id(id)
                if split.isPaid:
                    split_data = {"accountId": None, "isPaid": False, "paidDate": None}
                    update_split(id, split_data)
                    self.app.notify(
                        title="Reverted split",
                        message="Marked this split as unpaid",
                        severity="information",
                        timeout=3,
                    )
                else:
                    split_data = {
                        "accountId": self.page_parent.mode["accountId"][
                            "default_value"
                        ],
                        "isPaid": True,
                        "paidDate": datetime.now(),
                    }
                    update_split(id, split_data)
                    self.app.notify(
                        title="Completed split",
                        message=f"With account {self.page_parent.mode['accountId']['default_value_text']} today",
                        severity="information",
                        timeout=3,
                    )
                self.page_parent.rebuild()
            case "p":
                person = get_person_by_id(id)
                if not person:
                    self.app.notify(
                        title="Error",
                        message="Person not found",
                        severity="error",
                        timeout=2,
                    )
                    return
                self.app.push_screen(
                    InputModal(
                        "Edit Person", form=self.person_form.get_filled_form(person.id)
                    ),
                    callback=check_result_person,
                )
            case _:
                pass

    def action_delete(self) -> None:
        if not (hasattr(self, "current_row") and self.current_row):
            self.app.notify(
                title="Error", message="Nothing selected", severity="error", timeout=2
            )
            self.app.bell()
            return
        # ----------------- - ---------------- #
        type = self.current_row.split("-")[0]
        id = self.current_row.split("-")[1]

        if type == "s":
            self.app.notify(
                title="Error",
                message="You cannot delete or add splits to a record after creation.",
                severity="error",
                timeout=2,
            )
            return

        # ----------------- - ---------------- #
        def check_delete(result) -> None:
            if result:
                delete_record(id)
                self.app.notify(
                    title="Success",
                    message="Record deleted",
                    severity="information",
                    timeout=3,
                )
                self.page_parent.rebuild()

        # ----------------- - ---------------- #
        match type:
            case "r":
                self.app.push_screen(
                    ConfirmationModal("Are you sure you want to delete this record?"),
                    callback=check_delete,
                )
            case "s":
                self.app.push_screen(
                    ConfirmationModal("Are you sure you want to delete this split?"),
                    callback=check_delete,
                )
            case _:
                pass

    def action_new_transfer(self) -> None:
        def check_result(result) -> None:
            if result:
                try:
                    create_record(result)
                except Exception as e:
                    self.app.notify(
                        title="Error", message=f"{e}", severity="error", timeout=10
                    )
                else:
                    self.app.notify(
                        title="Success",
                        message="Record created",
                        severity="information",
                        timeout=3,
                    )
                    self.page_parent.rebuild()

        self.app.push_screen(
            TransferModal(
                title="New transfer / exchange",
                defaultDate=self.page_parent.mode["date"].strftime("%d"),
            ),
            callback=check_result,
        )

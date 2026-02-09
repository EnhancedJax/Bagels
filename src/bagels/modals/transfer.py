from datetime import datetime
from typing import override

from textual import events
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import (
    Input,
    Label,
    ListItem,
    ListView,
)

from bagels.components.autocomplete import AutoComplete
from bagels.components.fields import Fields
from bagels.forms.transfer_forms import TransferForm
from bagels.managers.currency import get_main_currency, get_rate
from bagels.managers.accounts import get_all_accounts_with_balance
from bagels.managers.record_templates import get_template_by_id
from bagels.modals.base_widget import ModalContainer
from bagels.utils.format import parse_formula_expression
from bagels.utils.money import format_account_balance, format_account_name, format_amount
from bagels.utils.validation import validateForm


class Accounts(ListView):
    def __init__(self, accounts, initial_id: int = 0, type: str = "", *args, **kwargs):
        main_currency = get_main_currency()
        initial_index = accounts.index(
            next((account for account in accounts if account.id == initial_id), None)
        )
        super().__init__(
            *[
                ListItem(
                    Label(
                        format_account_name(account),
                        classes="name " + ("hidden-name" if account.hidden else ""),
                    ),
                    Label(
                        format_account_balance(account, main_currency),
                        classes="balance "
                        + ("hidden-balance" if account.hidden else ""),
                    ),
                    classes="item",
                    id=f"account-{account.id}",
                )
                for account in accounts
            ],
            id=f"{type}-accounts",
            classes="accounts",
            initial_index=initial_index,
            *args,
            **kwargs,
        )


class TransferModal(ModalScreen):
    def __init__(
        self,
        title="",
        record=None,
        isTemplate=False,
        defaultDate=datetime.now().strftime("%d"),
        *args,
        **kwargs,
    ):
        super().__init__(classes="modal-screen", *args, **kwargs)
        self.accounts = get_all_accounts_with_balance(get_hidden=True)
        if record:
            self.form = TransferForm(isTemplate, defaultDate).get_filled_form(record)
        else:
            self.form = TransferForm(isTemplate, defaultDate).get_form()
        self.fromAccount = record.accountId if record else self.accounts[0].id
        self.toAccount = record.transferToAccountId if record else self.accounts[1].id
        self.title = title
        self.atAccountList = False

    @override
    def _on_mount(self, event: events.Mount) -> None:
        self.rebuild()
        self._refresh_exchange_preview()
        return super()._on_mount(event)

    def on_descendant_focus(self, event: events.DescendantFocus):
        id = event.widget.id
        if id.endswith("-accounts"):
            self.atAccountList = True
        else:
            self.atAccountList = False

    def on_key(self, event: events.Key):
        if self.atAccountList:
            if event.key == "right":
                self.screen.focus_next()
            elif event.key == "left":
                self.screen.focus_previous()
        else:
            if event.key == "up":
                self.screen.focus_previous()
            elif event.key == "down":
                self.screen.focus_next()
        if event.key == "enter":
            self.action_submit()
        elif event.key == "escape":
            self.dismiss(None)

    def rebuild(self):
        self.fromAccountsSelector = Accounts(
            self.accounts, initial_id=self.fromAccount, type="from"
        )
        self.toAccountsSelector = Accounts(
            self.accounts, initial_id=self.toAccount, type="to"
        )
        transfer_modal = self.query_one("#transfer-modal")
        container = Container(
            self.fromAccountsSelector,
            Label(">>>", classes="arrow"),
            self.toAccountsSelector,
            classes="transfer-accounts-container",
        )
        last_container = transfer_modal.query(".transfer-accounts-container")
        if len(last_container) > 0:
            last_container[0].remove()
        transfer_modal.mount(container, after=0)

    def on_list_view_highlighted(self, event: ListView.Highlighted):
        accountId = event.item.id.split("-")[1]
        if event.list_view.id == "from-accounts":
            self.fromAccount = int(accountId)
        elif event.list_view.id == "to-accounts":
            self.toAccount = int(accountId)
        self._refresh_exchange_preview()

    def on_auto_complete_selected(self, event: AutoComplete.Selected) -> None:
        if "field-label" in event.input.id:
            template = get_template_by_id(event.input.heldValue)
            fieldWidget = self.query_one("#field-amount")
            fieldWidget.value = str(getattr(template, "amount"))
            fieldWidget = self.query_one("#field-transferToAmount")
            fieldWidget.value = (
                str(template.transferToAmount)
                if getattr(template, "transferToAmount", None) is not None
                else ""
            )

            self.fromAccount = template.accountId
            self.toAccount = template.transferToAccountId
            self.rebuild()
            self._refresh_exchange_preview()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id in {"field-amount", "field-transferToAmount", "field-date"}:
            self._refresh_exchange_preview()

    def _get_selected_accounts(self):
        account_by_id = {account.id: account for account in self.accounts}
        from_account = account_by_id.get(int(self.fromAccount))
        to_account = account_by_id.get(int(self.toAccount))
        return from_account, to_account

    def _parse_amount_input(self, field_id: str) -> float | None:
        field = self.query_one(f"#{field_id}")
        raw_value = str(field.value or "").strip()
        if raw_value == "":
            return None
        return parse_formula_expression(raw_value)

    def _parse_date_input(self) -> datetime:
        if not self.query("#field-date"):
            return datetime.now()
        field = self.query_one("#field-date")
        raw = str(field.value or "").strip()
        if raw == "":
            return datetime.now()
        try:
            if raw.isdigit():
                month = datetime.now().strftime("%m")
                year = datetime.now().strftime("%y")
                return datetime.strptime(f"{raw} {month} {year}", "%d %m %y")
            return datetime.strptime(raw, "%d %m %y")
        except ValueError:
            return datetime.now()

    def _refresh_exchange_preview(self) -> None:
        preview_label = self.query_one("#exchange-preview")
        from_account, to_account = self._get_selected_accounts()
        if from_account is None or to_account is None:
            preview_label.update("")
            return

        if from_account.currencyCode == to_account.currencyCode:
            preview_label.update("")
            return

        amount = self._parse_amount_input("field-amount")
        to_amount = self._parse_amount_input("field-transferToAmount")
        date = self._parse_date_input()
        rate = get_rate(from_account.currencyCode, to_account.currencyCode, at=date)
        if rate is None:
            preview_label.update(
                f"Exchange: {from_account.currencyCode} → {to_account.currencyCode}. Enter destination amount manually."
            )
            return

        if amount is not None and to_amount is None:
            suggested = round(amount * rate, 6)
            destination_field = self.query_one("#field-transferToAmount")
            destination_field.value = str(suggested)
            to_amount = suggested

        message = (
            f"Exchange: 1 {from_account.currencyCode} = {rate:.6f} {to_account.currencyCode}"
        )
        if amount is not None and to_amount is not None:
            message += (
                f" | {format_amount(amount, from_account.currencyCode)}"
                f" -> {format_amount(to_amount, to_account.currencyCode)}"
            )
        preview_label.update(message)

    def _show_transfer_error(self, message: str) -> None:
        transfer_error_label = self.query_one("#transfer-error")
        transfer_error_label.update(message)
        transfer_error_label.add_class("active")

    def _clear_transfer_error(self) -> None:
        transfer_error_label = self.query_one("#transfer-error")
        transfer_error_label.update("")
        transfer_error_label.remove_class("active")

    def action_submit(self):
        resultForm, errors, isValid = validateForm(self, self.form)
        from_account, to_account = self._get_selected_accounts()
        is_cross_currency = (
            from_account is not None
            and to_account is not None
            and from_account.currencyCode != to_account.currencyCode
        )
        transfer_to_amount = resultForm.get("transferToAmount")
        if transfer_to_amount in ("", None):
            transfer_to_amount = None
        else:
            transfer_to_amount = float(transfer_to_amount)

        # custom check for from and to accounts
        if self.fromAccount == self.toAccount:
            self._show_transfer_error("From and to accounts cannot be the same")
            return

        if is_cross_currency and transfer_to_amount is None:
            rate = get_rate(
                from_account.currencyCode,
                to_account.currencyCode,
                at=resultForm.get("date"),
            )
            if rate is not None and resultForm.get("amount"):
                transfer_to_amount = round(float(resultForm["amount"]) * rate, 6)
            else:
                self._show_transfer_error(
                    "Destination Amount is required for cross-currency transfers"
                )
                return

        self._clear_transfer_error()
        if isValid:
            resultForm["accountId"] = int(self.fromAccount)
            resultForm["transferToAccountId"] = int(self.toAccount)
            resultForm["isTransfer"] = True
            resultForm["transferToAmount"] = transfer_to_amount
            self.dismiss(resultForm)
        else:
            previousErrors = self.query(".error")
            for error in previousErrors:
                error.remove()
            for key, value in errors.items():
                field = self.query_one(f"#row-field-{key}")
                field.mount(Label(value, classes="error"))

    def compose(self) -> ComposeResult:
        yield ModalContainer(
            Container(
                Fields(self.form),
                Label(id="exchange-preview", classes="exchange-preview"),
                Label(id="transfer-error"),
                id="transfer-modal",
            ),
            custom_classes="wrapper max-width-80",
        )

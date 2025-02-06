# region Accounts
from textual import events
from textual.app import ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import Label, ListItem, ListView, Static

from bagels.components.indicators import EmptyIndicator
from bagels.config import CONFIG
from bagels.forms.account_forms import AccountForm
from bagels.managers.accounts import (
    create_account,
    delete_account,
    get_all_accounts_with_balance,
    update_account,
)
from bagels.modals.confirmation import ConfirmationModal
from bagels.modals.input import InputModal


class AccountsList(ListView):
    def __init__(self, accounts, *args, **kwargs):
        super().__init__(
            *[
                ListItem(
                    Container(
                        Label(
                            str(account.name),
                            classes="name",
                            id=f"account-{account.id}-name",
                        ),
                        Label(
                            str(account.description or ""),
                            classes=f"description{'none' if not account.description else ''}",
                            id=f"account-{account.id}-description",
                        ),
                        classes="left-container",
                    ),
                    Label(
                        str(account.balance),
                        classes="balance",
                        id=f"account-{account.id}-balance",
                    ),
                    classes="account-container",
                    id=f"account-{account.id}-container",
                )
                for account in accounts
            ],
            id="accounts-list",
            *args,
            **kwargs,
        )


class AccountMode(ScrollableContainer):
    BINDINGS = [
        (CONFIG.hotkeys.new, "new", "New account"),
        (CONFIG.hotkeys.delete, "delete", "Archive account"),
        (CONFIG.hotkeys.edit, "edit", "Edit account"),
    ]

    can_focus = True

    def __init__(self, parent: Static, *args, **kwargs) -> None:
        super().__init__(
            *args, **kwargs, id="accounts-container", classes="module-container"
        )
        super().__setattr__(
            "border_subtitle",
            f"{CONFIG.hotkeys.home.select_prev_account} {CONFIG.hotkeys.home.select_next_account}",
        )
        self.page_parent = parent
        self.account_form = AccountForm()

    def on_mount(self) -> None:
        self.rebuild()

    # region Builder
    # -------------- Builder ------------- #

    def rebuild(self) -> None:
        net_balance = 0
        for account in get_all_accounts_with_balance():
            net_balance += account.balance
            # Update balance
            self.query_one(f"#account-{account.id}-balance").update(
                str(account.balance)
            )

            # Update account container classes
            account_container = self.query_one(f"#account-{account.id}-container")
            selected = (
                "selected"
                if self.page_parent.mode["accountId"]["default_value"] == account.id
                else ""
            )
            account_container.classes = f"account-container {selected}"

            # Update name/description label
            name_label = self.query_one(f"#account-{account.id}-name")
            name_label.update(account.name)
            description_label: Label = self.query_one(
                f"#account-{account.id}-description"
            )
            description_label.update(account.description)
            if account.description == "" or account.description is None:
                description_label.add_class("none")
            else:
                description_label.remove_class("none")

            # Scroll to selected account
            if selected:
                self.scroll_to_widget(account_container)

        super().__setattr__(
            "border_title",
            f"Accounts @= {round(net_balance, CONFIG.defaults.round_decimals)}",
        )

    # region Callbacks
    # ------------- Callbacks ------------ #

    def on_key(self, event: events.Key) -> None:
        if event.key == "up":
            self.page_parent.action_select_prev_account()
        elif event.key == "down":
            self.page_parent.action_select_next_account()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        account_id = event.item.id.split("-")[1]
        self.page_parent.action_select_account(account_id)

    # region cud
    # ---------------- cud --------------- #

    def action_new(self) -> None:
        def check_result(result) -> None:
            if result:
                try:
                    create_account(result)
                except Exception as e:
                    self.app.notify(
                        title="Error", message=f"{e}", severity="error", timeout=10
                    )
                self.app.notify(
                    title="Success",
                    message=f"Account {result['name']} created",
                    severity="information",
                    timeout=3,
                )
                self.app.refresh(layout=True, recompose=True)  # the big button

        account_form = self.account_form.get_form()
        self.app.push_screen(
            InputModal("New Account", account_form), callback=check_result
        )

    def action_edit(self) -> None:
        id = self.page_parent.mode["accountId"]["default_value"]

        def check_result(result) -> None:
            if result:
                try:
                    update_account(id, result)
                except Exception as e:
                    self.app.notify(
                        title="Error", message=f"{e}", severity="error", timeout=10
                    )
                self.app.notify(
                    title="Success",
                    message=f"Account {result['name']} updated",
                    severity="information",
                    timeout=3,
                )
                self.page_parent.rebuild()

        if id:
            filled_account_form = self.account_form.get_filled_form(id)
            self.app.push_screen(
                InputModal("Edit Account", filled_account_form), callback=check_result
            )
        else:
            self.app.notify(
                title="Error",
                message="No account selected",
                severity="error",
                timeout=3,
            )

    def action_delete(self) -> None:
        id = self.page_parent.mode["accountId"]["default_value"]
        name = self.page_parent.mode["accountId"]["default_value_text"]

        def check_delete(result) -> None:
            if result:
                delete_account(id)
                self.app.notify(
                    title="Success",
                    message="Archived account",
                    severity="information",
                    timeout=3,
                )
                self.app.refresh(layout=True, recompose=True)  # the big button

        if id:
            self.app.push_screen(
                ConfirmationModal(
                    f"Are you sure you want to archive account '{name}'?"
                ),
                check_delete,
            )
        else:
            self.app.notify(
                title="Error",
                message="No account selected",
                severity="error",
                timeout=3,
            )
        pass

    # region View
    # --------------- View --------------- #

    def compose(self) -> ComposeResult:
        accounts = get_all_accounts_with_balance()
        if not accounts:
            yield EmptyIndicator("No accounts")
            return

        yield AccountsList(accounts)

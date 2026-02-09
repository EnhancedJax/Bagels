import copy
from datetime import datetime

from rich.text import Text

from bagels.forms.form import Form, FormField, Option, Options
from bagels.managers.accounts import get_all_accounts_with_balance
from bagels.managers.currency import get_main_currency
from bagels.managers.categories import get_all_categories_by_freq
from bagels.managers.persons import get_all_persons
from bagels.managers.record_templates import get_record_templates
from bagels.managers.records import get_record_by_id
from bagels.utils.money import format_account_balance, format_amount


class RecordForm:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ------------ Blueprints ------------ #

    FORM = Form(
        fields=[
            FormField(
                placeholder="Label",
                title="Label / Template name",
                key="label",
                type="autocomplete",
                options=Options(),
                autocomplete_selector=False,
                is_required=True,
            ),
            FormField(
                title="Category",
                key="categoryId",
                type="autocomplete",
                options=Options(),
                is_required=True,
                placeholder="Select Category",
            ),
            FormField(
                placeholder="0.00",
                title="Amount",
                key="amount",
                type="number",
                min=0,
                is_required=True,
            ),
            FormField(
                title="Account",
                key="accountId",
                type="autocomplete",
                options=Options(),
                is_required=True,
                placeholder="Select Account",
            ),
            FormField(
                title="Type",
                key="isIncome",
                type="boolean",
                labels=["Expense", "Income"],
                default_value=False,
            ),
            FormField(
                placeholder="dd (mm) (yy)",
                title="Date",
                key="date",
                type="dateAutoDay",
                default_value=datetime.now().strftime("%d"),
            ),
        ]
    )

    SPLIT_FORM = Form(
        fields=[
            FormField(
                title="Person",
                key="personId",
                type="autocomplete",
                options=Options(),
                create_action=True,
                is_required=True,
                placeholder="Select Person",
            ),
            FormField(
                title="Amount",
                key="amount",
                type="number",
                min=0,
                is_required=True,
                placeholder="0.00",
            ),
            FormField(
                title="Paid",
                key="isPaid",
                type="hidden",
                default_value=False,
            ),
            FormField(
                title="Paid to account",
                key="accountId",
                type="hidden",
                options=Options(),
                placeholder="Select Account",
            ),
            FormField(
                title="Paid Date",
                key="paidDate",
                type="hidden",
                default_value=None,
            ),
        ]
    )

    # ----------------- - ---------------- #

    def __init__(self):
        self._populate_form_options()

    # region Helpers
    # -------------- Helpers ------------- #

    def _populate_form_options(self):
        templates = get_record_templates()
        self.FORM.fields[0].options = Options(
            items=[
                Option(
                    text=template.label,
                    value=template.id,
                    postfix=Text(
                        format_amount(
                            template.amount,
                            getattr(template.account, "currencyCode", None),
                        ),
                        style="yellow",
                    ),
                )
                for template in templates
            ]
        )

        accounts = get_all_accounts_with_balance()
        main_currency = get_main_currency()
        self.FORM.fields[3].options = Options(
            items=[
                Option(
                    text=account.name,
                    value=account.id,
                    postfix=Text(
                        format_account_balance(account, main_currency),
                        style="yellow",
                    ),
                )
                for account in accounts
            ]
        )
        if accounts:
            self.FORM.fields[3].default_value = accounts[0].id
            self.FORM.fields[3].default_value_text = accounts[0].name

        categories = get_all_categories_by_freq()
        self.FORM.fields[1].options = Options(
            items=[
                Option(
                    text=category.name,
                    value=category.id,
                    prefix=Text("●", style=category.color),
                    postfix=(
                        Text(
                            (
                                f"↪ {category.parentCategory.name}"
                                if category.parentCategory
                                else ""
                            ),
                            style=category.parentCategory.color,
                        )
                        if category.parentCategory
                        else ""
                    ),
                )
                for category, _ in categories
            ]
        )
        people = get_all_persons()
        self.SPLIT_FORM.fields[0].options = Options(
            items=[Option(text=person.name, value=person.id) for person in people]
        )
        self.SPLIT_FORM.fields[3].options = Options(
            items=[
                Option(
                    text=account.name,
                    value=account.id,
                )
                for account in accounts
            ]
        )

    # region Builders
    # ------------- Builders ------------- #

    def get_split_form(
        self, index: int, isPaid: bool = False, defaultPaidDate: datetime = None
    ) -> Form:
        split_form = copy.deepcopy(self.SPLIT_FORM)
        for field in split_form.fields:
            fieldKey = field.key
            field.key = f"{fieldKey}-{index}"
            if fieldKey == "isPaid":
                field.default_value = isPaid
            elif fieldKey == "accountId" and isPaid:
                field.type = "autocomplete"
                field.is_required = True
            elif fieldKey == "paidDate" and isPaid:
                field.type = "dateAutoDay"
                field.is_required = True
                field.default_value = (
                    defaultPaidDate.strftime("%d %m %y") if defaultPaidDate else ""
                )
        return split_form

    def get_filled_form(self, recordId: int) -> tuple[list, list]:
        """Return a copy of the form with values from the record"""
        filled_form = copy.deepcopy(self.FORM)
        record = get_record_by_id(recordId, populate_splits=True)

        for field in filled_form.fields:
            fieldKey = field.key
            value = getattr(record, fieldKey)

            match fieldKey:
                case "date":
                    # if value is this month, simply set %d, else set %d %m %y
                    if value.month == datetime.now().month:
                        field.default_value = value.strftime("%d")
                    else:
                        field.default_value = value.strftime("%d %m %y")
                case "isIncome":
                    field.default_value = value
                case "categoryId":
                    field.default_value = record.category.id
                    field.default_value_text = record.category.name
                case "accountId":
                    field.default_value = record.account.id
                    field.default_value_text = record.account.name
                case "label":
                    field.default_value = str(value) if value is not None else ""
                    field.type = "string"  # disable autocomplete
                case _:
                    field.default_value = str(value) if value is not None else ""

        filled_splits = Form()
        for index, split in enumerate(record.splits):
            split_form = self.get_split_form(index, split.isPaid)
            for field in split_form.fields:
                fieldKey = field.key.split("-")[0]
                value = getattr(split, fieldKey)

                match fieldKey:
                    case "paidDate":
                        if value:
                            if value.month == datetime.now().month:
                                field.default_value = value.strftime("%d")
                            else:
                                field.default_value = value.strftime("%d %m %y")
                    case "accountId":
                        if split.account:
                            field.default_value = split.account.id
                            field.default_value_text = split.account.name
                    case "personId":
                        field.default_value = split.person.id
                        field.default_value_text = split.person.name
                    case "isPaid":
                        field.default_value = split.isPaid
                    case _:
                        field.default_value = str(value) if value is not None else ""

                filled_splits.fields.append(field)

        return filled_form, filled_splits

    # date: datetime
    # isIncome: bool
    # accountId: {
    #     default_value: None,
    #     default_value_text: "Select account",
    # }
    def get_form(self, default_values: dict):  # TODO: properly type everything
        """Return the base form with default values"""
        form = copy.deepcopy(self.FORM)

        if not default_values:  # should never happen
            return form

        for field in form.fields:
            match field.key:
                case "date":
                    value = default_values["date"]
                    if value.month == datetime.now().month:
                        field.default_value = value.strftime("%d")
                    else:
                        field.default_value = value.strftime("%d %m %y")
                case "isIncome":
                    field.default_value = default_values["isIncome"]
                case "accountId":
                    field.default_value = default_values["accountId"]["default_value"]
                    field.default_value_text = default_values["accountId"][
                        "default_value_text"
                    ]
        return form

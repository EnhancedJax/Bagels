import copy
from rich.text import Text

from bagels.managers.currency import get_main_currency
from bagels.managers.accounts import get_all_accounts_with_balance
from bagels.managers.categories import get_all_categories_by_freq
from bagels.managers.record_templates import get_template_by_id
from bagels.forms.form import Form, FormField, Option, Options
from bagels.utils.money import format_account_balance


class RecordTemplateForm:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ------------ Blueprints ------------ #

    FORM = Form(
        fields=[
            FormField(
                placeholder="Template label",
                title="Label",
                key="label",
                type="string",
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
        ]
    )

    # ----------------- - ---------------- #

    def __init__(self):
        self._populate_form_options()

    # -------------- Helpers ------------- #

    def _populate_form_options(self):
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

    # ------------- Builders ------------- #

    def get_filled_form(self, templateId: int) -> list:
        """Return a copy of the form with values from the record"""
        filled_form = copy.deepcopy(self.FORM)
        template = get_template_by_id(templateId)

        for field in filled_form.fields:
            fieldKey = field.key
            value = getattr(template, fieldKey)

            match fieldKey:
                case "isIncome":
                    field.default_value = value
                case "categoryId":
                    field.default_value = template.category.id
                    field.default_value_text = template.category.name
                case "accountId":
                    field.default_value = template.account.id
                    field.default_value_text = template.account.name
                case _:
                    field.default_value = str(value) if value is not None else ""

        return filled_form

    def get_form(self):
        """Return the base form with default values"""
        form = copy.deepcopy(self.FORM)
        return form

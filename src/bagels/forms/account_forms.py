import copy
from bagels.config import CONFIG
from bagels.currencies import get_default_currency_code
from bagels.currencies import get_currency_items
from bagels.managers.accounts import get_account_by_id
from bagels.forms.form import Form, FormField, Option, Options


class AccountForm:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ------------ Blueprints ------------ #

    FORM = Form(
        fields=[
            FormField(
                placeholder="My Account",
                title="Name",
                key="name",
                type="string",
                is_required=True,
            ),
            FormField(
                placeholder="0.00",
                title="Beginning Balance",
                key="beginningBalance",
                type="number",
                default_value="0",
                is_required=True,
            ),
            FormField(
                placeholder="(Optional) Number, purpose etc.",
                title="Description",
                key="description",
                type="string",
            ),
            FormField(
                placeholder="(Optional) dd",
                title="Repayment Date",
                key="repaymentDate",
                type="integer",
            ),
            FormField(
                title="Currency",
                key="currencyCode",
                type="autocomplete",
                options=Options(),
                is_required=True,
                placeholder="Select Currency",
            ),
        ]
    )
    # ------------- Builders ------------- #

    def get_filled_form(self, accountId: int):
        form = copy.deepcopy(self.FORM)
        account = get_account_by_id(accountId)
        main_currency = (
            CONFIG.state.currency.main_currency if CONFIG else get_default_currency_code()
        )
        self._populate_currency_options(form)
        for field in form.fields:
            value = getattr(account, field.key)
            field.default_value = str(value) if value is not None else ""
            if field.key == "currencyCode":
                field.default_value = (value or main_currency).upper()
                field.default_value_text = field.default_value
        return form

    def get_form(self):
        form = copy.deepcopy(self.FORM)
        self._populate_currency_options(form)
        main_currency = (
            CONFIG.state.currency.main_currency if CONFIG else get_default_currency_code()
        )
        for field in form.fields:
            if field.key == "currencyCode":
                field.default_value = main_currency
                field.default_value_text = main_currency
        return form

    def _populate_currency_options(self, form: Form) -> None:
        for field in form.fields:
            if field.key == "currencyCode":
                field.options = Options(
                    items=[
                        Option(text=code, value=code, postfix=name)
                        for code, name in get_currency_items()
                    ]
                )
                return

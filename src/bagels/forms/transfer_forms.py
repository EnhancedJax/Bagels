import copy
from datetime import datetime

from rich.text import Text

from bagels.forms.form import Form, FormField, Option, Options
from bagels.managers.record_templates import get_transfer_templates
from bagels.utils.money import format_amount
from bagels.models.record import Record


class TransferForm:
    _instance = None

    def __new__(cls, *args, **kwargs):
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
                title="Amount",
                key="amount",
                type="number",
                placeholder="0.00",
                min=0,
                is_required=True,
            ),
            FormField(
                title="Destination Amount",
                key="transferToAmount",
                type="number",
                placeholder="0.00 (required for cross-currency)",
                min=0,
                is_required=False,
            ),
            FormField(
                title="Date",
                key="date",
                type="dateAutoDay",
                placeholder="dd (mm) (yy)",
            ),
        ]
    )

    TEMPLATE_FORM = Form(
        fields=[
            FormField(
                title="Label",
                key="label",
                type="string",
                placeholder="Label",
                is_required=True,
            ),
            FormField(
                title="Amount",
                key="amount",
                type="number",
                placeholder="0.00",
                min=0,
                is_required=True,
            ),
            FormField(
                title="Destination Amount",
                key="transferToAmount",
                type="number",
                placeholder="0.00 (required for cross-currency)",
                min=0,
                is_required=False,
            ),
        ]
    )

    # ----------------- - ---------------- #

    def __init__(self, isTemplate: bool = False, defaultDate: str = None):
        self.isTemplate = isTemplate
        self.defaultDate = defaultDate
        self._populate_form_options()

    # region Helpers
    # -------------- Helpers ------------- #

    def _populate_form_options(self):
        templates = get_transfer_templates()
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
        self.FORM.fields[3].default_value = self.defaultDate

    # region Builders
    # ------------- Builders ------------- #

    def get_filled_form(self, record: Record) -> Form:
        """Return a copy of the form with values from the record"""
        filled_form = copy.deepcopy(
            self.FORM if not self.isTemplate else self.TEMPLATE_FORM
        )

        if not record.isTransfer:
            return filled_form, []

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
                case "label":
                    field.default_value = str(value) if value is not None else ""
                    field.type = "string"  # disable autocomplete
                case _:
                    field.default_value = str(value) if value is not None else ""

        return filled_form

    def get_form(self, hidden_fields: dict = {}):
        """Return the base form with default values"""
        form = copy.deepcopy(self.FORM if not self.isTemplate else self.TEMPLATE_FORM)
        for field in form.fields:
            key = field.key
            if key in hidden_fields:
                field.type = "hidden"
                if isinstance(hidden_fields[key], dict):
                    field.default_value = hidden_fields[key]["default_value"]
                    field.default_value_text = hidden_fields[key]["default_value_text"]
                else:
                    field.default_value = hidden_fields[key]
        return form

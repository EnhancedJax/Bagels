from datetime import datetime
from typing import Any, Dict, Tuple

from textual.widget import Widget

from bagels.forms.form import Form, FormField
from bagels.utils.format import parse_formula_expression


# ---------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------
class InvalidFormDataException(Exception):
    """Raised when a form field contains invalid or inconsistent data."""
    pass


class AutocompleteOptionMismatchException(Exception):
    """Raised when a value does not match the expected autocomplete options."""
    pass


# ---------------------------------------------------------------
# Validation Helpers  - Added Custom Exception Handeling
# ---------------------------------------------------------------
def _validate_number(
    value: str, field: FormField, is_float: bool = False
) -> Tuple[bool, str | None, Any]:
    """Validate a number field and return (is_valid, error_message, numeric_value)"""
    if not value:
        if field.is_required:
            raise InvalidFormDataException(f"Field '{field.key}' is required")
        return True, None, None

    try:
        num_val = float(value) if is_float else int(value)
    except ValueError:
        raise InvalidFormDataException(f"Invalid numeric input: {value}")

    if field.min is not None and num_val <= (float(field.min) if is_float else int(field.min)):
        raise InvalidFormDataException(f"Value must be greater than {field.min}")

    if field.max is not None and num_val > (float(field.max) if is_float else int(field.max)):
        raise InvalidFormDataException(f"Value must be less than {field.max}")

    return True, None, num_val


def _validate_date(
    value: str, field: FormField, auto_day: bool = False
) -> Tuple[datetime | None, str | None]:
    """Validate a date field and return (parsed_date, error_message)"""
    if not value or value == "":
        if field.is_required:
            raise InvalidFormDataException(f"Field '{field.key}' is required")
        return None, None

    try:
        if auto_day and value.isdigit():
            this_month = datetime.now().strftime("%m")
            this_year = datetime.now().strftime("%y")
            date = datetime.strptime(f"{value} {this_month} {this_year}", "%d %m %y")
            return date, None
        date = datetime.strptime(value, "%d %m %y")
        return date, None
    except ValueError:
        format_str = "dd (mm) (yy) format" if auto_day else "dd mm yy format"
        raise InvalidFormDataException(f"Invalid date format for field '{field.key}'; must be in {format_str}")


def _validate_autocomplete(
    value: str, held_value: str, field: FormField
) -> Tuple[bool, str | None]:
    """Validate an autocomplete field and return (is_valid, error_message)"""
    if not value and not held_value:
        if field.is_required:
            raise AutocompleteOptionMismatchException(f"Field '{field.key}' requires a selection")
        return True, None

    if not field.options or not field.options.items:
        return True, None

    if field.options.items[0].text:
        matching_items = [item for item in field.options.items if item.text == value]
        if not matching_items:
            raise AutocompleteOptionMismatchException(f"Invalid selection for field '{field.key}'")
        if any(str(item.value) == str(held_value) for item in matching_items):
            return True, None
        else:
            raise AutocompleteOptionMismatchException(f"Invalid selection (not tabbed) for field '{field.key}'")
    else:
        if held_value not in [str(item.value) for item in field.options.items]:
            raise AutocompleteOptionMismatchException(f"Invalid selection for field '{field.key}'")

    return True, None


# ---------------------------------------------------------------
# Main Validation Function - Added Custom Exception Handeling
# ---------------------------------------------------------------
def validateForm(
    formComponent: Widget, formData: Form
) -> Tuple[Dict[str, Any], Dict[str, str], bool]:
    """
    Validates all fields in a form.
    Returns:
        result: dictionary of field_key -> parsed value
        errors: dictionary of field_key -> error message
        isValid: True if all fields are valid
    """
    result = {}
    errors = {}
    isValid = True

    for field in formData.fields:
        fieldKey = field.key
        fieldWidget = formComponent.query_one(f"#field-{fieldKey}")
        fieldValue = (
            fieldWidget.heldValue
            if hasattr(fieldWidget, "heldValue")
            else fieldWidget.value
        )

        try:
            match field.type:
                case "integer":
                    _, _, num_val = _validate_number(fieldValue, field)
                    if num_val is not None:
                        result[fieldKey] = num_val

                case "number":
                    _, _, num_val = _validate_number(fieldValue, field, is_float=True)
                    if num_val is not None:
                        result[fieldKey] = num_val

                case "date":
                    date, _ = _validate_date(fieldValue, field)
                    if date:
                        result[fieldKey] = date

                case "dateAutoDay":
                    date, _ = _validate_date(fieldValue, field, auto_day=True)
                    if date:
                        result[fieldKey] = date

                case "autocomplete":
                    if field.autocomplete_selector:
                        _validate_autocomplete(fieldWidget.value, fieldValue, field)
                        if fieldValue:
                            result[fieldKey] = fieldValue
                    else:
                        if not fieldWidget.value and field.is_required:
                            raise InvalidFormDataException(f"Field '{field.key}' is required")
                        result[fieldKey] = fieldWidget.value

                case _:
                    if not fieldValue and field.is_required:
                        raise InvalidFormDataException(f"Field '{field.key}' is required")
                    result[fieldKey] = fieldValue

        except (InvalidFormDataException, AutocompleteOptionMismatchException) as e:
            errors[fieldKey] = str(e)
            isValid = False

    return result, errors, isValid

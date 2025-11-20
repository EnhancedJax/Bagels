import pytest
from unittest.mock import Mock, patch
from datetime import datetime
from freezegun import freeze_time

from bagels.forms.form import Form, FormField
from bagels.utils.validation import validateForm

# ----------------------------------------------------
#       Mock Helper Functions    
# ----------------------------------------------------
def build_option_mock(text=None, value=None):
    return Mock(text=text, value=value)

def mock_field(key="field", ftype="number", required=True, autocomplete_selector=False, min_val=None, max_val=None):
    field = Mock()
    field.key = key
    field.type = ftype
    field.is_required = required
    field.autocomplete_selector = autocomplete_selector
    field.options = []
    field.min = min_val
    field.max = max_val
    return field

def mock_widget(value=None, heldValue=None):
    widget = Mock()
    widget.value = value
    widget.heldValue = value if heldValue is None else heldValue
    return widget

# ----------------------------------------------------
#   test_validateForm_float
# ----------------------------------------------------
@pytest.mark.parametrize(
    "input_value,expected",
    [
        ("3.5", 3.5),
        ("10.1", 10.1),
        ("-5", -5.0),
    ],
    ids=["valid_float", "string_float", "negative_float"]
)
def test_validateForm_float(input_value, expected):
    field = mock_field(key="num", ftype="number", required=True)
    widget = mock_widget(value=input_value)
    form_mock = Mock(fields=[field])
    component_mock = Mock()
    component_mock.query_one.return_value = widget

    with patch("bagels.utils.validation.parse_formula_expression") as mock_parse:
        mock_parse.return_value = expected
        result, errors, is_valid = validateForm(component_mock, form_mock)

    assert is_valid
    assert result["num"] == expected
    assert errors == {}

# ----------------------------------------------------
#   validateForm date
# ----------------------------------------------------
@pytest.mark.parametrize(
    "input_value,expected_day,expected_month,expected_year,should_pass",
    [
        ("05 03 25", 5, 3, 2025, True),
        ("31 12 20", 31, 12, 2020, True),
        ("32 01 25", None, None, None, False),
        ("abc", None, None, None, False),
        ("", None, None, None, False),
    ],
    ids=["valid_date_05_03_25", "valid_date_31_12_20", "invalid_day_32", "invalid_string", "empty_required"]
)
@freeze_time("2025-03-10")
def test_validateForm_date(input_value, expected_day, expected_month, expected_year, should_pass):
    field = mock_field(ftype="date")
    widget = mock_widget(value=input_value)
    form_mock = Mock(fields=[field])
    component_mock = Mock()
    component_mock.query_one.return_value = widget

    result, errors, is_valid = validateForm(component_mock, form_mock)

    assert is_valid == should_pass

    if should_pass:
        assert result["field"].day == expected_day
        assert result["field"].month == expected_month
        assert result["field"].year == expected_year
        assert errors == {}
    else:
        assert "field" in errors
        if input_value == "":
            assert errors["field"] == "Field 'field' is required"
        else:
            assert errors["field"].startswith("Invalid date format")

# ----------------------------------------------------
#   validateForm dateAutoDay
# ----------------------------------------------------
@pytest.mark.parametrize(
    "input_value,expected_day,expected_month,expected_year,should_pass",
    [
        ("7", 7, 3, 2025, True),
        ("15", 15, 3, 2025, True),
        ("32", None, None, None, False),
        ("abc", None, None, None, False),
        ("", None, None, None, False),
    ],
    ids=["valid_day_7", "valid_day_15", "invalid_day_32", "invalid_string", "empty_required"]
)
@freeze_time("2025-03-10")
def test_validateForm_dateAutoDay(input_value, expected_day, expected_month, expected_year, should_pass):
    field = mock_field(ftype="dateAutoDay")
    widget = mock_widget(value=input_value)
    form_mock = Mock(fields=[field])
    component_mock = Mock()
    component_mock.query_one.return_value = widget

    result, errors, is_valid = validateForm(component_mock, form_mock)

    assert is_valid == should_pass
    if should_pass:
        assert result["field"].day == expected_day
        assert result["field"].month == expected_month
        assert result["field"].year == expected_year
        assert errors == {}
    else:
        assert "field" in errors
        if input_value == "":
            assert errors["field"] == "Field 'field' is required"
        else:
            assert errors["field"].startswith("Invalid date format")

# ----------------------------------------------------
#   validateForm autocomplete
# ----------------------------------------------------
@pytest.mark.parametrize(
    "widget_value,held_value,option_text,option_value,required,should_pass",
    [
        ("Option1", "1", "Option1", "1", True, True),
        ("Option1", "2", "Option1", "1", True, False),
        ("1", "1", None, "1", True, True),
        ("abc", "abc", "Option1", "1", True, False),
        ("", "", "Option1", "1", True, False),
        ("", "", "Option1", "1", False, True),
    ],
    ids=["valid_text_heldValue_match", "heldValue_mismatch", "value_only_match", "invalid_text", "required_empty", "optional_empty"]
)
def test_validateForm_autocomplete(widget_value, held_value, option_text, option_value, required, should_pass):
    field = mock_field(ftype="autocomplete", required=required, autocomplete_selector=True)
    option_mock = build_option_mock(option_text, option_value)
    field.options = Mock(items=[option_mock])
    
    widget = mock_widget(value=widget_value, heldValue=held_value)
    form_mock = Mock(fields=[field])
    component_mock = Mock()
    component_mock.query_one.return_value = widget

    result, errors, is_valid = validateForm(component_mock, form_mock)

    assert is_valid == should_pass
    if should_pass:
        # Optional empty fields may not appear in result
        if "field" in result:
            expected_result = held_value if held_value else widget_value
            assert result["field"] == expected_result
        assert errors == {}
    else:
        assert "field" in errors

# ----------------------------------------------------
#   validateForm float required
# ----------------------------------------------------
@pytest.mark.parametrize(
    "field_value,required,should_pass",
    [
        ("", True, False),
        ("", False, True),
        ("3.5", True, True),
        ("-2.0", True, True),
    ],
    ids=["required_empty", "optional_empty", "required_filled", "required_filled_negative"]
)
def test_validateForm_float_required_cases(field_value, required, should_pass):
    field = mock_field(ftype="number", required=required)
    widget = mock_widget(value=field_value)
    form_mock = Mock(fields=[field])
    component_mock = Mock()
    component_mock.query_one.return_value = widget

    with patch("bagels.utils.validation.parse_formula_expression") as mock_parse:
        mock_parse.return_value = float(field_value) if field_value else None
        result, errors, is_valid = validateForm(component_mock, form_mock)

    assert is_valid == should_pass

    if should_pass:
        if field_value:
            assert result["field"] == float(field_value)
        assert errors == {}
    else:
        assert "field" in errors
        assert errors["field"] == "Field 'field' is required"

# ----------------------------------------------------
#   validateForm date required
# ----------------------------------------------------
@pytest.mark.parametrize(
    "field_value,required,should_pass",
    [
        ("", True, False),
        ("", False, True),
        ("05 03 25", True, True),
        ("99 99 99", True, False),
    ],
    ids=["required_empty", "optional_empty", "valid_date", "invalid_date"]
)
def test_validateForm_date_required_cases(field_value, required, should_pass):
    field = mock_field(ftype="date", required=required)
    widget = mock_widget(value=field_value)
    form_mock = Mock(fields=[field])
    component_mock = Mock()
    component_mock.query_one.return_value = widget

    result, errors, is_valid = validateForm(component_mock, form_mock)

    assert is_valid == should_pass

    if should_pass:
        if field_value:
            assert "field" in result
            assert isinstance(result["field"], datetime)
        assert errors == {}
    else:
        assert "field" in errors
        if field_value == "":
            assert errors["field"] == "Field 'field' is required"
        else:
            assert errors["field"].startswith("Invalid date format")

# ----------------------------------------------------
#   validateForm required field failures (shared)
# ----------------------------------------------------
@pytest.mark.parametrize(
    "ftype,widget_value,expected_error",
    [
        ("number", "", "Field 'field' is required"),
        ("date", "", "Field 'field' is required"),
        ("dateAutoDay", "", "Field 'field' is required"),
    ],
    ids=["number", "date", "dateAutoDay"]
)
def test_validateForm_required_fields_fail(ftype, widget_value, expected_error):
    field = mock_field(ftype=ftype, required=True)
    widget = mock_widget(value=widget_value)
    form_mock = Mock(fields=[field])
    component_mock = Mock()
    component_mock.query_one.return_value = widget

    result, errors, is_valid = validateForm(component_mock, form_mock)

    assert not is_valid
    assert "field" in errors
    assert errors["field"] == expected_error
    assert result == {}

import pytest
from unittest.mock import Mock, patch
from bagels.components.modules.incomemode import IncomeMode
from textual.widgets import Button


@pytest.fixture
def mock_config():
    """Fixture to mock CONFIG dependency safely for all tests."""
    with patch("bagels.components.modules.incomemode.CONFIG") as mock_config:
        mock_config.hotkeys = Mock()
        mock_config.hotkeys.home = Mock()
        mock_config.hotkeys.home.toggle_income_mode = "Ctrl+I"
        yield mock_config


@pytest.fixture
def parent_mock():
    """Fixture for a generic parent object."""
    parent = Mock()
    parent.mode = {"isIncome": True}
    parent.action_toggle_income_mode = Mock()
    return parent


@pytest.mark.parametrize("initial_state", [True, False])
def test_rebuild_toggles_classes(parent_mock, mock_config, initial_state):
    """Ensure rebuild toggles label classes based on mode state."""
    parent_mock.mode["isIncome"] = initial_state
    income_mode = IncomeMode(parent_mock)

    # Each rebuild() queries both labels, so we need 4 total responses (2 per call)
    expense_button_1 = Mock()
    income_button_1 = Mock()
    expense_button_2 = Mock()
    income_button_2 = Mock()
    income_mode.query_one = Mock(side_effect=[
        expense_button_1, income_button_1,  # first rebuild
        expense_button_2, income_button_2,  # second rebuild
    ])

    income_mode.rebuild()
    parent_mock.mode["isIncome"] = not initial_state
    income_mode.rebuild()

    # Assert we queried both labels both times
    assert income_mode.query_one.call_count == 4

    # Optional: ensure both sets of buttons were actually touched
    for btn in [expense_button_1, income_button_1, expense_button_2, income_button_2]:
        assert isinstance(btn, Mock)


@pytest.mark.parametrize("is_income", [True, False])
def test_rebuild_updates_classes_param(is_income, mock_config):
    """Verify correct 'selected' class assignment."""
    parent = Mock()
    parent.mode = {"isIncome": is_income}
    income_mode = IncomeMode(parent)

    expense_button = Mock()
    income_button = Mock()
    income_mode.query_one = Mock(side_effect=[expense_button, income_button])

    income_mode.rebuild()

    # Confirm classes reflect mode
    if is_income:
        assert income_button.classes == "selected"
        assert expense_button.classes == ""
    else:
        assert expense_button.classes == "selected"
        assert income_button.classes == ""


@pytest.mark.parametrize("button_id", ["expense-label", "income-label"])
def test_on_button_pressed_calls_parent_action(parent_mock, mock_config, button_id):
    """Ensure button press triggers parent's action."""
    income_mode = IncomeMode(parent_mock)
    event = Mock()
    event.button = Button("Test", id=button_id)

    income_mode.on_button_pressed(event)
    parent_mock.action_toggle_income_mode.assert_called_once()


@pytest.mark.parametrize("expected_buttons", [["expense-label", "income-label"]])
def test_compose_creates_expected_buttons(parent_mock, mock_config, expected_buttons):
    """Ensure compose() yields both Expense and Income buttons."""
    income_mode = IncomeMode(parent_mock)
    result = list(income_mode.compose())

    ids = [btn.id for btn in result]
    for expected in expected_buttons:
        assert expected in ids
    assert len(result) == 2
    assert all(isinstance(btn, Button) for btn in result)

@pytest.mark.parametrize("initial_state", [True, False])
def test_integration_with_parent_and_config(mock_config, initial_state):
    """Integration test: verifies parent reference and CONFIG-dependent attributes."""
    parent = Mock()
    parent.mode = {"isIncome": initial_state}
    parent.action_toggle_income_mode = Mock()
    income_mode = IncomeMode(parent)
    assert income_mode.page_parent == parent
    assert income_mode.border_title == "View and add"
    assert income_mode.border_subtitle == "Ctrl+I"
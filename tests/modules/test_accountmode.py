import pytest
from unittest.mock import Mock, patch, PropertyMock
from textual.widgets import Button
import sys


@pytest.fixture
def mock_config_module(monkeypatch):
    mock_config = Mock()
    mock_config.hotkeys = Mock()
    mock_config.hotkeys.new = "N"
    mock_config.hotkeys.delete = "D"
    mock_config.hotkeys.edit = "E"

    mock_config.hotkeys.home = Mock()
    mock_config.hotkeys.home.select_prev_account = "<"
    mock_config.hotkeys.home.select_next_account = ">"

    # Had a type error with round_decimals being accessed prior to adding this mock
    mock_config.defaults = Mock()
    mock_config.defaults.round_decimals = 2

    sys.modules["bagels.config"] = Mock(CONFIG=mock_config)
    return mock_config


def test_accountmode_module_rebuild(mock_config_module):
    from bagels.components.modules.accountmode import AccountMode

    account_mode = AccountMode(parent=Mock())
    assert hasattr(account_mode, "rebuild")


def test_accountmode_module_bindings(mock_config_module):
    from bagels.components.modules.accountmode import AccountMode

    account_mode = AccountMode(parent=Mock())
    bindings = {key: action for key, action, _ in account_mode.BINDINGS}

    assert bindings.get(mock_config_module.hotkeys.new) == "new"
    assert bindings.get(mock_config_module.hotkeys.delete) == "delete"
    assert bindings.get(mock_config_module.hotkeys.edit) == "edit"


@pytest.mark.parametrize(
    "accounts_list, expected_items",
    [
        ([], 0),
        ([Mock(name="Checking", balance=100, id=1)], 1),
    ],
)
def test_rebuild_with_mocked_accounts(
    mock_config_module, accounts_list, expected_items
):
    from bagels.components.modules import accountmode

    with patch.object(
        accountmode, "get_all_accounts_with_balance", return_value=accounts_list
    ):
        mock_parent = Mock()
        mock_parent.mode = {"accountId": {"default_value": 1}}
        account_mode = accountmode.AccountMode(parent=mock_parent)

        account_mode.query = Mock(return_value=[Mock()])  # assume accounts are mounted
        mock_balance = Mock()
        mock_container = Mock()
        mock_name = Mock()
        mock_description = Mock()

        # Return the correct widget depending on selector
        def query_one_side_effect(selector):
            if "balance" in selector:
                return mock_balance
            if "container" in selector:
                return mock_container
            if "name" in selector:
                return mock_name
            if "description" in selector:
                return mock_description
            return Mock()

        account_mode.query_one = Mock(side_effect=query_one_side_effect)
        account_mode.scroll_to_widget = Mock()

        # Run the rebuild
        account_mode.rebuild()

        if expected_items == 0:
            # No accounts — should never call query_one
            account_mode.query_one.assert_not_called()
        else:
            # For 1 account, we expect several update calls:
            mock_balance.update.assert_called_once_with(str(accounts_list[0].balance))
            mock_name.update.assert_called_once_with(accounts_list[0].name)
            mock_description.update.assert_called_once_with(
                accounts_list[0].description
            )
            mock_container.classes.startswith("account-container")

            # Should set border title properly
            assert hasattr(account_mode, "border_title")
            assert "Accounts @=" in account_mode.border_title


@pytest.mark.parametrize(
    "Balance, Id, Description",
    [
        (123.45, 99, "Savings"),
        (0.0, 100, ""),
        (50.0, 101, None),
    ],
)
def test_rebuild_updates_account_widgets(mock_config_module, Balance, Id, Description):
    from bagels.components.modules import accountmode

    # Mock one account
    mock_account = Mock(name="Test", balance=Balance, id=Id, description=Description)
    with patch.object(
        accountmode, "get_all_accounts_with_balance", return_value=[mock_account]
    ):
        mock_parent = Mock()
        mock_parent.mode = {"accountId": {"default_value": 99}}
        account_mode = accountmode.AccountMode(parent=mock_parent)

        mock_balance_label = Mock()
        mock_name_label = Mock()
        mock_desc_label = Mock()
        mock_container = Mock()

        account_mode.query_one = Mock(
            side_effect=lambda selector: {
                f"#account-{Id}-balance": mock_balance_label,
                f"#account-{Id}-name": mock_name_label,
                f"#account-{Id}-description": mock_desc_label,
                f"#account-{Id}-container": mock_container,
            }[selector]
        )
        account_mode.query = Mock(return_value=[mock_container])
        account_mode.scroll_to_widget = Mock()

        # Run the rebuild
        account_mode.rebuild()

        mock_balance_label.update.assert_called_once_with(str(Balance))
        mock_desc_label.update.assert_called_once_with(Description)

        if Description in ("", None):
            mock_desc_label.add_class.assert_called_once_with("none")
            mock_desc_label.remove_class.assert_not_called()
        else:
            mock_desc_label.remove_class.assert_called_once_with("none")
            mock_desc_label.add_class.assert_not_called()

        # Check selection logic
        if Id == 99:
            assert "selected" in mock_container.classes
            account_mode.scroll_to_widget.assert_called_once_with(mock_container)
        else:
            assert "selected" not in mock_container.classes
            account_mode.scroll_to_widget.assert_not_called()


@pytest.mark.parametrize(
    "account_selected, expected_push_screen, expected_notify",
    [
        (42, 1, 0),
        (None, 0, 1),
        (100, 1, 0),
    ],
)
def test_action_edit_account_param(
    mock_config_module, account_selected, expected_push_screen, expected_notify
):
    from bagels.components.modules import accountmode

    mock_parent = Mock()
    mock_parent.mode = {"accountId": {"default_value": account_selected}}
    account_mode = accountmode.AccountMode(parent=mock_parent)

    mock_app = Mock()
    with patch.object(
        accountmode.AccountMode, "app", new_callable=PropertyMock
    ) as mock_app_prop:
        mock_app_prop.return_value = mock_app

        account_mode.account_form.get_filled_form = Mock(
            return_value={"name": "Example"}
        )

        account_mode.action_edit()

        assert mock_app.push_screen.call_count == expected_push_screen
        assert mock_app.notify.call_count == expected_notify

        if expected_push_screen:
            screen = mock_app.push_screen.call_args[0][0]
            assert hasattr(screen, "title")
            assert "Edit" in screen.title

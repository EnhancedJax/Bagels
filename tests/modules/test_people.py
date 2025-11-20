import pytest
from unittest.mock import Mock, patch, PropertyMock
from textual.widgets import Button
import sys


@pytest.fixture
def mock_config_module(monkeypatch):
    mock_config = Mock()
    mock_config.hotkeys = Mock()
    mock_config.hotkeys.edit = "E"
    mock_config.hotkeys.delete = "D"

    # Insert the mock CONFIG module before import
    sys.modules["bagels.config"] = Mock(CONFIG=mock_config)
    return mock_config


def test_people_module_rebuild(mock_config_module):
    from bagels.components.modules.people import (
        People,
    )  # Import AFTER patch to prevent config break

    people_module = People()
    assert hasattr(people_module, "rebuild")


def test_people_module_bindings(mock_config_module):
    from bagels.components.modules.people import (
        People,
    )  # Import AFTER patch to prevent config break

    people_module = People()
    bindings = {binding.key: binding.action for binding in people_module.BINDINGS}
    assert bindings.get(mock_config_module.hotkeys.edit) == "edit_person"
    assert bindings.get(mock_config_module.hotkeys.delete) == "delete_person"


@pytest.mark.parametrize(
    "people_list, expected_calls",
    [
        ([], 0),
        ([Mock(name="Alice", due=10, id=1)], 1),
    ],
)
def test_rebuild_with_mocked_persons(mock_config_module, people_list, expected_calls):
    from bagels.components.modules import (
        people,
    )  # Import AFTER patch to prevent config break

    with patch.object(people, "get_persons_with_net_due", return_value=people_list):
        mock_table = Mock()
        mock_indicator = Mock()

        mock_table.columns = []
        mock_table.add_columns = Mock()
        mock_table.add_row = Mock()
        mock_table.clear = Mock()

        mock_query_one = Mock(side_effect=[mock_table, mock_indicator])

        p = people.People()
        p.query_one = mock_query_one

        p.rebuild()

        assert mock_table.add_row.call_count == expected_calls
        assert mock_indicator.display == (not people_list)


@pytest.mark.parametrize("has_row", [False, True])
def test_action_delete_person(mock_config_module, has_row):
    from bagels.components.modules import (
        people,
    )  # Import AFTER patch to prevent config break

    p = people.People()
    p.rebuild = Mock()

    mock_app = Mock()
    mock_form = Mock()
    mock_form.get_filled_form.return_value = {"name": "Bob"}

    with patch.object(
        people.People, "app", new_callable=PropertyMock, return_value=mock_app
    ):
        if has_row:
            p.current_row = 1
            mock_person = Mock(name="Alice")
            with (
                patch.object(people, "get_person_by_id", return_value=mock_person),
                patch.object(people, "delete_person") as mock_delete,
            ):
                p.action_delete_person()
                p.app.push_screen.assert_called_once()
                callback = p.app.push_screen.call_args[0][1]
                callback(True)
                mock_delete.assert_called_once_with(1)
                p.rebuild.assert_called_once()
        else:
            p.current_row = None
            p.action_delete_person()
            p.app.notify.assert_called_once_with(
                title="Error",
                message="A person must be selected for this action.",
                severity="error",
                timeout=2,
            )


def test_action_delete_check_delete(mock_config_module):
    from bagels.components.modules import (
        people,
    )  # Import AFTER patch to prevent config break

    p = people.People()
    p.rebuild = Mock()
    p.current_row = 1

    mock_app = Mock()

    with patch.object(
        people.People, "app", new_callable=PropertyMock, return_value=mock_app
    ):
        mock_person = Mock(name="Alice")
        with (
            patch.object(people, "get_person_by_id", return_value=mock_person),
            patch.object(people, "delete_person", return_value=True) as mock_delete,
        ):
            p.action_delete_person()
            p.app.push_screen.assert_called_once()
            callback = p.app.push_screen.call_args[0][1]
            callback(True)
            mock_delete.assert_called_once_with(1)

            p.rebuild.assert_called_once()


def test_action_delete_person_no_selection(mock_config_module):
    from bagels.components.modules import (
        people,
    )  # Import AFTER patch to prevent config break

    p = people.People()
    p.current_row = None

    mock_app = Mock()

    with patch.object(
        people.People, "app", new_callable=PropertyMock, return_value=mock_app
    ):
        p.action_delete_person()
        mock_app.notify.assert_called_once_with(
            title="Error",
            message="A person must be selected for this action.",
            severity="error",
            timeout=2,
        )


def test_action_edit_person_success(mock_config_module):
    from bagels.components.modules import (
        people,
    )  # Import AFTER patch to prevent config break

    p = people.People()
    p.rebuild = Mock()
    p.current_row = 123

    mock_app = Mock()
    mock_form = Mock()
    mock_form.get_filled_form.return_value = {"name": "Bob"}

    with (
        patch.object(
            people.People, "app", new_callable=PropertyMock, return_value=mock_app
        ),
        patch.object(people, "PersonForm", return_value=mock_form),
        patch.object(people, "update_person") as mock_update,
    ):
        p.action_edit_person()

        mock_app.push_screen.assert_called_once()

        callback = mock_app.push_screen.call_args[1]["callback"]
        callback({"name": "Bob"})

        mock_update.assert_called_once_with(123, {"name": "Bob"})
        mock_app.notify.assert_any_call(
            title="Success",
            message="Person Bob updated",
            severity="information",
            timeout=3,
        )
        p.rebuild.assert_called_once()


def test_action_edit_person_no_selection(mock_config_module):
    from bagels.components.modules import (
        people,
    )  # Import AFTER patch to prevent config break

    p = people.People()
    p.current_row = None

    mock_app = Mock()

    with patch.object(
        people.People, "app", new_callable=PropertyMock, return_value=mock_app
    ):
        p.action_edit_person()
        mock_app.notify.assert_called_once_with(
            title="Error",
            message="A person must be selected for this action.",
            severity="error",
            timeout=2,
        )

from types import SimpleNamespace
from unittest.mock import PropertyMock

import importlib
import pytest

from bagels import config as bagels_config

if bagels_config.CONFIG is None:
    bagels_config.CONFIG = bagels_config.Config.get_default()

people_module = importlib.import_module("bagels.components.modules.people")
People = people_module.People


class DummyApp:
    def __init__(self):
        self.notifications = []
        self.last_screen = None

    def notify(self, **payload):
        self.notifications.append(payload)

    def push_screen(self, modal, callback):
        self.last_screen = (modal, callback)


@pytest.fixture
def people_instance(mocker):
    mock_app = DummyApp()
    mocker.patch.object(People, "app", new_callable=PropertyMock, return_value=mock_app)
    people = People()
    people.current_row = None
    return people


class TestPeopleModule:
    def test_on_data_table_row_highlighted_updates_current_row(self, people_instance):
        event = SimpleNamespace(row_key=SimpleNamespace(value=42))
        people_instance.on_data_table_row_highlighted(event)
        assert people_instance.current_row == 42

    @pytest.mark.parametrize(
        "action_name",
        ["action_delete_person", "action_edit_person"],
    )
    def test_actions_without_selection_trigger_notification(
        self, people_instance, mocker, action_name
    ):
        notifier = mocker.spy(people_instance, "_notify_no_select")
        getattr(people_instance, action_name)()
        notifier.assert_called_once()

    def test_action_delete_person_confirms_and_deletes(
        self, people_instance, mocker
    ):
        delete_person = mocker.patch.object(people_module, "delete_person")
        mocker.patch.object(
            people_module,
            "get_person_by_id",
            return_value=SimpleNamespace(name="Casey"),
        )
        people_instance.rebuild = mocker.MagicMock()
        people_instance.current_row = 3

        people_instance.action_delete_person()
        assert people_instance.app.last_screen is not None
        _, callback = people_instance.app.last_screen

        callback(True)

        delete_person.assert_called_once_with(3)
        people_instance.rebuild.assert_called_once()

    def test_action_delete_person_handles_delete_error(
        self, people_instance, mocker
    ):
        mocker.patch.object(
            people_module,
            "get_person_by_id",
            return_value=SimpleNamespace(name="Quinn"),
        )
        mocker.patch.object(
            people_module, "delete_person", side_effect=RuntimeError("db down")
        )
        people_instance.rebuild = mocker.MagicMock()
        people_instance.current_row = 7

        people_instance.action_delete_person()
        _, callback = people_instance.app.last_screen
        callback(True)

        assert people_instance.app.notifications
        assert people_instance.app.notifications[-1]["severity"] == "error"

    def test_action_delete_person_cancel_does_not_call_delete(
        self, people_instance, mocker
    ):
        delete_person = mocker.patch.object(people_module, "delete_person")
        mocker.patch.object(
            people_module,
            "get_person_by_id",
            return_value=SimpleNamespace(name="River"),
        )
        people_instance.current_row = 9

        people_instance.action_delete_person()
        _, callback = people_instance.app.last_screen
        callback(False)

        delete_person.assert_not_called()

    def test_action_edit_person_updates_successfully(
        self, people_instance, mocker
    ):
        mocker.patch.object(
            people_module,
            "get_person_by_id",
            return_value=SimpleNamespace(name="Parker"),
        )
        update_person = mocker.patch.object(
            people_module, "update_person", return_value=SimpleNamespace()
        )
        mocker.patch.object(
            people_module,
            "PersonForm",
            return_value=SimpleNamespace(
                get_filled_form=lambda _id: {"name": "Taylor"}
            ),
        )
        mocker.patch.object(
            people_module, "InputModal", return_value="modal"
        )
        people_instance.rebuild = mocker.MagicMock()
        people_instance.current_row = 1

        people_instance.action_edit_person()
        _, callback = people_instance.app.last_screen
        callback({"name": "Morgan"})

        update_person.assert_called_once_with(1, {"name": "Morgan"})
        assert people_instance.app.notifications[-1]["severity"] == "information"
        people_instance.rebuild.assert_called_once()

    def test_action_edit_person_handles_update_error(
        self, people_instance, mocker
    ):
        mocker.patch.object(
            people_module,
            "PersonForm",
            return_value=SimpleNamespace(
                get_filled_form=lambda _id: {"name": "Taylor"}
            ),
        )
        mocker.patch.object(
            people_module, "InputModal", return_value="modal"
        )
        mocker.patch.object(
            people_module,
            "update_person",
            side_effect=RuntimeError("cannot update"),
        )
        mocker.patch.object(
            people_module,
            "get_person_by_id",
            return_value=SimpleNamespace(name="Parker"),
        )
        people_instance.current_row = 12

        people_instance.action_edit_person()
        _, callback = people_instance.app.last_screen
        callback({"name": "New Name"})

        assert people_instance.app.notifications
        assert people_instance.app.notifications[-1]["severity"] == "error"

import pytest
from unittest import mock
from bagels.modals import record
from bagels.managers import record_templates
from bagels.models.account import Account
from bagels.models.category import Category, Nature
from bagels.models.database.db import Base

# from bagels.modals.record import RecordModal
from bagels.config import CONFIG
from bagels.modals.record import Binding

import pytest
from unittest.mock import MagicMock

from unittest.mock import MagicMock, patch


@pytest.fixture(scope="module", autouse=True)
def patch_config():
    with patch("bagels.modals.record.CONFIG") as mock_config:
        mock_config.hotkeys.record_modal.new_split = "ctrl+n"
        mock_config.hotkeys.record_modal.new_paid_split = "ctrl+p"
        mock_config.hotkeys.record_modal.delete_last_split = "ctrl+d"
        mock_config.hotkeys.record_modal.submit_and_template = "ctrl+s"
        yield


@pytest.fixture
def subject():
    """Create a test instance with mocked dependencies."""
    BINDINGS = [
        Binding(
            CONFIG.hotkeys.record_modal.new_split,
            "add_split",
            "+split",
            priority=True,
        ),
        Binding(
            CONFIG.hotkeys.record_modal.new_paid_split,
            "add_paid_split",
            "+paid split",
            priority=True,
        ),
        Binding(
            CONFIG.hotkeys.record_modal.delete_last_split,
            "delete_last_split",
            "-last split",
            priority=True,
        ),
        Binding(
            CONFIG.hotkeys.record_modal.submit_and_template,
            "submit_and_template",
            "Submit & Template",
            priority=True,
        ),
    ]

    from bagels.modals.record import RecordModal

    obj = RecordModal(title="Test Title")

    # Mock methods that interact with the UI or external objects
    obj.query_one = MagicMock()
    mock_container = MagicMock()
    obj.query_one.return_value = mock_container

    obj.record_form = MagicMock()
    mock_form = MagicMock()
    mock_form.fields = []
    obj.record_form.get_split_form.return_value = mock_form

    obj.splitForm = MagicMock()
    obj.splitForm.fields = []

    obj._get_split_widget = MagicMock(return_value="widget")

    # Set a known starting state
    obj.splitCount = 0

    return obj


def test_action_add_split_calls_and_increments(subject):
    """Verify that action_add_split calls mount and increments splitCount."""
    subject.action_add_split(paid=False)

    # Verify that query_one was called for the container
    subject.query_one.assert_any_call("#splits-container", object)

    # Verify that mount was called with the expected widget
    mock_container = subject.query_one.return_value
    mock_container.mount.assert_called_once_with("widget")

    # Verify that splitCount was incremented
    assert subject.splitCount == 1


def test_action_add_paid_split_calls_action_add_split(subject):
    """Verify that action_add_paid_split calls action_add_split with paid=True."""
    subject.action_add_split = MagicMock()
    subject.action_add_paid_split()
    subject.action_add_split.assert_called_once_with(paid=True)

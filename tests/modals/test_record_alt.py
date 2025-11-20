import pytest
from unittest import mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from bagels.models.database.db import Base

import sys
import types
import pytest


# ---- Patch CONFIG before import to avoid AttributeError ---- #
class DummyRecordModalHotkeys:
    new_split = "ctrl+n"
    new_paid_split = "ctrl+p"
    delete_last_split = "ctrl+d"
    submit_and_template = "ctrl+s"


class DummyHotkeys:
    record_modal = DummyRecordModalHotkeys()


class DummyConfig:
    hotkeys = DummyHotkeys()


sys.modules["bagels.config"] = types.SimpleNamespace(CONFIG=DummyConfig())

# ---- Now safe to import the module ---- #
from bagels.modals import record
import bagels.modals.record as record
import bagels.managers.record_templates as rt
from bagels.modals import record
from bagels.models.account import Account
from bagels.models.category import Category, Nature
from bagels.managers import record_templates


# ---- Fixtures ---- #
@pytest.fixture(params=[True, False])
def record_modal(monkeypatch, request):
    """Create a RecordModal instance with DB dependencies mocked out."""
    # Mock all DB calls to prevent hitting nonexistent tables
    monkeypatch.setattr(record, "get_all_persons", lambda: [])
    monkeypatch.setattr(record, "get_all_accounts_with_balance", lambda: [])
    # monkeypatch.setattr(record, "get_all_record_templates", lambda: [])

    # If RecordModal internally imports models, mock those too
    monkeypatch.setattr(record, "record_templates", mock.Mock(), raising=False)
    monkeypatch.setattr(record.record_templates, "get_all", classmethod(lambda cls: []))
    monkeypatch.setattr(record.record_templates, "query", mock.Mock())

    split_form = record.RecordForm()
    modal = record.RecordModal(
        title="Test Record Modal",
        splitForm=split_form,
        isEditing=request.param,
    )
    return modal


# ---- Tests ---- #
def test_action_add_split(record_modal):
    """Ensure add_split increases split count and appends fields."""
    initial_count = record_modal.splitCount
    record_modal.action_add_split()
    assert record_modal.splitCount == initial_count + 1
    assert (
        len(record_modal.splitForm)
        == record_modal.splitFormOneLength * record_modal.splitCount
    )


# def test_action_add_paid_split(record_modal):
#     """Ensure add_paid_split calls add_split and increments correctly."""
#     initial_count = record_modal.splitCount
#     record_modal.action_add_paid_split()
#     assert record_modal.splitCount == initial_count + 1


# def test_action_delete_last_split(record_modal):
#     """Ensure delete_last_split decrements the count safely."""
#     record_modal.action_add_split()  # ensure there's something to delete
#     initial_count = record_modal.splitCount
#     record_modal.action_delete_last_split()
#     assert record_modal.splitCount == max(initial_count - 1, 0)


# def test_action_submit_and_template(record_modal):
#     """Ensure submit_and_template sets shift_pressed and calls action_submit."""
#     with mock.patch.object(record_modal, "action_submit") as mock_submit:
#         record_modal.action_submit_and_template()
#         assert record_modal.shift_pressed is True
#         mock_submit.assert_called_once()


# def test_action_submit_success(record_modal):
#     """Ensure successful submission calls dismiss with expected payload."""
#     # Mock validateForm for both form and splitForm validation
#     with (
#         mock.patch(
#             "bagels.modals.record.validateForm",
#             side_effect=[
#                 ({"record": "ok"}, {}, True),
#                 ({"split0": "ok"}, {}, True),
#             ],
#         ) as mock_validate,
#         mock.patch.object(record_modal, "dismiss") as mock_dismiss,
#     ):
#         record_modal.action_submit()

#         assert mock_validate.call_count == 2
#         mock_dismiss.assert_called_once()
#         args, kwargs = mock_dismiss.call_args
#         result = args[0]
#         assert "record" in result
#         assert "splits" in result
#         assert isinstance(result["splits"], list)


# def test_action_submit_failure(record_modal):
#     """Ensure failed validation calls _update_errors instead of dismiss."""
#     with (
#         mock.patch(
#             "bagels.modals.record.validateForm",
#             side_effect=[
#                 ({}, {"label": "error"}, False),
#                 ({}, {}, True),
#             ],
#         ) as mock_validate,
#         mock.patch.object(record_modal, "_update_errors") as mock_update,
#         mock.patch.object(record_modal, "dismiss") as mock_dismiss,
#     ):
#         record_modal.action_submit()

#         mock_update.assert_called_once()
#         mock_dismiss.assert_not_called()


# def test_get_splits_from_result(record_modal):
#     """Verify helper returns correct split dictionary structure."""
#     record_modal.splitCount = 2
#     result_form = {
#         "personId-0": 1,
#         "amount-0": 10,
#         "isPaid-0": True,
#         "accountId-0": 2,
#         "paidDate-0": "2025-01-01",
#         "personId-1": 3,
#         "amount-1": 20,
#         "isPaid-1": False,
#         "accountId-1": 4,
#         "paidDate-1": "2025-01-02",
#     }
#     splits = record_modal._get_splits_from_result(result_form)
#     assert len(splits) == 2
#     assert splits[0]["amount"] == 10
#     assert splits[1]["personId"] == 3

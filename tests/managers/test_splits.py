from datetime import datetime
from typing import Dict

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from bagels.managers import splits
from bagels import config as bagels_config
from bagels.models.account import Account
from bagels.models.database.db import Base
from bagels.models.person import Person
from bagels.models.record import Record
from bagels.models.split import Split
import bagels.models.record as record_model
import bagels.models.split as split_model

if bagels_config.CONFIG is None:
    bagels_config.CONFIG = bagels_config.Config.get_default()
record_model.CONFIG = bagels_config.CONFIG
split_model.CONFIG = bagels_config.CONFIG


@pytest.fixture
def split_env() -> Dict[str, int]:
    """Provide an isolated in-memory database and base record/person data."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    original_session_factory = splits.Session
    splits.Session = sessionmaker(bind=engine)

    with splits.Session() as session:
        account = Account(
            name="Test Account",
            description="For split tests",
            beginningBalance=0.0,
            repaymentDate=None,
            hidden=False,
        )
        session.add(account)
        session.commit()
        session.refresh(account)

        person = Person(name="Alice")
        session.add(person)
        session.commit()
        session.refresh(person)

        record = Record(
            label="Groceries",
            amount=100.0,
            date=datetime.now(),
            accountId=account.id,
            account=account,
            isIncome=False,
            isTransfer=False,
        )
        session.add(record)
        session.commit()
        session.refresh(record)

        record_id = record.id
        person_id = person.id
        account_id = account.id

    yield {
        "record_id": record_id,
        "person_id": person_id,
        "account_id": account_id,
    }

    Base.metadata.drop_all(engine)
    splits.Session = original_session_factory


def _create_split(record_id: int, person_id: int, account_id: int, **overrides):
    payload = {
        "recordId": record_id,
        "personId": person_id,
        "accountId": account_id,
        "amount": 50.0,
        "isPaid": False,
        "paidDate": None,
    }
    payload.update(overrides)
    return splits.create_split(payload)


class TestSplitManager:
    @pytest.mark.parametrize(
        ("amount", "is_paid"),
        [
            (45.5, False),
            (10.0, True),
            (99.9, False),
        ],
    )
    def test_create_split_persists_new_entry(
        self, split_env, amount, is_paid
    ):
        new_split = _create_split(
            split_env["record_id"],
            split_env["person_id"],
            split_env["account_id"],
            amount=amount,
            isPaid=is_paid,
            paidDate=datetime.now() if is_paid else None,
        )

        assert new_split.id is not None

        with splits.Session() as session:
            stored = session.get(Split, new_split.id)
            assert stored is not None
            assert stored.personId == split_env["person_id"]
            assert stored.amount == amount
            assert stored.isPaid == is_paid

    def test_get_splits_by_record_id_returns_all_matches(self, split_env):
        _create_split(split_env["record_id"], split_env["person_id"], split_env["account_id"])
        _create_split(
            split_env["record_id"],
            split_env["person_id"],
            split_env["account_id"],
            amount=30.0,
        )

        results = splits.get_splits_by_record_id(split_env["record_id"])
        assert len(results) == 2
        assert {split.amount for split in results} == {50.0, 30.0}

    def test_get_split_by_id_returns_split(self, split_env):
        created = _create_split(
            split_env["record_id"], split_env["person_id"], split_env["account_id"]
        )

        fetched = splits.get_split_by_id(created.id)
        assert fetched is not None
        assert fetched.id == created.id

    @pytest.mark.parametrize("missing_id", [9999, -1, 0])
    def test_get_split_by_id_returns_none_for_missing(
        self, split_env, missing_id
    ):
        assert splits.get_split_by_id(missing_id) is None

    def test_update_split_updates_attributes(self, split_env, mocker):
        created = _create_split(
            split_env["record_id"], split_env["person_id"], split_env["account_id"]
        )

        session_spy = mocker.spy(splits, "Session")
        updated = splits.update_split(created.id, {"amount": 75.0, "isPaid": True})
        assert updated is not None
        assert session_spy.call_count >= 1

        with splits.Session() as session:
            stored = session.get(Split, created.id)
            assert stored.amount == 75.0
            assert stored.isPaid is True

    def test_update_split_returns_none_for_missing_id(self, split_env):
        assert splits.update_split(9999, {"amount": 20.0}) is None

    def test_delete_split_removes_entry(self, split_env, mocker):
        created = _create_split(
            split_env["record_id"], split_env["person_id"], split_env["account_id"]
        )
        session_spy = mocker.spy(splits, "Session")

        deleted = splits.delete_split(created.id)
        assert deleted is not None
        assert deleted.id == created.id
        assert session_spy.call_count >= 1

        with splits.Session() as session:
            assert session.get(Split, created.id) is None

    @pytest.mark.parametrize("missing_id", [4242, -5, 0])
    def test_delete_split_returns_none_when_missing(
        self, split_env, missing_id
    ):
        assert splits.delete_split(missing_id) is None

    def test_delete_splits_by_record_id_clears_all(self, split_env):
        _create_split(split_env["record_id"], split_env["person_id"], split_env["account_id"])
        _create_split(split_env["record_id"], split_env["person_id"], split_env["account_id"])

        splits.delete_splits_by_record_id(split_env["record_id"])

        with splits.Session() as session:
            remaining = (
                session.query(Split)
                .filter(Split.recordId == split_env["record_id"])
                .all()
            )
            assert remaining == []

    def test_create_split_closes_session_on_failure(self, mocker):
        fake_session = mocker.MagicMock()
        fake_session.commit.side_effect = RuntimeError("boom")
        mocker.patch.object(splits, "Session", return_value=fake_session)

        with pytest.raises(RuntimeError):
            splits.create_split(
                {
                    "recordId": 1,
                    "personId": 1,
                    "accountId": 1,
                    "amount": 10.0,
                    "isPaid": False,
                    "paidDate": None,
                }
            )

        fake_session.add.assert_called_once()
        fake_session.close.assert_called_once()

    def test_get_split_by_id_closes_session_on_error(self, mocker):
        fake_session = mocker.MagicMock()
        fake_session.query.return_value.get.side_effect = RuntimeError("db down")
        mocker.patch.object(splits, "Session", return_value=fake_session)

        with pytest.raises(RuntimeError):
            splits.get_split_by_id(101)

        fake_session.close.assert_called_once()

    def test_delete_splits_by_record_id_closes_session_on_error(
        self, mocker
    ):
        fake_session = mocker.MagicMock()
        fake_delete = fake_session.query.return_value.filter_by.return_value.delete
        fake_delete.side_effect = RuntimeError("constraint failure")
        mocker.patch.object(splits, "Session", return_value=fake_session)

        with pytest.raises(RuntimeError):
            splits.delete_splits_by_record_id(33)

        fake_session.close.assert_called_once()

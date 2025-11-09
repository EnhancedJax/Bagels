from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload, sessionmaker

from bagels.managers.splits import create_split, get_splits_by_record_id, update_split
from bagels.managers.utils import get_operator_amount, get_start_end_of_period
from bagels.models.account import Account
from bagels.models.category import Category
from bagels.models.database.app import db_engine
from bagels.models.record import Record
from bagels.models.split import Split

Session = sessionmaker(bind=db_engine)


# Custom exceptions for records manager
class RecordNotFoundException(Exception):
    """Raised when a record with the requested id cannot be found.

    Attributes:
        record_id -- id of the record that was not found
    """


class InvalidRecordDataException(Exception):
    """Raised when provided record data is invalid or missing required fields."""


class DatabaseOperationException(Exception):
    """Raised when an underlying database operation fails.

    The original exception is chained on raise to preserve context.
    """



# region Create
def create_record(record_data: dict):
    """Create a Record from a mapping of values.

    Raises:
        InvalidRecordDataException: If record_data is not a dict or missing required keys.
        DatabaseOperationException: If an underlying DB error occurs.
    """
    if not isinstance(record_data, dict):
        raise InvalidRecordDataException("record_data must be a dict")

    session = Session()
    try:
        record = Record(**record_data)
        session.add(record)
        session.commit()
        session.refresh(record)
        session.expunge(record)
        return record
    except SQLAlchemyError as e:
        # Wrap DB errors in a project-specific exception for callers/tests
        raise DatabaseOperationException("Failed to create record") from e
    finally:
        session.close()


def create_record_and_splits(record_data: dict, splits_data: list[dict]):
    """Create a record and associated splits.

    Raises:
        InvalidRecordDataException: If inputs are of incorrect types.
        DatabaseOperationException: If any DB operation fails.
    """
    if not isinstance(splits_data, list):
        raise InvalidRecordDataException("splits_data must be a list of mappings")

    session = Session()
    try:
        record = create_record(record_data)
        for split in splits_data:
            if not isinstance(split, dict):
                raise InvalidRecordDataException("each split must be a dict")
            split["recordId"] = record.id
            create_split(split)
        return record
    except SQLAlchemyError as e:
        raise DatabaseOperationException("Failed to create record and splits") from e
    finally:
        session.close()


# region Get
def get_record_by_id(record_id: int, populate_splits: bool = False):
    session = Session()
    try:
        query = session.query(Record).options(
            joinedload(Record.category), joinedload(Record.account)
        )

        if populate_splits:
            query = query.options(
                joinedload(Record.splits).options(
                    joinedload(Split.account), joinedload(Split.person)
                )
            )

        record = query.get(record_id)
        if not record:
            # Documented exception: raised when the requested record does not exist
            raise RecordNotFoundException(f"No record found for id={record_id}")
        return record
    finally:
        session.close()


def get_record_total_split_amount(record_id: int):
    session = Session()
    try:
        splits = get_splits_by_record_id(record_id)
        if splits is None:
            raise RecordNotFoundException(f"No splits found for record id={record_id}")
        return sum((getattr(split, "amount", 0) or 0) for split in splits)
    finally:
        session.close()


def get_records(
    offset: int = 0,
    offset_type: str = "month",
    account_id: int = None,
    category_piped_names: str = None,
    operator_amount: str = None,
    label: str = None,
):
    session = Session()
    try:
        query = session.query(Record).options(
            joinedload(Record.category),
            joinedload(Record.account),
            joinedload(Record.transferToAccount),
            joinedload(Record.splits).options(
                joinedload(Split.account), joinedload(Split.person)
            ),
        )

        start_of_period, end_of_period = get_start_end_of_period(offset, offset_type)
        query = query.filter(
            Record.date >= start_of_period, Record.date < end_of_period
        )

        if account_id not in [None, ""]:
            query = query.filter(Record.accountId == account_id)
        if category_piped_names not in [None, ""]:
            category_names = category_piped_names.split("|")
            query = query.join(Record.category).filter(
                Category.name.in_(category_names)
            )
        if operator_amount not in [None, ""]:
            try:
                operator, amount = get_operator_amount(operator_amount)
            except Exception as e:
                raise InvalidRecordDataException(
                    f"Invalid operator_amount format: {operator_amount}"
                ) from e
            if operator and amount:
                query = query.filter(Record.amount.op(operator)(amount))
        if label not in [None, ""]:
            query = query.filter(Record.label.ilike(f"%{label}%"))

        createdAt_column = getattr(Record, "createdAt")
        date_column = func.date(getattr(Record, "date"))
        query = query.order_by(date_column.desc(), createdAt_column.desc())

        records = query.all()
        return records
    except SQLAlchemyError as e:
        raise DatabaseOperationException("Failed to query records") from e
    finally:
        session.close()


def _get_spending_records(session, start_date, end_date):
    """Common function to fetch records for spending calculations"""
    return (
        session.query(Record)
        .filter(
            Record.isIncome == False,  # noqa: E712
            Record.date >= start_date,
            Record.date < end_date,
            Record.isTransfer == False,  # noqa: E712
        )
        .options(joinedload(Record.splits))
        .all()
    )


def _calculate_daily_spending(records, start_date, end_date, cumulative=False):
    """Calculate daily spending with optional cumulative sum"""
    daily_spending = {}
    for record in records:
        date_key = record.date.date()
        splits_sum = sum(split.amount for split in record.splits)
        actual_spend = record.amount - splits_sum
        daily_spending[date_key] = daily_spending.get(date_key, 0) + actual_spend

    current_date = start_date.date()
    end_date_normalized = end_date.date()
    today = datetime.today().date()
    result = []
    running_total = 0

    while current_date <= end_date_normalized:
        if current_date <= today:
            daily_amount = daily_spending.get(current_date, 0)
            if cumulative:
                running_total += daily_amount
                result.append(running_total)
            else:
                result.append(daily_amount)
        current_date += timedelta(days=1)

    return result


def get_spending(start_date, end_date) -> list[float]:
    """Gets a list of spent amounts for each day in the period, less split amounts of the records"""
    session = Session()
    try:
        records = _get_spending_records(session, start_date, end_date)
        return _calculate_daily_spending(
            records, start_date, end_date, cumulative=False
        )
    except SQLAlchemyError as e:
        raise DatabaseOperationException("Failed to calculate spending") from e
    finally:
        session.close()


def get_spending_trend(start_date, end_date) -> list[float]:
    """Gets a cumulative list of spent amounts for each day in the period"""
    session = Session()
    try:
        records = _get_spending_records(session, start_date, end_date)
        return _calculate_daily_spending(records, start_date, end_date, cumulative=True)
    except SQLAlchemyError as e:
        raise DatabaseOperationException("Failed to calculate spending trend") from e
    finally:
        session.close()


def is_record_all_splits_paid(record_id: int):
    session = Session()
    try:
        splits = get_splits_by_record_id(record_id)
        if splits is None:
            raise RecordNotFoundException(f"No splits found for record id={record_id}")
        return all(getattr(split, "isPaid", False) for split in splits)
    finally:
        session.close()


def get_daily_balance(start_date, end_date) -> list[float]:
    """Gets a list of account balances for each day in the period"""
    # Calculating net beginning balance

    # Handle records up till start_date, then process each day one by one.

    # Records.isIncome ? add : subtract

    # for Record.splits => Record.isIncome ? subtract Split.amount : add Split.amount

    # Record.isTransfer ? Record.transferToAccount.name == "Outside source" ? subtract : Record.account.name == "Outside source" ? add : ignore

    # return result
    session = Session()
    try:
        accounts = session.query(Account).filter(Account.deletedAt.is_(None)).all()
        total_balance = sum(a.beginningBalance for a in accounts)
        old_records = (
            session.query(Record)
            .filter(
                Record.date < start_date, Record.accountId.in_([a.id for a in accounts])
            )
            .options(
                joinedload(Record.splits),
                joinedload(Record.account),
                joinedload(Record.transferToAccount),
            )
            .all()
        )

        def adjust_balance(r):
            if r.isTransfer:
                if r.transferToAccount and r.transferToAccount.name == "Outside source":
                    return -r.amount
                if r.account and r.account.name == "Outside source":
                    return r.amount
                return 0
            if r.isIncome:
                return r.amount - sum(s.amount for s in r.splits)
            return -r.amount + sum(s.amount for s in r.splits)

        for rec in old_records:
            total_balance += adjust_balance(rec)

        results = []
        current = start_date
        today = datetime.today()
        while current <= end_date:
            if current > today:
                break
            day_records = (
                session.query(Record)
                .filter(
                    func.date(Record.date) == current.date(),
                    Record.accountId.in_([a.id for a in accounts]),
                )
                .options(
                    joinedload(Record.splits),
                    joinedload(Record.account),
                    joinedload(Record.transferToAccount),
                )
                .all()
            )
            day_effect = sum(adjust_balance(dr) for dr in day_records)
            total_balance += day_effect
            results.append(total_balance)
            current += timedelta(days=1)
        return results
    except SQLAlchemyError as e:
        raise DatabaseOperationException("Failed to calculate daily balance") from e
    finally:
        session.close()


# region Update
def update_record(record_id: int, updated_data: dict):
    """Update the record with the provided mapping.

    Raises:
        RecordNotFoundException: If the record doesn't exist.
        InvalidRecordDataException: If updated_data is not a dict.
        DatabaseOperationException: For underlying DB errors.
    """
    if not isinstance(updated_data, dict):
        raise InvalidRecordDataException("updated_data must be a dict")

    session = Session()
    try:
        record = session.query(Record).get(record_id)
        if not record:
            raise RecordNotFoundException(f"No record found for id={record_id}")
        for key, value in updated_data.items():
            setattr(record, key, value)
        session.commit()
        session.refresh(record)
        session.expunge(record)
        return record
    except SQLAlchemyError as e:
        raise DatabaseOperationException("Failed to update record") from e
    finally:
        session.close()


def update_record_and_splits(
    record_id: int, record_data: dict, splits_data: list[dict]
):
    session = Session()
    try:
        record = update_record(record_id, record_data)
        record_splits = get_splits_by_record_id(record_id)
        for index, split in enumerate(record_splits):
            update_split(split.id, splits_data[index])
        return record
    except SQLAlchemyError as e:
        raise DatabaseOperationException("Failed to update record and splits") from e
    finally:
        session.close()


# region Delete
def delete_record(record_id: int):
    session = Session()
    try:
        record = session.query(Record).get(record_id)
        if not record:
            raise RecordNotFoundException(f"No record found for id={record_id}")
        session.delete(record)
        session.commit()
        return record
    except SQLAlchemyError as e:
        raise DatabaseOperationException("Failed to delete record") from e
    finally:
        session.close()

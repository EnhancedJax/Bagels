from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from bagels.config import CONFIG
from bagels.currencies import normalize_currency_code
from bagels.managers.currency import (
    convert_account_amount,
    get_account_currency,
    get_main_currency,
)
from bagels.models.account import Account
from bagels.models.database.app import db_engine
from bagels.models.record import Record
from bagels.models.split import Split

Session = sessionmaker(bind=db_engine)


def _round_decimals() -> int:
    return CONFIG.defaults.round_decimals if CONFIG is not None else 2


def _normalize_account_payload(data: dict, include_default: bool = True) -> dict:
    payload = dict(data)
    if "currencyCode" in payload or include_default:
        payload["currencyCode"] = normalize_currency_code(
            payload.get("currencyCode"), fallback=get_main_currency()
        )
    return payload


# region Create


def create_account(data):
    session = Session()
    try:
        new_account = Account(**_normalize_account_payload(data, include_default=True))
        session.add(new_account)
        session.commit()
        session.refresh(new_account)
        session.expunge(new_account)
        return new_account
    finally:
        session.close()


# region Read


def get_account_balance(accountId, session=None):
    """Returns the net balance of an account.

    Rules:
    - Consider all record "account" and split "account"
    - Records with isTransfer should consider both "account" and "transferToAccount"
    - Records and splits should be considered separately, unlike net figures which consider records and splits together.

    Args:
        accountId (int): The ID of the account to get the balance
        session (Session, optional): SQLAlchemy session to use. If None, creates a new session.
    """
    if session is None:
        session = Session()
        should_close = True
    else:
        should_close = False

    try:
        # Initialize balance
        balance = (
            session.query(Account)
            .filter(Account.id == accountId)
            .first()
            .beginningBalance
        )

        # Get all records for this account
        records = session.query(Record).filter(Record.accountId == accountId).all()

        # Calculate balance from records
        for record in records:
            if record.isTransfer:
                # For transfers, subtract full amount (transfers out)
                balance -= record.amount
            elif record.isIncome:
                # For income records, add full amount
                balance += record.amount
            else:
                # For expense records, subtract full amount
                balance -= record.amount

        # Get all records where this account is the transfer destination
        transfer_to_records = (
            session.query(Record)
            .filter(Record.transferToAccountId == accountId, Record.isTransfer == True)  # noqa
            .all()
        )

        # Add transfers into this account
        for record in transfer_to_records:
            incoming = (
                record.transferToAmount
                if record.transferToAmount is not None
                else record.amount
            )
            balance += incoming

        # Get all splits where this account is specified
        splits = session.query(Split).filter(Split.accountId == accountId).all()

        # Add paid splits (they represent money coming into this account)
        for split in splits:
            if split.isPaid:
                if split.record.isIncome:
                    balance -= split.amount
                else:
                    balance += split.amount

        return round(balance, _round_decimals())
    finally:
        if should_close:
            session.close()


def _get_base_accounts_query(get_hidden=False):
    stmt = select(Account).filter(Account.deletedAt.is_(None))
    if not get_hidden:
        stmt = stmt.filter(Account.hidden.is_(False))
    else:
        stmt = stmt.order_by(Account.hidden)
    return stmt


def get_all_accounts(get_hidden=False):
    session = Session()
    try:
        stmt = _get_base_accounts_query(get_hidden)
        accounts = session.scalars(stmt).all()
        main_currency = get_main_currency()
        for account in accounts:
            account.currencyCode = get_account_currency(account, fallback=main_currency)
            session.expunge(account)
        return accounts
    finally:
        session.close()


def get_accounts_count(get_hidden=False):
    session = Session()
    try:
        stmt = _get_base_accounts_query(get_hidden)
        return len(session.scalars(stmt).all())
    finally:
        session.close()


def get_all_accounts_with_balance(get_hidden=False):
    session = Session()
    try:
        stmt = _get_base_accounts_query(get_hidden)
        accounts = session.scalars(stmt).all()
        main_currency = get_main_currency()
        for account in accounts:
            account.currencyCode = get_account_currency(account, fallback=main_currency)
            account.balance = get_account_balance(account.id, session)
            account.balance_main = convert_account_amount(
                account.balance,
                account,
                to_currency=main_currency,
            )
            session.expunge(account)
        return accounts
    finally:
        session.close()


def get_account_balance_by_id(account_id):
    session = Session()
    try:
        return get_account_balance(account_id, session)
    finally:
        session.close()


def get_account_by_id(account_id):
    session = Session()
    try:
        account = session.get(Account, account_id)
        if account is not None:
            account.currencyCode = get_account_currency(account)
            session.expunge(account)
        return account
    finally:
        session.close()


# region Update


def update_account(account_id, data):
    session = Session()
    try:
        account = session.get(Account, account_id)
        if account:
            for key, value in _normalize_account_payload(
                data, include_default=False
            ).items():
                setattr(account, key, value)
            session.commit()
            session.refresh(account)
            session.expunge(account)
        return account
    finally:
        session.close()


# region Delete


def delete_account(account_id):
    session = Session()
    try:
        account = session.get(Account, account_id)
        if account:
            account.deletedAt = datetime.now()
            session.commit()
            return True
        return False
    finally:
        session.close()

import re
from datetime import datetime, timedelta
from functools import lru_cache

from sqlalchemy.orm import joinedload, sessionmaker
from textual.widget import Widget

from bagels.config import CONFIG
from bagels.managers.currency import convert_account_amount, get_main_currency
from bagels.models.category import Category
from bagels.models.database.app import db_engine
from bagels.models.record import Record

Session = sessionmaker(bind=db_engine)


def _round_decimals() -> int:
    return CONFIG.defaults.round_decimals if CONFIG is not None else 2


def _first_day_of_week() -> int:
    return CONFIG.defaults.first_day_of_week if CONFIG is not None else 6


# --------------- query -------------- #


def try_method_query_one(widget: Widget, query: str, method: str, params):
    try:
        widget = widget.query_one(query)
        getattr(widget, method)(*params)
    except Exception as e:
        print(e)
        return


# region period
# -------------- period -------------- #
def _get_start_end_of_year(offset: int = 0):
    now = datetime.now()
    target_year = now.year + offset
    start_of_year = datetime(target_year, 1, 1, 0, 0, 0)
    end_of_year = datetime(target_year, 12, 31, 23, 59, 59)
    return start_of_year, end_of_year


def _get_start_end_of_month(offset: int = 0):
    now = datetime.now()
    # Calculate target month and year
    target_month = now.month + offset
    target_year = now.year + (target_month - 1) // 12
    target_month = ((target_month - 1) % 12) + 1

    # Calculate next month and year for end date
    next_month = target_month + 1
    next_year = target_year + (next_month - 1) // 12
    next_month = ((next_month - 1) % 12) + 1

    start_of_month = datetime(target_year, target_month, 1, 0, 0, 0)
    end_of_month = datetime(next_year, next_month, 1, 0, 0, 0) - timedelta(seconds=1)

    return start_of_month, end_of_month


def _get_start_end_of_week(offset: int = 0):
    now = datetime.now()
    # Apply offset in weeks
    now = now + timedelta(weeks=offset)
    first_day_of_week = _first_day_of_week()
    start_of_week = (
        now - timedelta(days=(now.weekday() - first_day_of_week) % 7)
    ).replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = (start_of_week + timedelta(days=6)).replace(
        hour=23, minute=59, second=59
    )
    return start_of_week, end_of_week


def _get_start_end_of_day(offset: int = 0):
    now = datetime.now()
    # Apply offset in days
    now = now + timedelta(days=offset)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=23, minute=59, second=59)
    return start_of_day, end_of_day


def get_start_end_of_period(offset: int = 0, offset_type: str = "month"):
    match offset_type:
        case "year":
            return _get_start_end_of_year(offset)
        case "month":
            return _get_start_end_of_month(offset)
        case "week":
            return _get_start_end_of_week(offset)
        case "day":
            return _get_start_end_of_day(offset)


# region figure
# -------------- figure -------------- #


def get_period_figures(
    accountId=None,
    offset_type=None,
    offset=None,
    isIncome=None,
    nature=None,
    session=None,
):
    """Returns the income / expense for a given period.

    Rules:
    - Filter applies to records only by the "date" column, and splits should always be considered by their associated record.
    - Income and expenses should be calculated from record less their splits, regardless of the account of the split.
    - Transfers are not income or expenses, but should be included in the net total.

    Args:
        accountId (int): The ID of the account to filter by. (Optional)
        offset_type (str): The type of period to filter by.
        offset (int): The offset from the current period.
        isIncome (bool): Whether to filter by income or expense.
        nature (Nature): Filter by category nature (Want/Need/Must). (Optional)
        session (Session, optional): SQLAlchemy session to use. If None, creates a new session.
    """
    if session is None:
        session = Session()
        should_close = True
    else:
        should_close = False

    try:
        query = session.query(Record).options(joinedload(Record.account))

        # Filter by account if specified
        if accountId is not None:
            query = query.filter(Record.accountId == accountId)

        # Filter by date period if specified
        if offset_type is not None and offset is not None:
            start_of_period, end_of_period = get_start_end_of_period(
                offset, offset_type
            )
            query = query.filter(
                Record.date >= start_of_period, Record.date < end_of_period
            )

        # Filter by category nature if specified
        if nature is not None:
            query = query.join(Record.category).filter(Category.nature == nature)

        # Calculate net amount
        total = 0
        records = query.all()
        main_currency = get_main_currency()
        use_global_conversion = accountId is None

        for record in records:
            # Skip records that are marked as transfers if filtering by income type
            if isIncome is not None and record.isTransfer:
                continue

            # Skip records that don't match income filter if specified
            if isIncome is not None and record.isIncome != isIncome:
                continue

            # Calculate amount after subtracting splits
            split_total = sum(split.amount for split in record.splits)
            record_amount = record.amount - split_total
            if use_global_conversion:
                record_amount = convert_account_amount(
                    record_amount,
                    record.account,
                    to_currency=main_currency,
                    at=record.date,
                    session=session,
                )

            if not record.isTransfer:
                # For regular income/expenses
                if record.isIncome:
                    total += record_amount
                else:
                    total -= record_amount

        return abs(round(total, _round_decimals()))
    finally:
        if should_close:
            session.close()


# region average
# -------------- average ------------- #


def _get_days_in_period(offset: int = 0, offset_type: str = "month"):
    start_of_period, end_of_period = get_start_end_of_period(offset, offset_type)
    days = (end_of_period - start_of_period).days + 1
    return days


def get_period_average(net: int = 0, offset: int = 0, offset_type: str = "month"):
    days = _get_days_in_period(offset, offset_type)
    return round(net / days, _round_decimals())


# region filter process
# ------------ filter process ------------ #


def get_operator_amount(operator_amount: str = None):
    # operators can be >=, >, =, <=, <
    # first validate the string to have one of operators and a number.
    # then split the string to get the operator and the number.
    # then return the operator and amount.
    if re.match(r"^(>=|>|=|<=|<)?\d+(\.\d+)?$", operator_amount):
        if operator_amount[0].isdigit():
            operator, amount = "=", operator_amount
        elif operator_amount[1].isdigit():
            operator, amount = operator_amount[:1], operator_amount[1:]
        else:
            operator, amount = operator_amount[:2], operator_amount[2:]
        amount = float(amount)
        return operator, amount
    else:
        return None, None


# region Budgeting
# ------------- budgeting ------------ #


def get_income_to_use(offset: int):
    metric = CONFIG.state.budgeting.income_assess_metric  # use number if provided
    threshold = CONFIG.state.budgeting.income_assess_threshold
    fallback = CONFIG.state.budgeting.income_assess_fallback

    limit = 0
    if metric == "periodIncome":
        this_month_income = get_period_figures(
            isIncome=True, offset=offset, offset_type="month"
        )
        if this_month_income > threshold:
            limit = this_month_income
        else:
            limit = get_period_figures(
                isIncome=True, offset=offset - 1, offset_type="month"
            )

    if limit < fallback:
        limit = fallback

    return limit


def dynamic_cache(func, *args, **kwargs):
    # Create a cached version of the function
    cached_func = lru_cache()(func)
    # Call the cached version with the provided arguments
    result = cached_func(*args, **kwargs)
    return result

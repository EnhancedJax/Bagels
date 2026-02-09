from datetime import datetime, timedelta
from typing import Iterable

import requests
from sqlalchemy import and_, select
from sqlalchemy.orm import sessionmaker

from bagels.config import CONFIG
from bagels.currencies import get_default_currency_code, normalize_currency_code
from bagels.models.database.app import db_engine
from bagels.models.exchange_rate import ExchangeRate

Session = sessionmaker(bind=db_engine)

FRANKFURTER_API_URL = "https://api.frankfurter.dev/v1"
_LAST_FETCH_FAILED_AT: dict[tuple[str, str, datetime], datetime] = {}


def _round_decimals() -> int:
    return CONFIG.defaults.round_decimals if CONFIG is not None else 2


def get_main_currency() -> str:
    if CONFIG is None:
        return get_default_currency_code()
    return normalize_currency_code(CONFIG.state.currency.main_currency)


def get_account_currency(account, fallback: str | None = None) -> str:
    fallback_currency = (
        normalize_currency_code(fallback) if fallback is not None else get_main_currency()
    )
    return normalize_currency_code(
        getattr(account, "currencyCode", None), fallback=fallback_currency
    )


def _normalize_rate_date(at: datetime | None) -> datetime:
    target = at or datetime.now()
    return datetime(target.year, target.month, target.day)


def _fetch_rate_from_api(base: str, quote: str, rate_date: datetime) -> tuple[float, datetime] | None:
    fail_key = (base, quote, rate_date)
    last_failed = _LAST_FETCH_FAILED_AT.get(fail_key)
    if last_failed is not None and (datetime.now() - last_failed) < timedelta(minutes=10):
        return None

    target_day = rate_date.date()
    today = datetime.now().date()
    date_path = "latest" if target_day >= today else target_day.isoformat()
    url = f"{FRANKFURTER_API_URL}/{date_path}"
    try:
        response = requests.get(
            url,
            params={"base": base, "symbols": quote},
            timeout=6,
        )
        response.raise_for_status()
        payload = response.json()
        rate = payload.get("rates", {}).get(quote)
        date_str = payload.get("date")
        if rate is None or date_str is None:
            _LAST_FETCH_FAILED_AT[fail_key] = datetime.now()
            return None
        fetched_date = datetime.strptime(date_str, "%Y-%m-%d")
        _LAST_FETCH_FAILED_AT.pop(fail_key, None)
        return float(rate), fetched_date
    except Exception:
        _LAST_FETCH_FAILED_AT[fail_key] = datetime.now()
        return None


def _get_cached_rate(
    session,
    base: str,
    quote: str,
    rate_date: datetime,
) -> float | None:
    stmt = (
        select(ExchangeRate)
        .where(
            and_(
                ExchangeRate.baseCurrency == base,
                ExchangeRate.quoteCurrency == quote,
                ExchangeRate.rateDate == rate_date,
            )
        )
        .limit(1)
    )
    row = session.scalars(stmt).first()
    if not row:
        return None

    # Historical rates are immutable enough for our use case.
    if rate_date.date() < datetime.now().date():
        return float(row.rate)

    if row.validUntil >= datetime.now():
        return float(row.rate)

    return None


def _upsert_rate(
    session,
    base: str,
    quote: str,
    rate: float,
    rate_date: datetime,
    source: str = "frankfurter",
) -> None:
    stmt = (
        select(ExchangeRate)
        .where(
            and_(
                ExchangeRate.baseCurrency == base,
                ExchangeRate.quoteCurrency == quote,
                ExchangeRate.rateDate == rate_date,
            )
        )
        .limit(1)
    )
    existing = session.scalars(stmt).first()
    refresh_hours = CONFIG.state.currency.refresh_hours if CONFIG is not None else 24
    valid_until = (
        datetime.now() + timedelta(hours=refresh_hours)
        if rate_date.date() >= datetime.now().date()
        else datetime.now() + timedelta(days=3650)
    )

    if existing:
        existing.rate = rate
        existing.source = source
        existing.fetchedAt = datetime.now()
        existing.validUntil = valid_until
        session.add(existing)
        return

    session.add(
        ExchangeRate(
            baseCurrency=base,
            quoteCurrency=quote,
            rateDate=rate_date,
            rate=rate,
            source=source,
            fetchedAt=datetime.now(),
            validUntil=valid_until,
        )
    )


def get_rate(
    base_currency: str,
    quote_currency: str,
    at: datetime | None = None,
    session=None,
) -> float | None:
    main_currency = get_main_currency()
    base = normalize_currency_code(base_currency, fallback=main_currency)
    quote = normalize_currency_code(quote_currency, fallback=main_currency)
    if base == quote:
        return 1.0

    should_close = session is None
    if should_close:
        session = Session()

    try:
        rate_date = _normalize_rate_date(at)
        cached = _get_cached_rate(session, base, quote, rate_date)
        if cached is not None:
            return cached

        fetched = _fetch_rate_from_api(base, quote, rate_date)
        if fetched is None:
            # Stale fallback if any cached historical/live value exists.
            fallback_stmt = (
                select(ExchangeRate)
                .where(
                    and_(
                        ExchangeRate.baseCurrency == base,
                        ExchangeRate.quoteCurrency == quote,
                    )
                )
                .order_by(ExchangeRate.fetchedAt.desc())
                .limit(1)
            )
            fallback = session.scalars(fallback_stmt).first()
            return float(fallback.rate) if fallback else None

        rate, fetched_date = fetched
        fetched_date = _normalize_rate_date(fetched_date)
        if should_close:
            _upsert_rate(session, base, quote, rate, fetched_date)
            _upsert_rate(session, quote, base, 1 / rate, fetched_date)
            session.commit()
        else:
            # Avoid committing caller-owned sessions used by read paths.
            write_session = Session()
            try:
                _upsert_rate(write_session, base, quote, rate, fetched_date)
                _upsert_rate(write_session, quote, base, 1 / rate, fetched_date)
                write_session.commit()
            finally:
                write_session.close()
        return rate
    finally:
        if should_close:
            session.close()


def convert_amount(
    amount: float | int,
    from_currency: str,
    to_currency: str | None = None,
    at: datetime | None = None,
    session=None,
) -> float:
    main_currency = get_main_currency()
    target_currency = normalize_currency_code(to_currency, fallback=main_currency)
    from_code = normalize_currency_code(from_currency, fallback=main_currency)
    to_code = normalize_currency_code(target_currency, fallback=main_currency)
    if from_code == to_code:
        return round(float(amount), _round_decimals())

    rate = get_rate(from_code, to_code, at=at, session=session)
    if rate is None:
        # Keep app usable offline: show native amount if rate can't be fetched.
        return round(float(amount), _round_decimals())

    return round(float(amount) * rate, _round_decimals())


def convert_account_amount(
    amount: float | int,
    account,
    to_currency: str | None = None,
    at: datetime | None = None,
    session=None,
) -> float:
    target_currency = normalize_currency_code(to_currency, fallback=get_main_currency())
    source_currency = get_account_currency(account, fallback=target_currency)
    return convert_amount(
        amount,
        source_currency,
        target_currency,
        at=at,
        session=session,
    )


def warm_rates_for_currencies(
    currencies: Iterable[str], target_currency: str | None = None
) -> None:
    target = normalize_currency_code(target_currency, fallback=get_main_currency())
    session = Session()
    try:
        unique_codes = {
            normalize_currency_code(code, fallback=target) for code in currencies if code
        }
        unique_codes.add(target)
        for code in unique_codes:
            if code == target:
                continue
            get_rate(code, target, session=session)
        session.commit()
    finally:
        session.close()

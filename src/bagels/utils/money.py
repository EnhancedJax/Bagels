from bagels.config import CONFIG


def format_amount(amount: float | int, currency_code: str | None = None) -> str:
    decimals = CONFIG.defaults.round_decimals if CONFIG is not None else 2
    number = round(float(amount), decimals)
    base = f"{number:.{decimals}f}"
    if currency_code:
        return f"{base} {currency_code}"
    return base


def format_account_name(account) -> str:
    name = getattr(account, "name", "")
    currency_code = getattr(account, "currencyCode", None)
    if currency_code:
        return f"{name} ({currency_code})"
    return str(name)


def format_account_balance(account, main_currency: str) -> str:
    account_currency = getattr(account, "currencyCode", None)
    native_balance = format_amount(getattr(account, "balance", 0), account_currency)
    if account_currency == main_currency:
        return native_balance

    balance_in_main = getattr(account, "balance_main", None)
    if balance_in_main is None:
        return native_balance
    return f"{native_balance} (~{format_amount(balance_in_main, main_currency)})"

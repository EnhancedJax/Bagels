DEFAULT_CURRENCY_CODE = "EUR"

# Major currencies + PLN (as requested)
SUPPORTED_CURRENCIES: dict[str, str] = {
    "PLN": "Polish zloty",
    "USD": "US dollar",
    "EUR": "Euro",
    "GBP": "Pound sterling",
    "CHF": "Swiss franc",
    "JPY": "Japanese yen",
    "CAD": "Canadian dollar",
    "AUD": "Australian dollar",
    "NZD": "New Zealand dollar",
    "CNY": "Chinese yuan",
    "HKD": "Hong Kong dollar",
    "SGD": "Singapore dollar",
    "SEK": "Swedish krona",
    "NOK": "Norwegian krone",
    "DKK": "Danish krone",
    "CZK": "Czech koruna",
    "HUF": "Hungarian forint",
    "RON": "Romanian leu",
    "BGN": "Bulgarian lev",
    "TRY": "Turkish lira",
    "INR": "Indian rupee",
    "KRW": "South Korean won",
    "MXN": "Mexican peso",
    "BRL": "Brazilian real",
    "ZAR": "South African rand",
    "AED": "UAE dirham",
    "SAR": "Saudi riyal",
}

SUPPORTED_CURRENCY_CODES = tuple(sorted(SUPPORTED_CURRENCIES.keys()))


def get_default_currency_code() -> str:
    return DEFAULT_CURRENCY_CODE


def normalize_currency_code(code: str | None, fallback: str | None = None) -> str:
    fallback_code = fallback if fallback is not None else get_default_currency_code()
    if not code:
        return fallback_code
    upper = str(code).upper().strip()
    if upper in SUPPORTED_CURRENCIES:
        return upper
    return fallback_code


def is_supported_currency(code: str | None) -> bool:
    if not code:
        return False
    return str(code).upper().strip() in SUPPORTED_CURRENCIES


def get_currency_items() -> list[tuple[str, str]]:
    return [(code, name) for code, name in SUPPORTED_CURRENCIES.items()]

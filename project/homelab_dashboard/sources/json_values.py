import math


def as_number(*, value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def as_integer(*, value: object) -> int | None:
    number: float | None = as_number(value=value)
    return None if number is None else int(number)


def as_text(*, value: object) -> str | None:
    return value if isinstance(value, str) and value else None

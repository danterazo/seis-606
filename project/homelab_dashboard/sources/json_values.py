import math
from typing import Optional


def as_number(*, value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return float(value)


def as_integer(*, value: object) -> Optional[int]:
    number: Optional[float] = as_number(value=value)
    return None if number is None else int(number)


def as_text(*, value: object) -> Optional[str]:
    return value if isinstance(value, str) and value else None

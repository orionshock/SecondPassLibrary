from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.core.validators import DecimalValidator, MinValueValidator


SERIES_INDEX_MAX_DIGITS = 8
SERIES_INDEX_DECIMAL_PLACES = 2
SERIES_INDEX_MIN_VALUE = Decimal("0.01")

_validate_digits = DecimalValidator(
    max_digits=SERIES_INDEX_MAX_DIGITS,
    decimal_places=SERIES_INDEX_DECIMAL_PLACES,
)
_validate_positive = MinValueValidator(SERIES_INDEX_MIN_VALUE)


def normalize_series_index(value: Decimal | str | int | None) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        index = Decimal(text)
    except InvalidOperation as exc:
        raise ValidationError("Enter a valid Series index.") from exc
    if not index.is_finite():
        raise ValidationError("Enter a valid Series index.")
    _validate_digits(index)
    _validate_positive(index)
    return index

from __future__ import annotations

import time
import unicodedata

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import salted_hmac

from accounts.operational_logging import logger

from .models import BrowserLoginThrottleSlot


# Household-friendly limits: ten credential checks per source over ten minutes,
# and five checks for a normalized username over fifteen minutes. Slots expire
# naturally; each login request also deletes a bounded batch of stale rows.
LOGIN_SOURCE_ATTEMPT_LIMIT = 10
LOGIN_SOURCE_WINDOW = timedelta(minutes=10)
LOGIN_USERNAME_ATTEMPT_LIMIT = 5
LOGIN_USERNAME_WINDOW = timedelta(minutes=15)
LOGIN_THROTTLE_CLEANUP_BATCH = 100
SQLITE_RESERVATION_RETRIES = 10
UNKNOWN_SOURCE = "unknown"
MAX_NORMALIZED_USERNAME_CHARS = 150


class LoginTemporarilyThrottled(ValueError):
    def __init__(self, *, reason: str, retry_after_seconds: int) -> None:
        super().__init__()
        self.reason = reason
        self.retry_after_seconds = retry_after_seconds


@dataclass(frozen=True, slots=True)
class LoginAttemptReservation:
    source_key: str
    username_key: str
    source_slot: int
    username_slot: int
    thresholds_reached: tuple[tuple[str, str, int, int], ...]


def normalize_login_username(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    return normalized[:MAX_NORMALIZED_USERNAME_CHARS]


def reserve_login_attempt(
    *, source_ip: str | None, username: str
) -> LoginAttemptReservation:
    source_key = _bucket_key("source", source_ip or UNKNOWN_SOURCE)
    username_key = _bucket_key("username", normalize_login_username(username))
    for attempt in range(SQLITE_RESERVATION_RETRIES):
        try:
            return _reserve_login_attempt_once(
                source_key=source_key,
                username_key=username_key,
            )
        except OperationalError as exc:
            is_sqlite_lock = connection.vendor == "sqlite" and "locked" in str(exc).lower()
            if not is_sqlite_lock or attempt == SQLITE_RESERVATION_RETRIES - 1:
                raise
            time.sleep(0.01 * (attempt + 1))
    raise RuntimeError("Login throttle reservation retry loop exhausted.")


@transaction.atomic
def _reserve_login_attempt_once(
    *, source_key: str, username_key: str
) -> LoginAttemptReservation:
    now = timezone.now()
    _delete_expired_slots(now=now)
    source_slot = _claim_slot(
        bucket_type=BrowserLoginThrottleSlot.BUCKET_SOURCE,
        bucket_key=source_key,
        limit=LOGIN_SOURCE_ATTEMPT_LIMIT,
        expires_at=now + LOGIN_SOURCE_WINDOW,
        now=now,
    )
    username_slot = _claim_slot(
        bucket_type=BrowserLoginThrottleSlot.BUCKET_USERNAME,
        bucket_key=username_key,
        limit=LOGIN_USERNAME_ATTEMPT_LIMIT,
        expires_at=now + LOGIN_USERNAME_WINDOW,
        now=now,
    )
    reached: list[tuple[str, str, int, int]] = []
    if source_slot == LOGIN_SOURCE_ATTEMPT_LIMIT - 1:
        reached.append(
            (
                "source",
                source_key,
                LOGIN_SOURCE_ATTEMPT_LIMIT,
                int(LOGIN_SOURCE_WINDOW.total_seconds()),
            )
        )
    if username_slot == LOGIN_USERNAME_ATTEMPT_LIMIT - 1:
        reached.append(
            (
                "username",
                username_key,
                LOGIN_USERNAME_ATTEMPT_LIMIT,
                int(LOGIN_USERNAME_WINDOW.total_seconds()),
            )
        )
    return LoginAttemptReservation(
        source_key=source_key,
        username_key=username_key,
        source_slot=source_slot,
        username_slot=username_slot,
        thresholds_reached=tuple(reached),
    )


def _claim_slot(
    *, bucket_type: str, bucket_key: str, limit: int, expires_at, now
) -> int:
    BrowserLoginThrottleSlot.objects.filter(
        bucket_type=bucket_type,
        bucket_key=bucket_key,
        expires_at__lte=now,
    ).delete()
    for slot in range(limit):
        try:
            with transaction.atomic():
                BrowserLoginThrottleSlot.objects.create(
                    bucket_type=bucket_type,
                    bucket_key=bucket_key,
                    slot=slot,
                    expires_at=expires_at,
                )
            return slot
        except IntegrityError:
            continue

    oldest_expiry = BrowserLoginThrottleSlot.objects.filter(
        bucket_type=bucket_type,
        bucket_key=bucket_key,
        expires_at__gt=now,
    ).order_by("expires_at").values_list("expires_at", flat=True).first()
    retry_after = max(1, int((oldest_expiry - now).total_seconds())) if oldest_expiry else 1
    raise LoginTemporarilyThrottled(
        reason=bucket_type,
        retry_after_seconds=retry_after,
    )


def clear_login_attempts(reservation: LoginAttemptReservation) -> None:
    BrowserLoginThrottleSlot.objects.filter(
        Q(
            bucket_type=BrowserLoginThrottleSlot.BUCKET_SOURCE,
            bucket_key=reservation.source_key,
        )
        | Q(
            bucket_type=BrowserLoginThrottleSlot.BUCKET_USERNAME,
            bucket_key=reservation.username_key,
        )
    ).delete()


def release_login_reservation(reservation: LoginAttemptReservation) -> None:
    BrowserLoginThrottleSlot.objects.filter(
        Q(
            bucket_type=BrowserLoginThrottleSlot.BUCKET_SOURCE,
            bucket_key=reservation.source_key,
            slot=reservation.source_slot,
        )
        | Q(
            bucket_type=BrowserLoginThrottleSlot.BUCKET_USERNAME,
            bucket_key=reservation.username_key,
            slot=reservation.username_slot,
        )
    ).delete()


def record_failed_login(reservation: LoginAttemptReservation) -> None:
    for dimension, key, count, window_seconds in reservation.thresholds_reached:
        logger.warning(
            "Browser login throttle threshold reached: dimension=%s bucket_ref=%s "
            "count=%s window_seconds=%s",
            dimension,
            key[:12],
            count,
            window_seconds,
        )


def _delete_expired_slots(*, now) -> None:
    expired_ids = list(
        BrowserLoginThrottleSlot.objects.filter(expires_at__lte=now)
        .order_by("expires_at", "pk")
        .values_list("pk", flat=True)[:LOGIN_THROTTLE_CLEANUP_BATCH]
    )
    if expired_ids:
        BrowserLoginThrottleSlot.objects.filter(pk__in=expired_ids).delete()


def _bucket_key(dimension: str, value: str) -> str:
    return salted_hmac(
        f"accounts.browser_login_throttle.{dimension}",
        value,
        secret=settings.SECRET_KEY,
        algorithm="sha256",
    ).hexdigest()

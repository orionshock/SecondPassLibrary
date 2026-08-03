from __future__ import annotations

import hmac
import hashlib
import secrets
import time
import unicodedata
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, OperationalError, connection, transaction
from django.db.models import Q
from django.utils import timezone

from accounts.operational_logging import logger, user_uuid

from .models import ClientLoginRequest, ClientPairingThrottleSlot, UserClientSession


HUMAN_CODE_GROUP_SIZE = 4
HUMAN_CODE_GROUPS = 2
HUMAN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LOGIN_REQUEST_TTL_MINUTES = 10
POLL_INTERVAL_SECONDS = 3

# Pairing creation is anonymous. Keep enough capacity for a few real devices
# while bounding row creation over the ten-minute request lifetime.
MAX_ACTIVE_PENDING_REQUESTS_PER_IP = 5
MAX_ACTIVE_PENDING_REQUESTS_PER_FINGERPRINT = 3
REQUEST_USER_AGENT_MAX_CHARS = 256

BEARER_TOKEN_PREFIX = "spl_"
BEARER_TOKEN_BYTES = 32

LAST_SEEN_THROTTLE_SECONDS = 60
SQLITE_CONSUMPTION_LOCK_RETRIES = 5
SQLITE_CREATION_LOCK_RETRIES = 10
UNKNOWN_SOURCE_BUCKET = "unknown"


class PairingRequestThrottled(ValueError):
    pass


def normalize_human_code(code: str) -> str:
    return (code or "").strip().upper().replace("-", "").replace(" ", "")


def format_human_code(code: str) -> str:
    normalized = normalize_human_code(code)
    if not normalized:
        return ""
    parts = []
    for i in range(0, len(normalized), HUMAN_CODE_GROUP_SIZE):
        parts.append(normalized[i : i + HUMAN_CODE_GROUP_SIZE])
    return "-".join(parts)


def generate_human_code() -> str:
    """
    Generate a short human code suitable for typing/reading aloud.
    Example: ABCD-1234 (but excluding ambiguous characters).
    """
    n = HUMAN_CODE_GROUP_SIZE * HUMAN_CODE_GROUPS
    raw = "".join(secrets.choice(HUMAN_CODE_ALPHABET) for _ in range(n))
    return format_human_code(raw)


def hash_client_secret(value: str) -> str:
    """
    Keyed one-way hash for codes/tokens. Raw values are never stored.
    """
    key = (settings.SECRET_KEY or "").encode("utf-8")
    msg = (value or "").encode("utf-8")
    return hmac.new(key, msg, digestmod="sha256").hexdigest()


def generate_bearer_token() -> str:
    token = secrets.token_urlsafe(BEARER_TOKEN_BYTES)
    return f"{BEARER_TOKEN_PREFIX}{token}"


def _now():
    return timezone.now()


def _expires_at_for_login_request(now=None):
    now = now or _now()
    return now + timedelta(minutes=LOGIN_REQUEST_TTL_MINUTES)


def _get_request_meta(
    *, request_user_agent: str | None, request_ip: str | None
) -> tuple[str, str | None]:
    ua = (request_user_agent or "")[:REQUEST_USER_AGENT_MAX_CHARS]
    ip = request_ip or None
    return ua, ip


def _request_fingerprint(*, client_name: str, client_type: str, user_agent: str) -> str:
    # This is secondary duplicate suppression, not a durable client identity.
    # Client-controlled punctuation or metadata changes may produce a new value;
    # the normalized source bucket remains the primary anonymous abuse limit.
    material = "\0".join(
        (
            _normalized_fingerprint_text(client_name),
            _normalized_fingerprint_text(client_type),
            user_agent,
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _normalized_fingerprint_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _source_bucket_key(request_ip: str | None) -> str:
    source = request_ip or UNKNOWN_SOURCE_BUCKET
    return hash_client_secret(f"pairing-source\0{source}")


def pairing_request_ref(login_request: ClientLoginRequest) -> str:
    return str(login_request.pk).replace("-", "")[:12]


def _safe_log_client_value(value: str, *, max_chars: int) -> str:
    return " ".join((value or "").split())[:max_chars] or "-"


def create_login_request(
    *,
    client_name: str,
    client_type: str,
    request_user_agent: str | None = None,
    request_ip: str | None = None,
) -> tuple[ClientLoginRequest, str]:
    name = (client_name or "").strip()
    ctype = (client_type or "").strip()
    if not name:
        raise ValueError("client_name is required.")
    if len(name) > 200:
        raise ValueError("client_name is too long.")
    if not ctype:
        raise ValueError("client_type is required.")
    if len(ctype) > 64:
        raise ValueError("client_type is too long.")

    ua, ip = _get_request_meta(request_user_agent=request_user_agent, request_ip=request_ip)
    fingerprint = _request_fingerprint(client_name=name, client_type=ctype, user_agent=ua)
    for attempt in range(SQLITE_CREATION_LOCK_RETRIES):
        try:
            return _create_login_request_once(
                name=name,
                client_type=ctype,
                user_agent=ua,
                request_ip=ip,
                fingerprint=fingerprint,
            )
        except OperationalError as exc:
            is_sqlite_lock = connection.vendor == "sqlite" and "locked" in str(exc).lower()
            if not is_sqlite_lock or attempt == SQLITE_CREATION_LOCK_RETRIES - 1:
                raise
            time.sleep(0.01 * (attempt + 1))
    raise RuntimeError("Pairing request creation retry loop exhausted.")


@transaction.atomic
def _create_login_request_once(
    *,
    name: str,
    client_type: str,
    user_agent: str,
    request_ip: str | None,
    fingerprint: str,
) -> tuple[ClientLoginRequest, str]:
    now = _now()
    expires_at = _expires_at_for_login_request(now)
    source_key = _source_bucket_key(request_ip)

    code = generate_human_code()
    obj = ClientLoginRequest.objects.create(
        code_hash=hash_client_secret(normalize_human_code(code)),
        client_name=name,
        client_type=client_type,
        status=ClientLoginRequest.STATUS_PENDING,
        expires_at=expires_at,
        request_user_agent=user_agent,
        request_fingerprint=fingerprint,
        request_ip=request_ip,
    )

    _claim_throttle_slot(
        login_request=obj,
        bucket_type=ClientPairingThrottleSlot.BUCKET_SOURCE,
        bucket_key=source_key,
        limit=MAX_ACTIVE_PENDING_REQUESTS_PER_IP,
        expires_at=expires_at,
        now=now,
        reason="source_limit",
    )
    _claim_throttle_slot(
        login_request=obj,
        bucket_type=ClientPairingThrottleSlot.BUCKET_FINGERPRINT,
        bucket_key=fingerprint,
        limit=MAX_ACTIVE_PENDING_REQUESTS_PER_FINGERPRINT,
        expires_at=expires_at,
        now=now,
        reason="fingerprint_limit",
    )

    pairing_ref = pairing_request_ref(obj)
    safe_type = _safe_log_client_value(client_type, max_chars=64)
    safe_name = _safe_log_client_value(name, max_chars=80)
    transaction.on_commit(
        lambda: logger.info(
            "Client pairing request created: pairing_ref=%s client_type=%s client_name=%s",
            pairing_ref,
            safe_type,
            safe_name,
        )
    )
    return obj, code


def _claim_throttle_slot(
    *,
    login_request: ClientLoginRequest,
    bucket_type: str,
    bucket_key: str,
    limit: int,
    expires_at,
    now,
    reason: str,
) -> None:
    ClientPairingThrottleSlot.objects.filter(
        bucket_type=bucket_type,
        bucket_key=bucket_key,
        expires_at__lte=now,
    ).delete()
    for slot in range(limit):
        try:
            with transaction.atomic():
                ClientPairingThrottleSlot.objects.create(
                    login_request=login_request,
                    bucket_type=bucket_type,
                    bucket_key=bucket_key,
                    slot=slot,
                    expires_at=expires_at,
                )
            return
        except IntegrityError:
            continue

    logger.warning(
        "Client pairing request throttled: reason=%s client_type=%s client_name=%s",
        reason,
        _safe_log_client_value(login_request.client_type, max_chars=64),
        _safe_log_client_value(login_request.client_name, max_chars=80),
    )
    raise PairingRequestThrottled()


def is_login_request_expired(obj: ClientLoginRequest, now=None) -> bool:
    now = now or _now()
    if obj.status == ClientLoginRequest.STATUS_EXPIRED:
        return True
    return obj.expires_at <= now


def get_pending_login_request_for_code(code: str) -> ClientLoginRequest | None:
    normalized = normalize_human_code(code)
    if not normalized:
        return None
    code_hash = hash_client_secret(normalized)
    now = _now()
    qs = ClientLoginRequest.objects.filter(
        code_hash=code_hash,
        status=ClientLoginRequest.STATUS_PENDING,
        expires_at__gt=now,
    ).order_by("-created_at")
    return qs.first()


def approve_login_request(
    *, login_request: ClientLoginRequest, user, client_name: str
) -> ClientLoginRequest:
    now = _now()
    with transaction.atomic():
        updated = ClientLoginRequest.objects.filter(
            pk=login_request.pk,
            status=ClientLoginRequest.STATUS_PENDING,
            expires_at__gt=now,
        ).update(
            status=ClientLoginRequest.STATUS_APPROVED,
            approved_by=user,
            approved_at=now,
            client_name=client_name,
            request_user_agent="",
            request_fingerprint="",
            request_ip=None,
            updated_at=now,
        )
        if updated:
            ClientPairingThrottleSlot.objects.filter(
                login_request_id=login_request.pk
            ).delete()
    if not updated:
        ClientLoginRequest.objects.filter(
            pk=login_request.pk,
            status=ClientLoginRequest.STATUS_PENDING,
            expires_at__lte=now,
        ).update(
            status=ClientLoginRequest.STATUS_EXPIRED,
            request_user_agent="",
            request_fingerprint="",
            request_ip=None,
            updated_at=now,
        )
        login_request.refresh_from_db()
        if is_login_request_expired(login_request, now=now):
            raise ValueError("Login request is expired.")
        raise ValueError("Login request is not pending.")

    login_request.refresh_from_db()
    logger.info(
        "Client pairing approved: actor=%s target=%s pairing_ref=%s client_type=%s "
        "client_name=%s",
        user_uuid(user),
        user_uuid(user),
        pairing_request_ref(login_request),
        _safe_log_client_value(login_request.client_type, max_chars=64),
        _safe_log_client_value(login_request.client_name, max_chars=80),
    )
    return login_request


def deny_login_request(*, login_request: ClientLoginRequest, user) -> ClientLoginRequest:
    now = _now()
    with transaction.atomic():
        updated = ClientLoginRequest.objects.filter(
            pk=login_request.pk,
            status=ClientLoginRequest.STATUS_PENDING,
            expires_at__gt=now,
        ).update(
            status=ClientLoginRequest.STATUS_DENIED,
            approved_by=user,
            approved_at=now,
            request_user_agent="",
            request_fingerprint="",
            request_ip=None,
            updated_at=now,
        )
        if updated:
            ClientPairingThrottleSlot.objects.filter(
                login_request_id=login_request.pk
            ).delete()
    if not updated:
        ClientLoginRequest.objects.filter(
            pk=login_request.pk,
            status=ClientLoginRequest.STATUS_PENDING,
            expires_at__lte=now,
        ).update(
            status=ClientLoginRequest.STATUS_EXPIRED,
            request_user_agent="",
            request_fingerprint="",
            request_ip=None,
            updated_at=now,
        )
        login_request.refresh_from_db()
        if is_login_request_expired(login_request, now=now):
            raise ValueError("Login request is expired.")
        raise ValueError("Login request is not pending.")

    login_request.refresh_from_db()
    logger.info(
        "Client pairing denied: actor=%s target=%s pairing_ref=%s client_type=%s "
        "client_name=%s",
        user_uuid(user),
        user_uuid(user),
        pairing_request_ref(login_request),
        _safe_log_client_value(login_request.client_type, max_chars=64),
        _safe_log_client_value(login_request.client_name, max_chars=80),
    )
    return login_request


@dataclass(frozen=True)
class ConsumeResult:
    session: UserClientSession
    access_token: str


def consume_login_request(*, login_request: ClientLoginRequest) -> ConsumeResult | None:
    """
    If the request is approved, create a UserClientSession and return the raw bearer token exactly once.
    If it is not approved, returns None.
    """
    for attempt in range(SQLITE_CONSUMPTION_LOCK_RETRIES):
        try:
            return _consume_login_request_once(login_request_id=login_request.pk)
        except OperationalError as exc:
            is_sqlite_lock = connection.vendor == "sqlite" and "locked" in str(exc).lower()
            if not is_sqlite_lock or attempt == SQLITE_CONSUMPTION_LOCK_RETRIES - 1:
                raise
            time.sleep(0.01 * (attempt + 1))
    return None


def log_consumption_rejection(
    *, login_request: ClientLoginRequest, state: str
) -> None:
    logger.info(
        "Client pairing consumption rejected: pairing_ref=%s state=%s client_type=%s",
        pairing_request_ref(login_request),
        state,
        _safe_log_client_value(login_request.client_type, max_chars=64),
    )


@transaction.atomic
def _consume_login_request_once(*, login_request_id) -> ConsumeResult | None:
    now = _now()

    invalid_approver = ClientLoginRequest.objects.filter(
        Q(approved_by__isnull=True) | Q(approved_by__is_active=False),
        pk=login_request_id,
        status=ClientLoginRequest.STATUS_APPROVED,
        expires_at__gt=now,
    ).update(
        status=ClientLoginRequest.STATUS_EXPIRED,
        consumed_at=None,
        request_user_agent="",
        request_fingerprint="",
        request_ip=None,
        updated_at=now,
    )
    if invalid_approver:
        ClientPairingThrottleSlot.objects.filter(login_request_id=login_request_id).delete()
        return None

    claimed = ClientLoginRequest.objects.filter(
        pk=login_request_id,
        status=ClientLoginRequest.STATUS_APPROVED,
        approved_by__isnull=False,
        approved_by__is_active=True,
        expires_at__gt=now,
    ).update(
        status=ClientLoginRequest.STATUS_CONSUMED,
        consumed_at=now,
        request_user_agent="",
        request_fingerprint="",
        request_ip=None,
        updated_at=now,
    )
    if not claimed:
        current = ClientLoginRequest.objects.select_related("approved_by").get(
            pk=login_request_id
        )
        if current.status == ClientLoginRequest.STATUS_CONSUMED:
            logger.info(
                "Client pairing consumption replay rejected: pairing_ref=%s client_type=%s",
                pairing_request_ref(current),
                _safe_log_client_value(current.client_type, max_chars=64),
            )
            return None
        if is_login_request_expired(current, now=now):
            ClientLoginRequest.objects.filter(
                pk=current.pk,
                status__in=(
                    ClientLoginRequest.STATUS_PENDING,
                    ClientLoginRequest.STATUS_APPROVED,
                ),
            ).update(
                status=ClientLoginRequest.STATUS_EXPIRED,
                request_user_agent="",
                request_fingerprint="",
                request_ip=None,
                updated_at=now,
            )
            ClientPairingThrottleSlot.objects.filter(
                login_request_id=login_request_id
            ).delete()
            logger.info(
                "Expired client pairing consumption rejected: pairing_ref=%s client_type=%s",
                pairing_request_ref(current),
                _safe_log_client_value(current.client_type, max_chars=64),
            )
        return None

    locked = ClientLoginRequest.objects.select_related("approved_by").get(
        pk=login_request_id
    )

    user = locked.approved_by
    if not user or getattr(user, "is_anonymous", False) or not user.is_active:
        raise RuntimeError("Claimed pairing request has no active approving user.")

    token = generate_bearer_token()
    token_hash = hash_client_secret(token)

    session = UserClientSession.objects.create(
        user=user,
        name=locked.client_name,
        client_type=locked.client_type,
        token_hash=token_hash,
        last_seen_at=None,
        expires_at=None,
        revoked_at=None,
    )

    actor = user_uuid(user)
    pairing_ref = pairing_request_ref(locked)
    session_id = session.pk
    safe_type = _safe_log_client_value(session.client_type, max_chars=64)
    safe_name = _safe_log_client_value(session.name, max_chars=80)
    transaction.on_commit(
        lambda: logger.info(
            "Client session created from pairing: actor=%s target=%s pairing_ref=%s "
            "client_session=%s client_type=%s client_name=%s",
            actor,
            actor,
            pairing_ref,
            session_id,
            safe_type,
            safe_name,
        )
    )
    return ConsumeResult(session=session, access_token=token)


def authenticate_bearer_token(raw_token: str) -> UserClientSession | None:
    if not raw_token or not isinstance(raw_token, str):
        return None
    token = raw_token.strip()
    if not token.startswith(BEARER_TOKEN_PREFIX):
        return None

    token_hash = hash_client_secret(token)
    now = _now()

    try:
        session = (
            UserClientSession.objects.select_related("user")
            .get(token_hash=token_hash)
        )
    except UserClientSession.DoesNotExist:
        return None

    if session.revoked_at is not None:
        return None
    if session.expires_at is not None and session.expires_at <= now:
        return None

    user = session.user
    if not user or getattr(user, "is_anonymous", False):
        return None
    if not bool(getattr(user, "is_active", True)):
        return None

    # Best-effort last-seen update (throttled).
    last = session.last_seen_at
    if last is None or (now - last) > timedelta(seconds=LAST_SEEN_THROTTLE_SECONDS):
        UserClientSession.objects.filter(pk=session.pk).update(last_seen_at=now, updated_at=now)
        session.last_seen_at = now

    return session

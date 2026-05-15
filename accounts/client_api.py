from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import ClientLoginRequest, UserClientSession


HUMAN_CODE_GROUP_SIZE = 4
HUMAN_CODE_GROUPS = 2
HUMAN_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
LOGIN_REQUEST_TTL_MINUTES = 10
POLL_INTERVAL_SECONDS = 3

BEARER_TOKEN_PREFIX = "spl_"
BEARER_TOKEN_BYTES = 32

LAST_SEEN_THROTTLE_SECONDS = 60


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


def _get_request_meta(*, request_user_agent: str | None, request_ip: str | None) -> tuple[str, str | None]:
    ua = (request_user_agent or "")[:4000]
    ip = request_ip or None
    return ua, ip


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

    code = generate_human_code()
    code_hash = hash_client_secret(normalize_human_code(code))
    ua, ip = _get_request_meta(request_user_agent=request_user_agent, request_ip=request_ip)

    obj = ClientLoginRequest.objects.create(
        code_hash=code_hash,
        client_name=name,
        client_type=ctype,
        status=ClientLoginRequest.STATUS_PENDING,
        expires_at=_expires_at_for_login_request(),
        request_user_agent=ua,
        request_ip=ip,
    )
    return obj, code


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


def approve_login_request(*, login_request: ClientLoginRequest, user) -> ClientLoginRequest:
    now = _now()
    if login_request.status != ClientLoginRequest.STATUS_PENDING:
        raise ValueError("Login request is not pending.")
    if is_login_request_expired(login_request, now=now):
        login_request.status = ClientLoginRequest.STATUS_EXPIRED
        login_request.save(update_fields=["status", "updated_at"])
        raise ValueError("Login request is expired.")

    login_request.status = ClientLoginRequest.STATUS_APPROVED
    login_request.approved_by = user
    login_request.approved_at = now
    login_request.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return login_request


def deny_login_request(*, login_request: ClientLoginRequest, user) -> ClientLoginRequest:
    now = _now()
    if login_request.status != ClientLoginRequest.STATUS_PENDING:
        raise ValueError("Login request is not pending.")
    if is_login_request_expired(login_request, now=now):
        login_request.status = ClientLoginRequest.STATUS_EXPIRED
        login_request.save(update_fields=["status", "updated_at"])
        raise ValueError("Login request is expired.")

    login_request.status = ClientLoginRequest.STATUS_DENIED
    login_request.approved_by = user
    login_request.approved_at = now
    login_request.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return login_request


@dataclass(frozen=True)
class ConsumeResult:
    session: UserClientSession
    access_token: str


@transaction.atomic
def consume_login_request(*, login_request: ClientLoginRequest) -> ConsumeResult | None:
    """
    If the request is approved, create a UserClientSession and return the raw bearer token exactly once.
    If it is not approved, returns None.
    """
    now = _now()

    locked = (
        ClientLoginRequest.objects.select_for_update()
        .select_related("approved_by")
        .get(pk=login_request.pk)
    )

    if locked.status == ClientLoginRequest.STATUS_CONSUMED:
        return None
    if is_login_request_expired(locked, now=now):
        if locked.status not in (ClientLoginRequest.STATUS_CONSUMED, ClientLoginRequest.STATUS_EXPIRED):
            locked.status = ClientLoginRequest.STATUS_EXPIRED
            locked.save(update_fields=["status", "updated_at"])
        return None
    if locked.status != ClientLoginRequest.STATUS_APPROVED:
        return None

    user = locked.approved_by
    if not user or getattr(user, "is_anonymous", False):
        return None
    if not bool(getattr(user, "is_active", True)):
        return None

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

    locked.status = ClientLoginRequest.STATUS_CONSUMED
    locked.consumed_at = now
    locked.save(update_fields=["status", "consumed_at", "updated_at"])

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

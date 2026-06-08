from __future__ import annotations

import json
import re
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .import_services import MarginaliaImportError


TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
EXPIRED_MESSAGE = "Import preview expired. Please preview the file again."


def stage_marginalia_import(*, user, payload: dict[str, Any]) -> str:
    cleanup_staged_imports()
    token = secrets.token_urlsafe(32)
    data = {
        "staged_at": timezone.now().isoformat(),
        "user_id": user.id,
        "payload": payload,
    }
    path = staged_import_path(token)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return token


def load_staged_marginalia_import(*, user, token: str) -> dict[str, Any]:
    cleanup_staged_imports()
    path = staged_import_path(token)
    if not path.exists():
        raise _expired()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise _expired() from None
    if data.get("user_id") != user.id:
        raise _expired()
    staged_at = parse_datetime(str(data.get("staged_at") or ""))
    if staged_at is None or staged_at < timezone.now() - timedelta(hours=24):
        delete_staged_marginalia_import(token=token)
        raise _expired()
    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise _expired()
    return payload


def delete_staged_marginalia_import(*, token: str) -> None:
    try:
        staged_import_path(token).unlink(missing_ok=True)
    except OSError:
        pass


def cleanup_staged_imports() -> None:
    root = staged_import_dir()
    if not root.exists():
        return
    cutoff = timezone.now() - timedelta(hours=24)
    for path in root.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            staged_at = parse_datetime(str(data.get("staged_at") or ""))
            if staged_at is None or staged_at < cutoff:
                path.unlink(missing_ok=True)
        except (OSError, json.JSONDecodeError):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass


def staged_import_path(token: str) -> Path:
    if not isinstance(token, str) or not TOKEN_RE.fullmatch(token):
        raise _expired()
    root = staged_import_dir().resolve()
    path = (root / f"{token}.json").resolve()
    if root != path.parent:
        raise _expired()
    return path


def staged_import_dir() -> Path:
    return Path(settings.IMPORTS_DIR) / "staged"


def _expired() -> MarginaliaImportError:
    return MarginaliaImportError(
        EXPIRED_MESSAGE,
        [{"path": "$.import_token", "message": EXPIRED_MESSAGE}],
    )

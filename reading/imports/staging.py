from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import re
import secrets
from datetime import timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .services import MarginaliaImportError


TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
EXPIRED_MESSAGE = "Import preview expired. Please preview the file again."
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StagedImportCleanupResult:
    removed: int
    stale_files: int
    corrupt_files: int
    cleanup_failures: int


def stage_marginalia_import(
    *, user, payload: dict[str, Any], include_empty_sessions: bool = False
) -> str:
    cleanup_staged_imports()
    token = secrets.token_urlsafe(32)
    data = {
        "staged_at": timezone.now().isoformat(),
        "user_id": user.id,
        "payload": payload,
        "include_empty_sessions": include_empty_sessions,
    }
    path = staged_import_path(token)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return token


def load_staged_marginalia_import(
    *, user, token: str
) -> tuple[dict[str, Any], bool]:
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
    return payload, data.get("include_empty_sessions") is True


def delete_staged_marginalia_import(*, token: str) -> None:
    try:
        staged_import_path(token).unlink(missing_ok=True)
    except OSError:
        pass


def cleanup_staged_imports() -> int:
    result = _cleanup_staged_imports()
    if result.corrupt_files or result.cleanup_failures:
        logger.warning(
            "Staged marginalia import cleanup completed with recoverable problems: "
            "removed=%d stale=%d corrupt=%d cleanup_failures=%d",
            result.removed,
            result.stale_files,
            result.corrupt_files,
            result.cleanup_failures,
        )
    elif result.removed:
        logger.info(
            "Staged marginalia import cleanup completed: removed=%d stale=%d "
            "corrupt=%d cleanup_failures=%d",
            result.removed,
            result.stale_files,
            result.corrupt_files,
            result.cleanup_failures,
        )
    return result.removed


def _cleanup_staged_imports() -> StagedImportCleanupResult:
    root = staged_import_dir()
    if not root.exists():
        return StagedImportCleanupResult(
            removed=0,
            stale_files=0,
            corrupt_files=0,
            cleanup_failures=0,
        )
    cutoff = timezone.now() - timedelta(hours=24)
    removed = 0
    stale_files = 0
    corrupt_files = 0
    cleanup_failures = 0
    root_resolved = root.resolve()
    for path in root.iterdir():
        if not path.is_file() or path.suffix != ".json" or not TOKEN_RE.fullmatch(path.stem):
            continue
        try:
            if path.resolve().parent != root_resolved:
                continue
        except OSError:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            staged_at = parse_datetime(str(data.get("staged_at") or ""))
            if staged_at is None or staged_at < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
                stale_files += 1
        except (OSError, json.JSONDecodeError):
            corrupt_files += 1
            try:
                path.unlink(missing_ok=True)
                removed += 1
            except OSError:
                cleanup_failures += 1
    return StagedImportCleanupResult(
        removed=removed,
        stale_files=stale_files,
        corrupt_files=corrupt_files,
        cleanup_failures=cleanup_failures,
    )


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

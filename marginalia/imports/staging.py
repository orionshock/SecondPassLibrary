from __future__ import annotations

import hashlib
import logging
import os
import re
import secrets

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from tempfile import NamedTemporaryFile

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from marginalia.models import ImportStage


IMPORT_STAGE_LIFETIME = timedelta(hours=2)
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
STORAGE_NAME_PATTERN = re.compile(r"^[0-9a-f]{64}\.json$")
logger = logging.getLogger(__name__)


class ImportStageStorageError(Exception):
    pass


class ImportStageUnavailableError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class CleanupResult:
    expired_stages_found: int = 0
    records_deleted: int = 0
    files_deleted: int = 0
    missing_files: int = 0
    failures: int = 0


def create_import_stage(
    *, user, raw: bytes, include_empty_sessions: bool, preview: dict
):
    token = secrets.token_urlsafe(32)
    digest = _token_digest(token)
    storage_name = f"{digest}.json"
    path = stage_file_path(storage_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    stage = None
    try:
        with NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=".marginalia-import-",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(raw)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        with transaction.atomic():
            stage = ImportStage.objects.create(
                user=user,
                token_digest=digest,
                expires_at=timezone.now() + IMPORT_STAGE_LIFETIME,
                include_empty_sessions=include_empty_sessions,
                storage_name=storage_name,
                preview=preview,
            )
            os.replace(temporary_path, path)
            temporary_path = None
        return token, stage
    except Exception as exc:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
        path.unlink(missing_ok=True)
        if stage is not None and stage.pk:
            ImportStage.objects.filter(pk=stage.pk).delete()
        raise ImportStageStorageError from exc


def load_import_stage(*, user, token: str) -> ImportStage:
    if not isinstance(token, str) or not TOKEN_PATTERN.fullmatch(token):
        raise ImportStageUnavailableError
    stage = ImportStage.objects.filter(
        user=user,
        token_digest=_token_digest(token),
    ).first()
    if stage is None:
        raise ImportStageUnavailableError
    if (
        stage.expires_at <= timezone.now()
        or not stage_file_path(stage.storage_name).is_file()
    ):
        _delete_stage(stage)
        raise ImportStageUnavailableError
    return stage


def claim_import_stage(*, user, token: str) -> ImportStage:
    if not isinstance(token, str) or not TOKEN_PATTERN.fullmatch(token):
        raise ImportStageUnavailableError
    digest = _token_digest(token)
    now = timezone.now()
    ImportStage.objects.filter(
        user=user,
        token_digest=digest,
        expires_at__gt=now,
        state=ImportStage.STATE_READY,
    ).update(state=ImportStage.STATE_APPLYING)
    stage = (
        ImportStage.objects.select_for_update()
        .filter(user=user, token_digest=digest)
        .first()
    )
    if stage is None or stage.expires_at <= now:
        raise ImportStageUnavailableError
    if (
        stage.state == ImportStage.STATE_APPLYING
        and not stage_file_path(stage.storage_name).is_file()
    ):
        raise ImportStageUnavailableError
    return stage


def read_staged_archive(stage: ImportStage) -> bytes:
    try:
        return stage_file_path(stage.storage_name).read_bytes()
    except (OSError, ImportStageStorageError) as exc:
        raise ImportStageUnavailableError from exc


def delete_applied_stage_file(storage_name: str) -> None:
    try:
        stage_file_path(storage_name).unlink(missing_ok=True)
    except (OSError, ImportStageStorageError):
        logger.warning("Marginalia import apply could not delete its staged archive.")


def cleanup_import_stages(*, dry_run: bool = False) -> CleanupResult:
    expired = list(ImportStage.objects.filter(expires_at__lte=timezone.now()))
    records_deleted = 0
    files_deleted = 0
    missing_files = 0
    failures = 0
    for stage in expired:
        path = stage_file_path(stage.storage_name)
        if not path.exists():
            missing_files += 1
        elif not dry_run:
            try:
                path.unlink()
                files_deleted += 1
            except OSError:
                failures += 1
                logger.warning(
                    "Marginalia import stage cleanup could not delete a staged file."
                )
                continue
        if not dry_run:
            stage.delete()
            records_deleted += 1

    referenced = set(ImportStage.objects.values_list("storage_name", flat=True))
    root = import_stage_root()
    if root.exists():
        for path in root.iterdir():
            if (
                not path.is_file()
                or not STORAGE_NAME_PATTERN.fullmatch(path.name)
                or path.name in referenced
            ):
                continue
            if dry_run:
                continue
            try:
                path.unlink()
                files_deleted += 1
            except OSError:
                failures += 1
                logger.warning(
                    "Marginalia import stage cleanup could not delete an orphaned file."
                )
    return CleanupResult(
        expired_stages_found=len(expired),
        records_deleted=records_deleted,
        files_deleted=files_deleted,
        missing_files=missing_files,
        failures=failures,
    )


def import_stage_root() -> Path:
    return Path(settings.IMPORTS_DIR) / "staged" / "marginalia"


def stage_file_path(storage_name: str) -> Path:
    if not STORAGE_NAME_PATTERN.fullmatch(storage_name):
        raise ImportStageStorageError
    root = import_stage_root().resolve()
    path = (root / storage_name).resolve()
    if path.parent != root:
        raise ImportStageStorageError
    return path


def _delete_stage(stage: ImportStage) -> None:
    try:
        stage_file_path(stage.storage_name).unlink(missing_ok=True)
    except OSError:
        logger.warning(
            "Marginalia import stage expiry cleanup could not delete a staged file."
        )
    stage.delete()


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from django.utils import timezone

from marginalia.archives import render_archive_json, serialize_archive
from marginalia.models import ReadingSession


class NoExportableSessionsError(ValueError):
    pass


class SelectedSessionNotFoundError(LookupError):
    pass


@dataclass(frozen=True, slots=True)
class MarginaliaExportDocument:
    content: bytes
    generated_at: datetime


def export_all_marginalia(
    *,
    user,
    include_empty_sessions: bool = False,
) -> MarginaliaExportDocument:
    return _build_export(
        sessions=ReadingSession.objects.filter(user=user),
        include_empty_sessions=include_empty_sessions,
    )


def export_selected_marginalia(
    *,
    user,
    reading_session_ids: list[UUID],
    include_empty_sessions: bool = False,
) -> MarginaliaExportDocument:
    sessions = ReadingSession.objects.filter(
        user=user,
        pk__in=reading_session_ids,
    )
    if sessions.count() != len(reading_session_ids):
        raise SelectedSessionNotFoundError
    return _build_export(
        sessions=sessions,
        include_empty_sessions=include_empty_sessions,
    )


def _build_export(*, sessions, include_empty_sessions: bool) -> MarginaliaExportDocument:
    generated_at = timezone.now()
    archive = serialize_archive(
        sessions,
        generated_at=generated_at,
        include_empty_sessions=include_empty_sessions,
    )
    if not archive.books:
        raise NoExportableSessionsError
    return MarginaliaExportDocument(
        content=render_archive_json(archive),
        generated_at=generated_at,
    )

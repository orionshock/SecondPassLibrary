from __future__ import annotations

import logging
from pathlib import Path
import shutil

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from library.imports.cli_presentation import ImportCliPresenter, bounded_context, format_bytes
from library.imports.cli_sources import (
    ImportSourceAdapter,
    ImportSourceFatalError,
)
from library.imports.epub import import_epub_file
from library.imports.results import ImportRunStats
from library.queries import defer_visible_books_cache_invalidation


MIN_DESTINATION_FREE_BYTES = 1024 * 1024 * 1024
PROGRESS_INTERVAL = 100
logger = logging.getLogger(__name__)


def run_cli_import(*, command: BaseCommand, source: ImportSourceAdapter) -> ImportRunStats:
    presenter = ImportCliPresenter(command)
    stats = ImportRunStats(source_method=source.method)
    free_bytes = _destination_free_bytes()
    presenter.run_started(source=source, free_bytes=free_bytes)
    logger.info(
        "CLI library import started: source_method=%s source=%s limits=%s",
        source.method,
        bounded_context(source.source),
        source.limit_description,
    )
    if free_bytes is not None and free_bytes < MIN_DESTINATION_FREE_BYTES:
        message = _low_space_message(free_bytes)
        presenter.fatal(message, stats=stats)
        raise CommandError(message)

    try:
        with defer_visible_books_cache_invalidation():
            for ordinal, event in enumerate(source.iter_events(), start=1):
                stats.discovered += 1
                presenter.candidate_started(ordinal, event)
                if event.candidate is not None:
                    free_bytes = _destination_free_bytes()
                    required = MIN_DESTINATION_FREE_BYTES + event.candidate.file_size
                    if free_bytes is not None and free_bytes < required:
                        message = _low_space_message(free_bytes)
                        presenter.fatal(
                            message,
                            stats=stats,
                            next_source=event.source_label,
                        )
                        raise CommandError(message)
                    stats.presented += 1
                    logger.info(
                        "CLI import candidate presented: source_method=%s ordinal=%d source=%s",
                        source.method,
                        ordinal,
                        bounded_context(event.source_label),
                    )
                    candidate = event.candidate
                    result = import_epub_file(
                        candidate.file_obj,
                        source_filename=candidate.epub_filename,
                        source_label=candidate.source_label,
                        source_method=candidate.source_method,
                        sidecar_opf=candidate.sidecar_opf,
                        sidecar_cover_bytes=candidate.sidecar_cover_bytes,
                        actor=None,
                        candidate_ordinal=ordinal,
                    )
                else:
                    result = event.result
                    logger.warning(
                        "CLI import source candidate not presented: "
                        "source_method=%s ordinal=%d category=%s",
                        source.method,
                        ordinal,
                        result.error_category if result is not None else "unknown",
                    )
                if result is None:
                    raise ImportSourceFatalError("Source adapter returned no candidate result.")
                stats.record(
                    result,
                    source_failure=event.candidate is None and result.status == "failed",
                    ambiguous=event.ambiguous,
                    processed_bytes=event.processed_bytes,
                )
                stats.last_completed_candidate = ordinal
                presenter.candidate_completed(result)
                if ordinal % PROGRESS_INTERVAL == 0:
                    presenter.progress(stats)
                    logger.info(
                        "CLI library import progress: source_method=%s completed=%d "
                        "imported=%d failed=%d",
                        source.method,
                        ordinal,
                        stats.imported,
                        stats.failed,
                    )
                if result.error_category == "io_error":
                    raise ImportSourceFatalError(
                        "Candidate I/O or storage failed; continuing may be unsafe."
                    )
    except KeyboardInterrupt:
        presenter.interrupted(stats)
        logger.warning(
            "CLI library import interrupted: source_method=%s completed=%d",
            source.method,
            stats.last_completed_candidate,
        )
        raise
    except ImportSourceFatalError as exc:
        presenter.fatal(str(exc), stats=stats)
        logger.error(
            "CLI library import stopped: source_method=%s completed=%d reason=%s",
            source.method,
            stats.last_completed_candidate,
            type(exc).__name__,
        )
        raise CommandError(str(exc)) from exc

    presenter.summary(stats, source=source)
    logger.info(
        "CLI library import completed: source_method=%s discovered=%d presented=%d "
        "imported=%d duplicate=%d conflict=%d skipped=%d failed=%d "
        "source_failures=%d ambiguous=%d processed_bytes=%d",
        source.method,
        stats.discovered,
        stats.presented,
        stats.imported,
        stats.duplicates,
        stats.conflicts,
        stats.skipped,
        stats.failed,
        stats.source_failures,
        stats.ambiguous,
        stats.processed_bytes,
    )
    if stats.failed or stats.conflicts:
        raise CommandError(
            "Import completed with failed, conflicting, or ambiguous candidates."
        )
    return stats


def _destination_free_bytes() -> int | None:
    path = Path(settings.MEDIA_ROOT)
    while not path.exists() and path != path.parent:
        path = path.parent
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return None


def _low_space_message(free_bytes: int) -> str:
    return (
        f"Destination free space is {format_bytes(free_bytes)}; at least "
        f"{format_bytes(MIN_DESTINATION_FREE_BYTES)} must remain."
    )

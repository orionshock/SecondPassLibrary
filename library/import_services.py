from __future__ import annotations

import shutil
from pathlib import Path
import uuid
import zipfile
from typing import Callable
import posixpath

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from .models import ImportJob, ImportJobItem


def _imports_dir() -> Path:
    return Path(getattr(settings, "IMPORTS_DIR", getattr(settings, "USERDATA_DIR")))  # type: ignore[arg-type]


def _stage_uploaded_file(
    *, uploaded_file: UploadedFile, job_id: uuid.UUID, source_type: str
) -> tuple[str, Path]:
    imports_dir = _imports_dir()
    job_dir = imports_dir / "jobs" / str(job_id)
    job_dir.mkdir(parents=True, exist_ok=True)

    extension = ".zip" if source_type == ImportJob.SOURCE_ZIP else ".epub"
    staged_name = f"{uuid.uuid4().hex}{extension}"
    staged_path = job_dir / staged_name

    with staged_path.open("wb") as out:
        for chunk in uploaded_file.chunks():
            out.write(chunk)

    staged_rel = str(Path("jobs") / str(job_id) / staged_name)
    return staged_rel, staged_path


def create_import_job_from_upload(*, user, uploaded_file: UploadedFile) -> ImportJob:
    name = (uploaded_file.name or "").strip()
    lower = name.lower()
    if lower.endswith(".epub"):
        source_type = ImportJob.SOURCE_EPUB
    elif lower.endswith(".zip"):
        source_type = ImportJob.SOURCE_ZIP
    else:
        raise ValueError("Upload must be a .epub or .zip file.")

    job = ImportJob.objects.create(
        user=user,
        status=ImportJob.STATUS_PENDING,
        source_type=source_type,
        source_filename=name,
    )
    staged_rel, _staged_path = _stage_uploaded_file(
        uploaded_file=uploaded_file, job_id=job.id, source_type=source_type
    )
    job.staged_path = staged_rel
    job.save(update_fields=["staged_path", "updated_at"])
    return job


def _safe_zip_member_name(name: str) -> str | None:
    if not name:
        return None
    if name.startswith(("/", "\\")) or ":" in name:
        return None
    normalized = Path(name)
    if any(part in {"..", ""} for part in normalized.parts):
        return None
    return name.replace("\\", "/")


def _zip_sidecar_opf_for_epub(
    *,
    epub_member: str,
    opfs_by_dir: dict[str, list[str]],
    members_index: dict[str, zipfile.ZipInfo],
) -> str | None:
    epub_member = epub_member.replace("\\", "/")
    d = posixpath.dirname(epub_member)
    base = posixpath.basename(epub_member)
    stem, _ext = posixpath.splitext(base)

    preferred = posixpath.join(d, "metadata.opf") if d else "metadata.opf"
    if preferred in members_index:
        return preferred

    same_base = posixpath.join(d, f"{stem}.opf") if d else f"{stem}.opf"
    if same_base in members_index:
        return same_base

    opfs = opfs_by_dir.get(d or "", [])
    if len(opfs) == 1:
        return opfs[0]

    return None


def process_import_job(
    *,
    job: ImportJob,
    import_epub_func: Callable[..., object],
    max_opf_xml_bytes: int,
    max_cover_bytes: int,
) -> ImportJob:
    if job.status not in {ImportJob.STATUS_PENDING, ImportJob.STATUS_FAILED}:
        return job

    staged_rel = (job.staged_path or "").strip()
    if not staged_rel:
        job.status = ImportJob.STATUS_FAILED
        job.message = "Missing staged upload."
        job.save(update_fields=["status", "message", "updated_at"])
        return job

    imports_dir = _imports_dir()
    staged_path = imports_dir / staged_rel
    if not staged_path.exists():
        job.status = ImportJob.STATUS_FAILED
        job.message = "Staged upload missing on disk."
        job.save(update_fields=["status", "message", "updated_at"])
        return job

    job.status = ImportJob.STATUS_PROCESSING
    job.message = ""
    job.total_found = 0
    job.imported_count = 0
    job.duplicate_count = 0
    job.failed_count = 0
    job.save(
        update_fields=[
            "status",
            "message",
            "total_found",
            "imported_count",
            "duplicate_count",
            "failed_count",
            "updated_at",
        ]
    )

    extracted_dir: Path | None = None
    try:
        if job.source_type == ImportJob.SOURCE_EPUB:
            job.total_found = 1
            result = import_epub_func(str(staged_path))
            status_val = getattr(result, "status", None)
            item_status = (
                ImportJobItem.STATUS_IMPORTED
                if status_val == "imported"
                else ImportJobItem.STATUS_DUPLICATE
                if status_val == "duplicate"
                else ImportJobItem.STATUS_FAILED
            )
            ImportJobItem.objects.create(
                job=job,
                status=item_status,
                source_name=job.source_filename or "",
                book=getattr(result, "book", None),
                book_file=getattr(result, "book_file", None),
                message=getattr(result, "message", "") or "",
            )
        else:
            extracted_dir = imports_dir / "jobs" / str(job.id) / "extracted"
            extracted_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(staged_path, "r") as zf:
                members_index: dict[str, zipfile.ZipInfo] = {}
                epub_members: list[zipfile.ZipInfo] = []
                opfs_by_dir: dict[str, list[str]] = {}

                for info in zf.infolist():
                    if info.is_dir():
                        continue
                    safe_name = _safe_zip_member_name(info.filename)
                    if safe_name is None:
                        continue
                    info.filename = safe_name
                    members_index[safe_name] = info

                    lower = safe_name.lower()
                    if lower.endswith(".epub"):
                        epub_members.append(info)
                    elif lower.endswith(".opf"):
                        d = posixpath.dirname(safe_name)
                        opfs_by_dir.setdefault(d, []).append(safe_name)

                members = epub_members
                job.total_found = len(members)
                job.save(update_fields=["total_found", "updated_at"])

                for info in members:
                    source_name = info.filename
                    try:
                        extracted_name = f"{uuid.uuid4().hex}.epub"
                        extracted_path = extracted_dir / extracted_name
                        with zf.open(info, "r") as src, extracted_path.open("wb") as dst:
                            shutil.copyfileobj(src, dst)

                        sidecar_opf_member = _zip_sidecar_opf_for_epub(
                            epub_member=source_name,
                            opfs_by_dir=opfs_by_dir,
                            members_index=members_index,
                        )
                        sidecar_opf_bytes: bytes | None = None
                        sidecar_opf_dir: str | None = None
                        if sidecar_opf_member is not None:
                            try:
                                with zf.open(sidecar_opf_member, "r") as opf_fp:
                                    sidecar_opf_bytes = opf_fp.read(max_opf_xml_bytes + 1)
                                if sidecar_opf_bytes and len(sidecar_opf_bytes) > max_opf_xml_bytes:
                                    sidecar_opf_bytes = None
                                else:
                                    sidecar_opf_dir = posixpath.dirname(sidecar_opf_member)
                            except Exception:
                                sidecar_opf_bytes = None
                                sidecar_opf_dir = None

                        def asset_reader(member: str) -> bytes | None:
                            safe = _safe_zip_member_name(member)
                            if safe is None:
                                return None
                            if safe not in members_index:
                                return None
                            try:
                                with zf.open(safe, "r") as fp:
                                    data = fp.read(max_cover_bytes + 1)
                                if len(data) > max_cover_bytes:
                                    return None
                                return data
                            except Exception:
                                return None

                        result = import_epub_func(
                            str(extracted_path),
                            sidecar_opf_bytes=sidecar_opf_bytes,
                            sidecar_opf_dir=sidecar_opf_dir,
                            sidecar_asset_reader=asset_reader if sidecar_opf_bytes and sidecar_opf_dir else None,
                        )

                        status_val = getattr(result, "status", None)
                        item_status = (
                            ImportJobItem.STATUS_IMPORTED
                            if status_val == "imported"
                            else ImportJobItem.STATUS_DUPLICATE
                            if status_val == "duplicate"
                            else ImportJobItem.STATUS_FAILED
                        )
                        ImportJobItem.objects.create(
                            job=job,
                            status=item_status,
                            source_name=source_name,
                            book=getattr(result, "book", None),
                            book_file=getattr(result, "book_file", None),
                            message=getattr(result, "message", "") or "",
                        )
                    except Exception as e:
                        ImportJobItem.objects.create(
                            job=job,
                            status=ImportJobItem.STATUS_FAILED,
                            source_name=source_name,
                            message=f"Failed to import EPUB: {e}",
                        )
                        continue

        job.imported_count = ImportJobItem.objects.filter(
            job=job, status=ImportJobItem.STATUS_IMPORTED
        ).count()
        job.duplicate_count = ImportJobItem.objects.filter(
            job=job, status=ImportJobItem.STATUS_DUPLICATE
        ).count()
        job.failed_count = ImportJobItem.objects.filter(
            job=job, status=ImportJobItem.STATUS_FAILED
        ).count()
        job.status = (
            ImportJob.STATUS_COMPLETED
            if job.failed_count == 0
            else ImportJob.STATUS_FAILED
        )
        job.message = "Import completed." if job.status == ImportJob.STATUS_COMPLETED else "Import completed with failures."
        job.save(
            update_fields=[
                "status",
                "message",
                "imported_count",
                "duplicate_count",
                "failed_count",
                "updated_at",
            ]
        )
        return job
    finally:
        if extracted_dir is not None and extracted_dir.exists():
            for child in extracted_dir.iterdir():
                if child.is_file():
                    child.unlink(missing_ok=True)
            try:
                extracted_dir.rmdir()
            except OSError:
                pass
        staged_path.unlink(missing_ok=True)


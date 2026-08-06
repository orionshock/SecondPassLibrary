from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import logging
import unicodedata
from collections.abc import Iterable

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify

from core.operational_logging import info_on_commit, safe_log_label, user_log_label
from library.models import Book, BookCatalogTag, CatalogTag


logger = logging.getLogger(__name__)


class CatalogTagMergeError(Exception):
    pass


class CatalogTagMergeSelectionError(CatalogTagMergeError):
    pass


class CatalogTagMergePlanStale(CatalogTagMergeError):
    pass


class CatalogTagMergeNameConflict(CatalogTagMergeError):
    pass


@dataclass(frozen=True)
class CatalogTagMergeItem:
    id: str
    name: str
    sort_name: str
    slug: str
    book_count: int


@dataclass(frozen=True)
class CatalogTagMergePlan:
    fingerprint: str
    tags: tuple[CatalogTagMergeItem, ...]
    total_relationships: int
    unique_books: int
    duplicate_relationships: int


@dataclass(frozen=True)
class CatalogTagMergeResult:
    survivor: CatalogTag
    source_tags_deleted: int
    books_affected: int
    relationships_created: int
    duplicate_relationships_collapsed: int


def normalize_catalog_tag_name(value: str) -> tuple[str, str]:
    name = " ".join(unicodedata.normalize("NFKC", str(value or "")).split())
    normalized_name = name.casefold()
    if not name:
        raise ValidationError({"catalog_tags": "Tag names cannot be blank."})
    if len(name) > 255 or len(normalized_name) > 255:
        raise ValidationError({"catalog_tags": "Tag names must be 255 characters or fewer."})
    return name, normalized_name


def normalize_catalog_tag_sort_name(value: str) -> str:
    sort_name = " ".join(unicodedata.normalize("NFKC", str(value or "")).split())
    if len(sort_name) > 255:
        raise ValidationError({"sort_name": "Sort name must be 255 characters or fewer."})
    return sort_name


def resolve_catalog_tag(name: str) -> CatalogTag:
    display_name, normalized_name = normalize_catalog_tag_name(name)
    existing = CatalogTag.objects.filter(normalized_name=normalized_name).first()
    if existing is not None:
        return existing
    return CatalogTag.objects.create(
        name=display_name,
        sort_name=display_name,
        normalized_name=normalized_name,
        slug=available_catalog_tag_slug(normalized_name),
    )


def replace_book_catalog_tags(*, book: Book, names: list[str]) -> None:
    tags_by_id = {}
    for name in names:
        tag = resolve_catalog_tag(name)
        tags_by_id[tag.id] = tag

    old_tag_ids = set(
        BookCatalogTag.objects.filter(book=book).values_list("catalog_tag_id", flat=True)
    )
    BookCatalogTag.objects.filter(book=book).delete()
    BookCatalogTag.objects.bulk_create(
        [BookCatalogTag(book=book, catalog_tag=tag) for tag in tags_by_id.values()]
    )
    CatalogTag.objects.filter(id__in=old_tag_ids).filter(book_catalog_tags__isnull=True).delete()


def available_catalog_tag_slug(normalized_name: str) -> str:
    digest = hashlib.sha256(normalized_name.encode("utf-8")).hexdigest()
    base = slugify(normalized_name, allow_unicode=True)[:255].strip("-")
    if base and not CatalogTag.objects.filter(slug=base).exists():
        return base
    stem = base[:246].rstrip("-") if base else "tag"
    for length in range(8, 65, 4):
        candidate = f"{stem}-{digest[:length]}"
        if not CatalogTag.objects.filter(slug=candidate).exists():
            return candidate
    raise ValidationError({"catalog_tags": "Could not generate a unique tag slug."})


def build_catalog_tag_merge_plan(tag_ids: Iterable) -> CatalogTagMergePlan:
    return _build_catalog_tag_merge_plan(tag_ids=tag_ids, lock=False)


def merge_catalog_tags(
    *,
    tag_ids: Iterable,
    survivor_id,
    final_name: str,
    final_sort_name: str,
    expected_fingerprint: str,
    actor=None,
) -> CatalogTagMergeResult:
    with transaction.atomic():
        plan = _build_catalog_tag_merge_plan(tag_ids=tag_ids, lock=True)
        if plan.fingerprint != expected_fingerprint:
            raise CatalogTagMergePlanStale(
                "The selected tags changed after preview. Review the refreshed merge plan."
            )

        selected_ids = {item.id for item in plan.tags}
        survivor_key = str(survivor_id)
        if survivor_key not in selected_ids:
            raise CatalogTagMergeSelectionError(
                "The surviving tag must be one of the selected tags."
            )

        display_name, normalized_name = normalize_catalog_tag_name(final_name)
        sort_name = normalize_catalog_tag_sort_name(final_sort_name)
        conflict = (
            CatalogTag.objects.select_for_update()
            .exclude(pk__in=selected_ids)
            .filter(normalized_name=normalized_name)
            .first()
        )
        if conflict is not None:
            raise CatalogTagMergeNameConflict(
                f'Catalog Tag "{conflict.name}" already uses that normalized name. '
                "Include it in the selection and choose it as the survivor."
            )

        survivor = CatalogTag.objects.select_for_update().get(pk=survivor_key)
        source_ids = selected_ids - {survivor_key}
        affected_book_ids = set(
            BookCatalogTag.objects.filter(catalog_tag_id__in=selected_ids).values_list(
                "book_id", flat=True
            )
        )
        existing_survivor_book_ids = set(
            BookCatalogTag.objects.filter(catalog_tag=survivor).values_list(
                "book_id", flat=True
            )
        )
        missing_survivor_book_ids = affected_book_ids - existing_survivor_book_ids
        BookCatalogTag.objects.bulk_create(
            [
                BookCatalogTag(book_id=book_id, catalog_tag=survivor)
                for book_id in missing_survivor_book_ids
            ]
        )
        BookCatalogTag.objects.filter(catalog_tag_id__in=source_ids).delete()
        CatalogTag.objects.filter(pk__in=source_ids).delete()

        survivor.name = display_name
        survivor.sort_name = sort_name
        survivor.normalized_name = normalized_name
        survivor.full_clean()
        survivor.save(update_fields=["name", "sort_name", "normalized_name", "updated_at"])

        result = CatalogTagMergeResult(
            survivor=survivor,
            source_tags_deleted=len(source_ids),
            books_affected=plan.unique_books,
            relationships_created=len(missing_survivor_book_ids),
            duplicate_relationships_collapsed=plan.duplicate_relationships,
        )
        info_on_commit(
            logger,
            "Catalog Tags merged: survivor=%s actor=%s source_tags=%d books=%d "
            "duplicate_relationships=%d",
            safe_log_label(survivor.name, fallback=str(survivor.pk)),
            user_log_label(actor),
            result.source_tags_deleted,
            result.books_affected,
            result.duplicate_relationships_collapsed,
        )
        return result


def _build_catalog_tag_merge_plan(
    *, tag_ids: Iterable, lock: bool
) -> CatalogTagMergePlan:
    selected_ids = {str(tag_id) for tag_id in tag_ids}
    if len(selected_ids) < 2:
        raise CatalogTagMergeSelectionError("Select at least two Catalog Tags to merge.")

    tags_query = CatalogTag.objects.filter(pk__in=selected_ids).order_by(
        "sort_name", "name", "id"
    )
    relationships_query = BookCatalogTag.objects.filter(
        catalog_tag_id__in=selected_ids
    ).order_by("catalog_tag_id", "book_id", "id")
    if lock:
        tags_query = tags_query.select_for_update()
        relationships_query = relationships_query.select_for_update()

    tags = list(tags_query)
    found_ids = {str(tag.pk) for tag in tags}
    if found_ids != selected_ids:
        raise CatalogTagMergeSelectionError(
            "One or more selected Catalog Tags no longer exist. Select the tags again."
        )

    relationships = list(
        relationships_query.values_list("id", "catalog_tag_id", "book_id")
    )
    counts = Counter(str(tag_id) for _row_id, tag_id, _book_id in relationships)
    unique_books = len({str(book_id) for _row_id, _tag_id, book_id in relationships})
    items = tuple(
        CatalogTagMergeItem(
            id=str(tag.pk),
            name=tag.name,
            sort_name=tag.sort_name,
            slug=tag.slug,
            book_count=counts[str(tag.pk)],
        )
        for tag in tags
    )
    fingerprint_payload = {
        "tags": [
            {
                "id": str(tag.pk),
                "name": tag.name,
                "sort_name": tag.sort_name,
                "normalized_name": tag.normalized_name,
                "slug": tag.slug,
                "updated_at": tag.updated_at.isoformat(),
            }
            for tag in tags
        ],
        "relationships": [
            [str(row_id), str(tag_id), str(book_id)]
            for row_id, tag_id, book_id in relationships
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(
            fingerprint_payload,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    total_relationships = len(relationships)
    return CatalogTagMergePlan(
        fingerprint=fingerprint,
        tags=items,
        total_relationships=total_relationships,
        unique_books=unique_books,
        duplicate_relationships=total_relationships - unique_books,
    )

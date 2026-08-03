from __future__ import annotations

import hashlib
import unicodedata

from django.core.exceptions import ValidationError
from django.utils.text import slugify

from library.models import Book, BookCatalogTag, CatalogTag


def normalize_catalog_tag_name(value: str) -> tuple[str, str]:
    name = " ".join(unicodedata.normalize("NFKC", str(value or "")).split())
    normalized_name = name.casefold()
    if not name:
        raise ValidationError({"catalog_tags": "Tag names cannot be blank."})
    if len(name) > 255 or len(normalized_name) > 255:
        raise ValidationError({"catalog_tags": "Tag names must be 255 characters or fewer."})
    return name, normalized_name


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

from django.test import TestCase

from library.catalog.tag_services import (
    CatalogTagMergeNameConflict,
    CatalogTagMergePlanStale,
    build_catalog_tag_merge_plan,
    merge_catalog_tags,
    normalize_catalog_tag_name,
    resolve_catalog_tag,
)
from library.models import Book, BookCatalogTag, CatalogTag


class CatalogTagServiceTests(TestCase):
    def test_normalization_is_unicode_aware_and_preserves_first_display_name(self):
        first = resolve_catalog_tag("  Urban   Ｆantasy ")
        second = resolve_catalog_tag("urban fantasy")

        self.assertEqual(normalize_catalog_tag_name("  Urban   Ｆantasy "), ("Urban Fantasy", "urban fantasy"))
        self.assertEqual(second, first)
        self.assertEqual(first.name, "Urban Fantasy")
        self.assertEqual(first.slug, "urban-fantasy")

    def test_slug_collision_gets_deterministic_suffix(self):
        first = resolve_catalog_tag("A B")
        second = resolve_catalog_tag("A-B")

        self.assertEqual(first.slug, "a-b")
        self.assertRegex(second.slug, r"^a-b-[0-9a-f]{8}$")


class CatalogTagMergeServiceTests(TestCase):
    def setUp(self):
        self.survivor = resolve_catalog_tag("Science Fiction")
        self.source = resolve_catalog_tag("Sci-Fi")
        self.unrelated = resolve_catalog_tag("Mystery")
        self.shared_book = Book.objects.create(title="Shared")
        self.source_book = Book.objects.create(title="Source only")
        self.survivor_book = Book.objects.create(title="Survivor only")
        BookCatalogTag.objects.bulk_create(
            [
                BookCatalogTag(book=self.shared_book, catalog_tag=self.survivor),
                BookCatalogTag(book=self.shared_book, catalog_tag=self.source),
                BookCatalogTag(book=self.source_book, catalog_tag=self.source),
                BookCatalogTag(book=self.survivor_book, catalog_tag=self.survivor),
            ]
        )

    def test_plan_reports_per_tag_counts_unique_books_and_overlaps(self):
        plan = build_catalog_tag_merge_plan([self.survivor.pk, self.source.pk])

        self.assertEqual(
            {item.name: item.book_count for item in plan.tags},
            {"Sci-Fi": 2, "Science Fiction": 2},
        )
        self.assertEqual(plan.total_relationships, 4)
        self.assertEqual(plan.unique_books, 3)
        self.assertEqual(plan.duplicate_relationships, 1)
        self.assertRegex(plan.fingerprint, r"^[0-9a-f]{64}$")

    def test_merge_preserves_survivor_identity_slug_books_and_unique_relationships(self):
        plan = build_catalog_tag_merge_plan([self.survivor.pk, self.source.pk])
        survivor_id = self.survivor.pk
        survivor_slug = self.survivor.slug

        result = merge_catalog_tags(
            tag_ids=[self.survivor.pk, self.source.pk],
            survivor_id=self.survivor.pk,
            final_name="  Speculative   Fiction ",
            final_sort_name=" Fiction,   Speculative ",
            expected_fingerprint=plan.fingerprint,
        )

        self.assertEqual(result.survivor.pk, survivor_id)
        self.assertEqual(result.survivor.slug, survivor_slug)
        self.assertEqual(result.survivor.name, "Speculative Fiction")
        self.assertEqual(result.survivor.sort_name, "Fiction, Speculative")
        self.assertEqual(result.source_tags_deleted, 1)
        self.assertEqual(result.books_affected, 3)
        self.assertEqual(result.relationships_created, 1)
        self.assertEqual(result.duplicate_relationships_collapsed, 1)
        self.assertFalse(CatalogTag.objects.filter(pk=self.source.pk).exists())
        self.assertTrue(CatalogTag.objects.filter(pk=self.unrelated.pk).exists())
        self.assertEqual(Book.objects.count(), 3)
        self.assertEqual(
            set(result.survivor.books.values_list("title", flat=True)),
            {"Shared", "Source only", "Survivor only"},
        )
        self.assertEqual(
            BookCatalogTag.objects.filter(catalog_tag=result.survivor).count(),
            3,
        )

    def test_unselected_name_collision_rolls_back_without_changes(self):
        plan = build_catalog_tag_merge_plan([self.survivor.pk, self.source.pk])

        with self.assertRaisesRegex(
            CatalogTagMergeNameConflict,
            "Include it in the selection",
        ):
            merge_catalog_tags(
                tag_ids=[self.survivor.pk, self.source.pk],
                survivor_id=self.survivor.pk,
                final_name=self.unrelated.name,
                final_sort_name=self.unrelated.sort_name,
                expected_fingerprint=plan.fingerprint,
            )

        self.assertTrue(CatalogTag.objects.filter(pk=self.source.pk).exists())
        self.assertEqual(BookCatalogTag.objects.count(), 4)
        self.survivor.refresh_from_db()
        self.assertEqual(self.survivor.name, "Science Fiction")

    def test_relationship_change_after_preview_rejects_merge_without_changes(self):
        plan = build_catalog_tag_merge_plan([self.survivor.pk, self.source.pk])
        late_book = Book.objects.create(title="Late change")
        BookCatalogTag.objects.create(book=late_book, catalog_tag=self.source)

        with self.assertRaises(CatalogTagMergePlanStale):
            merge_catalog_tags(
                tag_ids=[self.survivor.pk, self.source.pk],
                survivor_id=self.survivor.pk,
                final_name="Speculative Fiction",
                final_sort_name="Fiction, Speculative",
                expected_fingerprint=plan.fingerprint,
            )

        self.assertTrue(CatalogTag.objects.filter(pk=self.source.pk).exists())
        self.assertTrue(
            BookCatalogTag.objects.filter(book=late_book, catalog_tag=self.source).exists()
        )

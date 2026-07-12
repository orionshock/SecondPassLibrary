from django.test import TestCase

from library.catalog.tag_services import normalize_catalog_tag_name, resolve_catalog_tag


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

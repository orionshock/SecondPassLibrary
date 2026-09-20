from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from secondpass.library_urls import parse_library_urls


class LibraryUrlsTests(SimpleTestCase):
    def test_order_and_original_origin_are_preserved(self):
        self.assertEqual(
            parse_library_urls(
                " https://library.home.example:8443/, "
                "http://192.168.1.25:8000, https://library.public.example "
            ),
            [
                "https://library.home.example:8443",
                "http://192.168.1.25:8000",
                "https://library.public.example",
            ],
        )

    def test_duplicates_are_removed_without_reordering(self):
        self.assertEqual(
            parse_library_urls(
                "https://home.example,https://public.example/,"
                "https://HOME.example/,https://public.example,https://home.example:443"
            ),
            ["https://home.example", "https://public.example"],
        )

    def test_unset_value_produces_no_declared_urls(self):
        self.assertEqual(parse_library_urls(""), [])

    def test_malformed_urls_are_rejected(self):
        for raw in (
            "https://good.example,",
            ",https://good.example",
            "https://good.example,,https://other.example",
            "ftp://good.example",
            "https://",
            "https://user:pass@good.example",
            "https://good.example/books",
            "https://good.example?x=1",
            "https://good.example#fragment",
            "https://good.example:99999",
            "https://good.example:0",
            "https://good.example\n",
        ):
            with self.subTest(raw=raw), self.assertRaises(ImproperlyConfigured):
                parse_library_urls(raw)

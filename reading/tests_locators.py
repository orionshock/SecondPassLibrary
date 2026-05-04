from __future__ import annotations

from django.test import TestCase

from .locators import normalize_locator
from .tests_utils import IsolatedUserdataMixin


class LocatorNormalizationTest(IsolatedUserdataMixin, TestCase):
    def test_normalize_locator_adds_format_epub_when_missing(self):
        locator = {"cfi": "/6/4"}
        normalized = normalize_locator(locator)
        self.assertEqual(normalized["format"], "epub")

    def test_normalize_locator_does_not_mutate_input(self):
        locator = {"cfi": "/6/4"}
        _normalized = normalize_locator(locator)
        self.assertNotIn("format", locator)

    def test_normalize_locator_preserves_unknown_fields(self):
        locator = {"cfi": "/6/4", "weird": {"x": 1}}
        normalized = normalize_locator(locator)
        self.assertEqual(normalized["weird"], {"x": 1})

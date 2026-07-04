from django.test import SimpleTestCase

from reading.profile.validation import normalize_epub_cfi


class ReadingProfileHelpersTest(SimpleTestCase):
    def test_normalize_epub_cfi_wraps_raw_paths(self):
        self.assertEqual(normalize_epub_cfi("/6/4"), "epubcfi(/6/4)")
        self.assertEqual(normalize_epub_cfi(" epubcfi(/6/4) "), "epubcfi(/6/4)")

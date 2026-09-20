from django.test import SimpleTestCase

from marginalia.cfi import is_supported_durable_cfi


class DurableCfiProfileTests(SimpleTestCase):
    def test_accepts_compact_structural_points_and_ranges(self):
        for cfi in (
            "epubcfi(/6/8)",
            "epubcfi(/6/8!/4/2)",
            "epubcfi(/6/8!/4/3:0)",
            "epubcfi(/6/8!/4/2,/1:1,/3:4)",
            "epubcfi(/6/8!/4/3,:1,:4)",
            # Reduced from the historical Reader export: spine ID on /4.
            "epubcfi(/6/18!/4[chapter-identifier-01]/2,/708/1:0,/710/1:119)",
            "epubcfi(/6/58!/4[chapter-identifier-01]/2/906/1:280)",
            "epubcfi(/6/8[chap01ref]!/4/3:2)",
            "epubcfi(/6/8[chapitre-é]!/4/2[正文])",
            "epubcfi(/6/8[chapter]/4[section],/2[heading]/1:1,/4[ending]/1:4)",
        ):
            with self.subTest(cfi=cfi):
                self.assertTrue(is_supported_durable_cfi(cfi))

    def test_rejects_unsupported_or_malformed_cfis(self):
        for cfi in (
            "",
            "epubcfi()",
            " epubcfi(/6/8) ",
            "epubcfi(/6/8",
            "epubcfi(/6/8))",
            "epubcfi(/6//8)",
            "epubcfi(/6/08)",
            "epubcfi(/1/8)",
            "epubcfi(/6/8!)",
            "epubcfi(/6/8:01)",
            "epubcfi(/6/8:1/2)",
            "epubcfi(/6/8,/1:1)",
            "epubcfi(/6/8,/1:1,)",
            "epubcfi(/6/8,/1:1,/2:2,/3:3)",
            "epubcfi(/6/8[])",
            "epubcfi(/6/8[chapter,other])",
            "epubcfi(/6/8[chapter with spaces])",
            "epubcfi(/6/8[1starts-with-digit])",
            "epubcfi(/6/8[id:with-colon])",
            "epubcfi(/6/8!/4/1[text-node-id])",
            "epubcfi(/6/8!/4/0[virtual-node-id])",
            "epubcfi(/6/8[bad^x])",
            "epubcfi(/6/8[bad^])",
            "epubcfi(/6/8[bad[nested]])",
            "epubcfi(/6/8[bad;extension])",
            "epubcfi(/6/8[bad=extension])",
            "epubcfi(/6/8!/4/3:2[before])",
            "epubcfi(/6/8!/4/3:2[before,after])",
            "epubcfi(/6/8!/4/3:2[,])",
            "epubcfi(/6/8!/4/3:2[before,])",
            "epubcfi(/6/8!/4/3:2[before,after,extra])",
            "epubcfi(/6/8!/4/3:2[before;extension])",
            "epubcfi(/6/8~12.5)",
            "epubcfi(/6/8@10:20)",
            "epubcfi(/6/8;s=before)",
            "epubcfi(/6/8^/4)",
        ):
            with self.subTest(cfi=cfi):
                self.assertFalse(is_supported_durable_cfi(cfi))

    def test_rejects_oversized_id_assertions(self):
        self.assertTrue(
            is_supported_durable_cfi(f"epubcfi(/6/8[{'a' * 128}])")
        )
        self.assertFalse(
            is_supported_durable_cfi(
                f"epubcfi(/6/8[{'a' * 129}])"
            )
        )
        self.assertTrue(
            is_supported_durable_cfi(
                f"epubcfi(/6/8[{'a' * 128}]/4[{'b' * 128}])"
            )
        )
        self.assertFalse(
            is_supported_durable_cfi(
                f"epubcfi(/6/8[{'a' * 128}]/4[{'b' * 128}]/2[x])"
            )
        )

from __future__ import annotations

from pathlib import Path

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django import forms
from django.test import RequestFactory, TestCase

from library.models import Book
from reading.admin import (
    AnnotationAdmin,
    AnnotationAdminForm,
    AnnotationInline,
    ReadingProgressInline,
    ReadingSessionAdmin,
)
from reading.models import HIGHLIGHT_COLOR_TOKENS
from reading.models import Annotation, ReadingProgress, ReadingSession


ROOT = Path(__file__).resolve().parents[2]


class _DummySite(AdminSite):
    pass


class ReadingAdminDisplayTests(TestCase):
    def setUp(self):
        self.site = _DummySite()
        self.session_admin = ReadingSessionAdmin(ReadingSession, self.site)
        self.annotation_admin = AnnotationAdmin(Annotation, self.site)
        self.annotation_inline = AnnotationInline(ReadingSession, self.site)
        self.progress_inline = ReadingProgressInline(ReadingSession, self.site)
        self.factory = RequestFactory()
        self.request = self.factory.get("/admin/reading/readingsession/")
        self.user = User.objects.create_user(
            username="reader", email="reader@example.com", password="pw"
        )
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pw"
        )
        self.book = Book.objects.create(title="Readable Admin Book")
        self.session = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Morning read",
        )
        self.annotation = Annotation.objects.create(
            session=self.session,
            book=self.book,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            motivation=Annotation.MOTIVATION_HIGHLIGHTING,
            selector_value="epubcfi(/6/2!/4/2/8)",
            highlight_text="A useful highlighted passage for operator review.",
            comment_text="A short note.",
        )

    def test_reading_session_changelist_has_diagnostic_columns(self):
        self.assertEqual(
            self.session_admin.list_display,
            [
                "short_session_id",
                "session_label",
                "user",
                "book",
                "status",
                "is_active",
                "created_at",
                "updated_at",
            ],
        )
        self.assertIn("status", self.session_admin.list_filter)
        self.assertIn("is_active", self.session_admin.list_filter)
        self.assertIn("name", self.session_admin.search_fields)
        self.assertIn("book__title", self.session_admin.search_fields)
        self.assertIn("user__username", self.session_admin.search_fields)

    def test_reading_session_form_order_and_readonly_diagnostics(self):
        self.request.user = self.superuser

        self.assertEqual(
            self.session_admin.fields,
            [
                "name",
                "id",
                "user",
                "book",
                "status",
                "is_active",
                "notes",
                "completed_at",
                "created_at",
                "updated_at",
                "started_at",
            ],
        )
        readonly = self.session_admin.get_readonly_fields(
            self.request, obj=self.session
        )
        self.assertIn("id", readonly)
        self.assertIn("created_at", readonly)
        self.assertIn("updated_at", readonly)
        self.assertIn("started_at", readonly)
        self.assertEqual(self.session_admin.autocomplete_fields, ["user", "book"])

    def test_reading_session_display_helpers_are_short_and_readable(self):
        self.assertEqual(
            self.session_admin.short_session_id(self.session),
            str(self.session.pk)[:8],
        )
        self.assertEqual(self.session_admin.session_label(self.session), "Morning read")

        self.session.name = ""
        self.assertEqual(
            self.session_admin.session_label(self.session),
            "Unnamed session",
        )

    def test_annotation_inline_is_readonly_diagnostic_with_delete(self):
        self.request.user = self.superuser

        self.assertEqual(
            self.annotation_inline.template,
            "admin/reading/readingsession/edit_inline/annotations_tabular.html",
        )
        self.assertFalse(self.annotation_inline.has_add_permission(self.request))
        self.assertFalse(self.annotation_inline.has_change_permission(self.request))
        self.assertTrue(self.annotation_inline.can_delete)
        self.assertTrue(self.annotation_inline.has_delete_permission(self.request))
        for field in [
            "kind_display",
            "annotation_link",
            "created_at",
            "updated_at",
        ]:
            self.assertIn(field, self.annotation_inline.readonly_fields)
        self.assertNotIn("locator_summary", self.annotation_inline.readonly_fields)
        self.assertNotIn("highlight_preview", self.annotation_inline.readonly_fields)
        self.assertNotIn("comment_preview", self.annotation_inline.readonly_fields)

    def test_annotation_inline_links_short_id_to_annotation_admin(self):
        self.assertEqual(
            self.annotation_inline.kind_display(self.annotation), "Highlight"
        )
        html = str(self.annotation_inline.annotation_link(self.annotation))

        self.assertIn(str(self.annotation.pk)[:8], html)
        self.assertIn(f"/admin/reading/annotation/{self.annotation.pk}/change/", html)

    def test_reading_session_admin_shows_progress_before_annotations(self):
        self.assertEqual(
            self.session_admin.inlines,
            [ReadingProgressInline, AnnotationInline],
        )

    def test_progress_inline_is_readonly_and_does_not_lazy_create(self):
        self.request.user = self.superuser

        self.assertEqual(self.progress_inline.extra, 0)
        self.assertEqual(self.progress_inline.max_num, 1)
        self.assertFalse(self.progress_inline.can_delete)
        self.assertFalse(self.progress_inline.has_add_permission(self.request))
        self.assertFalse(
            self.progress_inline.has_change_permission(self.request, obj=self.session)
        )
        self.assertFalse(
            self.progress_inline.has_delete_permission(self.request, obj=self.session)
        )
        self.assertEqual(
            self.progress_inline.fields,
            [
                "progression",
                "current_location_summary",
                "profile_version",
                "created_at",
                "updated_at",
            ],
        )
        self.assertEqual(
            self.progress_inline.readonly_fields,
            self.progress_inline.fields,
        )

    def test_progress_inline_current_location_summary_is_readable(self):
        progress = ReadingProgress.objects.create(
            session=self.session,
            progression=0.42,
            current_location={
                "href": "chapter-03.xhtml",
                "progression": 0.42,
            },
        )

        self.assertEqual(
            self.progress_inline.current_location_summary(progress),
            '{"href": "chapter-03.xhtml","progression": 0.42}',
        )

    def test_annotation_inline_template_omits_original_object_label(self):
        template = (
            ROOT
            / "reading"
            / "templates"
            / "admin"
            / "reading"
            / "readingsession"
            / "edit_inline"
            / "annotations_tabular.html"
        ).read_text(encoding="utf-8")

        self.assertIn("inline_admin_form.pk_field.field", template)
        self.assertIn("inline_admin_form.fk_field.field", template)
        self.assertIn("Delete?", template)
        self.assertNotIn("{{ inline_admin_form.original }}", template)
        self.assertNotIn('class="original"', template)
        self.assertNotIn("<p>{{ field.contents }}</p>", template)

    def test_annotation_admin_standalone_editability_policy_remains_registered(self):
        self.request.user = self.superuser

        self.assertTrue(self.annotation_admin.has_add_permission(self.request))
        self.assertTrue(
            self.annotation_admin.has_change_permission(
                self.request, obj=self.annotation
            )
        )
        self.assertTrue(
            self.annotation_admin.has_delete_permission(
                self.request, obj=self.annotation
            )
        )

    def test_annotation_admin_changelist_columns_and_deleted_filter(self):
        self.assertEqual(
            self.annotation_admin.list_display,
            [
                "short_annotation_id",
                "session_user",
                "short_session_id",
                "motivation",
                "created_at",
            ],
        )
        self.assertIn("is_deleted", self.annotation_admin.list_filter)
        self.assertNotIn("is_deleted", self.annotation_admin.list_display)
        self.assertEqual(self.annotation_admin.session_user(self.annotation), "reader")
        self.assertEqual(
            self.annotation_admin.short_session_id(self.annotation),
            str(self.session.pk)[:8],
        )

    def test_annotation_admin_highlight_color_uses_choice_field(self):
        field = AnnotationAdminForm.base_fields["highlight_color"]

        self.assertIsInstance(field, forms.ChoiceField)
        self.assertFalse(field.required)
        choices = dict(field.choices)
        self.assertIn("", choices)
        self.assertEqual(
            {token for token in choices if token},
            HIGHLIGHT_COLOR_TOKENS,
        )

    def test_annotation_admin_highlight_color_form_rejects_unknown_token(self):
        form = AnnotationAdminForm(
            data={
                "session": str(self.session.pk),
                "book": str(self.book.pk),
                "motivation": Annotation.MOTIVATION_HIGHLIGHTING,
                "anchor_kind": Annotation.ANCHOR_KIND_HIGHLIGHT,
                "selector_kind": "epub_cfi",
                "selector_value": "epubcfi(/6/2)",
                "highlight_text": "text",
                "highlight_color": "red",
                "profile_version": "0.1.0",
            },
            instance=Annotation(),
        )

        self.assertFalse(form.is_valid())
        self.assertIn("highlight_color", form.errors)

from datetime import timedelta
from types import SimpleNamespace

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import path, reverse
from django.utils import timezone

from library.models import Book
from marginalia.admin import (
    AnnotationAdmin,
    ImportStageAdmin,
    ReadingSessionAdmin,
    SessionAnnotationInline,
)
from marginalia.imports.staging import stage_file_path
from marginalia.models import Annotation, ImportStage, ReadingSession
from tests.testenv.filesystem import IsolatedUserdataMixin


User = get_user_model()
urlpatterns = [path("admin/", admin.site.urls)]


@override_settings(ROOT_URLCONF=__name__)
class MarginaliaAdminTests(IsolatedUserdataMixin, TestCase):
    def setUp(self):
        self.site = AdminSite()
        self.session_admin = ReadingSessionAdmin(ReadingSession, self.site)
        self.annotation_admin = AnnotationAdmin(Annotation, self.site)
        self.stage_admin = ImportStageAdmin(ImportStage, self.site)
        self.operator = User.objects.create_superuser(
            username="operator",
            email="operator@example.test",
            password="pw",
        )
        self.user = User.objects.create_user(username="reader", password="pw")
        self.book = Book.objects.create(title="Admin Book", checksum="a" * 64)
        self.request = RequestFactory().get("/admin/marginalia/")
        self.request.user = self.operator

    def create_session(self, *, status=ReadingSession.STATUS_ACTIVE, book=None):
        values = {"user": self.user, "book": book or self.book, "status": status}
        if status == ReadingSession.STATUS_CLOSED:
            values["closed_at"] = timezone.now()
        return ReadingSession.objects.create(**values)

    def create_annotation(self, session, *, client_id="annotation-1"):
        return Annotation.objects.create(
            session=session,
            client_id=client_id,
            kind=Annotation.KIND_HIGHLIGHT,
            location="epubcfi(/6/2)",
            location_label="Chapter 01 · 2%",
            highlight_text="Selected text",
            highlight_color="yellow",
        )

    def create_stage(self, *, suffix="1"):
        storage_name = f"{'a' * 63}{suffix}.json"
        path = stage_file_path(storage_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        stage = ImportStage.objects.create(
            user=self.user,
            token_digest=f"{'b' * 63}{suffix}",
            expires_at=timezone.now() + timedelta(hours=2),
            storage_name=storage_name,
            preview={
                "summary": {
                    "book_count": 2,
                    "reading_session_count": 3,
                    "annotation_count": 4,
                }
            },
        )
        return stage, path

    def test_registered_models_and_retained_annotation_admin_are_configured(self):
        self.assertIsInstance(admin.site._registry[ReadingSession], ReadingSessionAdmin)
        self.assertIsInstance(admin.site._registry[Annotation], AnnotationAdmin)
        self.assertIsInstance(admin.site._registry[ImportStage], ImportStageAdmin)
        self.assertTrue(
            {"user_account", "book", "status", "annotation_count"}.issubset(
                self.session_admin.list_display
            )
        )
        self.assertIn("status", self.session_admin.list_filter)
        self.assertIn("book__title", self.session_admin.search_fields)
        self.assertEqual(self.session_admin.autocomplete_fields, ["user", "book"])
        self.assertIn("is_deleted", self.annotation_admin.list_filter)
        self.assertIn("client_id", self.annotation_admin.search_fields)
        self.assertEqual(self.annotation_admin.autocomplete_fields, ["session"])
        self.assertIn("state", self.stage_admin.list_filter)
        self.assertEqual(self.stage_admin.autocomplete_fields, ["user"])

    def test_session_page_shows_only_its_annotations_without_redundant_labels(self):
        session = self.create_session()
        annotation = self.create_annotation(session)
        deleted = self.create_annotation(session, client_id="deleted-annotation")
        deleted.highlight_text = "Deleted selected text"
        deleted.is_deleted = True
        deleted.save(update_fields=["highlight_text", "is_deleted", "updated_at"])
        other_book = Book.objects.create(title="Other Book", checksum="e" * 64)
        other_session = self.create_session(book=other_book)
        other = self.create_annotation(other_session, client_id="other-annotation")
        other.highlight_text = "Other Session selected text"
        other.save(update_fields=["highlight_text", "updated_at"])
        self.client.force_login(self.operator)

        response = self.client.get(
            reverse("admin:marginalia_readingsession_change", args=[session.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Selected text")
        self.assertNotContains(response, "Other Session selected text")
        annotation_url = reverse(
            "admin:marginalia_annotation_change",
            args=[annotation.pk],
        )
        self.assertContains(response, f'href="{annotation_url}">Highlight</a>')
        self.assertNotContains(response, str(annotation))
        annotation_response = self.client.get(annotation_url)
        self.assertEqual(annotation_response.status_code, 200)
        self.assertContains(annotation_response, annotation.client_id)
        self.assertNotContains(response, "column-kind")
        self.assertNotContains(response, "column-is_deleted")
        self.assertNotContains(response, "column-created_at")
        self.assertContains(response, "column-deleted_state")
        self.assertContains(response, ">Deleted</strong>", count=1)
        self.assertContains(response, "Soft delete")
        self.assertContains(response, "Hard delete permanently")
        self.assertContains(response, "hard delete is permanent")

    def test_annotation_admin_is_hidden_from_global_index(self):
        self.client.force_login(self.operator)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Annotations")

    def test_session_context_soft_and_hard_delete_only_selected_annotations(self):
        session = self.create_session()
        soft = self.create_annotation(session, client_id="soft")
        hard = self.create_annotation(session, client_id="hard")
        keep = self.create_annotation(session, client_id="keep")
        other_book = Book.objects.create(title="Other Book", checksum="f" * 64)
        other_session = self.create_session(book=other_book)
        other = self.create_annotation(other_session, client_id="other")
        inline = SessionAnnotationInline(ReadingSession, self.site)
        FormSet = inline.get_formset(self.request, session)
        prefix = FormSet.get_default_prefix()
        rows = list(FormSet(instance=session, prefix=prefix).get_queryset())
        data = {
            f"{prefix}-TOTAL_FORMS": str(len(rows)),
            f"{prefix}-INITIAL_FORMS": str(len(rows)),
            f"{prefix}-MIN_NUM_FORMS": "0",
            f"{prefix}-MAX_NUM_FORMS": "1000",
        }
        for index, row in enumerate(rows):
            data[f"{prefix}-{index}-id"] = str(row.pk)
            data[f"{prefix}-{index}-session"] = str(session.pk)
            if row.pk == soft.pk:
                data[f"{prefix}-{index}-soft_delete"] = "on"
            if row.pk == hard.pk:
                data[f"{prefix}-{index}-DELETE"] = "on"
        formset = FormSet(data=data, instance=session, prefix=prefix)
        self.assertTrue(formset.is_valid(), formset.errors)
        self.session_admin.message_user = lambda *args, **kwargs: None

        self.session_admin.save_formset(
            self.request,
            SimpleNamespace(instance=session),
            formset,
            True,
        )

        soft.refresh_from_db()
        keep.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(soft.is_deleted)
        self.assertIsNotNone(soft.deleted_at)
        self.assertFalse(Annotation.objects.filter(pk=hard.pk).exists())
        self.assertFalse(keep.is_deleted)
        self.assertFalse(other.is_deleted)

    def test_annotation_admin_preserves_and_clears_the_deletion_clock(self):
        session = self.create_session()
        annotation = self.create_annotation(session)

        annotation.is_deleted = True
        self.annotation_admin.save_model(
            self.request, annotation, form=None, change=True
        )
        annotation.refresh_from_db()
        deleted_at = annotation.deleted_at
        self.assertIsNotNone(deleted_at)

        annotation.location_label = "Chapter 2"
        self.annotation_admin.save_model(
            self.request, annotation, form=None, change=True
        )
        annotation.refresh_from_db()
        self.assertEqual(annotation.deleted_at, deleted_at)

        annotation.is_deleted = False
        self.annotation_admin.save_model(
            self.request, annotation, form=None, change=True
        )
        annotation.refresh_from_db()
        self.assertIsNone(annotation.deleted_at)

    def test_detail_pages_expose_persisted_fields_without_fake_raw_token(self):
        session_fields = _fieldset_names(self.session_admin.fieldsets)
        self.assertEqual(
            session_fields,
            {
                "id",
                "user",
                "book",
                "name",
                "notes",
                "status",
                "started_at",
                "closed_at",
                "progress_location",
                "progress_location_label",
                "progress_updated_at",
                "created_at",
                "updated_at",
            },
        )
        annotation_fields = _fieldset_names(self.annotation_admin.fieldsets)
        self.assertEqual(
            annotation_fields,
            {field.name for field in Annotation._meta.fields},
        )
        stage_fields = _fieldset_names(self.stage_admin.fieldsets)
        self.assertEqual(
            stage_fields, {field.name for field in ImportStage._meta.fields}
        )
        self.assertNotIn("import_token", stage_fields)
        self.assertNotIn("raw_token", stage_fields)

    def test_only_model_generated_fields_are_readonly(self):
        self.assertEqual(
            set(self.session_admin.readonly_fields),
            {"id", "started_at", "created_at", "updated_at"},
        )
        self.assertEqual(
            set(self.annotation_admin.readonly_fields),
            {"id", "created_at", "updated_at"},
        )
        self.assertEqual(
            set(self.stage_admin.readonly_fields),
            {"id", "created_at", "updated_at"},
        )
        for repair_field in (
            "kind",
            "location",
            "location_label",
            "highlight_text",
            "quote_prefix",
            "quote_suffix",
            "highlight_color",
            "comment_text",
            "is_deleted",
        ):
            self.assertNotIn(repair_field, self.annotation_admin.readonly_fields)

    def test_admin_forms_allow_active_and_closed_session_metadata_repair(self):
        active = self.create_session()
        active_form_class = self.session_admin.get_form(self.request, obj=active)
        active_form = active_form_class(
            data={
                "user": self.user.pk,
                "book": self.book.pk,
                "name": "Repaired active name",
                "notes": "Repaired active notes",
                "status": "active",
                "closed_at": "",
                "progress_location": "",
                "progress_location_label": "",
                "progress_updated_at": "",
            },
            instance=active,
        )
        self.assertTrue(active_form.is_valid(), active_form.errors)
        active_form.save()

        closed_book = Book.objects.create(title="Closed Admin Book", checksum="c" * 64)
        closed = self.create_session(
            status=ReadingSession.STATUS_CLOSED, book=closed_book
        )
        closed_form_class = self.session_admin.get_form(self.request, obj=closed)
        closed_form = closed_form_class(
            data={
                "user": self.user.pk,
                "book": closed_book.pk,
                "name": "Repaired closed name",
                "notes": "Repaired closed notes",
                "status": "closed",
                "closed_at_0": closed.closed_at.strftime("%Y-%m-%d"),
                "closed_at_1": closed.closed_at.strftime("%H:%M:%S"),
                "progress_location": "",
                "progress_location_label": "",
                "progress_updated_at": "",
            },
            instance=closed,
        )
        self.assertTrue(closed_form.is_valid(), closed_form.errors)
        closed_form.save()

        active.refresh_from_db()
        closed.refresh_from_db()
        self.assertEqual(active.name, "Repaired active name")
        self.assertEqual(closed.name, "Repaired closed name")

    def test_list_query_data_is_bounded(self):
        sessions = [self.create_session()]
        for index in range(1, 4):
            book = Book.objects.create(
                title=f"Admin Book {index}", checksum=f"{index}" * 64
            )
            sessions.append(self.create_session(book=book))
        for index, session in enumerate(sessions):
            self.create_annotation(session, client_id=f"annotation-{index}")

        with CaptureQueriesContext(connection) as queries:
            session_rows = list(self.session_admin.get_queryset(self.request))
            for row in session_rows:
                str(row.user)
                str(row.book)
                self.session_admin.annotation_count(row)
        self.assertEqual(len(queries), 1)

        with CaptureQueriesContext(connection) as queries:
            annotation_rows = list(self.annotation_admin.get_queryset(self.request))
            for row in annotation_rows:
                self.annotation_admin.session_user(row)
                self.annotation_admin.session_book(row)
        self.assertEqual(len(queries), 1)

        self.create_stage()
        with CaptureQueriesContext(connection) as queries:
            stage_rows = list(self.stage_admin.get_queryset(self.request))
            for row in stage_rows:
                str(row.user)
                self.stage_admin.preview_book_count(row)
        self.assertEqual(len(queries), 1)

    def test_session_and_book_deletion_cascade_through_marginalia(self):
        session = self.create_session()
        annotation = self.create_annotation(session)
        session.delete()
        self.assertFalse(Annotation.objects.filter(pk=annotation.pk).exists())

        session = self.create_session()
        annotation = self.create_annotation(session, client_id="annotation-2")
        self.book.delete()
        self.assertFalse(ReadingSession.objects.filter(pk=session.pk).exists())
        self.assertFalse(Annotation.objects.filter(pk=annotation.pk).exists())

    def test_import_stage_admin_deletion_removes_only_its_staged_files(self):
        first, first_path = self.create_stage(suffix="1")
        second, second_path = self.create_stage(suffix="2")
        with self.captureOnCommitCallbacks(execute=True):
            self.stage_admin.delete_model(self.request, first)
        self.assertFalse(first_path.exists())
        self.assertTrue(second_path.exists())

        with self.captureOnCommitCallbacks(execute=True):
            self.stage_admin.delete_queryset(
                self.request,
                ImportStage.objects.filter(pk=second.pk),
            )
        self.assertFalse(second_path.exists())
        self.assertEqual(ImportStage.objects.count(), 0)


def _fieldset_names(fieldsets) -> set[str]:
    return {
        field_name for _title, options in fieldsets for field_name in options["fields"]
    }

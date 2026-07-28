from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils import timezone
from tests.testenv.filesystem import IsolatedMediaRootMixin

from accounts.models import UserProfile
from library.models import BookSeries, Series
from reading.models import ReadingProgress, ReadingSession
from reading.services import create_annotation
from tests.utils.books import create_file_backed_book
from tests.utils.users import set_user_role


User = get_user_model()


def book_selection(book, sessions="all"):
    return {"book_id": str(book.id), "sessions": sessions}


def session_selection(book, *sessions):
    return book_selection(book, [str(session.id) for session in sessions])


def selected_export_payload(*books, include_empty_sessions=False):
    return {
        "books": list(books),
        "include_empty_sessions": include_empty_sessions,
    }


class ExportUserMixin(IsolatedMediaRootMixin):
    def create_librarian_user(self, *, username, password="pw"):
        user = User.objects.create_user(username=username, password=password)
        set_user_role(user, UserProfile.ROLE_LIBRARIAN)
        return user


class SingleBookExportFixtureMixin(ExportUserMixin):
    def set_up_single_book_export_world(self):
        self.user = self.create_librarian_user(username="u1")
        self.other = self.create_librarian_user(username="u2")

        self.book = create_file_backed_book(
            title="Export Book", epub_bytes=b"export-book"
        ).book
        self.series = Series.objects.create(name="Export Series")
        BookSeries.objects.create(
            book=self.book, series=self.series, series_index="2.5"
        )
        self.other_book = create_file_backed_book(
            title="Other Book", epub_bytes=b"other-book"
        ).book

        self.session1 = ReadingSession.objects.create(
            user=self.user, book=self.book, name="First pass", notes="Session notes"
        )
        self.other_user_session = ReadingSession.objects.create(
            user=self.other, book=self.book
        )
        self.other_book_session = ReadingSession.objects.create(
            user=self.user, book=self.other_book
        )

        ReadingProgress.objects.create(
            session=self.session1,
            current_location={
                "format": "epub",
                "href": "Text/ch1.xhtml",
                "cfi": "epubcfi(/6/2)",
            },
            progression=0.42,
        )

        self.highlight = create_annotation(
            session=self.session1,
            anchor_kind="highlight",
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/2[chapter]!/4/2)",
            highlight_text="selected text",
            quote_prefix="before ",
            quote_suffix=" after",
            highlight_color="green",
            comment_text="reader note",
        )
        self.deleted = create_annotation(
            session=self.session1,
            anchor_kind="highlight",
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/10)",
            highlight_text="deleted text",
            highlight_color="yellow",
        )
        self.deleted.is_deleted = True
        self.deleted.save(update_fields=["is_deleted", "updated_at"])

        self.session1.is_active = False
        self.session1.status = ReadingSession.STATUS_ARCHIVED
        self.session1.save(update_fields=["is_active", "status", "updated_at"])

        self.session2 = ReadingSession.objects.create(
            user=self.user,
            book=self.book,
            name="Second pass",
        )
        self.bookmark = create_annotation(
            session=self.session2,
            anchor_kind="bookmark",
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/8)",
        )
        self.session2.is_active = False
        self.session2.status = ReadingSession.STATUS_COMPLETED
        self.session2.completed_at = timezone.now()
        self.session2.save(
            update_fields=["is_active", "status", "completed_at", "updated_at"]
        )

    def _book_url(self):
        return "/api/v1/reading/export/"

    def _session_url(self, session=None, book=None):
        session = session or self.session1
        book = book or self.book
        return f"/api/v1/reading/export/books/{book.id}/{session.id}/"

    def _post_book(self, book=None, sessions="all"):
        book = book or self.book
        return self.client.post(
            self._book_url(),
            selected_export_payload(book_selection(book, sessions)),
            format="json",
        )


class AllExportFixtureMixin(ExportUserMixin):
    def set_up_all_export_world(self):
        self.user = self.create_librarian_user(username="u1")
        self.other = User.objects.create_user(username="u2", password="pw")

        self.book1 = create_file_backed_book(
            title="Alpha Book", epub_bytes=b"alpha"
        ).book
        self.book2 = create_file_backed_book(title="Beta Book", epub_bytes=b"beta").book
        self.no_session_book = create_file_backed_book(
            title="No Session Book", epub_bytes=b"none"
        ).book
        self.other_only_book = create_file_backed_book(
            title="Other User Book", epub_bytes=b"other"
        ).book

        self.session1 = ReadingSession.objects.create(
            user=self.user, book=self.book1, name="Alpha session"
        )
        self.session2 = ReadingSession.objects.create(
            user=self.user, book=self.book2, name="Beta session"
        )
        self.other_session = ReadingSession.objects.create(
            user=self.other, book=self.other_only_book, name="Other session"
        )

        create_annotation(
            session=self.session1,
            anchor_kind="highlight",
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/2)",
            highlight_text="alpha quote",
            highlight_color="yellow",
        )

    def _url(self):
        return "/api/v1/reading/export/"


class SelectedExportFixtureMixin(ExportUserMixin):
    def set_up_selected_export_world(self):
        self.user = self.create_librarian_user(username="u1")
        self.other = self.create_librarian_user(username="u2")

        self.book = create_file_backed_book(
            title="Selected Export", epub_bytes=b"selected"
        ).book
        self.other_book = create_file_backed_book(
            title="Other Book", epub_bytes=b"other"
        ).book

        self.session1 = ReadingSession.objects.create(
            user=self.user, book=self.book, name="First"
        )
        create_annotation(
            session=self.session1,
            anchor_kind="highlight",
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/2)",
            highlight_text="first quote",
        )
        self.session1.is_active = False
        self.session1.status = ReadingSession.STATUS_ARCHIVED
        self.session1.save(update_fields=["is_active", "status", "updated_at"])

        self.session2 = ReadingSession.objects.create(
            user=self.user, book=self.book, name="Second"
        )
        create_annotation(
            session=self.session2,
            anchor_kind="bookmark",
            selector_kind="epub_cfi",
            selector_value="epubcfi(/6/4)",
        )
        self.session2.is_active = False
        self.session2.status = ReadingSession.STATUS_COMPLETED
        self.session2.completed_at = timezone.now()
        self.session2.save(
            update_fields=["is_active", "status", "completed_at", "updated_at"]
        )

        self.other_user_session = ReadingSession.objects.create(
            user=self.other, book=self.book
        )
        self.other_book_session = ReadingSession.objects.create(
            user=self.user, book=self.other_book
        )

    def _url(self):
        return "/api/v1/reading/export/"

    def _body(self, *books):
        return selected_export_payload(*books)

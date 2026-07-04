
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession
from library.groups.services import ensure_book_public_assignment, ensure_user_public_membership
from reading.models import Annotation, ReadingSession
from tests.reading.utils import IsolatedUserdataMixin
from tests.utils.books import create_file_backed_book


User = get_user_model()


class ReadingAPITestBase(IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="u1", password="pass1", email="u1@example.com"
        )
        self.user2 = User.objects.create_user(
            username="u2", password="pass2", email="u2@example.com"
        )
        self.book = create_file_backed_book(title="Book 1").book
        ensure_book_public_assignment(book=self.book, added_by=None)

        self.session2 = ReadingSession.objects.create(user=self.user2, book=self.book)
        self.annotation2 = Annotation.objects.create(
            session=self.session2,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/2)",
            highlight_text="secret",
            comment_text="secret",
        )


class ReadingClientBearerAPITestBase(IsolatedUserdataMixin, APITestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="u1", password="pass1", email="u1@example.com"
        )
        self.user2 = User.objects.create_user(
            username="u2", password="pass2", email="u2@example.com"
        )
        ensure_user_public_membership(user=self.user1)
        ensure_user_public_membership(user=self.user2)

        self.book = create_file_backed_book(title="Book 1").book
        ensure_book_public_assignment(book=self.book, added_by=None)

        # Cross-user fixtures
        self.session2 = ReadingSession.objects.create(user=self.user2, book=self.book)
        self.annotation2 = Annotation.objects.create(
            session=self.session2,
            motivation=Annotation.MOTIVATION_COMMENTING,
            anchor_kind=Annotation.ANCHOR_KIND_HIGHLIGHT,
            book=self.book,
            selector_value="epubcfi(/6/2)",
            highlight_text="secret",
            comment_text="secret",
        )

        self.token = "spl_testtoken_reading"
        UserClientSession.objects.create(
            user=self.user1,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(self.token),
            last_seen_at=None,
            expires_at=None,
            revoked_at=None,
        )
        self._auth_header = f"Bearer {self.token}"

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.cache import cache

from accounts.models import UserProfile
from library.models import (
    Author,
    Book,
    BookAuthor,
    BookCatalogTag,
    BookGroupAssignment,
    BookSeries,
    CatalogTag,
    LibraryGroup,
    LibraryGroupMembership,
    Series,
)


def queryset_titles(queryset) -> list[str]:
    return list(queryset.order_by("title").values_list("title", flat=True))


def response_titles(response) -> list[str]:
    return [row["title"] for row in response.json()["results"]]


def set_user_role(user, role: str) -> None:
    user.profile.role = role
    user.profile.save(update_fields=["role", "updated_at"])


def create_catalog_book(
    title: str,
    *,
    author: Author,
    group: LibraryGroup,
    series: Series | None = None,
    series_index: str | None = None,
    tag: CatalogTag | None = None,
    description: str = "",
) -> Book:
    book = Book.objects.create(title=title, description=description)
    BookAuthor.objects.create(book=book, author=author, position=0)
    if series is not None:
        BookSeries.objects.create(book=book, series=series, series_index=series_index)
    if tag is not None:
        BookCatalogTag.objects.create(book=book, catalog_tag=tag)
    BookGroupAssignment.objects.create(book=book, group=group)
    return book


class LibraryCatalogApiFixtureMixin:
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        set_user_role(self.reader, UserProfile.ROLE_READER)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)

        self.public = LibraryGroup.objects.create(name="Common Room")
        self.hidden = LibraryGroup.objects.create(name="Hidden")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.public)

        self.alpha = Author.objects.create(name="Alpha Author", sort_name="Alpha Author")
        self.beta = Author.objects.create(name="Beta Author", sort_name="Beta Author")
        self.zeta = Author.objects.create(name="Zeta Author", sort_name="Zeta Author")
        self.first_series = Series.objects.create(name="First Series", sort_name="First Series")
        self.second_series = Series.objects.create(name="Second Series", sort_name="Second Series")
        self.fantasy = CatalogTag.objects.create(name="Fantasy", normalized_name="fantasy")
        self.mystery = CatalogTag.objects.create(name="Mystery", normalized_name="mystery")

        self.visible_one = create_catalog_book(
            "Visible One",
            author=self.beta,
            series=self.first_series,
            series_index="2.00",
            tag=self.fantasy,
            group=self.public,
            description="dresden case file",
        )
        self.visible_two = create_catalog_book(
            "Visible Two",
            author=self.alpha,
            series=self.first_series,
            series_index="1.00",
            tag=self.mystery,
            group=self.public,
        )
        self.visible_three = create_catalog_book(
            "Visible Three",
            author=self.zeta,
            series=self.second_series,
            series_index="1.00",
            tag=self.fantasy,
            group=self.public,
        )
        self.hidden_book = create_catalog_book(
            "Hidden Dresden",
            author=self.alpha,
            series=self.second_series,
            series_index="9.00",
            tag=self.fantasy,
            group=self.hidden,
            description="dresden hidden file",
        )
        self.multi_group = create_catalog_book(
            "Multi Group",
            author=self.alpha,
            group=self.public,
        )
        BookGroupAssignment.objects.create(book=self.multi_group, group=self.hidden)

        self.assertTrue(self.client.login(username="reader", password="pw"))

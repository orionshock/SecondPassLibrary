from types import SimpleNamespace

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import path, reverse

from library.admin import (
    AuthorAdmin,
    AuthorBookContextInline,
    GroupBookContextInline,
    GroupMembershipContextInline,
    LibraryGroupAdmin,
    SeriesAdmin,
    SeriesBookContextInline,
)
from library.models import (
    Author,
    Book,
    BookAuthor,
    BookGroupAssignment,
    BookSeries,
    LibraryGroup,
    LibraryGroupMembership,
    Series,
)


User = get_user_model()
urlpatterns = [path("admin/", admin.site.urls)]


def _delete_formset(FormSet, *, instance, selected):
    prefix = FormSet.get_default_prefix()
    rows = list(FormSet(instance=instance, prefix=prefix).get_queryset())
    data = {
        f"{prefix}-TOTAL_FORMS": str(len(rows)),
        f"{prefix}-INITIAL_FORMS": str(len(rows)),
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
    }
    for index, row in enumerate(rows):
        data[f"{prefix}-{index}-id"] = str(row.pk)
        data[f"{prefix}-{index}-{FormSet.fk.name}"] = str(instance.pk)
        if row.pk == selected.pk:
            data[f"{prefix}-{index}-DELETE"] = "on"
    return FormSet(data=data, instance=instance, prefix=prefix)


@override_settings(ROOT_URLCONF=__name__)
class LibraryContextAdminTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_superuser(username="operator", password="pw")
        self.request = RequestFactory().post("/admin/library/")
        self.request.user = self.operator
        self.client.force_login(self.operator)

    def test_primary_changelists_remain_without_relationship_changelists(self):
        for model, route in (
            (LibraryGroup, "admin:library_librarygroup_changelist"),
            (Author, "admin:library_author_changelist"),
            (Series, "admin:library_series_changelist"),
            (Book, "admin:library_book_changelist"),
        ):
            self.assertIn(model, admin.site._registry)
            self.assertEqual(self.client.get(reverse(route)).status_code, 200)
        self.assertNotIn(LibraryGroupMembership, admin.site._registry)
        self.assertNotIn(BookGroupAssignment, admin.site._registry)

    def test_group_page_renders_memberships_books_and_direct_edit_links(self):
        group = LibraryGroup.objects.create(name="Context Group")
        user = User.objects.create_user(username="reader")
        membership = LibraryGroupMembership.objects.create(user=user, group=group)
        author = Author.objects.create(name="Context Author")
        series = Series.objects.create(name="Context Series")
        book = Book.objects.create(title="Context Book")
        BookAuthor.objects.create(book=book, author=author, position=0)
        BookSeries.objects.create(book=book, series=series)
        assignment = BookGroupAssignment.objects.create(
            book=book,
            group=group,
            added_by=self.operator,
        )

        response = self.client.get(
            reverse("admin:library_librarygroup_change", args=[group.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Users and memberships")
        self.assertContains(response, "Assigned Books")
        user_url = reverse("admin:auth_user_change", args=[user.pk])
        book_url = reverse("admin:library_book_change", args=[book.pk])
        self.assertContains(response, f'href="{user_url}">reader</a>')
        self.assertContains(response, "Member")
        self.assertContains(response, f'href="{book_url}">Context Book</a>')
        self.assertContains(response, "Context Author")
        self.assertContains(response, "Context Series")
        self.assertNotContains(response, str(membership))
        self.assertNotContains(response, str(assignment))
        self.assertNotContains(response, "column-membership_link")
        self.assertNotContains(response, "column-added_by")
        self.assertNotContains(response, "column-created_at")
        self.assertContains(response, "Remove relationship")

    def test_group_context_removes_only_selected_relationships_not_objects(self):
        group = LibraryGroup.objects.create(name="Remove From")
        safe_group = LibraryGroup.objects.create(name="Keep Membership")
        users = [User.objects.create_user(username=f"reader-{index}") for index in range(2)]
        memberships = [
            LibraryGroupMembership.objects.create(user=user, group=group) for user in users
        ]
        for user in users:
            LibraryGroupMembership.objects.create(user=user, group=safe_group)
        books = [Book.objects.create(title=f"Book {index}") for index in range(2)]
        assignments = [
            BookGroupAssignment.objects.create(book=book, group=group) for book in books
        ]
        for book in books:
            BookGroupAssignment.objects.create(book=book, group=safe_group)
        model_admin = LibraryGroupAdmin(LibraryGroup, admin.site)
        model_admin.message_user = lambda *args, **kwargs: None

        membership_inline = GroupMembershipContextInline(
            LibraryGroup,
            admin.site,
        )
        MembershipFormSet = membership_inline.get_formset(self.request, group)
        membership_formset = _delete_formset(
            MembershipFormSet,
            instance=group,
            selected=memberships[0],
        )
        self.assertTrue(membership_formset.is_valid(), membership_formset.errors)
        model_admin.save_formset(
            self.request,
            SimpleNamespace(instance=group),
            membership_formset,
            True,
        )

        book_inline = GroupBookContextInline(LibraryGroup, admin.site)
        BookFormSet = book_inline.get_formset(self.request, group)
        book_formset = _delete_formset(
            BookFormSet,
            instance=group,
            selected=assignments[0],
        )
        self.assertTrue(book_formset.is_valid(), book_formset.errors)
        model_admin.save_formset(
            self.request,
            SimpleNamespace(instance=group),
            book_formset,
            True,
        )

        self.assertFalse(
            LibraryGroupMembership.objects.filter(pk=memberships[0].pk).exists()
        )
        self.assertTrue(
            LibraryGroupMembership.objects.filter(pk=memberships[1].pk).exists()
        )
        self.assertFalse(
            BookGroupAssignment.objects.filter(pk=assignments[0].pk).exists()
        )
        self.assertTrue(
            BookGroupAssignment.objects.filter(pk=assignments[1].pk).exists()
        )
        self.assertEqual(User.objects.filter(pk__in=[user.pk for user in users]).count(), 2)
        self.assertEqual(Book.objects.filter(pk__in=[book.pk for book in books]).count(), 2)

    def test_author_context_links_books_and_removes_only_selected_relationship(self):
        author = Author.objects.create(name="Context Author")
        books = [Book.objects.create(title=f"Authored {index}") for index in range(2)]
        relationships = [
            BookAuthor.objects.create(book=book, author=author, position=0) for book in books
        ]
        response = self.client.get(reverse("admin:library_author_change", args=[author.pk]))
        self.assertEqual(response.status_code, 200)
        for book, relationship in zip(books, relationships, strict=True):
            book_url = reverse("admin:library_book_change", args=[book.pk])
            self.assertContains(response, f'href="{book_url}">{book.title}</a>')
            self.assertNotContains(response, str(relationship))
        self.assertNotContains(response, "column-created_at")
        self.assertNotContains(response, "column-updated_at")
        self.assertContains(response, "Remove relationship")

        inline = AuthorBookContextInline(Author, admin.site)
        FormSet = inline.get_formset(self.request, author)
        formset = _delete_formset(FormSet, instance=author, selected=relationships[0])
        self.assertTrue(formset.is_valid(), formset.errors)
        AuthorAdmin(Author, admin.site).save_formset(
            self.request,
            SimpleNamespace(instance=author),
            formset,
            True,
        )
        self.assertFalse(BookAuthor.objects.filter(pk=relationships[0].pk).exists())
        self.assertTrue(BookAuthor.objects.filter(pk=relationships[1].pk).exists())
        self.assertEqual(Book.objects.filter(pk__in=[book.pk for book in books]).count(), 2)

    def test_author_admin_sanitizes_biography(self):
        author = Author.objects.create(name="Admin Author")
        form_class = AuthorAdmin(Author, admin.site).get_form(self.request, author)
        form = form_class(
            data={
                "name": author.name,
                "sort_name": "",
                "normalized_name": "",
                "biography": '<p class="lead">Safe <em>bio</em></p><script>bad()</script>',
            },
            instance=author,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        author.refresh_from_db()
        self.assertEqual(author.biography, "<p>Safe <em>bio</em></p>")

    def test_series_context_links_books_and_removes_only_selected_relationship(self):
        series = Series.objects.create(name="Context Series")
        books = [Book.objects.create(title=f"Series Book {index}") for index in range(2)]
        relationships = [BookSeries.objects.create(book=book, series=series) for book in books]
        response = self.client.get(reverse("admin:library_series_change", args=[series.pk]))
        self.assertEqual(response.status_code, 200)
        for book, relationship in zip(books, relationships, strict=True):
            book_url = reverse("admin:library_book_change", args=[book.pk])
            self.assertContains(response, f'href="{book_url}">{book.title}</a>')
            self.assertNotContains(response, str(relationship))
        self.assertNotContains(response, "column-created_at")
        self.assertNotContains(response, "column-updated_at")
        self.assertContains(response, "Remove relationship")

        inline = SeriesBookContextInline(Series, admin.site)
        FormSet = inline.get_formset(self.request, series)
        formset = _delete_formset(FormSet, instance=series, selected=relationships[0])
        self.assertTrue(formset.is_valid(), formset.errors)
        SeriesAdmin(Series, admin.site).save_formset(
            self.request,
            SimpleNamespace(instance=series),
            formset,
            True,
        )
        self.assertFalse(BookSeries.objects.filter(pk=relationships[0].pk).exists())
        self.assertTrue(BookSeries.objects.filter(pk=relationships[1].pk).exists())
        self.assertEqual(Book.objects.filter(pk__in=[book.pk for book in books]).count(), 2)

    def test_series_admin_sanitizes_summary(self):
        series = Series.objects.create(name="Admin Series")
        form_class = SeriesAdmin(Series, admin.site).get_form(self.request, series)
        form = form_class(
            data={
                "name": series.name,
                "sort_name": "",
                "normalized_name": "",
                "summary": '<ul><li onclick="bad()">Safe</li></ul><img src="bad">',
            },
            instance=series,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        series.refresh_from_db()
        self.assertEqual(series.summary, "<ul><li>Safe</li></ul>")

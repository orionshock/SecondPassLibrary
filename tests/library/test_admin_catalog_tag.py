from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from library.admin import CatalogTagAdmin
from library.models import CatalogTag


class CatalogTagAdminTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_superuser(
            username="owner",
            password="pw",
        )
        self.request = RequestFactory().post("/admin/library/catalogtag/")
        self.request.user = self.owner
        self.model_admin = CatalogTagAdmin(CatalogTag, admin.site)

    def test_layout_and_read_only_identity_fields(self):
        form_class = self.model_admin.get_form(self.request)

        self.assertEqual(
            self.model_admin.get_fields(self.request),
            ["name", "sort_name", "normalized_name", "slug"],
        )
        self.assertEqual(
            set(self.model_admin.get_readonly_fields(self.request)),
            {"normalized_name", "slug"},
        )
        self.assertEqual(list(form_class.base_fields), ["name", "sort_name"])

    def test_submitted_normalized_name_is_ignored(self):
        form_class = self.model_admin.get_form(self.request)
        form = form_class(
            data={
                "name": "  Urban   Fantasy ",
                "sort_name": "Fantasy, Urban",
                "normalized_name": "attacker-controlled",
                "slug": "attacker-controlled",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)
        tag = form.save()
        self.assertEqual(tag.name, "Urban Fantasy")
        self.assertEqual(tag.normalized_name, "urban fantasy")
        self.assertEqual(tag.slug, "urban-fantasy")

    def test_name_change_recalculates_identity_and_preserves_slug(self):
        tag = CatalogTag.objects.create(
            name="Mystery",
            sort_name="Mystery",
            normalized_name="mystery",
            slug="mystery",
        )
        form_class = self.model_admin.get_form(self.request, tag)
        form = form_class(
            data={"name": "Crime Fiction", "sort_name": "Fiction, Crime"},
            instance=tag,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        tag.refresh_from_db()
        self.assertEqual(tag.normalized_name, "crime fiction")
        self.assertEqual(tag.slug, "mystery")

    def test_sort_name_only_change_preserves_normalized_identity_and_slug(self):
        tag = CatalogTag.objects.create(
            name="Science Fiction",
            sort_name="Science Fiction",
            normalized_name="science fiction",
            slug="science-fiction",
        )
        form_class = self.model_admin.get_form(self.request, tag)
        form = form_class(
            data={"name": tag.name, "sort_name": "Fiction, Science"},
            instance=tag,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        tag.refresh_from_db()
        self.assertEqual(tag.normalized_name, "science fiction")
        self.assertEqual(tag.slug, "science-fiction")

    def test_conflicting_normalized_name_is_a_form_error(self):
        CatalogTag.objects.create(
            name="Urban Fantasy",
            normalized_name="urban fantasy",
            slug="urban-fantasy",
        )
        tag = CatalogTag.objects.create(
            name="Mystery",
            normalized_name="mystery",
            slug="mystery",
        )
        form_class = self.model_admin.get_form(self.request, tag)
        form = form_class(
            data={"name": " URBAN   FANTASY ", "sort_name": ""},
            instance=tag,
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            form.errors["name"],
            ["A Catalog Tag with this normalized name already exists."],
        )

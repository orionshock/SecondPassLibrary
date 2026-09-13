from importlib import import_module
from types import SimpleNamespace

from django import forms
from django.contrib import admin
from django.contrib.admin.widgets import RelatedFieldWidgetWrapper
from django.test import SimpleTestCase, override_settings
from django.urls import path

from core.admin_widgets import keep_only_view_related_control_for_models
from library.models import BookSeries, LibraryGroup, Series


urlpatterns = [path("admin/", admin.site.urls)]


@override_settings(ROOT_URLCONF=__name__)
class AdminWidgetControlTests(SimpleTestCase):
    def related_widget(self):
        relation = BookSeries._meta.get_field("series").remote_field
        return RelatedFieldWidgetWrapper(
            forms.Select(),
            relation,
            admin.site,
            can_add_related=True,
            can_change_related=True,
            can_delete_related=True,
            can_view_related=True,
        )

    def test_target_related_widget_renders_only_the_view_shortcut(self):
        widget = self.related_widget()
        formfield = SimpleNamespace(widget=widget)
        db_field = BookSeries._meta.get_field("series")

        keep_only_view_related_control_for_models(
            formfield,
            db_field,
            {Series},
        )
        rendered = widget.render("series", None)

        self.assertIn("related-widget-wrapper-link view-related", rendered)
        self.assertNotIn("related-widget-wrapper-link add-related", rendered)
        self.assertNotIn("related-widget-wrapper-link change-related", rendered)
        self.assertNotIn("related-widget-wrapper-link delete-related", rendered)

    def test_importing_library_admin_does_not_change_an_unscoped_widget(self):
        import_module("library.admin")
        widget = self.related_widget()
        formfield = SimpleNamespace(widget=widget)
        db_field = BookSeries._meta.get_field("series")

        keep_only_view_related_control_for_models(
            formfield,
            db_field,
            {LibraryGroup},
        )
        rendered = widget.render("series", None)

        self.assertIn("related-widget-wrapper-link view-related", rendered)
        self.assertIn("related-widget-wrapper-link add-related", rendered)
        self.assertIn("related-widget-wrapper-link change-related", rendered)
        self.assertIn("related-widget-wrapper-link delete-related", rendered)

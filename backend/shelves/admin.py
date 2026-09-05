from __future__ import annotations

from django import forms
from django.contrib import admin
from django.contrib.admin import DateFieldListFilter
from django.contrib.admin.utils import quote
from django.db.models import Count
from django.forms.models import BaseInlineFormSet
from django.urls import NoReverseMatch
from django.urls import reverse
from django.utils.html import format_html

from core.admin_widgets import (
    UserRelatedViewOnlyControlsMixin,
    keep_only_view_related_control_for_models,
)
from core.rich_text import sanitize_descriptive_prose
from library.models import LibraryGroup

from .models import Shelf, ShelfItem
from .item_services import canonicalize_shelf_positions


class ShelfAdminForm(forms.ModelForm):
    class Meta:
        model = Shelf
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].strip = False

    def clean_description(self):
        return sanitize_descriptive_prose(self.cleaned_data.get("description"))

    def clean(self):
        cleaned_data = super().clean()

        owner_type = cleaned_data.get("owner_type")
        owner_user = cleaned_data.get("owner_user")
        owner_group = cleaned_data.get("owner_group")
        visibility = cleaned_data.get("visibility")

        if owner_type == Shelf.OWNER_TYPE_USER:
            if owner_user is None:
                self.add_error(
                    "owner_user", "User-owned shelf must have an owner user."
                )
            if owner_group is not None:
                self.add_error(
                    "owner_group", "User-owned shelf must not have an owner group."
                )
            if visibility not in [Shelf.VISIBILITY_PRIVATE, Shelf.VISIBILITY_LISTED]:
                self.add_error("visibility", "Invalid visibility for user-owned shelf.")
        elif owner_type == Shelf.OWNER_TYPE_GROUP:
            if owner_group is None:
                self.add_error(
                    "owner_group", "Group-owned shelf must have an owner group."
                )
            if owner_user is not None:
                self.add_error(
                    "owner_user", "Group-owned shelf must not have an owner user."
                )
            if visibility != Shelf.VISIBILITY_PRIVATE:
                self.add_error(
                    "visibility",
                    "Group-owned shelves must use visibility=private.",
                )
        elif owner_type is not None:
            self.add_error("owner_type", "Invalid owner type.")

        return cleaned_data


class LibraryGroupRelatedViewOnlyControlsMixin:
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        return keep_only_view_related_control_for_models(
            formfield,
            db_field,
            {LibraryGroup},
        )


class ShelfItemInlineFormSet(BaseInlineFormSet):
    def save_existing_objects(self, commit=True):
        self._deleted_shelf_ids: set[object] = set()
        saved_objects = super().save_existing_objects(commit=commit)

        if commit and self._deleted_shelf_ids:
            for shelf in Shelf.objects.filter(pk__in=self._deleted_shelf_ids):
                canonicalize_shelf_positions(shelf)

        return saved_objects

    def delete_existing(self, obj, commit=True):
        shelf_id = obj.shelf_id
        super().delete_existing(obj, commit=commit)
        if commit and shelf_id is not None:
            self._deleted_shelf_ids.add(shelf_id)


class ShelfItemInline(admin.TabularInline):
    model = ShelfItem
    formset = ShelfItemInlineFormSet
    template = "admin/shelves/shelf/edit_inline/shelf_items_tabular.html"
    extra = 0
    fields = ["book_link", "position", "added_by", "created_at", "updated_at"]
    readonly_fields = [
        "book_link",
        "position",
        "added_by",
        "created_at",
        "updated_at",
    ]
    can_delete = True
    show_change_link = False

    @admin.display(description="Book")
    def book_link(self, obj):
        if obj.pk is None or obj.book_id is None:
            return ""
        try:
            url = reverse("admin:library_book_change", args=[obj.book_id])
        except NoReverseMatch:
            url = f"/admin/library/book/{quote(obj.book_id)}/change/"
        return format_html('<a href="{}">{}</a>', url, obj.book.title)

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("book", "added_by")
            .order_by("position", "created_at")
        )


@admin.register(Shelf)
class ShelfAdmin(
    LibraryGroupRelatedViewOnlyControlsMixin,
    UserRelatedViewOnlyControlsMixin,
    admin.ModelAdmin,
):
    form = ShelfAdminForm
    list_display = [
        "id",
        "name",
        "owner_type",
        "owner_user",
        "owner_group",
        "visibility",
        "item_count",
        "created_by",
        "updated_at",
    ]
    list_filter = [
        "owner_type",
        "visibility",
        ("created_at", DateFieldListFilter),
        ("updated_at", DateFieldListFilter),
    ]
    search_fields = [
        "name",
        "description",
        "owner_user__username",
        "owner_user__email",
        "owner_group__name",
        "created_by__username",
        "created_by__email",
    ]
    readonly_fields = ["id", "created_at", "updated_at", "created_by"]
    autocomplete_fields = ["owner_user", "owner_group", "created_by"]
    inlines = [ShelfItemInline]
    fields = [
        "id",
        "name",
        "description",
        "owner_type",
        "owner_user",
        "owner_group",
        "visibility",
        "created_by",
        "created_at",
        "updated_at",
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("owner_user", "owner_group", "created_by")
            .annotate(_item_count=Count("items"))
        )

    @admin.display(description="Items", ordering="_item_count")
    def item_count(self, obj):
        return obj._item_count

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in {"owner_user", "owner_group", "created_by"}:
            kwargs["required"] = False
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(ShelfItem)
class ShelfItemAdmin(admin.ModelAdmin):
    list_display = ["id", "shelf", "book", "position", "added_by", "updated_at"]
    list_filter = ["shelf__owner_type", ("created_at", DateFieldListFilter)]
    search_fields = ["shelf__name", "book__title", "added_by__username"]
    readonly_fields = [
        "id",
        "shelf",
        "book",
        "position",
        "added_by",
        "created_at",
        "updated_at",
    ]
    raw_id_fields = ["shelf", "book", "added_by"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.has_perm(
            "shelves.delete_shelf"
        ) or super().has_delete_permission(request, obj=obj)

    def has_module_permission(self, request):
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("shelf", "book", "added_by")
            .order_by("shelf_id", "position", "created_at")
        )

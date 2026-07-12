from types import MethodType

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from core import server_settings
from library.file_repair import (
    ChecksumChangeConfirmationRequired,
    ChecksumCollisionError,
    ReplaceExistingConfirmationRequired,
    StoredEpubRepairError,
    repair_stored_epub,
)
from library.groups import services as group_services
from library.groups.public_group import is_public_group

from .models import (
    Book,
    BookGroupAssignment,
    CatalogTag,
    LibraryGroup,
    LibraryGroupMembership,
)


LIBRARY_ADMIN_MODEL_ORDER = {
    "Book": (10, "Books"),
    "CatalogTag": (20, "Catalog Tags"),
    "LibraryGroup": (30, "Library Groups"),
    "LibraryGroupMembership": (40, "User Group Assignments"),
    "BookGroupAssignment": (50, "Book Group Assignments"),
}


def _sort_library_admin_models(app):
    for model in app["models"]:
        configuration = LIBRARY_ADMIN_MODEL_ORDER.get(model["object_name"])
        if configuration is not None:
            model["name"] = configuration[1]
    app["models"].sort(
        key=lambda model: (
            LIBRARY_ADMIN_MODEL_ORDER.get(model["object_name"], (100, ""))[0],
            model["name"],
        )
    )


def _install_library_admin_app_list_ordering():
    if hasattr(admin.site, "_secondpass_library_original_get_app_list"):
        return

    admin.site._secondpass_library_original_get_app_list = admin.site.get_app_list

    def get_app_list(self, request, app_label=None):
        app_list = self._secondpass_library_original_get_app_list(request, None)
        library_app = next(
            (app for app in app_list if app["app_label"] == "library"),
            None,
        )
        if library_app is not None:
            _sort_library_admin_models(library_app)
        if app_label is not None:
            app_list = [app for app in app_list if app["app_label"] == app_label]
        return app_list

    admin.site.get_app_list = MethodType(get_app_list, admin.site)


class StoredEpubRepairAdminForm(forms.Form):
    replacement_epub = forms.FileField(label="Replacement EPUB")
    replace_existing = forms.BooleanField(
        required=False,
        label="Replace existing stored file",
    )
    allow_checksum_change = forms.BooleanField(
        required=False,
        label="Allow different checksum",
        help_text=(
            "A different EPUB may invalidate existing EPUB CFI anchors used by "
            "progress, highlights, notes, and bookmarks."
        ),
    )


class AdvancedGroupsAssignmentAdminMixin:
    @staticmethod
    def _advanced_groups_enabled():
        return server_settings.advanced_library_groups_enabled()

    def get_model_perms(self, request):
        if not self._advanced_groups_enabled():
            return {}
        return super().get_model_perms(request)

    def has_module_permission(self, request):
        return self._advanced_groups_enabled() and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return self._advanced_groups_enabled() and super().has_view_permission(
            request,
            obj=obj,
        )

    def has_add_permission(self, request):
        return self._advanced_groups_enabled() and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return self._advanced_groups_enabled() and super().has_change_permission(
            request,
            obj=obj,
        )

    def has_delete_permission(self, request, obj=None):
        return self._advanced_groups_enabled() and super().has_delete_permission(
            request,
            obj=obj,
        )


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    search_fields = ["title", "sort_title", "checksum"]
    readonly_fields = ["book_file", "file_format", "checksum", "file_size"]
    change_form_template = "admin/library/book/change_form.html"

    def get_urls(self):
        return [
            path(
                "<path:object_id>/repair-stored-epub/",
                self.admin_site.admin_view(self.repair_stored_epub_view),
                name="library_book_repair_stored_epub",
            ),
            *super().get_urls(),
        ]

    def render_change_form(
        self,
        request,
        context,
        add=False,
        change=False,
        form_url="",
        obj=None,
    ):
        context["show_stored_epub_repair"] = bool(
            obj is not None and request.user.is_superuser
        )
        return super().render_change_form(
            request,
            context,
            add=add,
            change=change,
            form_url=form_url,
            obj=obj,
        )

    def repair_stored_epub_view(self, request, object_id):
        if not request.user.is_superuser:
            raise PermissionDenied
        book = self.get_object(request, object_id)
        if book is None:
            raise Http404

        change_url = reverse("admin:library_book_change", args=[book.pk])
        if request.method == "POST":
            form = StoredEpubRepairAdminForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    result = repair_stored_epub(
                        book=book,
                        uploaded_epub=form.cleaned_data["replacement_epub"],
                        replace_existing=form.cleaned_data["replace_existing"],
                        allow_checksum_change=form.cleaned_data[
                            "allow_checksum_change"
                        ],
                        actor=request.user,
                    )
                except StoredEpubRepairError as exc:
                    form.add_error(None, _bounded_file_repair_error(exc))
                else:
                    if result.checksum_changed:
                        messages.warning(
                            request,
                            "The stored EPUB checksum changed. Existing EPUB CFI "
                            "anchors may no longer match.",
                        )
                    messages.success(request, "Stored EPUB repaired successfully.")
                    return HttpResponseRedirect(change_url)
        else:
            form = StoredEpubRepairAdminForm()

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Repair stored EPUB",
            "book": book,
            "form": form,
            "change_url": change_url,
            "file_state": _book_file_state(book),
        }
        return TemplateResponse(
            request,
            "admin/library/book/repair_stored_epub.html",
            context,
        )


def _book_file_state(book):
    file_name = str(book.book_file.name or "")
    physical_exists = False
    if file_name:
        try:
            physical_exists = book.book_file.storage.exists(file_name)
        except Exception:
            physical_exists = False
    checksum = str(book.checksum or "")
    return {
        "has_reference": bool(file_name),
        "physical_exists": physical_exists,
        "format": str(book.file_format or "").upper(),
        "file_size": book.file_size,
        "checksum_short": f"{checksum[:12]}…" if checksum else "Not recorded",
    }


def _bounded_file_repair_error(exc):
    if isinstance(exc, ReplaceExistingConfirmationRequired):
        return "Confirm replacement of the existing stored EPUB to continue."
    if isinstance(exc, ChecksumChangeConfirmationRequired):
        return (
            "Confirm the different checksum to continue. Existing EPUB CFI "
            "anchors may no longer match."
        )
    if isinstance(exc, ChecksumCollisionError):
        return "Another Book already owns this EPUB content."
    return "Stored EPUB repair could not be completed."


@admin.register(LibraryGroup)
class LibraryGroupAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(CatalogTag)
class CatalogTagAdmin(admin.ModelAdmin):
    search_fields = ["name", "normalized_name"]


@admin.register(LibraryGroupMembership)
class LibraryGroupMembershipAdmin(
    AdvancedGroupsAssignmentAdminMixin,
    admin.ModelAdmin,
):
    list_display = ["user", "group", "is_curator", "created_at", "updated_at"]
    list_display_links = ["user"]
    list_filter = ["group", "is_curator"]
    search_fields = ["user__username", "user__email", "group__name"]
    readonly_fields = [
        "id",
        "user",
        "group",
        "created_at",
        "updated_at",
    ]
    actions = ["remove_assignments"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("user", "group")

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ["id", "created_at", "updated_at"]
        return self.readonly_fields

    def get_fields(self, request, obj=None):
        fields = ["user", "group"]
        if self._can_edit_curator(obj):
            fields.append("is_curator")
        if obj is not None:
            fields.extend(["created_at", "updated_at"])
        return fields

    @staticmethod
    def _can_edit_curator(obj):
        return bool(
            obj is not None
            and server_settings.advanced_library_groups_enabled()
            and not is_public_group(obj.group)
        )

    def save_model(self, request, obj, form, change):
        if change:
            if self._can_edit_curator(obj):
                group_services.set_group_membership_curator(
                    membership=obj,
                    is_curator=obj.is_curator,
                )
            return
        membership = group_services.add_user_to_group(
            user=obj.user,
            group=obj.group,
            is_curator=obj.is_curator,
        )
        obj.pk = membership.pk
        obj.is_curator = membership.is_curator
        obj.created_at = membership.created_at
        obj.updated_at = membership.updated_at

    def delete_model(self, request, obj):
        group_services.remove_user_from_group(user=obj.user, group=obj.group)

    @admin.action(description="Remove selected user-group assignments")
    def remove_assignments(self, request, queryset):
        removed = 0
        memberships = list(queryset.select_related("user", "group"))
        for membership in memberships:
            removed += group_services.remove_user_from_group(
                user=membership.user,
                group=membership.group,
            )
        self.message_user(request, f"Removed {removed} user-group assignment(s).")

@admin.register(BookGroupAssignment)
class BookGroupAssignmentAdmin(
    AdvancedGroupsAssignmentAdminMixin,
    admin.ModelAdmin,
):
    list_display = ["book", "group", "added_by", "created_at", "updated_at"]
    list_display_links = ["book"]
    list_filter = ["group"]
    search_fields = ["book__title", "book__checksum", "group__name", "added_by__username"]
    readonly_fields = ["id", "book", "group", "added_by", "created_at", "updated_at"]
    actions = ["remove_assignments"]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("book", "group", "added_by")

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return ["id", "added_by", "created_at", "updated_at"]
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        if change:
            return
        assignment = group_services.add_book_to_group(
            book=obj.book,
            group=obj.group,
            actor=request.user,
        )
        obj.pk = assignment.pk
        obj.added_by = assignment.added_by
        obj.created_at = assignment.created_at
        obj.updated_at = assignment.updated_at

    def delete_model(self, request, obj):
        group_services.remove_book_from_group(
            book=obj.book,
            group=obj.group,
            actor=request.user,
        )

    @admin.action(description="Remove selected book-group assignments")
    def remove_assignments(self, request, queryset):
        removed = 0
        assignments = list(queryset.select_related("book", "group"))
        for assignment in assignments:
            removed += group_services.remove_book_from_group(
                book=assignment.book,
                group=assignment.group,
                actor=request.user,
            )
        self.message_user(request, f"Removed {removed} book-group assignment(s).")

    def has_change_permission(self, request, obj=None):
        return False


_install_library_admin_app_list_ordering()

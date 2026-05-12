from __future__ import annotations

from django.contrib import admin
from django.contrib.admin import DateFieldListFilter

from .models import Shelf, ShelfItem


class ShelfItemInline(admin.TabularInline):
    model = ShelfItem
    extra = 0
    raw_id_fields = ["book", "added_by"]
    fields = ["book", "position", "added_by", "created_at", "updated_at"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Shelf)
class ShelfAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "owner_type",
        "owner_user",
        "owner_group",
        "visibility",
        "created_by",
        "updated_at",
    ]
    list_filter = ["owner_type", "visibility", ("created_at", DateFieldListFilter)]
    search_fields = [
        "name",
        "description",
        "owner_user__username",
        "owner_user__email",
        "owner_group__name",
    ]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["owner_user", "owner_group", "created_by"]
    inlines = [ShelfItemInline]


@admin.register(ShelfItem)
class ShelfItemAdmin(admin.ModelAdmin):
    list_display = ["shelf", "book", "position", "added_by", "updated_at"]
    list_filter = ["shelf__owner_type", ("created_at", DateFieldListFilter)]
    search_fields = ["shelf__name", "book__title"]
    readonly_fields = ["id", "created_at", "updated_at"]
    raw_id_fields = ["shelf", "book", "added_by"]


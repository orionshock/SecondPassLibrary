from django.contrib import admin

from .models import ServerSetting


@admin.register(ServerSetting)
class ServerSettingAdmin(admin.ModelAdmin):
    list_display = ["key", "updated_at"]
    search_fields = ["key", "description"]
    readonly_fields = ["key", "created_at", "updated_at"]

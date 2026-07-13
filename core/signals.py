from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import ServerSetting
from .server_settings import (
    APPLICATION_LOG_LEVEL_SETTING,
    DEFAULT_APPLICATION_LOG_LEVEL,
    apply_application_log_level,
    clear_server_settings_cache,
)


@receiver(post_save, sender=ServerSetting)
def _server_setting_post_save(sender, instance: ServerSetting, **kwargs) -> None:
    clear_server_settings_cache()
    if instance.key == APPLICATION_LOG_LEVEL_SETTING:
        apply_application_log_level(instance.value)


@receiver(post_delete, sender=ServerSetting)
def _server_setting_post_delete(sender, instance: ServerSetting, **kwargs) -> None:
    clear_server_settings_cache()
    if instance.key == APPLICATION_LOG_LEVEL_SETTING:
        apply_application_log_level(DEFAULT_APPLICATION_LOG_LEVEL)

from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured


class AdvancedGroupsConsolidationError(Exception):
    pass


class AdvancedGroupsConsolidationNotNeeded(Exception):
    pass


class AdvancedGroupsPlanStale(Exception):
    pass


def build_advanced_groups_disable_plan(*args, **kwargs):
    raise ImproperlyConfigured("LibraryReWrite2607 group consolidation is not rebuilt yet.")


def execute_advanced_groups_disable_plan(*args, **kwargs):
    raise ImproperlyConfigured("LibraryReWrite2607 group consolidation is not rebuilt yet.")

def keep_only_view_related_controls(widget):
    """Keep navigation while removing inline mutation shortcuts from a wrapper."""
    for flag in ("can_add_related", "can_change_related", "can_delete_related"):
        if hasattr(widget, flag):
            setattr(widget, flag, False)
    return widget


def keep_only_view_related_control_for_models(formfield, db_field, models):
    remote_field = getattr(db_field, "remote_field", None)
    related_model = getattr(remote_field, "model", None)
    if related_model not in models:
        return formfield

    keep_only_view_related_controls(formfield.widget)
    return formfield


class RelatedViewOnlyControlsMixin:
    related_view_only_models = frozenset()

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        return keep_only_view_related_control_for_models(
            formfield,
            db_field,
            self.related_view_only_models,
        )

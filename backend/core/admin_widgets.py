from django.contrib.auth import get_user_model


def keep_only_view_related_control_for_models(formfield, db_field, models):
    remote_field = getattr(db_field, "remote_field", None)
    related_model = getattr(remote_field, "model", None)
    if related_model not in models:
        return formfield

    widget = formfield.widget
    for flag in ("can_add_related", "can_change_related", "can_delete_related"):
        if hasattr(widget, flag):
            setattr(widget, flag, False)
    return formfield


def keep_only_user_view_related_control(formfield, db_field):
    return keep_only_view_related_control_for_models(
        formfield,
        db_field,
        {get_user_model()},
    )


class UserRelatedViewOnlyControlsMixin:
    def formfield_for_dbfield(self, db_field, request, **kwargs):
        formfield = super().formfield_for_dbfield(db_field, request, **kwargs)
        return keep_only_user_view_related_control(formfield, db_field)

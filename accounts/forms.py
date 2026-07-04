from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django import forms

from core.server_settings import DEFAULT_SERVER_NAME
from library.public_group import (
    DEFAULT_PUBLIC_GROUP_DESCRIPTION,
    DEFAULT_PUBLIC_GROUP_NAME,
)


User = get_user_model()


class FirstOwnerSetupForm(UserCreationForm):
    server_name = forms.CharField(
        label="Server Name",
        max_length=120,
        initial=DEFAULT_SERVER_NAME,
    )
    server_description = forms.CharField(
        label="Server Description",
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    public_group_name = forms.CharField(
        label="Public Group Name",
        max_length=255,
        initial=DEFAULT_PUBLIC_GROUP_NAME,
    )
    public_group_description = forms.CharField(
        label="Public Group Description",
        required=False,
        initial=DEFAULT_PUBLIC_GROUP_DESCRIPTION,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    first_name = forms.CharField(label="First name", max_length=150, required=False)
    last_name = forms.CharField(label="Last name", max_length=150, required=False)
    email = forms.EmailField(label="Email", required=False)
    advanced_library_groups_enabled = forms.BooleanField(
        label="Enable Advanced Library Group Usage",
        required=False,
        initial=False,
        help_text=(
            "Advanced library groups let you create separate curator-managed "
            "library rooms with their own memberships and group-owned shelves. "
            "Leave this off if you only need the Common Room, managed by librarians "
            "as the shared public library space."
        ),
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Password"
        self.fields["password2"].label = "Confirm password"

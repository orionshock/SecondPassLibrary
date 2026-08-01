from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django import forms

from core.server_settings import DEFAULT_SERVER_NAME
from library.groups.public_group import (
    DEFAULT_PUBLIC_GROUP_DESCRIPTION,
    DEFAULT_PUBLIC_GROUP_NAME,
)


User = get_user_model()


class FirstOwnerSetupForm(UserCreationForm):
    server_name = forms.CharField(
        label="Server Name",
        max_length=120,
        initial=DEFAULT_SERVER_NAME,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    server_description = forms.CharField(
        label="Server Description",
        max_length=1000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "autocomplete": "off"}),
    )
    public_group_name = forms.CharField(
        label="Public Group Name",
        max_length=255,
        initial=DEFAULT_PUBLIC_GROUP_NAME,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    public_group_description = forms.CharField(
        label="Public Group Description",
        required=False,
        initial=DEFAULT_PUBLIC_GROUP_DESCRIPTION,
        widget=forms.Textarea(attrs={"rows": 3, "autocomplete": "off"}),
    )
    first_name = forms.CharField(
        label="First name",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        label="Last name",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        widget=forms.EmailInput(
            attrs={
                "autocomplete": "email",
                "autocapitalize": "none",
                "autocorrect": "off",
                "spellcheck": "false",
            }
        ),
    )
    advanced_library_groups_enabled = forms.BooleanField(
        label="I understand and want advanced library groups",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"autocomplete": "off"}),
        help_text=(
            "Most households should leave this off unless they know they need "
            "multiple managed library rooms."
        ),
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].widget.attrs.update(
            {
                "autocomplete": "username",
                "autocapitalize": "none",
                "autocorrect": "off",
                "spellcheck": "false",
            }
        )
        self.fields["password1"].label = "Password"
        self.fields["password2"].label = "Confirm password"

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django import forms

from core.server_settings import DEFAULT_SERVER_NAME
from library.groups.public_group import (
    DEFAULT_PUBLIC_GROUP_DESCRIPTION,
    DEFAULT_PUBLIC_GROUP_NAME,
)

from .login_throttle import (
    LoginTemporarilyThrottled,
    clear_login_attempts,
    record_failed_login,
    release_login_reservation,
    reserve_login_attempt,
)
from .request_identity import canonical_client_ip


User = get_user_model()


class ThrottledAuthenticationForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "temporarily_throttled": (
            "Too many login attempts. Please wait a few minutes and try again."
        ),
    }

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if not username or not password:
            return super().clean()

        try:
            reservation = reserve_login_attempt(
                source_ip=canonical_client_ip(self.request),
                username=username,
            )
        except LoginTemporarilyThrottled as exc:
            raise ValidationError(
                self.error_messages["temporarily_throttled"],
                code="temporarily_throttled",
            ) from exc

        try:
            cleaned_data = super().clean()
        except ValidationError:
            record_failed_login(reservation)
            raise
        except Exception:
            release_login_reservation(reservation)
            raise

        clear_login_attempts(reservation)
        return cleaned_data


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

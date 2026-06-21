from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django import forms


User = get_user_model()


class FirstOwnerSetupForm(UserCreationForm):
    first_name = forms.CharField(label="First name", max_length=150, required=False)
    last_name = forms.CharField(label="Last name", max_length=150, required=False)
    email = forms.EmailField(label="Email", required=False)

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Password"
        self.fields["password2"].label = "Confirm password"

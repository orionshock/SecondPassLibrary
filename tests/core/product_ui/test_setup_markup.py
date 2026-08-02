"""Accessibility and interaction contracts for the Django-rendered Setup page."""

from django.core.cache import cache
from django.test import TestCase

from core.server_settings import clear_server_settings_cache


class SetupMarkupTests(TestCase):
    valid_setup_data = {
        "server_name": "Family Library",
        "server_description": "Shared at home.",
        "public_group_name": "Reading Room",
        "public_group_description": "Books for everyone.",
        "username": "owner",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada@example.com",
        "password1": "Correct-Horse-Battery-47",
        "password2": "Correct-Horse-Battery-47",
    }

    def setUp(self):
        cache.clear()
        clear_server_settings_cache()

    def test_setup_structure_and_field_semantics_remain_explicit(self):
        response = self.client.get("/setup/")
        form = response.context["form"]

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<legend>Server</legend>', html=True)
        self.assertContains(response, '<legend>Public Space</legend>', html=True)
        self.assertContains(response, '<legend>Owner Account</legend>', html=True)
        self.assertContains(response, '<legend>Advanced</legend>', html=True)
        self.assertEqual(response.content.count(b'<fieldset class="setup-section '), 4)

        for field_name in (
            "server_name",
            "public_group_name",
            "username",
            "password1",
            "password2",
        ):
            with self.subTest(field=field_name):
                self.assertTrue(form.fields[field_name].required)
        for field_name in (
            "server_description",
            "public_group_description",
            "first_name",
            "last_name",
            "email",
            "advanced_library_groups_enabled",
        ):
            with self.subTest(field=field_name):
                self.assertFalse(form.fields[field_name].required)

    def test_help_text_ids_match_django_aria_descriptions(self):
        response = self.client.get("/setup/")
        form = response.context["form"]
        content = response.content.decode("utf-8")

        fields_with_help = [field for field in form if field.help_text]
        self.assertTrue(fields_with_help)
        for field in fields_with_help:
            with self.subTest(field=field.name):
                help_id = f"{field.auto_id}_helptext"
                self.assertIn(f'id="{help_id}"', content)
                self.assertIn(help_id, str(field))

    def test_failed_setup_preserves_non_secret_values_and_focuses_first_error(self):
        response = self.client.post(
            "/setup/",
            {
                **self.valid_setup_data,
                "password2": "A-Different-Password-48",
            },
        )
        form = response.context["form"]
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(form["password2"].errors)
        self.assertContains(response, 'value="Family Library"', html=False)
        self.assertContains(response, 'value="Reading Room"', html=False)
        self.assertContains(response, "Shared at home.")
        self.assertContains(response, "Books for everyone.")
        self.assertNotContains(response, 'value="Correct-Horse-Battery-47"')
        self.assertIn('aria-invalid="true"', str(form["password2"]))
        self.assertIn("id_password2_helptext", str(form["password2"]))
        self.assertIn("id_password2_error", str(form["password2"]))
        self.assertIn('id="id_password2_helptext"', content)
        self.assertIn('id="id_password2_error"', content)
        self.assertIn("form.querySelector('[aria-invalid=\"true\"]')", content)
        self.assertIn('removeAttribute("autofocus")', content)
        self.assertIn("firstInvalidField.focus()", content)

    def test_initial_setup_keeps_username_autofocus(self):
        response = self.client.get("/setup/")
        form = response.context["form"]

        self.assertEqual(response.status_code, 200)
        self.assertIn("autofocus", str(form["username"]))
        self.assertFalse(form.errors)

    def test_setup_fields_use_explicit_autofill_semantics(self):
        response = self.client.get("/setup/")
        form = response.context["form"]

        expected_autocomplete = {
            "username": "username",
            "first_name": "given-name",
            "last_name": "family-name",
            "email": "email",
            "password1": "new-password",
            "password2": "new-password",
            "server_name": "off",
            "server_description": "off",
            "public_group_name": "off",
            "public_group_description": "off",
            "advanced_library_groups_enabled": "off",
        }
        for field_name, autocomplete in expected_autocomplete.items():
            with self.subTest(field=field_name):
                self.assertEqual(
                    form.fields[field_name].widget.attrs.get("autocomplete"),
                    autocomplete,
                )

        for field_name in ("username", "email"):
            with self.subTest(field=field_name):
                attrs = form.fields[field_name].widget.attrs
                self.assertEqual(attrs.get("autocapitalize"), "none")
                self.assertEqual(attrs.get("autocorrect"), "off")
                self.assertEqual(attrs.get("spellcheck"), "false")

    def test_dialog_state_reset_and_submit_pending_protection_are_wired(self):
        response = self.client.get("/setup/")
        content = response.content.decode("utf-8")

        self.assertContains(response, "data-setup-submit")
        self.assertContains(response, 'data-pending-label="Completing setup..."')
        self.assertIn('dialog.returnValue = ""', content)
        self.assertIn('form.addEventListener("submit"', content)
        self.assertIn('form.setAttribute("aria-busy", "true")', content)
        self.assertIn("submitButton.disabled = true", content)
        self.assertLess(
            content.index("event.preventDefault()"),
            content.index("submitButton.disabled = true"),
        )

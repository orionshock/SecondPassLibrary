from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from maintenance.admin import MaintenanceTaskConfigAdmin
from maintenance.models import MaintenanceTaskConfig, MaintenanceTaskRun


@override_settings(
    SECOND_PASS_ENABLE_DJANGO_ADMIN=True,
    ROOT_URLCONF="tests.maintenance.urls",
)
class MaintenanceAdminTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="maintenance-owner",
            password="testpass",
            email="owner@example.com",
        )
        self.configuration = MaintenanceTaskConfig.objects.get(
            task_key="cleanup_client_pairing_requests"
        )

    def test_surface_is_superuser_only_and_identity_is_read_only(self):
        staff = get_user_model().objects.create_user(
            username="staff",
            password="testpass",
            is_staff=True,
        )
        self.client.force_login(staff)
        url = reverse("admin:maintenance_maintenancetaskconfig_changelist")
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_login(self.superuser)
        response = self.client.get(
            reverse(
                "admin:maintenance_maintenancetaskconfig_change",
                args=(self.configuration.pk,),
            )
        )
        self.assertContains(response, "Cleanup Client Pairing Requests")
        self.assertContains(response, "Manual only")
        self.assertNotContains(response, 'name="task_key"')
        self.assertFalse(MaintenanceTaskConfigAdmin.actions)

    def test_run_now_creates_one_approved_run_visible_in_admin(self):
        self.client.force_login(self.superuser)
        run_url = reverse(
            "admin:maintenance_task_run_now", args=(self.configuration.pk,)
        )
        self.assertEqual(self.client.get(run_url).status_code, 200)

        with (
            patch("maintenance.services.enqueue_run") as enqueue,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post(run_url)

        run = MaintenanceTaskRun.objects.get()
        self.assertRedirects(
            response,
            reverse("admin:maintenance_maintenancetaskrun_change", args=(run.pk,)),
        )
        self.assertEqual(run.trigger, MaintenanceTaskRun.Trigger.ADMIN)
        self.assertEqual(run.requested_by, self.superuser)
        enqueue.assert_called_once_with(run.pk)
        result_page = self.client.get(
            reverse("admin:maintenance_maintenancetaskrun_change", args=(run.pk,))
        )
        self.assertContains(result_page, "Queued")
        self.assertContains(result_page, "Cleanup Client Pairing Requests")

    def test_run_now_rejects_duplicate_active_run(self):
        self.client.force_login(self.superuser)
        run_url = reverse(
            "admin:maintenance_task_run_now", args=(self.configuration.pk,)
        )
        MaintenanceTaskRun.objects.create(
            configuration=self.configuration,
            task_key=self.configuration.task_key,
            trigger=MaintenanceTaskRun.Trigger.ADMIN,
        )

        response = self.client.post(run_url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(MaintenanceTaskRun.objects.count(), 1)

    def test_retired_key_is_visible_but_cannot_be_run(self):
        retired = MaintenanceTaskConfig.objects.create(
            task_key="arbitrary.module.callable",
            enabled=True,
        )
        self.client.force_login(self.superuser)
        run_url = reverse("admin:maintenance_task_run_now", args=(retired.pk,))

        response = self.client.post(run_url)

        self.assertRedirects(
            response,
            reverse("admin:maintenance_maintenancetaskconfig_changelist"),
        )
        self.assertFalse(
            MaintenanceTaskRun.objects.filter(task_key=retired.task_key).exists()
        )

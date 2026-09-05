from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.models import ServerSetting
from core.server_settings import (
    MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
    MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
    clear_server_settings_cache,
    get_marginalia_active_session_tombstone_retention_days,
    get_marginalia_closed_session_tombstone_retention_days,
)
from maintenance.admin import MaintenanceTaskConfigAdmin
from maintenance.models import (
    MaintenanceFrequency,
    MaintenanceTaskConfig,
    MaintenanceTaskRun,
)
from marginalia.annotations.maintenance import execute_deleted_annotation_cleanup


@override_settings(
    SECOND_PASS_ENABLE_DJANGO_ADMIN=True,
    ROOT_URLCONF="tests.maintenance.urls",
)
class MaintenanceAdminTests(TestCase):
    def setUp(self):
        clear_server_settings_cache()
        self.superuser = get_user_model().objects.create_superuser(
            username="maintenance-owner",
            password="testpass",
            email="owner@example.com",
        )
        self.configuration = MaintenanceTaskConfig.objects.get(
            task_key="cleanup_client_pairing_requests"
        )

    def tearDown(self):
        clear_server_settings_cache()

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
        self.assertContains(result_page, "Refresh")
        self.assertNotContains(result_page, "History")
        self.assertNotContains(result_page, "Task key")

    def test_deleted_annotation_run_now_queues_registered_task(self):
        configuration = MaintenanceTaskConfig.objects.get(
            task_key="cleanup_deleted_annotations"
        )
        self.client.force_login(self.superuser)

        with (
            patch("maintenance.services.enqueue_run") as enqueue,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.post(
                reverse("admin:maintenance_task_run_now", args=(configuration.pk,))
            )

        run = MaintenanceTaskRun.objects.get(task_key=configuration.task_key)
        self.assertRedirects(
            response,
            reverse("admin:maintenance_maintenancetaskrun_change", args=(run.pk,)),
        )
        enqueue.assert_called_once_with(run.pk)

    def test_deleted_annotation_task_page_owns_retention_configuration(self):
        configuration = MaintenanceTaskConfig.objects.get(
            task_key="cleanup_deleted_annotations"
        )
        self.client.force_login(self.superuser)
        url = reverse(
            "admin:maintenance_maintenancetaskconfig_change",
            args=(configuration.pk,),
        )

        page = self.client.get(url)

        self.assertEqual(page.status_code, 200)
        self.assertIn("active_retention_days", page.context["adminform"].form.fields)
        self.assertIn("closed_retention_days", page.context["adminform"].form.fields)
        list_page = self.client.get(
            reverse("admin:maintenance_maintenancetaskconfig_changelist")
        )
        cleanup_list_form = next(
            form
            for form in list_page.context["cl"].formset.forms
            if form.instance.task_key == configuration.task_key
        )
        self.assertNotIn("active_retention_days", cleanup_list_form.fields)
        self.assertNotIn("closed_retention_days", cleanup_list_form.fields)

        response = self.client.post(
            url,
            {
                "enabled": "on",
                "frequency": MaintenanceFrequency.MONTHLY,
                "active_retention_days": "35",
                "closed_retention_days": "9",
            },
        )

        self.assertRedirects(
            response,
            reverse("admin:maintenance_maintenancetaskconfig_changelist"),
        )
        self.assertEqual(
            get_marginalia_active_session_tombstone_retention_days(), 35
        )
        self.assertEqual(
            get_marginalia_closed_session_tombstone_retention_days(), 9
        )
        result = execute_deleted_annotation_cleanup(dry_run=True)
        self.assertEqual(result.counts["active_retention_days"], 35)
        self.assertEqual(result.counts["closed_retention_days"], 9)

    def test_deleted_annotation_task_page_rejects_invalid_retention(self):
        configuration = MaintenanceTaskConfig.objects.get(
            task_key="cleanup_deleted_annotations"
        )
        self.client.force_login(self.superuser)
        url = reverse(
            "admin:maintenance_maintenancetaskconfig_change",
            args=(configuration.pk,),
        )

        response = self.client.post(
            url,
            {
                "enabled": "on",
                "frequency": MaintenanceFrequency.MONTHLY,
                "active_retention_days": "-1",
                "closed_retention_days": "7",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "active_retention_days", response.context["adminform"].form.errors
        )
        self.assertEqual(
            get_marginalia_active_session_tombstone_retention_days(), 28
        )
        self.assertEqual(
            get_marginalia_closed_session_tombstone_retention_days(), 7
        )

    def test_server_settings_admin_excludes_task_owned_retention_rows(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("admin:core_serversetting_changelist"))

        self.assertEqual(response.status_code, 200)
        visible_keys = set(
            response.context["cl"].queryset.values_list("key", flat=True)
        )
        self.assertNotIn(
            MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
            visible_keys,
        )
        self.assertNotIn(
            MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
            visible_keys,
        )
        self.assertTrue(
            ServerSetting.objects.filter(
                key=MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING
            ).exists()
        )

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

    def test_completed_run_uses_readable_nonduplicated_results(self):
        run = MaintenanceTaskRun.objects.create(
            configuration=self.configuration,
            task_key=self.configuration.task_key,
            trigger=MaintenanceTaskRun.Trigger.ADMIN,
            requested_by=self.superuser,
            status=MaintenanceTaskRun.Status.SUCCEEDED,
            result_summary=(
                "dry_run=False eligible=1 selected=1 deleted=1 retained=0"
            ),
            result_counts={
                "eligible": 1,
                "selected": 1,
                "would_delete": 1,
                "deleted": 1,
                "retained": 0,
            },
        )
        self.client.force_login(self.superuser)

        response = self.client.get(
            reverse("admin:maintenance_maintenancetaskrun_change", args=(run.pk,))
        )

        self.assertContains(response, "Eligible pairing requests")
        self.assertContains(response, "Pairing requests processed")
        self.assertContains(response, "Pairing requests that would be deleted")
        self.assertContains(response, "Pairing requests deleted")
        self.assertContains(response, "Pairing requests retained")
        self.assertContains(response, "Run now by maintenance-owner")
        self.assertNotContains(response, run.result_summary)
        self.assertNotContains(response, run.task_key)

    def test_prune_history_is_confirmed_and_removes_only_expired_completed_runs(self):
        now = timezone.now()
        old_run = MaintenanceTaskRun.objects.create(
            configuration=self.configuration,
            task_key=self.configuration.task_key,
            trigger=MaintenanceTaskRun.Trigger.SCHEDULED,
            status=MaintenanceTaskRun.Status.SUCCEEDED,
            completed_at=now - timedelta(days=8),
        )
        recent_run = MaintenanceTaskRun.objects.create(
            configuration=self.configuration,
            task_key=self.configuration.task_key,
            trigger=MaintenanceTaskRun.Trigger.SCHEDULED,
            status=MaintenanceTaskRun.Status.SUCCEEDED,
            completed_at=now,
        )
        active_run = MaintenanceTaskRun.objects.create(
            configuration=self.configuration,
            task_key=self.configuration.task_key,
            trigger=MaintenanceTaskRun.Trigger.ADMIN,
        )
        self.client.force_login(self.superuser)
        changelist_url = reverse(
            "admin:maintenance_maintenancetaskrun_changelist"
        )
        prune_url = reverse("admin:maintenance_task_run_prune_history")

        changelist = self.client.get(changelist_url)
        confirmation = self.client.get(prune_url)

        self.assertContains(changelist, "90-day rolling history")
        self.assertContains(changelist, "Queued and running runs")
        self.assertContains(changelist, "Prune to last 7 days")
        self.assertContains(changelist, "Delete completed history")
        self.assertContains(confirmation, "older than 7 days")
        self.assertTrue(MaintenanceTaskRun.objects.filter(pk=old_run.pk).exists())

        response = self.client.post(prune_url)

        self.assertRedirects(response, changelist_url)
        self.assertFalse(MaintenanceTaskRun.objects.filter(pk=old_run.pk).exists())
        self.assertTrue(MaintenanceTaskRun.objects.filter(pk=recent_run.pk).exists())
        self.assertTrue(MaintenanceTaskRun.objects.filter(pk=active_run.pk).exists())

    def test_manual_history_delete_removes_completed_runs_but_keeps_active_runs(self):
        completed_run = MaintenanceTaskRun.objects.create(
            configuration=self.configuration,
            task_key=self.configuration.task_key,
            trigger=MaintenanceTaskRun.Trigger.ADMIN,
            status=MaintenanceTaskRun.Status.SUCCEEDED,
            completed_at=timezone.now(),
        )
        active_run = MaintenanceTaskRun.objects.create(
            configuration=self.configuration,
            task_key=self.configuration.task_key,
            trigger=MaintenanceTaskRun.Trigger.ADMIN,
        )
        self.client.force_login(self.superuser)
        delete_url = reverse("admin:maintenance_task_run_delete_history")

        confirmation = self.client.get(delete_url)

        self.assertContains(confirmation, "current rolling history")
        self.assertTrue(
            MaintenanceTaskRun.objects.filter(pk=completed_run.pk).exists()
        )

        response = self.client.post(delete_url)

        self.assertRedirects(
            response,
            reverse("admin:maintenance_maintenancetaskrun_changelist"),
        )
        self.assertFalse(
            MaintenanceTaskRun.objects.filter(pk=completed_run.pk).exists()
        )
        self.assertTrue(MaintenanceTaskRun.objects.filter(pk=active_run.pk).exists())

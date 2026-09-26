from __future__ import annotations

import pytest

from tests.testenv.suite_markers import markers_for_test


@pytest.mark.parametrize(
    ("path", "nodeid", "expected"),
    (
        (
            "tests/core/test_media_serving.py",
            "tests/core/test_media_serving.py::MediaServingTests::test_response",
            ("security", "filesystem", "integration"),
        ),
        (
            "tests/accounts/passwords/test_future_workflow.py",
            "tests/accounts/passwords/test_future_workflow.py::PasswordTests::test_reset",
            ("security",),
        ),
        (
            "tests/core/product_ui/test_future_page.py",
            "tests/core/product_ui/test_future_page.py::PageTests::test_render",
            ("integration",),
        ),
        (
            "tests/core/test_media_serving.py.bak",
            "tests/core/test_media_serving.py.bak::MediaServingTests::test_response",
            (),
        ),
        (
            "tests/accounts/client_api/test_proxy_boundary.py",
            "tests/accounts/client_api/test_proxy_boundary.py::UvicornProxyBoundaryTests::test_request",
            ("security", "concurrency", "subprocess", "slow"),
        ),
        (
            "tests/marginalia/imports/test_apply_api.py",
            "tests/marginalia/imports/test_apply_api.py::MarginaliaImportApplyConcurrencyTests::test_competing_apply",
            ("security", "filesystem", "integration", "concurrency", "slow"),
        ),
        (
            "tests/core/test_django_settings.py",
            "tests/core/test_django_settings.py::DjangoSettingsContractTests::test_production_cookie_settings",
            ("subprocess",),
        ),
        (
            "tests/core/test_server_settings.py",
            "tests/core/test_server_settings.py::ServerSettingsCrossWorkerFreshnessTests::test_refresh",
            ("concurrency", "subprocess", "slow"),
        ),
        (
            "tests/maintenance/test_scheduling.py",
            "tests/maintenance/test_scheduling.py::MaintenanceDispatchConcurrencyTests::test_dispatch",
            ("concurrency", "slow"),
        ),
        (
            "tests/example/test_ordinary.py",
            "tests/example/test_ordinary.py::OrdinaryTests::test_behavior",
            (),
        ),
        (
            "tests/accounts/client_api/test_authentication.py",
            "tests/accounts/client_api/test_authentication.py::ClientApiAuthenticationTests::test_authenticates",
            ("push", "security"),
        ),
        (
            "tests/library/test_queries.py",
            "tests/library/test_queries.py::LibraryVisibilityQueryTests::test_reader_visibility",
            ("push", "security"),
        ),
        (
            "tests/library/imports/test_epub_archive_safety.py",
            "tests/library/imports/test_epub_archive_safety.py::EpubArchiveSafetyTests::test_rejects_bomb",
            ("security", "filesystem"),
        ),
        (
            "tests/marginalia/imports/test_checksum_round_trip.py",
            "tests/marginalia/imports/test_checksum_round_trip.py::MarginaliaChecksumRoundTripTests::test_round_trip",
            ("filesystem", "integration"),
        ),
    ),
)
def test_markers_for_test_classifies_representative_paths_and_nodes(
    path: str,
    nodeid: str,
    expected: tuple[str, ...],
) -> None:
    assert tuple(markers_for_test(path=path, nodeid=nodeid)) == expected

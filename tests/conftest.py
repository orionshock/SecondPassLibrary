from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.testenv.suite_markers import markers_for_test
from tests.testenv.filesystem import RuntimePathIsolation


@pytest.hookimpl(tryfirst=True)
def pytest_collection_modifyitems(config, items) -> None:
    """Apply the centrally audited verification-lane markers."""

    for item in items:
        test_path = item.path.relative_to(config.rootpath).as_posix()
        for marker_name in markers_for_test(path=test_path, nodeid=item.nodeid):
            item.add_marker(getattr(pytest.mark, marker_name))


@pytest.fixture
def isolated_runtime_paths() -> Iterator[RuntimePathIsolation]:
    isolation = RuntimePathIsolation(
        userdata=True,
        media=True,
        imports=True,
        static=True,
    )
    isolation.enable()
    try:
        yield isolation
    finally:
        isolation.disable()

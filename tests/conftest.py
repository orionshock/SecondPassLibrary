from __future__ import annotations

from collections.abc import Iterator

import pytest

from tests.testenv.filesystem import RuntimePathIsolation


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

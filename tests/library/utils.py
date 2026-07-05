from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from rest_framework.response import Response

from tests.testenv.filesystem import IsolatedMediaRootMixin

__all__ = ["IsolatedMediaRootMixin", "paginated_results"]


def paginated_results(response: Response) -> list[dict[str, Any]]:
    assert response.data is not None
    payload = cast(Mapping[str, Any], response.data)
    results = payload.get("results")
    assert isinstance(results, list)
    return cast(list[dict[str, Any]], results)

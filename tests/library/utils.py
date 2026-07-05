from __future__ import annotations

from typing import Any

from rest_framework.response import Response

from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.responses import response_data_list

__all__ = ["IsolatedMediaRootMixin", "paginated_results"]


def paginated_results(response: Response) -> list[Any]:
    return response_data_list(response)

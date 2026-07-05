from collections.abc import Mapping
from typing import Any, cast

from django.http.response import HttpResponseBase
from rest_framework.response import Response


def assert_http_response(response: object) -> HttpResponseBase:
    assert isinstance(response, HttpResponseBase)
    return response


def assert_response(response: object) -> Response:
    assert isinstance(response, Response)
    return response


def response_data_dict(response: Response) -> dict[str, Any]:
    data = response.data
    assert data is not None
    assert isinstance(data, dict)
    return cast(dict[str, Any], data)


def response_data_list(response: Response) -> list[Any]:
    data = response.data
    assert data is not None
    if isinstance(data, dict) and "results" in data:
        results = data["results"]
        assert isinstance(results, list)
        return cast(list[Any], results)
    assert isinstance(data, list)
    return cast(list[Any], data)


def paginated_results(response: Response) -> list[Any]:
    return response_data_list(response)


def payload_dict(payload: Mapping[str, Any], key: str) -> dict[str, Any]:
    value = payload[key]
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def payload_list(payload: Mapping[str, Any], key: str) -> list[Any]:
    value = payload[key]
    assert isinstance(value, list)
    return cast(list[Any], value)

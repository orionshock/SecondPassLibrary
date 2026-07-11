from __future__ import annotations

from rest_framework import status
from rest_framework.test import APIClient

from tests.utils.responses import assert_response


def authenticated_tracked_client(testcase, *, username: str, password: str = "pw"):
    client = APIClient()
    testcase.assertTrue(client.login(username=username, password=password))
    response = assert_response(client.get("/api/v1/accounts/me/"))
    testcase.assertEqual(response.status_code, status.HTTP_200_OK)
    session_key = client.session.session_key
    testcase.assertTrue(session_key)
    return client, session_key

from __future__ import annotations

from collections.abc import Mapping
import os
from pathlib import Path
import shutil
from typing import Any, cast
import uuid

from django.conf import settings
from django.test.utils import override_settings
import django.core.files.storage as storage
from django.utils.functional import empty
from rest_framework.response import Response


def paginated_results(response: Response) -> list[dict[str, Any]]:
    assert response.data is not None
    payload = cast(Mapping[str, Any], response.data)
    results = payload.get("results")
    assert isinstance(results, list)
    return cast(list[dict[str, Any]], results)


class IsolatedMediaRootMixin:
    """
    Ensure FileField writes during tests go to a temp MEDIA_ROOT.

    Avoid polluting the real `userdata/media` directory during test runs.
    """

    @classmethod
    def setUpClass(cls):
        parent_set_up = getattr(super(), "setUpClass", None)
        if callable(parent_set_up):
            parent_set_up()
        temp_root = Path(settings.BASE_DIR) / "TestFiles"
        temp_root.mkdir(parents=True, exist_ok=True)
        cls._media_root = str(temp_root / f"tmp_media_{uuid.uuid4().hex}")
        os.makedirs(cls._media_root, exist_ok=True)
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_root)
        cls._media_override.enable()

        # Ensure Django's storage backend picks up the overridden MEDIA_ROOT.
        # storages/default_storage can be initialized before this mixin runs.
        handler = cast(Any, getattr(storage, "storages"))
        handler._storages = {}
        handler._backends = None
        setattr(cast(Any, storage.default_storage), "_wrapped", empty)

    @classmethod
    def tearDownClass(cls):
        cls._media_override.disable()
        shutil.rmtree(cls._media_root, ignore_errors=True)
        parent_tear_down = getattr(super(), "tearDownClass", None)
        if callable(parent_tear_down):
            parent_tear_down()


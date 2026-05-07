from __future__ import annotations

import os
from pathlib import Path
import uuid
from typing import Any, cast

from django.conf import settings
from django.test.utils import override_settings
import django.core.files.storage as storage
from django.utils.functional import empty


class IsolatedUserdataMixin:
    """
    Keep reading tests from touching the real `userdata/` directory.

    This overrides runtime paths (MEDIA_ROOT/IMPORTS_DIR/STATIC_ROOT) for the
    test suite class.
    """

    @classmethod
    def setUpClass(cls):
        parent_set_up = getattr(super(), "setUpClass", None)
        if callable(parent_set_up):
            parent_set_up()
        temp_root = Path(settings.BASE_DIR) / "TestFiles"
        temp_root.mkdir(parents=True, exist_ok=True)

        cls._userdata_root = temp_root / f"tmp_reading_userdata_{uuid.uuid4().hex}"
        cls._userdata_root.mkdir(parents=True, exist_ok=True)

        media_root = str(cls._userdata_root / "media")
        imports_dir = cls._userdata_root / "imports"
        static_root = str(cls._userdata_root / "static")

        os.makedirs(media_root, exist_ok=True)
        imports_dir.mkdir(parents=True, exist_ok=True)
        os.makedirs(static_root, exist_ok=True)

        cls._override = override_settings(
            MEDIA_ROOT=media_root,
            IMPORTS_DIR=imports_dir,
            STATIC_ROOT=static_root,
        )
        cls._override.enable()

        handler = cast(Any, getattr(storage, "storages"))
        handler._storages = {}
        handler._backends = None
        setattr(cast(Any, storage.default_storage), "_wrapped", empty)

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        __import__("shutil").rmtree(cls._userdata_root, ignore_errors=True)
        parent_tear_down = getattr(super(), "tearDownClass", None)
        if callable(parent_tear_down):
            parent_tear_down()


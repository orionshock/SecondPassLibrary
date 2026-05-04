from __future__ import annotations

import os
import uuid
from pathlib import Path

from django.conf import settings
from django.test.utils import override_settings


class IsolatedUserdataMixin:
    """
    Keep reading tests from touching the real `userdata/` directory.

    This overrides runtime paths (MEDIA_ROOT/IMPORTS_DIR/STATIC_ROOT) for the
    test suite class.
    """

    @classmethod
    def setUpClass(cls):
        # Call into the next class in the MRO if it defines setUpClass()
        # (Pylance can't statically prove this on a mixin).
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

    @classmethod
    def tearDownClass(cls):
        cls._override.disable()
        __import__("shutil").rmtree(cls._userdata_root, ignore_errors=True)
        parent_tear_down = getattr(super(), "tearDownClass", None)
        if callable(parent_tear_down):
            parent_tear_down()

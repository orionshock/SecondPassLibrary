from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, cast

from django.test.utils import override_settings
import django.core.files.storage as storage
from django.utils.functional import empty


def reset_django_storage() -> None:
    """
    Clear cached storage backends after MEDIA_ROOT changes.
    """
    handler = cast(Any, getattr(storage, "storages"))
    handler._storages = {}
    handler._backends = None
    setattr(cast(Any, storage.default_storage), "_wrapped", empty)


class RuntimePathIsolation:
    """
    Explicit temp runtime-path override for tests.

    Uses the OS temp area so generated files do not land in committed fixture
    trees.
    """

    def __init__(
        self,
        *,
        media: bool = False,
        imports: bool = False,
        static: bool = False,
        userdata: bool = False,
    ) -> None:
        self.media = media
        self.imports = imports
        self.static = static
        self.userdata = userdata
        self._temporary_directory: TemporaryDirectory[str] | None = None
        self._override: Any = None
        self.root: Path | None = None
        self.userdata_root: Path | None = None
        self.media_root: Path | None = None
        self.imports_dir: Path | None = None
        self.static_root: Path | None = None

    def enable(self) -> None:
        self._temporary_directory = TemporaryDirectory(prefix="secondpass-test-")
        self.root = Path(self._temporary_directory.name)
        self.userdata_root = self.root / "userdata"
        self.media_root = (
            self.userdata_root / "media" if self.userdata else self.root / "media"
        )
        self.imports_dir = (
            self.userdata_root / "imports" if self.userdata else self.root / "imports"
        )
        self.static_root = self.root / "static"

        overrides: dict[str, Any] = {}
        if self.userdata:
            self.userdata_root.mkdir(parents=True, exist_ok=True)
            overrides["USERDATA_DIR"] = self.userdata_root
        if self.media:
            self.media_root.mkdir(parents=True, exist_ok=True)
            overrides["MEDIA_ROOT"] = str(self.media_root)
        if self.imports:
            self.imports_dir.mkdir(parents=True, exist_ok=True)
            overrides["IMPORTS_DIR"] = self.imports_dir
        if self.static:
            self.static_root.mkdir(parents=True, exist_ok=True)
            overrides["STATIC_ROOT"] = str(self.static_root)

        self._override = override_settings(**overrides)
        self._override.enable()
        reset_django_storage()

    def disable(self) -> None:
        if self._override is not None:
            self._override.disable()
            self._override = None
        reset_django_storage()
        if self._temporary_directory is not None:
            self._temporary_directory.cleanup()
            self._temporary_directory = None


class IsolatedMediaRootMixin:
    """
    Ensure FileField writes during tests go to a temp MEDIA_ROOT.
    """

    @classmethod
    def setUpClass(cls):
        parent_set_up = getattr(super(), "setUpClass", None)
        if callable(parent_set_up):
            parent_set_up()

        cls._media_runtime_paths_owned = False
        if getattr(cls, "_runtime_paths", None) is None:
            cls._runtime_paths = RuntimePathIsolation(media=True)
            cls._runtime_paths.enable()
            cls._media_runtime_paths_owned = True
        cls._media_root = str(cls._runtime_paths.media_root)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_media_runtime_paths_owned", False):
            cls._runtime_paths.disable()
        cls._media_runtime_paths_owned = False
        parent_tear_down = getattr(super(), "tearDownClass", None)
        if callable(parent_tear_down):
            parent_tear_down()


class IsolatedImportsMixin:
    """
    Isolate library import staging and media writes in OS temp directories.
    """

    @classmethod
    def setUpClass(cls):
        parent_set_up = getattr(super(), "setUpClass", None)
        if callable(parent_set_up):
            parent_set_up()
        cls._imports_runtime_paths_owned = False
        if getattr(cls, "_runtime_paths", None) is None:
            cls._runtime_paths = RuntimePathIsolation(media=True, imports=True)
            cls._runtime_paths.enable()
            cls._imports_runtime_paths_owned = True
        cls._imports_root = str(cls._runtime_paths.imports_dir)
        cls._media_root = str(cls._runtime_paths.media_root)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_imports_runtime_paths_owned", False):
            cls._runtime_paths.disable()
        cls._imports_runtime_paths_owned = False
        parent_tear_down = getattr(super(), "tearDownClass", None)
        if callable(parent_tear_down):
            parent_tear_down()


class IsolatedUserdataMixin:
    """
    Keep tests from touching real userdata/, media, imports, or static output.
    """

    @classmethod
    def setUpClass(cls):
        parent_set_up = getattr(super(), "setUpClass", None)
        if callable(parent_set_up):
            parent_set_up()
        cls._userdata_runtime_paths_owned = False
        if getattr(cls, "_runtime_paths", None) is None:
            cls._runtime_paths = RuntimePathIsolation(
                userdata=True,
                media=True,
                imports=True,
                static=True,
            )
            cls._runtime_paths.enable()
            cls._userdata_runtime_paths_owned = True
        cls._userdata_root = cls._runtime_paths.userdata_root
        cls._media_root = str(cls._runtime_paths.media_root)
        cls._imports_root = str(cls._runtime_paths.imports_dir)
        cls._static_root = str(cls._runtime_paths.static_root)

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "_userdata_runtime_paths_owned", False):
            cls._runtime_paths.disable()
        cls._userdata_runtime_paths_owned = False
        parent_tear_down = getattr(super(), "tearDownClass", None)
        if callable(parent_tear_down):
            parent_tear_down()

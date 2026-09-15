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


class _RuntimePathIsolationMixin:
    runtime_path_options: dict[str, bool] = {}

    @classmethod
    def _pre_setup(cls):
        isolation = RuntimePathIsolation(**cls.runtime_path_options)
        isolation.enable()
        cls._runtime_paths = isolation
        cls._expose_runtime_paths(isolation)
        try:
            super()._pre_setup()
        except Exception:
            isolation.disable()
            cls._runtime_paths = None
            raise

    def _post_teardown(self):
        isolation = self._runtime_paths
        try:
            super()._post_teardown()
        finally:
            isolation.disable()
            type(self)._runtime_paths = None

    @classmethod
    def _expose_runtime_paths(cls, isolation: RuntimePathIsolation) -> None:
        raise NotImplementedError


class IsolatedMediaRootMixin(_RuntimePathIsolationMixin):
    """Ensure each test's FileField writes use a fresh temporary MEDIA_ROOT."""

    runtime_path_options = {"media": True}

    @classmethod
    def _expose_runtime_paths(cls, isolation: RuntimePathIsolation) -> None:
        cls._media_root = str(isolation.media_root)


class IsolatedImportsMixin(_RuntimePathIsolationMixin):
    """Isolate each test's import staging and media writes."""

    runtime_path_options = {"media": True, "imports": True}

    @classmethod
    def _expose_runtime_paths(cls, isolation: RuntimePathIsolation) -> None:
        cls._imports_root = str(isolation.imports_dir)
        cls._media_root = str(isolation.media_root)


class IsolatedUserdataMixin(_RuntimePathIsolationMixin):
    """Keep each test's userdata, media, imports, and static output isolated."""

    runtime_path_options = {
        "userdata": True,
        "media": True,
        "imports": True,
        "static": True,
    }

    @classmethod
    def _expose_runtime_paths(cls, isolation: RuntimePathIsolation) -> None:
        cls._userdata_root = isolation.userdata_root
        cls._media_root = str(isolation.media_root)
        cls._imports_root = str(isolation.imports_dir)
        cls._static_root = str(isolation.static_root)

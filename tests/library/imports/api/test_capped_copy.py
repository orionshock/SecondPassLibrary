from __future__ import annotations

from pathlib import Path
import io

import pytest

from library.imports.upload import ImportResourceLimitError, _copy_fileobj_capped
from tests.library.imports.helpers import BaseImportApiTest


pytestmark = [pytest.mark.filesystem, pytest.mark.integration]


class CappedZipCopyTests(BaseImportApiTest):
    def test_capped_copy_failure_removes_partial_extracted_file(self):
        destination = Path(self._imports_root) / "partial.epub"

        with self.assertRaises(ImportResourceLimitError):
            _copy_fileobj_capped(
                src=io.BytesIO(b"12345"), dst_path=destination, max_bytes=4
            )

        self.assertFalse(destination.exists())

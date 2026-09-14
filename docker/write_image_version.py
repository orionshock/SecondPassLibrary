from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import sys


def write_image_version(
    output_path: Path,
    version: str,
    release_date: str = "",
) -> None:
    if not version:
        raise ValueError("Image version must not be empty.")

    effective_release_date = (
        release_date or datetime.now(timezone.utc).date().isoformat()
    )
    if date.fromisoformat(effective_release_date).isoformat() != effective_release_date:
        raise ValueError("Image release date must use YYYY-MM-DD format.")
    output_path.write_text(
        f"SERVER_VERSION = {version!r}\n"
        f"SERVER_RELEASE_DATE = {effective_release_date!r}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    write_image_version(Path(sys.argv[1]), sys.argv[2], sys.argv[3])

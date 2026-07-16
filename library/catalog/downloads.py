from __future__ import annotations

import unicodedata


DOWNLOAD_FILENAME_MAX_CHARS = 180
_UNSAFE_FILENAME_CHARS = frozenset('<>:"/\\|?*')


def book_download_filename(title: str) -> str:
    cleaned = "".join(
        " "
        if character in _UNSAFE_FILENAME_CHARS
        or unicodedata.category(character).startswith("C")
        else character
        for character in str(title or "")
    )
    cleaned = " ".join(cleaned.split()).strip(" .")
    if cleaned.casefold().endswith(".epub"):
        cleaned = cleaned[:-5].rstrip(" .")
    stem_limit = DOWNLOAD_FILENAME_MAX_CHARS - len(".epub")
    stem = cleaned[:stem_limit].rstrip(" .") or "book"
    return f"{stem}.epub"

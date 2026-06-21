from __future__ import annotations

import os
from pathlib import Path


SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "userdata",
    "out",
}

TEXT_EXTS = {
    ".py",
    ".md",
    ".txt",
    ".html",
    ".css",
    ".js",
    ".json",
    ".yml",
    ".yaml",
    ".toml",
}

MOJIBAKE_MARKERS = ("\u00c3", "\u00c2", "\u00e2")

# Normalize punctuation to ASCII after repairing encoding. Keeping this source
# ASCII-only prevents the repair tool itself from becoming an encoding test case.
PUNCT_REPLACEMENTS: dict[str, str] = {
    "\u2026": "...",
    "\u2014": "-",
    "\u2013": "-",
    "\u2019": "'",
    "\u2018": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u00a0": " ",
}

# Common CP1252/UTF-8 mojibake sequences. Build them from escaped code points so
# editors and shells never need to decode literal broken text in this file.
MOJIBAKE_SEQ_REPLACEMENTS: dict[str, str] = {
    "\u00e2\u20ac\u00a6": "...",
    "\u00e2\u20ac\u201d": "-",
    "\u00e2\u20ac\u201c": "-",
    "\u00e2\u20ac\u2122": "'",
    "\u00e2\u20ac\u02dc": "'",
    "\u00e2\u20ac\u0153": '"',
    "\u00e2\u20ac\u009d": '"',
    "\u00e2\u20ac\u017e": '"',
    "\u00c2\u00a0": " ",
    "\u00c2\u00b7": "-",
}


def _iter_text_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() in TEXT_EXTS:
                out.append(path)
    return out


def _decode_best_effort(data: bytes) -> str | None:
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _fix_mojibake(text: str) -> str:
    candidate = text
    if any(marker in text for marker in MOJIBAKE_MARKERS):
        for encoding in ("cp1252", "latin-1"):
            try:
                candidate = text.encode(encoding).decode("utf-8")
                break
            except UnicodeError:
                continue

    for source, replacement in MOJIBAKE_SEQ_REPLACEMENTS.items():
        candidate = candidate.replace(source, replacement)

    for source, replacement in PUNCT_REPLACEMENTS.items():
        candidate = candidate.replace(source, replacement)

    return candidate.replace("\r\n", "\n").replace("\r", "\n")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    changed = 0
    scanned = 0

    for path in _iter_text_files(repo_root):
        scanned += 1
        text = _decode_best_effort(path.read_bytes())
        if text is None:
            continue

        fixed = _fix_mojibake(text)
        if fixed != text:
            path.write_text(fixed, encoding="utf-8", newline="\n")
            changed += 1

    print(f"Scanned {scanned} files, updated {changed} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

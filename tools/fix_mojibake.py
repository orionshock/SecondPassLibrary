from __future__ import annotations

import argparse
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


def iter_text_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIR_NAMES]
        for name in filenames:
            path = Path(dirpath) / name
            if path.suffix.lower() in TEXT_EXTS:
                out.append(path)
    return out


def decode_best_effort(data: bytes) -> str | None:
    for encoding in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def fix_mojibake_text(text: str) -> str:
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


def has_mojibake_marker(text: str) -> bool:
    return any(marker in text for marker in MOJIBAKE_MARKERS)


def _check_repository(repo_root: Path) -> int:
    scanned = 0
    failures: list[str] = []

    for path in iter_text_files(repo_root):
        scanned += 1
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            failures.append(f"{path}: invalid UTF-8 ({exc})")
            continue

        if has_mojibake_marker(text):
            failures.append(f"{path}: contains mojibake marker")

    if failures:
        print("\n".join(failures))
        print(f"Scanned {scanned} files, found {len(failures)} encoding issue(s).")
        return 1

    print(f"Scanned {scanned} files, found no encoding issues.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Audit UTF-8 and mojibake markers without modifying files.",
    )
    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    if args.check:
        return _check_repository(repo_root)

    changed = 0
    scanned = 0

    for path in iter_text_files(repo_root):
        scanned += 1
        text = decode_best_effort(path.read_bytes())
        if text is None:
            continue

        fixed = fix_mojibake_text(text)
        if fixed != text:
            path.write_text(fixed, encoding="utf-8", newline="\n")
            changed += 1

    print(f"Scanned {scanned} files, updated {changed} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

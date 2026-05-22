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

MOJIBAKE_MARKERS = ("\u00c3", "\u00c2", "\u00e2")  # Ã  â

# Normalize a small set of punctuation to plain ASCII (not required for correctness,
# but avoids accidental mojibake-on-mojibake in future edits).
PUNCT_REPLACEMENTS: dict[str, str] = {
    "\u2026": "...",  # ...
    "\u2014": "-",  # -
    "\u2013": "-",  # -
    "\u2019": "'",  # '
    "\u2018": "'",  # '
    "\u201c": '"',  # "
    "\u201d": '"',  # "
    "\u00a0": " ",  # non-breaking space
}

# Common CP1252/UTF-8 mojibake sequences as literal Unicode strings.
# These appear when UTF-8 bytes are mis-decoded as CP1252.
MOJIBAKE_SEQ_REPLACEMENTS: dict[str, str] = {
    "...": "...",  # ...
    "â€\"": "-",  # -
    "-": "-",  # -
    "'": "'",  # '
    "'": "'",  # '
    """: '"',  # "
    "â€\u009d": '"',  # " (occasionally comes through as a control char)
    """: '"',  # "
    " ": " ",  # NBSP
    "-": "-",  # middle dot
}


def _iter_text_files(root: Path) -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped directories in-place for os.walk.
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in TEXT_EXTS:
                out.append(p)
    return out


def _decode_best_effort(data: bytes) -> str | None:
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def _fix_mojibake(text: str) -> str:
    # Common case: UTF-8 bytes were decoded as Latin-1/CP1252, resulting in Ã¢â‚¬Â¦ etc.
    if any(m in text for m in MOJIBAKE_MARKERS):
        try:
            # Prefer CP1252 for round-tripping because many mojibake strings include
            # characters like the Euro sign (U+20AC) which aren't in Latin-1.
            candidate = text.encode("cp1252").decode("utf-8")
        except UnicodeError:
            try:
                candidate = text.encode("latin-1").decode("utf-8")
            except UnicodeError:
                candidate = text
    else:
        candidate = text

    # If we couldn't safely round-trip the whole file (e.g. it contains characters
    # not representable in CP1252), apply targeted sequence fixes.
    for k, v in MOJIBAKE_SEQ_REPLACEMENTS.items():
        candidate = candidate.replace(k, v)

    for k, v in PUNCT_REPLACEMENTS.items():
        candidate = candidate.replace(k, v)

    # Normalize line endings to LF.
    candidate = candidate.replace("\r\n", "\n").replace("\r", "\n")
    return candidate


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    changed = 0
    scanned = 0

    for path in _iter_text_files(repo_root):
        scanned += 1
        data = path.read_bytes()
        text = _decode_best_effort(data)
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

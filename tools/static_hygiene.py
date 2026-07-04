from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from tools.fix_mojibake import (
        TEXT_EXTS,
        decode_best_effort,
        fix_mojibake_text,
        has_mojibake_marker,
    )
except ModuleNotFoundError:
    from fix_mojibake import (
        TEXT_EXTS,
        decode_best_effort,
        fix_mojibake_text,
        has_mojibake_marker,
    )


REPO_ROOT = Path(__file__).resolve().parents[1]
ENTITY_EXTS = {".html", ".js", ".css"}
FORBIDDEN_DECORATIVE_ENTITIES = (
    "&middot;",
    "&#183;",
    "&mdash;",
    "&ndash;",
    "&larr;",
    "&rarr;",
    "&hellip;",
)


@dataclass(frozen=True)
class HygieneIssue:
    path: Path
    line: int | None
    message: str


def _run_git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _is_text_candidate(path: Path) -> bool:
    return path.suffix.lower() in TEXT_EXTS


def _is_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:4096]
    except OSError:
        return True
    return b"\0" in chunk


def _existing_text_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path if path.is_absolute() else REPO_ROOT / path
        if resolved in seen or not resolved.exists() or not resolved.is_file():
            continue
        if _is_text_candidate(resolved) and not _is_binary(resolved):
            out.append(resolved)
            seen.add(resolved)
    return out


def touched_files() -> list[Path]:
    names: set[str] = set()
    for args in (
        ["diff", "--name-only", "--diff-filter=d"],
        ["diff", "--cached", "--name-only", "--diff-filter=d"],
        ["ls-files", "--others", "--exclude-standard"],
    ):
        result = _run_git(args)
        if result.returncode == 0:
            names.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    return _existing_text_paths([Path(name) for name in sorted(names)])


def all_tracked_files() -> list[Path]:
    result = _run_git(["ls-files"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git ls-files failed")
    return _existing_text_paths([Path(line.strip()) for line in result.stdout.splitlines() if line.strip()])


def check_decorative_entities(paths: list[Path]) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    for path in paths:
        if path.suffix.lower() not in ENTITY_EXTS:
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError as exc:
            issues.append(HygieneIssue(path, None, f"invalid UTF-8: {exc}"))
            continue
        for line_no, line in enumerate(lines, start=1):
            for token in FORBIDDEN_DECORATIVE_ENTITIES:
                if token in line:
                    issues.append(
                        HygieneIssue(path, line_no, f"decorative HTML entity {token!r}")
                    )
    return issues


def check_mojibake(paths: list[Path]) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            issues.append(HygieneIssue(path, None, f"invalid UTF-8: {exc}"))
            continue
        if has_mojibake_marker(text):
            issues.append(HygieneIssue(path, None, "contains likely mojibake marker"))
    return issues


def check_trailing_whitespace(paths: list[Path]) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(lines, start=1):
            if line.endswith((" ", "\t")):
                issues.append(HygieneIssue(path, line_no, "trailing whitespace"))
    return issues


def check_line_endings(paths: list[Path]) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    for path in paths:
        try:
            data = path.read_bytes()
        except OSError:
            continue
        offset = data.find(b"\r")
        if offset == -1:
            continue
        line_no = data[:offset].count(b"\n") + 1
        message = "CRLF line ending; repo requires LF"
        if offset + 1 >= len(data) or data[offset + 1 : offset + 2] != b"\n":
            message = "CR line ending; repo requires LF"
        issues.append(HygieneIssue(path, line_no, message))
    return issues


def fix_mojibake(paths: list[Path]) -> int:
    changed = 0
    for path in paths:
        text = decode_best_effort(path.read_bytes())
        if text is None:
            continue
        fixed = fix_mojibake_text(text)
        if fixed != text:
            path.write_text(fixed, encoding="utf-8", newline="\n")
            changed += 1
    return changed


def fix_line_endings(paths: list[Path]) -> int:
    changed = 0
    for path in paths:
        try:
            original = path.read_bytes()
        except OSError:
            continue
        fixed = original.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        if fixed != original:
            path.write_bytes(fixed)
            changed += 1
    return changed


def fix_trailing_whitespace(paths: list[Path]) -> int:
    changed = 0
    for path in paths:
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        lines = original.splitlines(keepends=True)
        fixed = "".join(_rstrip_line(line) for line in lines)
        if fixed != original:
            path.write_text(fixed, encoding="utf-8", newline="")
            changed += 1
    return changed


def _rstrip_line(line: str) -> str:
    newline = ""
    body = line
    if line.endswith("\r\n"):
        body = line[:-2]
        newline = "\r\n"
    elif line.endswith(("\n", "\r")):
        body = line[:-1]
        newline = line[-1]
    return body.rstrip(" \t") + newline


def run_git_diff_check() -> tuple[int, str]:
    result = _run_git(["diff", "--check"])
    output = "\n".join(part for part in (result.stdout.strip(), result.stderr.strip()) if part)
    return result.returncode, output


def print_issues(title: str, issues: list[HygieneIssue]) -> None:
    if not issues:
        print(f"{title}: OK")
        return
    print(f"{title}: {len(issues)} issue(s)")
    for issue in issues:
        location = _repo_relative(issue.path)
        if issue.line is not None:
            location = f"{location}:{issue.line}"
        print(f"  {location}: {issue.message}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run static hygiene checks for touched repository files."
    )
    parser.add_argument("--all", action="store_true", help="Scan all tracked text files.")
    parser.add_argument(
        "--fix-mojibake",
        action="store_true",
        help="Modify scanned files by repairing likely mojibake.",
    )
    parser.add_argument(
        "--fix-trailing-whitespace",
        action="store_true",
        help="Modify scanned files by trimming trailing whitespace.",
    )
    parser.add_argument(
        "--fix-line-endings",
        action="store_true",
        help="Modify scanned files by normalizing line endings to LF.",
    )
    parser.add_argument("--verbose", action="store_true", help="Print scanned file details.")
    args = parser.parse_args(argv)

    paths = all_tracked_files() if args.all else touched_files()
    if args.verbose:
        mode = "all tracked" if args.all else "touched"
        print(f"Scanning {len(paths)} {mode} text file(s).")
        for path in paths:
            print(f"  {_repo_relative(path)}")

    if args.fix_mojibake:
        changed = fix_mojibake(paths)
        print(f"fix-mojibake: updated {changed} file(s).")

    if args.fix_trailing_whitespace:
        changed = fix_trailing_whitespace(paths)
        print(f"fix-trailing-whitespace: updated {changed} file(s).")

    if args.fix_line_endings:
        changed = fix_line_endings(paths)
        print(f"fix-line-endings: updated {changed} file(s).")

    entity_issues = check_decorative_entities(paths)
    mojibake_issues = check_mojibake(paths)
    trailing_issues = check_trailing_whitespace(paths)
    line_ending_issues = check_line_endings(paths)
    diff_code, diff_output = run_git_diff_check()

    print_issues("Decorative HTML entities", entity_issues)
    print_issues("Mojibake", mojibake_issues)
    print_issues("Trailing whitespace", trailing_issues)
    print_issues("Line endings", line_ending_issues)
    if diff_code == 0:
        print("git diff --check: OK")
    else:
        print("git diff --check: failed")
        if diff_output:
            print(diff_output)

    failed = bool(
        entity_issues
        or mojibake_issues
        or trailing_issues
        or line_ending_issues
        or diff_code != 0
    )
    print(f"Static hygiene: {'FAILED' if failed else 'passed'} ({len(paths)} file(s) scanned).")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

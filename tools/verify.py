from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

from python_runtime import require_supported_python


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def run(
    label: str,
    command: list[str],
    *,
    environment: dict[str, str] | None = None,
) -> None:
    print(f"\n==> {label}", flush=True)
    subprocess.run(
        command,
        cwd=REPOSITORY_ROOT,
        check=True,
        env=environment,
    )


def parser() -> argparse.ArgumentParser:
    argument_parser = argparse.ArgumentParser(description="Run a supported verification lane.")
    argument_parser.add_argument(
        "--lane",
        choices=(
            "all",
            "fast",
            "backend",
            "backend-coverage",
            "frontend",
            "frontend-coverage",
            "security-deps",
        ),
        default="all",
    )
    return argument_parser


def main() -> int:
    require_supported_python()
    lane = parser().parse_args().lane
    python = sys.executable
    django_environment = os.environ.copy()
    django_environment["DJANGO_DEBUG"] = "1"
    test_environment = os.environ.copy()
    test_environment["DJANGO_DEBUG"] = "0"

    if lane == "backend":
        run("Backend tests", [python, "-m", "pytest", "-q"], environment=test_environment)
        return 0
    if lane == "backend-coverage":
        run("Erase Python coverage", [python, "-m", "coverage", "erase"])
        run(
            "Python coverage tests",
            [python, "-m", "coverage", "run", "--branch", "-m", "pytest", "-q"],
            environment=test_environment,
        )
        run("Python coverage HTML", [python, "-m", "coverage", "html"])
        run("Python coverage XML", [python, "-m", "coverage", "xml"])
        run("Python coverage summary", [python, "-m", "coverage", "report"])
        return 0

    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        raise RuntimeError("npm was not found in PATH")

    if lane == "frontend":
        run("Frontend verification", [npm, "--prefix", "frontend", "run", "verify"])
        return 0
    if lane == "frontend-coverage":
        run("Frontend coverage", [npm, "--prefix", "frontend", "run", "test:coverage"])
        return 0
    if lane == "security-deps":
        failures = []
        for label, command in (
            (
                "Python dependency advisories",
                [python, "-m", "pip_audit", "--requirement", "requirements.txt"],
            ),
            (
                "Frontend dependency advisories",
                [npm, "--prefix", "frontend", "audit", "--audit-level=high"],
            ),
        ):
            try:
                run(label, command)
            except subprocess.CalledProcessError:
                failures.append(label)
        if failures:
            print(
                "\nDependency advisory verification failed: "
                f"{', '.join(failures)}. Review the scanner output for "
                "advisories or registry/tool errors.",
                file=sys.stderr,
            )
            return 1
        return 0

    run("Ruff", [python, "-m", "ruff", "check", "."])
    run("Django system checks", [python, "backend/manage.py", "check"], environment=django_environment)
    run("Migration consistency", [python, "backend/manage.py", "makemigrations", "--check", "--dry-run"], environment=django_environment)
    backend_command = [python, "-m", "pytest", "-q"]
    if lane == "fast":
        backend_command.extend(["-m", "not slow and not integration and not concurrency and not subprocess"])
    run("Backend tests", backend_command, environment=test_environment)
    run("Frontend tests" if lane == "fast" else "Frontend verification", [npm, "--prefix", "frontend", "run", "test" if lane == "fast" else "verify"])
    run("Repository hygiene", [python, "tools/static_hygiene.py"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

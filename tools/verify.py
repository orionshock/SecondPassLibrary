from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


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


def main() -> int:
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if npm is None:
        raise RuntimeError("npm was not found in PATH")

    python = sys.executable
    django_environment = os.environ.copy()
    django_environment["DJANGO_DEBUG"] = "1"

    run("Ruff", [python, "-m", "ruff", "check", "."])
    run(
        "Django system checks",
        [python, "backend/manage.py", "check"],
        environment=django_environment,
    )
    run("Backend tests", [python, "-m", "pytest", "-q"])
    run("Frontend verification", [npm, "--prefix", "frontend", "run", "verify"])
    run("Repository hygiene", [python, "tools/static_hygiene.py"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from local_common import (
    BACKEND_DIR,
    FRONTEND_DIR,
    display_environment,
    load_project_environment,
    run,
    start_local_infrastructure,
)


VENV_DIR = BACKEND_DIR / ".venv"


def is_python_312(command: list[str]) -> bool:
    try:
        result = subprocess.run(
            [*command, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return result.stdout.strip() == "3.12"


def find_python_312() -> list[str]:
    candidates: list[list[str]] = []
    if os.name == "nt" and (launcher := shutil.which("py")):
        candidates.append([launcher, "-3.12"])
    for name in ("python3.12", "python3", "python"):
        if executable := shutil.which(name):
            candidates.append([executable])
    candidates.append([sys.executable])

    for candidate in candidates:
        if is_python_312(candidate):
            return candidate
    raise RuntimeError("Python 3.12 is required but was not found.")


def venv_python() -> Path:
    return VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main() -> int:
    python = venv_python()
    if python.is_file():
        if not is_python_312([str(python)]):
            raise RuntimeError(f"The existing virtual environment must use Python 3.12: {python}")
        print(f"\nReusing virtual environment: {VENV_DIR}", flush=True)
    else:
        run([*find_python_312(), "-m", "venv", str(VENV_DIR)])
    if not python.is_file():
        raise RuntimeError(f"Virtual-environment Python was not created: {python}")

    run([str(python), "-m", "pip", "install", "-r", str(BACKEND_DIR / "requirements.txt")])
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm is required but was not found in PATH.")
    run([npm, "install"], cwd=FRONTEND_DIR)

    env = load_project_environment(dotenv_python=python)
    display_environment("Local setup", env)
    start_local_infrastructure()
    manage_py = str(BACKEND_DIR / "manage.py")
    run([str(python), manage_py, "migrate"], cwd=BACKEND_DIR, env=env)
    run(
        [
            str(python),
            manage_py,
            "createuser",
            "--staff",
            "--if-not-exists",
            "--username",
            env["DJANGO_ADMIN_USERNAME"],
            "--password",
            env["DJANGO_ADMIN_PASSWORD"],
        ],
        cwd=BACKEND_DIR,
        env=env,
    )
    print(
        "\nPyCharm setup required:\n"
        "  1. Select backend/.venv as the project interpreter.\n"
        "  2. Mark backend as Sources Root.\n"
        "  3. Mark backend/staticfiles as Excluded.",
        flush=True,
    )
    print("\nLocal environment setup completed successfully.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"Local environment setup failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

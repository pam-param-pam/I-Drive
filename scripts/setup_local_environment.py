from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from local_common import (
    BACKEND_DIR,
    FRONTEND_DIR,
    PROJECT_DIR,
    display_environment,
    load_project_environment,
    run,
)


VENV_DIR = BACKEND_DIR / ".venv"


def write_xml(tree: ET.ElementTree, path: Path) -> None:
    ET.indent(tree, space="  ")
    tree.write(path, encoding="UTF-8", xml_declaration=True)


def configure_pycharm_project_structure() -> None:
    idea_dir = PROJECT_DIR / ".idea"
    module_files = sorted(idea_dir.glob("*.iml"))
    if not module_files:
        print("\nPyCharm module configuration was not found; skipping project structure setup.", flush=True)
        return

    source_url = "file://$MODULE_DIR$/backend"
    excluded_urls = {
        "file://$MODULE_DIR$/backend/.venv",
        "file://$MODULE_DIR$/backend/staticfiles",
    }
    for module_file in module_files:
        try:
            tree = ET.parse(module_file)
        except ET.ParseError as error:
            raise RuntimeError(f"Invalid PyCharm module configuration: {module_file}") from error

        root_manager = tree.find("./component[@name='NewModuleRootManager']")
        if root_manager is None:
            continue
        content_roots = root_manager.findall("content")
        content_root = next(
            (root for root in content_roots if root.get("url") == "file://$MODULE_DIR$"),
            content_roots[0] if content_roots else None,
        )
        if content_root is None:
            continue

        changed = False
        configured_sources = {
            folder.get("url") for folder in content_root.findall("sourceFolder")
        }
        if source_url not in configured_sources:
            source_folder = ET.Element(
                "sourceFolder",
                {"url": source_url, "isTestSource": "false"},
            )
            first_excluded_folder = next(
                (
                    index
                    for index, child in enumerate(content_root)
                    if child.tag == "excludeFolder"
                ),
                len(content_root),
            )
            content_root.insert(first_excluded_folder, source_folder)
            changed = True

        configured_exclusions = {
            folder.get("url") for folder in content_root.findall("excludeFolder")
        }
        for excluded_url in sorted(excluded_urls - configured_exclusions):
            ET.SubElement(content_root, "excludeFolder", {"url": excluded_url})
            changed = True

        if changed:
            write_xml(tree, module_file)
        print(f"\nPyCharm Sources Root: {BACKEND_DIR}", flush=True)
        print(f"PyCharm excluded directory: {BACKEND_DIR / 'staticfiles'}", flush=True)
        return

    print("\nNo compatible PyCharm module was found; skipping project structure setup.", flush=True)


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
    configure_pycharm_project_structure()
    run([*find_python_312(), "-m", "venv", str(VENV_DIR)])
    python = venv_python()
    if not python.is_file():
        raise RuntimeError(f"Virtual-environment Python was not created: {python}")

    run([str(python), "-m", "pip", "install", "-r", str(BACKEND_DIR / "requirements.txt")])
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
    if npm is None:
        raise RuntimeError("npm is required but was not found in PATH.")
    run([npm, "--prefix", str(FRONTEND_DIR), "install"])

    env = load_project_environment(dotenv_python=python)
    display_environment("Local setup", env)
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
    print("\nLocal environment setup completed successfully.", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        print(f"Local environment setup failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "backend"
FRONTEND_DIR = PROJECT_DIR / "frontend"

DEFAULT_ENVIRONMENT = {
    "IS_DEV_ENV": "True",
    "BEHIND_NGINX": "False",
    "PROTOCOL": "http",
    "DEPLOYMENT_HOST": "localhost",
    "BACKEND_SECRET_KEY": "local-development-backend-secret",
    "SIGNING_SECRET": "local-development-signing-secret",
    "BACKEND_BASE_URL": "http://localhost:8000",
    "BACKEND_PORT": "8000",
    "FRONTEND_PORT": "5173",
    "REDIS_ADDRESS": "localhost",
    "REDIS_PORT": "6379",
    "REDIS_PASSWORD": "admin",
    "POSTGRES_ADDRESS": "localhost",
    "POSTGRES_PORT": "5432",
    "POSTGRES_NAME": "idrive-postgres",
    "POSTGRES_USER": "admin",
    "POSTGRES_PASSWORD": "admin",
    "POSTGRES_VOLUME": "idrive_postgres_data",
    "REDIS_VOLUME": "idrive_redis_data",
    "PROMETHEUS_VOLUME": "idrive_prometheus_data",
    "GRAFANA_VOLUME": "idrive_grafana_data",
    "GRAFANA_ADMIN_USER": "admin",
    "GRAFANA_ADMIN_PASSWORD": "admin",
    "GRAFANA_PORT": "3000",
    "PROMETHEUS_PORT": "9090",
    "NGINX_PORT": "80",
}


def require_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise RuntimeError(f"Required executable is not available in PATH: {name}")
    return executable


def _displayed_command(command: list[str]) -> str:
    displayed = command.copy()
    for index, argument in enumerate(displayed[:-1]):
        if argument == "--password":
            displayed[index + 1] = "********"
    return " ".join(displayed)


def run(
    command: list[str],
    *,
    cwd: Path = PROJECT_DIR,
    env: dict[str, str] | None = None,
) -> None:
    print(f"\n> {_displayed_command(command)}", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def start(
    command: list[str],
    *,
    cwd: Path = PROJECT_DIR,
    env: dict[str, str] | None = None,
) -> subprocess.Popen:
    print(f"\n> {_displayed_command(command)}", flush=True)
    if os.name == "nt":
        return subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
    return subprocess.Popen(command, cwd=cwd, env=env, start_new_session=True)


def stop_process_tree(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)


def wait_for_processes(processes: list[subprocess.Popen]) -> int:
    while all(process.poll() is None for process in processes):
        time.sleep(0.25)
    return next(
        (process.returncode for process in processes if process.returncode not in (None, 0)),
        0,
    )


def acquire_instance_lock(address: tuple[str, int]) -> socket.socket:
    instance_lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        instance_lock.bind(address)
        instance_lock.listen(1)
    except OSError as error:
        instance_lock.close()
        raise RuntimeError(f"Another local launcher is already using lock {address}.") from error
    return instance_lock


def _dotenv_values(dotenv_python: Path | None) -> dict[str, str | None]:
    dotenv_file = PROJECT_DIR / ".env"
    if dotenv_python is None:
        from dotenv import dotenv_values

        return dict(dotenv_values(dotenv_file))

    result = subprocess.run(
        [
            str(dotenv_python),
            "-c",
            "import json,sys; from dotenv import dotenv_values; print(json.dumps(dotenv_values(sys.argv[1])))",
            str(dotenv_file),
        ],
        cwd=PROJECT_DIR,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def load_project_environment(*, dotenv_python: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    for name, value in DEFAULT_ENVIRONMENT.items():
        env.setdefault(name, value)
    for name, value in _dotenv_values(dotenv_python).items():
        if value is not None:
            env[name] = value

    env.setdefault("DJANGO_ADMIN_USERNAME", env["GRAFANA_ADMIN_USER"])
    env.setdefault("DJANGO_ADMIN_PASSWORD", env["GRAFANA_ADMIN_PASSWORD"])
    env.setdefault("VITE_BACKEND_BASE_URL", env["BACKEND_BASE_URL"])
    env.setdefault(
        "VITE_BACKEND_BASE_WS",
        env["BACKEND_BASE_URL"].replace("https://", "wss://").replace("http://", "ws://"),
    )
    os.environ.update(env)
    return env


def backend_environment(env: dict[str, str]) -> dict[str, str]:
    backend_env = env.copy()
    website_dir = (BACKEND_DIR / "website").resolve()
    python_path = backend_env.get("PYTHONPATH")
    if python_path:
        backend_env["PYTHONPATH"] = os.pathsep.join(
            entry
            for entry in python_path.split(os.pathsep)
            if Path(entry).resolve() != website_dir
        )
    return backend_env


def display_environment(title: str, env: dict[str, str]) -> None:
    print(f"\n{title} effective environment (.env overrides defaults; secrets masked):", flush=True)
    names = list(DEFAULT_ENVIRONMENT)
    names.extend(
        sorted(
            name
            for name in env
            if name.startswith(("DJANGO_ADMIN_", "VITE_BACKEND_")) and name not in DEFAULT_ENVIRONMENT
        )
    )
    for name in names:
        is_secret = "PASSWORD" in name or "SECRET" in name
        value = "******** (set)" if is_secret and env.get(name) else env.get(name, "<unset>")
        print(f"  {name}={value}", flush=True)


def display_urls(title: str, urls: tuple[tuple[str, str], ...]) -> None:
    print(f"\n{title} URLs:", flush=True)
    for label, url in urls:
        print(f"  {label}: {url}", flush=True)
    print(flush=True)


def compose_command(docker: str, compose_file: Path, *, project_name: str | None = None) -> list[str]:
    command = [docker, "compose"]
    if project_name:
        command.extend(["--project-name", project_name])
    command.extend(["-f", str(compose_file)])
    return command


def wait_for_compose_services(
    compose: list[str],
    services: tuple[str, ...],
    *,
    timeout: float = 120,
) -> None:
    deadline = time.monotonic() + timeout
    last_statuses: dict[str, str] = {}
    print("\nWaiting for local infrastructure...", flush=True)
    while time.monotonic() < deadline:
        statuses = {}
        for service in services:
            container = subprocess.run(
                [*compose, "ps", "-q", service],
                cwd=PROJECT_DIR,
                check=False,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if not container:
                statuses[service] = "missing"
                continue
            statuses[service] = subprocess.run(
                [
                    compose[0],
                    "inspect",
                    "--format",
                    "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}",
                    container,
                ],
                check=False,
                capture_output=True,
                text=True,
            ).stdout.strip()

        if all(status in {"healthy", "running"} for status in statuses.values()):
            print("Local infrastructure is ready.", flush=True)
            return
        if statuses != last_statuses:
            print(", ".join(f"{name}={status}" for name, status in statuses.items()), flush=True)
            last_statuses = statuses
        time.sleep(1)
    raise RuntimeError(f"Local infrastructure did not become ready: {last_statuses}")

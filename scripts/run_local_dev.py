from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from dotenv import dotenv_values


PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "backend"
FRONTEND_DIR = PROJECT_DIR / "frontend"
COMPOSE_FILE = PROJECT_DIR / "local-testing.docker-compose.yml"
INSTANCE_LOCK_ADDRESS = ("127.0.0.1", 49173)
INFRASTRUCTURE_SERVICES = ("redis", "postgres", "prometheus", "grafana")


def require_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise RuntimeError(f"Required executable is not available in PATH: {name}")
    return executable


def acquire_instance_lock(address: tuple[str, int] = INSTANCE_LOCK_ADDRESS) -> socket.socket:
    instance_lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        instance_lock.bind(address)
        instance_lock.listen(1)
    except OSError as error:
        instance_lock.close()
        raise RuntimeError("Local development environment is already running.") from error
    return instance_lock


def load_project_environment() -> None:
    defaults = {
        "IS_DEV_ENV": "True",
        "BEHIND_NGINX": "False",
        "PROTOCOL": "http",
        "DEPLOYMENT_HOST": "localhost",
        "BACKEND_SECRET_KEY": "local-development-backend-secret",
        "SIGNING_SECRET": "local-development-signing-secret",
        "BACKEND_BASE_URL": "http://localhost:8000",
        "REDIS_ADDRESS": "localhost",
        "REDIS_PORT": "6379",
        "REDIS_PASSWORD": "admin",
        "POSTGRES_ADDRESS": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_NAME": "idrive-postgres",
        "POSTGRES_USER": "admin",
        "POSTGRES_PASSWORD": "admin",
    }
    for name, value in defaults.items():
        os.environ.setdefault(name, value)
    for name, value in dotenv_values(PROJECT_DIR / ".env").items():
        if value is not None:
            os.environ[name] = value

    os.environ.setdefault("DJANGO_ADMIN_USERNAME", os.getenv("GRAFANA_ADMIN_USER", "admin"))
    os.environ.setdefault("DJANGO_ADMIN_PASSWORD", os.getenv("GRAFANA_ADMIN_PASSWORD", "admin"))
    os.environ.setdefault("VITE_BACKEND_BASE_URL", os.environ["BACKEND_BASE_URL"])
    os.environ.setdefault(
        "VITE_BACKEND_BASE_WS",
        os.environ["BACKEND_BASE_URL"].replace("https://", "wss://").replace("http://", "ws://"),
    )


def backend_environment() -> dict[str, str]:
    env = os.environ.copy()
    website_dir = (BACKEND_DIR / "website").resolve()
    python_path = env.get("PYTHONPATH")
    if python_path:
        env["PYTHONPATH"] = os.pathsep.join(
            entry
            for entry in python_path.split(os.pathsep)
            if Path(entry).resolve() != website_dir
        )
    return env


def run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    print(f"\n> {' '.join(command)}", flush=True)
    subprocess.run(command, cwd=cwd, env=env, check=True)


def start(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.Popen:
    print(f"\n> {' '.join(command)}", flush=True)
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


def wait_for_infrastructure(docker: str, timeout: float = 120) -> None:
    deadline = time.monotonic() + timeout
    last_statuses: dict[str, str] = {}
    print("Waiting for local infrastructure...", flush=True)

    while time.monotonic() < deadline:
        statuses: dict[str, str] = {}
        for service in INFRASTRUCTURE_SERVICES:
            container = subprocess.run(
                [docker, "compose", "-f", str(COMPOSE_FILE), "ps", "-q", service],
                cwd=PROJECT_DIR,
                check=False,
                capture_output=True,
                text=True,
            ).stdout.strip()
            if not container:
                statuses[service] = "missing"
                continue
            statuses[service] = subprocess.run(
                [docker, "inspect", "--format", "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}", container],
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


def main() -> int:
    instance_lock = acquire_instance_lock()
    processes: list[subprocess.Popen] = []
    docker: str | None = None
    infrastructure_started = False
    try:
        load_project_environment()
        docker = require_executable("docker")
        npm = require_executable("npm")
        python = sys.executable
        manage_py = str(BACKEND_DIR / "manage.py")
        backend_env = backend_environment()

        run(
            [docker, "compose", "-f", str(COMPOSE_FILE), "up", "-d", "--wait"],
            cwd=PROJECT_DIR,
        )
        infrastructure_started = True
        wait_for_infrastructure(docker)
        run([python, manage_py, "migrate"], cwd=BACKEND_DIR, env=backend_env)
        run(
            [python, manage_py, "createuser", "--staff", "--if-not-exists", "--username", os.environ["DJANGO_ADMIN_USERNAME"], "--password", os.environ["DJANGO_ADMIN_PASSWORD"]],
            cwd=BACKEND_DIR,
            env=backend_env,
        )

        commands = [
            ([python, manage_py, "runserver", "0.0.0.0:8000"], BACKEND_DIR, backend_env),
            ([npm, "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"], FRONTEND_DIR, None),
        ]
        for command, cwd, env in commands:
            processes.append(start(command, cwd=cwd, env=env))

        while all(process.poll() is None for process in processes):
            time.sleep(0.25)
        return next(
            (process.returncode for process in processes if process.returncode not in (None, 0)),
            0,
        )
    except KeyboardInterrupt:
        return 0
    finally:
        for process in processes:
            stop_process_tree(process)
        if infrastructure_started and docker is not None:
            subprocess.run(
                [docker, "compose", "-f", str(COMPOSE_FILE), "stop"],
                cwd=PROJECT_DIR,
                check=False,
            )
        instance_lock.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Local development startup failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

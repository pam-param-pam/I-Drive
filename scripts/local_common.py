from __future__ import annotations

import json
import os
import re
import shutil
import signal
import socket
import subprocess
import threading
import time
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_DIR / "backend"
FRONTEND_DIR = PROJECT_DIR / "frontend"
LOCAL_COMPOSE_FILE = PROJECT_DIR / "local-testing.docker-compose.yml"

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
    "DJANGO_ADMIN_USERNAME": "admin",
    "DJANGO_ADMIN_PASSWORD": "admin",
}


def require_executable(name: str) -> str:
    executable = shutil.which(name)
    if executable is None:
        raise RuntimeError(f"Required executable is not available in PATH: {name}")
    return executable


def run(command: list[str], cwd: Path = PROJECT_DIR, env: dict[str, str] | None = None, quiet: bool = False) -> None:
    print(f"\n> Running {Path(command[0]).name}", flush=True)
    if not quiet:
        subprocess.run(command, cwd=cwd, env=env, check=True)
        return

    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(
            f"{Path(command[0]).name} exited with code {result.returncode}."
        )


def start(command: list[str], cwd: Path = PROJECT_DIR, env: dict[str, str] | None = None) -> subprocess.Popen:
    print(f"\n> Starting {Path(command[0]).name}", flush=True)
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


def wait_for_processes(processes: list[subprocess.Popen], stop_requested: threading.Event | None = None) -> int:
    while all(process.poll() is None for process in processes):
        if stop_requested is not None and stop_requested.is_set():
            return 0
        time.sleep(0.25)
    return next(
        (process.returncode for process in processes if process.returncode not in (None, 0)),
        0,
    )


def acquire_instance_lock(address: tuple[str, int], launcher_name: str) -> socket.socket:
    def bind() -> socket.socket:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind(address)
            listener.listen(1)
        except OSError:
            listener.close()
            raise
        return listener

    try:
        return bind()
    except OSError:
        pass

    while True:
        try:
            answer = input(f"A local {launcher_name} launcher is already running on {address}. Kill it? [y/n]: ")
        except EOFError as error:
            raise RuntimeError("Cannot ask whether to stop the existing launcher") from error
        answer = answer.strip().lower()
        if answer in {"y", "yes"}:
            break
        if answer in {"n", "no"}:
            raise RuntimeError(f"The existing {launcher_name} launcher was left running")
        print("Please answer y or n.", flush=True)
    unsupported_owner = False
    try:
        with socket.create_connection(address, timeout=2) as connection:
            connection.settimeout(2)
            connection.sendall(f"IDRIVE_STOP {launcher_name}\n".encode("ascii"))
            with connection.makefile("rb") as stream:
                response = stream.readline(16)
            if response == b"NO\n":
                raise RuntimeError("The lock belongs to a different or unsupported process")
            unsupported_owner = response != b"OK\n"
    except OSError:
        unsupported_owner = True

    if unsupported_owner:
        if os.name != "nt":
            raise RuntimeError("The launcher holding the lock cannot be stopped automatically")
        stop_legacy_windows_launcher(address, launcher_name)

    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            return bind()
        except OSError:
            time.sleep(0.2)
    raise RuntimeError(f"The previous {launcher_name} launcher did not release lock {address}")


def stop_legacy_windows_launcher(address: tuple[str, int], launcher_name: str) -> None:
    """Replace a pre-control-protocol launcher only after checking its port and command line."""
    expected_script = {"celery": "run_local_celery.py", "development": "run_local_dev.py"}[launcher_name]
    netstat = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, check=True)
    listener_pid = None
    for line in netstat.stdout.splitlines():
        parts = line.split()
        if (len(parts) == 5 and parts[0] == "TCP" and parts[1] == f"{address[0]}:{address[1]}"
                and parts[3] == "LISTENING" and parts[4].isdigit()):
            listener_pid = int(parts[4])
            break
    if listener_pid is None:
        raise RuntimeError("Could not identify the process holding the launcher lock")

    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if powershell is None:
        raise RuntimeError("PowerShell is required to verify the existing launcher")
    inspect = subprocess.run([
        powershell, "-NoProfile", "-Command",
        f"$p = Get-CimInstance Win32_Process -Filter 'ProcessId = {listener_pid}'; "
        "if ($p) { @{Name=$p.Name; CommandLine=$p.CommandLine} | ConvertTo-Json -Compress }",
    ], capture_output=True, text=True, check=True)
    try:
        process = json.loads(inspect.stdout)
    except (json.JSONDecodeError, TypeError) as error:
        raise RuntimeError("Could not verify the process holding the launcher lock") from error
    if not isinstance(process, dict):
        raise RuntimeError("Could not verify the process holding the launcher lock")
    command_line = process.get("CommandLine") or ""
    script_pattern = r'(?:^|[\\/\s"])' + re.escape(expected_script) + r'(?:"|\s|$)'
    if (process.get("Name", "").lower() not in {"python.exe", "pythonw.exe"}
            or not re.search(script_pattern, command_line, re.IGNORECASE)):
        raise RuntimeError("The lock is held by a process other than the expected local launcher")

    print(f"Stopping existing {launcher_name} launcher (PID {listener_pid})...", flush=True)
    subprocess.run(["taskkill", "/PID", str(listener_pid), "/T", "/F"],
                   capture_output=True, text=True, check=False)


def watch_instance_lock(instance_lock: socket.socket, launcher_name: str) -> threading.Event:
    stop_requested = threading.Event()
    instance_lock.settimeout(0.5)

    def watch() -> None:
        while not stop_requested.is_set():
            try:
                connection, _ = instance_lock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with connection:
                connection.settimeout(2)
                try:
                    with connection.makefile("rb") as stream:
                        message = stream.readline(64)
                    if message == f"IDRIVE_STOP {launcher_name}\n".encode("ascii"):
                        connection.sendall(b"OK\n")
                        stop_requested.set()
                    else:
                        connection.sendall(b"NO\n")
                except OSError:
                    continue

    threading.Thread(target=watch, name=f"{launcher_name}-lock-control", daemon=True).start()
    return stop_requested


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

    env.setdefault("VITE_BACKEND_BASE_URL", env["BACKEND_BASE_URL"])
    env.setdefault(
        "VITE_BACKEND_BASE_WS",
        env["BACKEND_BASE_URL"].replace("https://", "wss://").replace("http://", "ws://"),
    )
    os.environ.update(env)
    return env

def write_project_environment(env: dict[str, str]) -> None:
    header = [
        "# AUTO-GENERATED FILE - DO NOT EDIT MANUALLY.",
        "# Re-run the local environment setup to regenerate this file.",
        "",
    ]

    def write_env_file(path: Path, values: dict[str, str]) -> None:
        lines = header.copy()

        for name, value in values.items():
            escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            lines.append(f'{name}="{escaped}"')

        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    write_env_file(
        BACKEND_DIR / ".env",
        {
            name: env[name]
            for name in DEFAULT_ENVIRONMENT
        },
    )

    write_env_file(
        FRONTEND_DIR / ".env",
        {
            "VITE_BACKEND_BASE_URL": env["VITE_BACKEND_BASE_URL"],
            "VITE_BACKEND_BASE_WS": env["VITE_BACKEND_BASE_WS"],
        },
    )

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


def start_local_infrastructure() -> list[str]:
    docker = require_executable("docker")
    local_compose = compose_command(docker, LOCAL_COMPOSE_FILE)
    run([*local_compose, "down"])
    run([*local_compose, "up", "--wait"])
    return local_compose


def wait_for_compose_services(compose: list[str], services: tuple[str, ...],  timeout: float = 120) -> None:
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

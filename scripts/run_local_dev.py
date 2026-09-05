from __future__ import annotations

import subprocess
import sys

from local_common import (
    BACKEND_DIR,
    FRONTEND_DIR,
    PROJECT_DIR,
    acquire_instance_lock,
    backend_environment,
    compose_command,
    display_environment,
    display_urls,
    load_project_environment,
    require_executable,
    run,
    start,
    stop_process_tree,
    wait_for_processes,
)


LOCAL_COMPOSE_FILE = PROJECT_DIR / "local-testing.docker-compose.yml"
FULL_COMPOSE_FILE = PROJECT_DIR / "docker-compose.yml"
FULL_STACK_PROJECT_NAME = "idrive-full-local"
INSTANCE_LOCK_ADDRESS = ("127.0.0.1", 49173)
def main() -> int:
    instance_lock = acquire_instance_lock(INSTANCE_LOCK_ADDRESS)
    processes: list[subprocess.Popen] = []
    local_compose: list[str] | None = None
    try:
        env = load_project_environment()
        display_environment("Local development", env)

        docker = require_executable("docker")
        npm = require_executable("npm")
        backend_env = backend_environment(env)
        manage_py = str(BACKEND_DIR / "manage.py")
        local_compose = compose_command(docker, LOCAL_COMPOSE_FILE)
        full_compose = compose_command(
            docker,
            FULL_COMPOSE_FILE,
            project_name=FULL_STACK_PROJECT_NAME,
        )

        run([*full_compose, "stop"])
        run([*local_compose, "up", "-d", "--wait"])

        processes = [
            start(
                [sys.executable, manage_py, "runserver", f"0.0.0.0:{env['BACKEND_PORT']}"],
                cwd=BACKEND_DIR,
                env=backend_env,
            ),
            start(
                [npm, "run", "dev", "--", "--host", "0.0.0.0", "--port", env["FRONTEND_PORT"]],
                cwd=FRONTEND_DIR,
            ),
        ]
        display_urls(
            "Local development",
            (
                ("Application", f"http://localhost:{env['FRONTEND_PORT']}"),
                ("Backend", env["BACKEND_BASE_URL"]),
                ("Grafana", f"http://localhost:{env['GRAFANA_PORT']}"),
                ("Prometheus", f"http://localhost:{env['PROMETHEUS_PORT']}"),
            ),
        )
        return wait_for_processes(processes)
    except KeyboardInterrupt:
        return 0
    finally:
        for process in processes:
            stop_process_tree(process)
        if local_compose is not None:
            subprocess.run([*local_compose, "stop"], cwd=PROJECT_DIR, check=False)
        instance_lock.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Local development startup failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

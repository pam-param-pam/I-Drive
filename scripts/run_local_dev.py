from __future__ import annotations

import subprocess
import sys

from local_common import (
    BACKEND_DIR,
    FRONTEND_DIR,
    PROJECT_DIR,
    acquire_instance_lock,
    backend_environment,
    display_urls,
    load_project_environment,
    require_executable,
    start,
    start_local_infrastructure,
    stop_process_tree,
    wait_for_processes, compose_command, LOCAL_COMPOSE_FILE,
)


INSTANCE_LOCK_ADDRESS = ("127.0.0.1", 49173)
def main() -> int:
    instance_lock = acquire_instance_lock(INSTANCE_LOCK_ADDRESS)
    processes: list[subprocess.Popen] = []
    docker = require_executable("docker")
    local_compose = compose_command(docker, LOCAL_COMPOSE_FILE)

    try:
        env = load_project_environment()

        npm = require_executable("npm")
        backend_env = backend_environment(env)
        manage_py = str(BACKEND_DIR / "manage.py")
        start_local_infrastructure()

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
        print("Stopping Compose... If you don't see 'Compose stopped` then it failed to stop.", flush=True)
        subprocess.run(
            [*local_compose, "stop", "--timeout", "1"],
            cwd=PROJECT_DIR,
            check=False,
        )
        print("Compose stopped.", flush=True)
        instance_lock.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (KeyError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Local development startup failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

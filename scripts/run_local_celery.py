from __future__ import annotations

import subprocess
import sys

from local_common import (
    BACKEND_DIR,
    LOCAL_COMPOSE_FILE,
    acquire_instance_lock,
    backend_environment,
    compose_command,
    load_project_environment,
    require_executable,
    start,
    stop_process_tree,
    wait_for_compose_services,
    wait_for_processes,
)


INSTANCE_LOCK_ADDRESS = ("127.0.0.1", 49174)
INFRASTRUCTURE_SERVICES = ("redis", "postgres", "prometheus", "grafana")
def main() -> int:
    instance_lock = acquire_instance_lock(INSTANCE_LOCK_ADDRESS)
    processes: list[subprocess.Popen] = []
    try:
        env = load_project_environment()
        docker = require_executable("docker")
        wait_for_compose_services(
            compose_command(docker, LOCAL_COMPOSE_FILE),
            INFRASTRUCTURE_SERVICES,
        )
        backend_env = backend_environment(env)
        celery = [sys.executable, "-m", "celery", "-A", "website"]
        commands = (
            [*celery, "worker", "-l", "INFO", "-P", "eventlet"],
            [*celery, "worker", "-l", "INFO", "--pool=solo", "-Q", "wsQ"],
            [*celery, "worker", "-l", "INFO", "--pool=solo", "-Q", "deletion", "-c", "1"],
            [*celery, "beat", "-l", "INFO", "--scheduler", "django_celery_beat.schedulers:DatabaseScheduler"],
        )
        processes = [start(command, cwd=BACKEND_DIR, env=backend_env) for command in commands]
        return wait_for_processes(processes)
    except KeyboardInterrupt:
        return 0
    finally:
        for process in processes:
            stop_process_tree(process)
        instance_lock.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Local Celery startup failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

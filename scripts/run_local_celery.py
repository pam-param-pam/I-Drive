from __future__ import annotations

import subprocess
import sys
import time

from run_local_dev import (
    BACKEND_DIR,
    acquire_instance_lock,
    backend_environment,
    load_project_environment,
    require_executable,
    start,
    stop_process_tree,
    wait_for_infrastructure,
)


CELERY_LOCK_ADDRESS = ("127.0.0.1", 49174)


def main() -> int:
    instance_lock = acquire_instance_lock(CELERY_LOCK_ADDRESS)
    processes: list[subprocess.Popen] = []

    try:
        load_project_environment()
        docker = require_executable("docker")
        python = sys.executable
        backend_env = backend_environment()
        wait_for_infrastructure(docker)

        commands = [
            [python, "-m", "celery", "-A", "website", "worker", "-l", "INFO", "-P", "eventlet"],
            [python, "-m", "celery", "-A", "website", "worker", "-l", "INFO", "--pool=solo", "-Q", "wsQ"],
            [python, "-m", "celery", "-A", "website", "worker", "-l", "INFO", "--pool=solo", "-Q", "deletion", "-c", "1"],
            [python, "-m", "celery", "-A", "website", "beat", "-l", "INFO", "--scheduler", "django_celery_beat.schedulers:DatabaseScheduler"],
        ]

        for command in commands:
            processes.append(start(command, cwd=BACKEND_DIR, env=backend_env))

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
        instance_lock.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print(f"Local Celery startup failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

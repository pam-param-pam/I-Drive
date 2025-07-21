# File: runcelery.py
import os
import signal
import subprocess
import sys
import time

import psutil
from django.core.management.base import BaseCommand
from django.utils import autoreload


DELAY_UNTIL_START = 1.0

# Multiple Celery command variants (edit to match your project needs)
CELERY_COMMANDS = [
    'celery -A website worker -l INFO -P eventlet',
    'celery -A website worker -l INFO --pool=solo -Q wsQ',
]

class Command(BaseCommand):

    help = 'Run and autoreload multiple Celery workers'

    celery_processes = []

    def kill_celery_processes(self):
        for proc in self.celery_processes:
            try:
                self.stdout.write(f'[*] Killing Celery process PID={proc.pid}')
                os.kill(proc.pid, signal.SIGTERM)
            except (psutil.NoSuchProcess, ProcessLookupError):
                self.stdout.write(f'[!] Process PID={proc.pid} already terminated.')
        self.celery_processes.clear()

    def run_celery_processes(self):
        time.sleep(DELAY_UNTIL_START)
        for cmd in CELERY_COMMANDS:
            self.stdout.write(f'[*] Starting: {cmd}')
            # Direct output to current console
            proc = subprocess.Popen(
                cmd,
                shell=True,
                stdout=sys.stdout,
                stderr=sys.stderr,
            )
            self.celery_processes.append(proc)

    def reload_celery(self):
        if self.celery_processes:
            self.stdout.write('[*] Reloading: Stopping running Celery workers...')
            self.kill_celery_processes()

        self.stdout.write('[*] Starting Celery workers...')
        self.run_celery_processes()

    def handle(self, *args, **options):
        autoreload.run_with_reloader(self.reload_celery)

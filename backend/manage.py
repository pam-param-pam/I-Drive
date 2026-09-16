#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from pathlib import Path


def load_local_development_environment() -> None:
    """Use the launcher's defaults for direct manage.py commands in a checkout."""
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    local_common = scripts_dir / "local_common.py"
    if not local_common.is_file():
        return

    sys.path.insert(0, str(scripts_dir))
    try:
        from local_common import load_project_environment

        load_project_environment()
    finally:
        sys.path.remove(str(scripts_dir))


def main():
    """Run administrative tasks."""
    load_local_development_environment()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'website.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()



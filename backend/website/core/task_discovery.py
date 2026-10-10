from pathlib import Path
from django.apps import apps


class RecursiveTaskDiscovery:
    def __call__(self) -> tuple[str, ...]:
        modules = set()
        for config in apps.get_app_configs():
            app_path = Path(config.path)
            if (app_path / "tasks.py").is_file():
                modules.add(f"{config.name}.tasks")
            tasks_path = app_path / "tasks"
            if not tasks_path.is_dir():
                continue
            modules.add(f"{config.name}.tasks")
            for path in tasks_path.rglob("*.py"):
                parts = path.relative_to(app_path).with_suffix("").parts
                if "__pycache__" in parts or not all(part.isidentifier() for part in parts):
                    continue
                if parts[-1] == "__init__":
                    parts = parts[:-1]
                modules.add(".".join((config.name, *parts)))
        return tuple(sorted(modules))

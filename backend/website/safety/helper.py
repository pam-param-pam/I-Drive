import os
import ast
import importlib

from ..models import DiscordAttachmentMixin


def get_classes_extending_discordAttachmentMixin() -> list[type[DiscordAttachmentMixin]]:
    base_class_name = "DiscordAttachmentMixin"
    models_dir = os.path.join("website", "models")

    matching_classes = []

    # Walk through all files in website/models/
    for filename in os.listdir(models_dir):
        if not filename.endswith(".py") or filename == "__init__.py":
            continue

        file_path = os.path.join(models_dir, filename)

        with open(file_path, "r", encoding="utf-8") as file:
            source_code = file.read()

        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            continue

        module_name = f"website.models.{filename[:-3]}"  # strip .py

        class ClassCollector(ast.NodeVisitor):
            def visit_ClassDef(self, node):
                # Check if class inherits from DiscordAttachmentMixin
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == base_class_name:
                        # Import module and extract class object
                        module = importlib.import_module(module_name)
                        class_obj = getattr(module, node.name, None)
                        if class_obj:
                            matching_classes.append(class_obj)
                self.generic_visit(node)

        collector = ClassCollector()
        collector.visit(tree)

    return matching_classes

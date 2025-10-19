import ast
import os

from ..models import DiscordAttachmentMixin


def get_classes_extending_discordAttachmentMixin() -> list[DiscordAttachmentMixin]:
    base_class_name = "DiscordAttachmentMixin"
    file_path = os.path.join("website", "models.py")

    with open(file_path, "r", encoding="utf-8") as file:
        source_code = file.read()

    tree = ast.parse(source_code)
    matching_classes = []

    class ClassCollector(ast.NodeVisitor):
        def visit_ClassDef(self, node):
            nonlocal matching_classes
            if node.bases:
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == base_class_name:
                        # Import the class dynamically
                        class_module = __import__("website.models", fromlist=[node.name])
                        class_obj = getattr(class_module, node.name)
                        matching_classes.append(class_obj)
            self.generic_visit(node)

    collector = ClassCollector()
    collector.visit(tree)

    return matching_classes




import importlib
import pkgutil

from ogd_integrated_view.apis import definitions
from ogd_integrated_view.apis.base import ApiDefinition


def discover_api_definitions() -> list[ApiDefinition]:
    apis: list[ApiDefinition] = []
    for _, module_name, _ in pkgutil.iter_modules(definitions.__path__):
        module = importlib.import_module(f"{definitions.__name__}.{module_name}")
        for attr in vars(module).values():
            if isinstance(attr, type) and issubclass(attr, ApiDefinition) and attr is not ApiDefinition:
                apis.append(attr())
    return apis

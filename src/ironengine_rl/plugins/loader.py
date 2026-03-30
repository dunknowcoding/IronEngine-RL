from __future__ import annotations

import importlib
import importlib.util
import inspect
import sys
from pathlib import Path
from types import ModuleType
from typing import Any


def load_plugin_symbol(spec: dict[str, Any]) -> Any:
    if module_path := spec.get("module_path"):
        module_name, _, symbol_name = module_path.partition(":")
        module = _import_module_with_workspace_fallback(module_name)
        return getattr(module, symbol_name or spec.get("symbol", "Plugin"))
    if file_path := spec.get("file_path"):
        symbol_name = spec.get("symbol", "Plugin")
        path = Path(file_path)
        module_name = spec.get("module_name", path.stem)
        loaded_module = _load_module_from_file(module_name, path)
        return getattr(loaded_module, symbol_name)
    raise ValueError("Plugin spec must define 'module_path' or 'file_path'.")


def instantiate_plugin(spec: dict[str, Any], **kwargs: Any) -> Any:
    plugin_obj = load_plugin_symbol(spec)
    if inspect.isclass(plugin_obj):
        return plugin_obj(**_filter_kwargs(plugin_obj, kwargs))
    if callable(plugin_obj):
        return plugin_obj(**_filter_kwargs(plugin_obj, kwargs))
    return plugin_obj


def describe_plugin_spec(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "module_path": spec.get("module_path"),
        "file_path": spec.get("file_path"),
        "symbol": spec.get("symbol"),
    }


def _import_module_with_workspace_fallback(module_name: str) -> ModuleType:
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        workspace_root = Path(__file__).resolve().parents[3]
        workspace_str = str(workspace_root)
        if workspace_str not in sys.path:
            sys.path.insert(0, workspace_str)
        return importlib.import_module(module_name)


def _load_module_from_file(module_name: str, path: Path) -> ModuleType:
    module_spec = importlib.util.spec_from_file_location(module_name, path)
    if module_spec is None or module_spec.loader is None:
        raise ImportError(f"Unable to load module from file: {path}")
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    return module


def _filter_kwargs(callable_obj: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
    try:
        signature = inspect.signature(callable_obj)
    except (TypeError, ValueError):
        return kwargs
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
        return kwargs
    allowed = set(signature.parameters)
    return {key: value for key, value in kwargs.items() if key in allowed}

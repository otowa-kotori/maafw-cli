"""
Load user Python scripts and discover CustomRecognition / CustomAction subclasses.

The loader uses ``importlib`` to import a ``.py`` file, then scans its attributes
for concrete subclasses of ``maa.custom_recognition.CustomRecognition`` and
``maa.custom_action.CustomAction``.  Each discovered class is instantiated
(no-arg constructor) and returned in a ``LoadResult``.

Module naming: ``maafw_custom_{stem}_{path_hash}`` ensures that scripts with the
same filename in different directories don't collide, and ``reload=True`` can
re-import the same module key.
"""
from __future__ import annotations

import hashlib
import importlib.util
import inspect
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_log = logging.getLogger("maafw_cli.core.script_loader")


@dataclass
class LoadResult:
    """Result of loading a user script."""

    path: str
    module_name: str
    recognitions: dict[str, Any] = field(default_factory=dict)
    actions: dict[str, Any] = field(default_factory=dict)


def _module_key(path: Path) -> str:
    """Derive a stable, unique module name from a file path."""
    stem = path.stem
    path_hash = hashlib.md5(str(path.resolve()).encode()).hexdigest()[:8]
    return f"maafw_custom_{stem}_{path_hash}"


def load_script(path: str | Path, *, reload: bool = False) -> LoadResult:
    """Load a Python script and discover custom recognition / action classes.

    Parameters
    ----------
    path:
        Path to a ``.py`` file.
    reload:
        If ``True``, remove any previously cached module and re-import.

    Returns
    -------
    LoadResult
        Discovered recognitions and actions (name -> instance).

    Raises
    ------
    FileNotFoundError
        If the path does not exist.
    ValueError
        If the path is not a ``.py`` file or contains no custom classes.
    ImportError
        If the script fails to import.
    """
    from maa.custom_action import CustomAction
    from maa.custom_recognition import CustomRecognition

    p = Path(path).resolve()

    if not p.exists():
        raise FileNotFoundError(f"Script not found: {p}")
    if p.suffix != ".py":
        raise ValueError(f"Not a Python file: {p}")

    module_name = _module_key(p)

    # Handle reload
    if reload and module_name in sys.modules:
        del sys.modules[module_name]
        _log.debug("Removed cached module '%s' for reload", module_name)

    # Import the module
    spec = importlib.util.spec_from_file_location(module_name, str(p))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot create module spec for: {p}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        # Clean up on failure
        sys.modules.pop(module_name, None)
        raise ImportError(f"Failed to import {p}: {exc}") from exc

    # Discover subclasses
    recognitions: dict[str, Any] = {}
    actions: dict[str, Any] = {}

    for _attr_name, obj in inspect.getmembers(module, inspect.isclass):
        # Skip the base classes themselves (they might be imported)
        if obj is CustomRecognition or obj is CustomAction:
            continue

        # Skip classes not defined in this module (imported from elsewhere)
        if getattr(obj, "__module__", None) != module_name:
            continue

        if issubclass(obj, CustomRecognition):
            name = getattr(obj, "name", None) or obj.__name__
            instance = obj()
            recognitions[name] = instance
            _log.info("Discovered CustomRecognition: %s", name)

        elif issubclass(obj, CustomAction):
            name = getattr(obj, "name", None) or obj.__name__
            instance = obj()
            actions[name] = instance
            _log.info("Discovered CustomAction: %s", name)

    result = LoadResult(
        path=str(p),
        module_name=module_name,
        recognitions=recognitions,
        actions=actions,
    )

    _log.info(
        "Loaded %s: %d recognitions, %d actions",
        p.name, len(recognitions), len(actions),
    )
    return result

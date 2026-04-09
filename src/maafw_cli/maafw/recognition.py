"""Generic recognition operations via MaaFramework.

Supports all MaaFW recognition types via reflection-based registry.
Reuses vision.py's resource/tasker/screencap infrastructure.
"""
from __future__ import annotations

import json
import logging
import typing
from dataclasses import MISSING, fields as dc_fields
from pathlib import Path
from typing import Any

from maa.pipeline import JRecognitionType
from maa.tasker import TaskDetail

from maafw_cli.core.errors import RecognitionError
from maafw_cli.core.log import Timer
from maafw_cli.core.session import Session
from maafw_cli.download import check_ocr_files_exist
from maafw_cli.maafw.vision import screencap, _save_screenshot

_log = logging.getLogger("maafw_cli.recognition")


# ── auto-generated registry ──────────────────────────────────────


def _build_registry() -> dict[str, tuple[JRecognitionType, type]]:
    """Build ``{type_name: (enum, dataclass)}`` from JRecognition's Union type.

    Uses the 1:1 ordering between ``JRecognitionType`` enum members and
    the ``JRecognitionParam`` Union type arguments.
    """
    from maa.pipeline import JRecognition  # noqa: F811 — local import keeps top-level lean

    param_hint = typing.get_type_hints(JRecognition)["param"]
    union_args = typing.get_args(param_hint)
    registry: dict[str, tuple[JRecognitionType, type]] = {}
    for enum_val, cls in zip(JRecognitionType, union_args):
        registry[enum_val.value] = (enum_val, cls)
    return registry


_REGISTRY = _build_registry()


# ── helpers ──────────────────────────────────────────────────────


def _parse_roi(raw: str) -> tuple[int, int, int, int]:
    """Parse ``"x,y,w,h"`` into a tuple."""
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        raise RecognitionError(f"Invalid ROI '{raw}'. Expected format: x,y,w,h")
    try:
        return tuple(int(p) for p in parts)  # type: ignore[return-value]
    except ValueError:
        raise RecognitionError(f"Invalid ROI '{raw}'. All values must be integers.")


def _parse_int_list(raw: str) -> list[int]:
    """Parse ``"200,0,0"`` into ``[200, 0, 0]``."""
    return [int(x.strip()) for x in raw.split(",")]


# ── type coercion ────────────────────────────────────────────────


def _coerce(value: Any, annotation: Any, *, from_string: bool = False) -> Any:
    """Coerce *value* to match the dataclass field *annotation*.

    Parameters
    ----------
    from_string:
        When ``True`` the value originates from CLI ``key=value`` pairs and
        is always a ``str`` that needs parsing.  When ``False`` the value
        comes from parsed JSON and may already be a native Python type.
    """
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)

    # --- simple scalars ---
    if annotation is int:
        return int(value)
    if annotation is float:
        return float(value)
    if annotation is bool:
        if isinstance(value, bool):
            return value
        return str(value).lower() in ("true", "1", "yes")
    if annotation is str:
        return str(value)

    # --- List[X] ---
    if origin is list:
        elem_type = args[0] if args else Any
        if from_string and isinstance(value, str):
            return _coerce_list_from_string(value, elem_type)
        if isinstance(value, list):
            if elem_type is Any:
                return value  # List[Any] — passthrough (And/Or sub-recognitions)
            return [_coerce(v, elem_type) for v in value]
        return value

    # --- Tuple[int, int, int, int] (JRect / roi / roi_offset) ---
    if origin is tuple:
        if from_string and isinstance(value, str):
            return _parse_roi(value)
        if isinstance(value, (list, tuple)):
            return tuple(value)
        return value

    # --- Union (e.g. JTarget = Union[bool, str, Tuple[int,int,int,int]]) ---
    if origin is typing.Union:
        return _coerce_union(value, args, from_string=from_string)

    # --- Any ---
    if annotation is Any:
        if from_string and isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    # --- unknown — passthrough ---
    return value



def _coerce_list_from_string(value: str, elem_type: Any) -> list:
    """Parse a comma-separated string into ``List[elem_type]``."""
    origin = typing.get_origin(elem_type)

    # List[List[int]] — try JSON first, fall back to wrapping comma-separated
    if origin is list:
        inner = typing.get_args(elem_type)
        inner_type = inner[0] if inner else Any
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [[_coerce(v, inner_type) for v in sub] for sub in parsed]
        except json.JSONDecodeError:
            pass
        # Fallback: treat "200,0,0" as a single inner list → [[200,0,0]]
        return [[_coerce(v, inner_type) for v in value.split(",")]]

    # List[List[str]] — also expect JSON
    if elem_type is Any:
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        return [s.strip() for s in value.split(",")]

    # List[str]
    if elem_type is str:
        return [s.strip() for s in value.split(",")]

    # List[int]
    if elem_type is int:
        return _parse_int_list(value)

    # List[float]
    if elem_type is float:
        return [float(x.strip()) for x in value.split(",")]

    # fallback
    return [s.strip() for s in value.split(",")]


def _coerce_union(value: Any, args: tuple, *, from_string: bool = False) -> Any:
    """Coerce a value for a Union type (e.g. ``JTarget``)."""
    # Filter out NoneType for Optional[X]
    non_none = [a for a in args if a is not type(None)]

    if from_string and isinstance(value, str):
        # Try bool keywords first
        if value.lower() in ("true", "false"):
            return value.lower() == "true"
        # Try tuple (roi-like: "x,y,w,h")
        if "," in value:
            parts = value.split(",")
            if len(parts) == 4:
                try:
                    return _parse_roi(value)
                except RecognitionError:
                    pass
        # Try int
        try:
            return int(value)
        except ValueError:
            pass
        # Fallback to string
        return value

    # From JSON — already typed, pass through
    if isinstance(value, bool):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(value) if any(typing.get_origin(a) is tuple for a in non_none) else value
    return value


# ── build_params ─────────────────────────────────────────────────


def build_params(reco_type: str, params: dict[str, str], *, from_string: bool = True) -> Any:
    """Build a J* dataclass from *reco_type* name + params dict.

    Parameters
    ----------
    reco_type:
        Recognition type name (e.g. ``"TemplateMatch"``).
    params:
        Parameter dict.  When *from_string* is ``True`` (default for CLI
        ``key=value`` mode) all values are strings that need parsing.
        When ``False`` values are native Python types from parsed JSON.
    from_string:
        Whether values are raw strings from CLI.

    Returns
    -------
    The appropriate J* dataclass instance.
    """
    entry = _REGISTRY.get(reco_type)
    if entry is None:
        supported = ", ".join(sorted(_REGISTRY))
        raise RecognitionError(
            f"Unknown recognition type '{reco_type}'. Supported: {supported}"
        )

    _, cls = entry
    kwargs: dict[str, Any] = {}
    field_map = {f.name: f for f in dc_fields(cls)}

    for key, value in params.items():
        field = field_map.get(key)
        if field is None:
            continue  # ignore unknown fields (forward-compat)
        kwargs[key] = _coerce(value, field.type, from_string=from_string)

    # Check required fields (no default and no default_factory)
    for f in dc_fields(cls):
        if f.name not in kwargs and f.default is MISSING and f.default_factory is MISSING:  # type: ignore[arg-type]
            raise RecognitionError(f"{reco_type} requires '{f.name}' parameter.")

    return cls(**kwargs)


def build_params_from_raw(raw: str) -> tuple[str, Any]:
    """Build recognition type + params from a raw JSON string.

    The JSON must contain a ``"recognition"`` key specifying the type.
    All other keys are treated as parameters.

    Returns ``(reco_type, params_obj)``.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RecognitionError(f"Invalid JSON: {e}")

    reco_type = data.pop("recognition", None)
    if not reco_type:
        raise RecognitionError("Raw JSON must contain a 'recognition' key.")

    if reco_type not in _REGISTRY:
        supported = ", ".join(sorted(_REGISTRY))
        raise RecognitionError(
            f"Unknown recognition type '{reco_type}'. Supported: {supported}"
        )

    return reco_type, build_params(reco_type, data, from_string=False)


# ── main entry point ─────────────────────────────────────────────


def recognize(
    session: Session,
    reco_type: str,
    params: dict[str, str] | None = None,
    raw: str | None = None,
) -> tuple[str, list, Path | None]:
    """Run a recognition operation on the current screen.

    Parameters
    ----------
    session:
        Session (provides controller, Resource, Tasker).
    reco_type:
        Recognition type name (e.g. ``"TemplateMatch"``).
        Ignored when *raw* is provided.
    params:
        Key-value parameters as strings (e.g. ``{"template": "btn.png"}``).
    raw:
        Raw JSON string containing ``"recognition"`` + parameters.
        When provided, *reco_type* and *params* are ignored.

    Returns
    -------
    tuple[str, list, Path | None]
        ``(resolved_reco_type, results, screenshot_path)`` where results is a list of
        recognition result objects and *screenshot_path* is the path to the saved
        screenshot (or ``None`` if saving failed).

    Raises
    ------
    RecognitionError
        On any failure (unknown type, screenshot failure, tasker failure, etc.).
    """
    with Timer("total recognition pipeline", log=_log):
        # Build params
        if raw is not None:
            resolved_type, params_obj = build_params_from_raw(raw)
        else:
            if not reco_type:
                raise RecognitionError("Recognition type is required.")
            resolved_type = reco_type
            params_obj = build_params(reco_type, params or {})

        reco_enum = _REGISTRY[resolved_type][0]

        # OCR needs model files
        if reco_enum == JRecognitionType.OCR and not check_ocr_files_exist():
            raise RecognitionError("OCR model not found. Run: maafw-cli resource download-ocr")

        tasker = session.get_tasker()
        if tasker is None:
            raise RecognitionError("Failed to initialize tasker (resource load failed).")

        image = screencap(session.controller)
        if image is None:
            raise RecognitionError("Screenshot failed — cannot run recognition without an image.")

        # Save screenshot to disk
        screenshot_path = _save_screenshot(image, prefix="reco")

        with Timer(f"{resolved_type} inference", log=_log):
            info: TaskDetail | None = (
                tasker.post_recognition(reco_enum, params_obj, image).wait().get()
            )
        if not info:
            raise RecognitionError(f"{resolved_type} recognition returned no result.")

        if not info.nodes:
            _log.warning("%s returned empty nodes list", resolved_type)
            raise RecognitionError(f"{resolved_type} recognition returned empty nodes.")

        return resolved_type, info.nodes[0].recognition.all_results, screenshot_path  # type: ignore[return-value]

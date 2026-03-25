"""Generic recognition operations via MaaFramework.

Supports TemplateMatch, FeatureMatch, ColorMatch, and OCR recognition types.
Reuses vision.py's resource/tasker/screencap infrastructure.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from maa.controller import Controller
from maa.pipeline import (
    JColorMatch,
    JFeatureMatch,
    JOCR,
    JRecognitionType,
    JTemplateMatch,
)
from maa.tasker import TaskDetail

from maafw_cli.core.errors import RecognitionError
from maafw_cli.core.log import Timer
from maafw_cli.download import check_ocr_files_exist
from maafw_cli.maafw.vision import _get_tasker, screencap

_log = logging.getLogger("maafw_cli.recognition")

# ── type string → enum mapping ───────────────────────────────────

_RECO_TYPE_MAP: dict[str, JRecognitionType] = {
    "TemplateMatch": JRecognitionType.TemplateMatch,
    "FeatureMatch": JRecognitionType.FeatureMatch,
    "ColorMatch": JRecognitionType.ColorMatch,
    "OCR": JRecognitionType.OCR,
}


# ── parameter builders ───────────────────────────────────────────

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


def _build_template_match_params(params: dict[str, str]) -> JTemplateMatch:
    """Build JTemplateMatch from parsed parameters."""
    if "template" not in params:
        raise RecognitionError("TemplateMatch requires 'template' parameter.")
    obj = JTemplateMatch(template=[t.strip() for t in params["template"].split(",")])
    if "roi" in params:
        obj.roi = _parse_roi(params["roi"])
    if "threshold" in params:
        obj.threshold = [float(params["threshold"])]
    if "order_by" in params:
        obj.order_by = params["order_by"]
    if "green_mask" in params:
        obj.green_mask = params["green_mask"].lower() in ("true", "1", "yes")
    if "method" in params:
        obj.method = int(params["method"])
    return obj


def _build_feature_match_params(params: dict[str, str]) -> JFeatureMatch:
    """Build JFeatureMatch from parsed parameters."""
    if "template" not in params:
        raise RecognitionError("FeatureMatch requires 'template' parameter.")
    obj = JFeatureMatch(template=[t.strip() for t in params["template"].split(",")])
    if "roi" in params:
        obj.roi = _parse_roi(params["roi"])
    if "ratio" in params:
        obj.ratio = float(params["ratio"])
    if "order_by" in params:
        obj.order_by = params["order_by"]
    if "detector" in params:
        obj.detector = params["detector"]
    if "count" in params:
        obj.count = int(params["count"])
    if "green_mask" in params:
        obj.green_mask = params["green_mask"].lower() in ("true", "1", "yes")
    return obj


def _build_color_match_params(params: dict[str, str]) -> JColorMatch:
    """Build JColorMatch from parsed parameters."""
    if "lower" not in params or "upper" not in params:
        raise RecognitionError("ColorMatch requires 'lower' and 'upper' parameters.")
    obj = JColorMatch(
        lower=[_parse_int_list(params["lower"])],
        upper=[_parse_int_list(params["upper"])],
    )
    if "roi" in params:
        obj.roi = _parse_roi(params["roi"])
    if "order_by" in params:
        obj.order_by = params["order_by"]
    if "method" in params:
        obj.method = int(params["method"])
    if "count" in params:
        obj.count = int(params["count"])
    if "connected" in params:
        obj.connected = params["connected"].lower() in ("true", "1", "yes")
    return obj


def _build_ocr_params(params: dict[str, str]) -> JOCR:
    """Build JOCR from parsed parameters."""
    obj = JOCR()
    if "roi" in params:
        obj.roi = _parse_roi(params["roi"])
    if "expected" in params:
        obj.expected = [e.strip() for e in params["expected"].split(",")]
    if "threshold" in params:
        obj.threshold = float(params["threshold"])
    if "order_by" in params:
        obj.order_by = params["order_by"]
    if "only_rec" in params:
        obj.only_rec = params["only_rec"].lower() in ("true", "1", "yes")
    if "model" in params:
        obj.model = params["model"]
    return obj


_PARAM_BUILDERS = {
    "TemplateMatch": _build_template_match_params,
    "FeatureMatch": _build_feature_match_params,
    "ColorMatch": _build_color_match_params,
    "OCR": _build_ocr_params,
}


def build_params(reco_type: str, params: dict[str, str]) -> Any:
    """Build recognition parameter object from type name and string params.

    Returns the appropriate J* dataclass instance.
    Raises :class:`RecognitionError` for unknown types or invalid parameters.
    """
    builder = _PARAM_BUILDERS.get(reco_type)
    if builder is None:
        supported = ", ".join(sorted(_PARAM_BUILDERS))
        raise RecognitionError(
            f"Unknown recognition type '{reco_type}'. Supported: {supported}"
        )
    return builder(params)


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

    if reco_type not in _RECO_TYPE_MAP:
        supported = ", ".join(sorted(_RECO_TYPE_MAP))
        raise RecognitionError(
            f"Unknown recognition type '{reco_type}'. Supported: {supported}"
        )

    # Convert remaining keys to string values for the builder
    str_params = {k: json.dumps(v) if isinstance(v, (list, dict)) else str(v) for k, v in data.items()}

    # For list-type params that came as JSON arrays, handle specially
    builder = _PARAM_BUILDERS[reco_type]
    return reco_type, _build_from_raw_dict(reco_type, data)


def _build_from_raw_dict(reco_type: str, data: dict) -> Any:
    """Build params from already-parsed JSON data (native types)."""
    if reco_type == "TemplateMatch":
        if "template" not in data:
            raise RecognitionError("TemplateMatch requires 'template' parameter.")
        obj = JTemplateMatch(template=data["template"])
        if "roi" in data:
            obj.roi = tuple(data["roi"])
        if "threshold" in data:
            t = data["threshold"]
            obj.threshold = t if isinstance(t, list) else [t]
        if "order_by" in data:
            obj.order_by = data["order_by"]
        if "green_mask" in data:
            obj.green_mask = bool(data["green_mask"])
        if "method" in data:
            obj.method = int(data["method"])
        return obj

    elif reco_type == "FeatureMatch":
        if "template" not in data:
            raise RecognitionError("FeatureMatch requires 'template' parameter.")
        obj = JFeatureMatch(template=data["template"])
        if "roi" in data:
            obj.roi = tuple(data["roi"])
        if "ratio" in data:
            obj.ratio = float(data["ratio"])
        if "order_by" in data:
            obj.order_by = data["order_by"]
        if "detector" in data:
            obj.detector = data["detector"]
        if "count" in data:
            obj.count = int(data["count"])
        if "green_mask" in data:
            obj.green_mask = bool(data["green_mask"])
        return obj

    elif reco_type == "ColorMatch":
        if "lower" not in data or "upper" not in data:
            raise RecognitionError("ColorMatch requires 'lower' and 'upper' parameters.")
        obj = JColorMatch(lower=data["lower"], upper=data["upper"])
        if "roi" in data:
            obj.roi = tuple(data["roi"])
        if "order_by" in data:
            obj.order_by = data["order_by"]
        if "method" in data:
            obj.method = int(data["method"])
        if "count" in data:
            obj.count = int(data["count"])
        if "connected" in data:
            obj.connected = bool(data["connected"])
        return obj

    elif reco_type == "OCR":
        obj = JOCR()
        if "roi" in data:
            obj.roi = tuple(data["roi"])
        if "expected" in data:
            obj.expected = data["expected"]
        if "threshold" in data:
            obj.threshold = float(data["threshold"])
        if "order_by" in data:
            obj.order_by = data["order_by"]
        if "only_rec" in data:
            obj.only_rec = bool(data["only_rec"])
        if "model" in data:
            obj.model = data["model"]
        return obj

    raise RecognitionError(f"Unknown recognition type '{reco_type}'.")


# ── main entry point ─────────────────────────────────────────────

def recognize(
    controller: Controller,
    reco_type: str,
    params: dict[str, str] | None = None,
    raw: str | None = None,
) -> tuple[str, list]:
    """Run a recognition operation on the current screen.

    Parameters
    ----------
    controller:
        Connected MaaFW controller.
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
    tuple[str, list]
        ``(resolved_reco_type, results)`` where results is a list of
        recognition result objects (BoxAndScoreResult, BoxAndCountResult, or OCRResult).

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

        reco_enum = _RECO_TYPE_MAP[resolved_type]

        # OCR needs model files
        if reco_enum == JRecognitionType.OCR and not check_ocr_files_exist():
            raise RecognitionError("OCR model not found. Run: maafw-cli resource download-ocr")

        tasker = _get_tasker(controller)
        if tasker is None:
            raise RecognitionError("Failed to initialize tasker (resource load failed).")

        image = screencap(controller)
        if image is None:
            raise RecognitionError("Screenshot failed — cannot run recognition without an image.")

        with Timer(f"{resolved_type} inference", log=_log):
            info: TaskDetail | None = (
                tasker.post_recognition(reco_enum, params_obj, image).wait().get()
            )
        if not info:
            raise RecognitionError(f"{resolved_type} recognition returned no result.")

        if not info.nodes:
            _log.warning("%s returned empty nodes list", resolved_type)
            raise RecognitionError(f"{resolved_type} recognition returned empty nodes.")

        return resolved_type, info.nodes[0].recognition.all_results  # type: ignore[return-value]

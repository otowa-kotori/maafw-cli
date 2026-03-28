"""
Vision operations — screenshot + OCR via MaaFramework.

Functions that need a Resource or Tasker take a ``Session`` as
their first argument.  Resource and controller lifecycle is managed
by ``Session``.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import cv2
from maa.controller import Controller
from maa.define import OCRResult
from maa.tasker import TaskDetail
from maa.pipeline import JRecognitionType, JOCR

from maafw_cli.core.errors import RecognitionError
from maafw_cli.core.log import Timer
from maafw_cli.core.session import Session
from maafw_cli.download import check_ocr_files_exist

_log = logging.getLogger("maafw_cli.vision")


def screencap(controller: Controller) -> Any:
    """Take a screenshot and return the raw image (numpy array).

    Returns ``None`` on failure.
    """
    with Timer("screencap", log=_log):
        return controller.post_screencap().wait().get()


def screencap_to_file(controller: Controller, output: str | Path | None = None) -> Path | None:
    """Take a screenshot and save to *output* (or an auto-named file).

    Returns the path on success, ``None`` on failure.
    """
    image = screencap(controller)
    if image is None:
        return None

    if output is None:
        from datetime import datetime
        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output = Path(f"screenshot_{ts}.png")
    else:
        output = Path(output)

    output.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output), image):
        return None
    return output


def ocr(
    session: Session,
    roi: tuple[int, int, int, int] | None = None,
) -> list[OCRResult]:
    """Run OCR, optionally restricted to *roi* ``(x, y, w, h)``.

    Returns a list of ``OCRResult`` (with ``.text``, ``.box``, ``.score``).
    Raises :class:`RecognitionError` on failure with a message indicating the cause.
    """
    with Timer("total OCR pipeline", log=_log):
        if not check_ocr_files_exist():
            raise RecognitionError("OCR model not found. Run: maafw-cli resource download-ocr")

        tasker = session.get_tasker()
        if tasker is None:
            raise RecognitionError("Failed to initialize OCR tasker (resource load failed).")

        image = screencap(session.controller)
        if image is None:
            raise RecognitionError("Screenshot failed — cannot run OCR without an image.")

        ocr_params = JOCR()
        if roi is not None:
            ocr_params.roi = roi

        with Timer("OCR inference", log=_log):
            info: TaskDetail | None = (
                tasker.post_recognition(JRecognitionType.OCR, ocr_params, image).wait().get()
            )
        if not info:
            raise RecognitionError("OCR recognition returned no result.")

        if not info.nodes:
            _log.warning("OCR returned empty nodes list")
            raise RecognitionError("OCR recognition returned empty nodes.")

        return info.nodes[0].recognition.all_results  # type: ignore[return-value]

"""Custom callbacks for integration testing.

Contains a CustomRecognition and a CustomAction that work with the
pipeline mock window (Welcome -> Login -> Home flow).
"""
import json
import logging
from pathlib import Path

from maa.custom_recognition import CustomRecognition
from maa.custom_action import CustomAction

# File logger — daemon process may not show stdout
_log = logging.getLogger("mock_custom_callbacks")
_log_file = Path(__file__).parent / "custom_callback_debug.log"
_fh = logging.FileHandler(str(_log_file), mode="w", encoding="utf-8")
_fh.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
_log.addHandler(_fh)
_log.setLevel(logging.DEBUG)


class FindTextCustom(CustomRecognition):
    """Run OCR on the screenshot and match a specific text.

    Target text is passed via ``custom_recognition_param`` JSON:
    ``{"expected": "START"}``.

    Uses ``context.run_recognition()`` to call MaaFW's built-in OCR,
    so this truly exercises the custom callback mechanism.
    """

    name = "FindTextCustom"

    def analyze(self, context, argv):
        try:
            return self._do_analyze(context, argv)
        except Exception:
            _log.exception("FindTextCustom.analyze CRASHED")
            return None

    def _do_analyze(self, context, argv):
        raw_param = argv.custom_recognition_param
        _log.debug("FindTextCustom raw param: type=%s repr=%r", type(raw_param).__name__, raw_param)

        params = json.loads(raw_param) if raw_param else {}
        expected = params.get("expected", "")
        roi = list(argv.roi)
        _log.debug("FindTextCustom.analyze: expected=%r, roi=%s, image_shape=%s",
                    expected, roi, argv.image.shape if hasattr(argv.image, 'shape') else '?')

        # Run built-in OCR via context
        reco_detail = context.run_recognition(
            "___internal_ocr___",
            argv.image,
            {
                "___internal_ocr___": {
                    "recognition": "OCR",
                    "expected": expected,
                    "roi": roi,
                }
            },
        )

        if reco_detail is None:
            _log.debug("FindTextCustom.analyze: run_recognition returned None")
            return None

        _log.debug(
            "FindTextCustom.analyze: hit! box=%s best_result=%s",
            reco_detail.box, reco_detail.best_result,
        )

        return self.AnalyzeResult(
            box=reco_detail.box,
            detail={"custom": True, "expected": expected, "raw_detail": reco_detail.raw_detail},
        )


class ClickTargetCustom(CustomAction):
    """Click the center of the recognized box.

    Uses ``context.tasker.controller`` to perform the click,
    driving real state transitions in the mock window.
    """

    name = "ClickTargetCustom"

    def run(self, context, argv):
        x = argv.box[0] + argv.box[2] // 2
        y = argv.box[1] + argv.box[3] // 2
        _log.debug("ClickTargetCustom.run: box=%s -> click(%d, %d)", argv.box, x, y)
        context.tasker.controller.post_click(x, y).wait()
        return True


class InputTextCustom(CustomAction):
    """Type text received via ``custom_action_param``.

    Expects ``{"text": "some text"}`` in the param JSON.
    Exercises the ``custom_action_param`` path that ``ClickTargetCustom``
    does not cover.
    """

    name = "InputTextCustom"

    def run(self, context, argv):
        raw_param = argv.custom_action_param
        _log.debug("InputTextCustom raw param: type=%s repr=%r", type(raw_param).__name__, raw_param)

        params = json.loads(raw_param) if raw_param else {}
        text = params.get("text", "")
        _log.debug("InputTextCustom.run: typing %r", text)

        context.tasker.controller.post_input_text(text).wait()
        return True

# Custom Recognition & Custom Action

Load user Python scripts as pipeline callbacks. MaaFW calls your code directly via ctypes — zero IPC overhead at runtime.

## Pipeline protocol reference

- 中文: <https://maafw.com/docs/3.1-PipelineProtocol>
- English: <https://maafw.com/en/docs/3.1-PipelineProtocol>

## CLI commands

```bash
# Load a script — discovers CustomRecognition / CustomAction subclasses
maafw-cli --on game custom load ./my_customs.py

# Reload after editing the script
maafw-cli --on game custom load ./my_customs.py --reload

# List registered customs
maafw-cli --on game custom list

# Unregister by name
maafw-cli --on game custom unload FindRedButton --type recognition
maafw-cli --on game custom unload ClickAndWait --type action
maafw-cli --on game custom unload SharedName          # default: both

# Clear all
maafw-cli --on game custom clear
```

## Pipeline JSON — Custom nodes

Set `"recognition": "Custom"` or `"action": "Custom"` and provide the registered name:

### Custom Recognition fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `custom_recognition` | string | required | Registered name of the CustomRecognition |
| `custom_recognition_param` | any JSON | `{}` | Passed to callback as JSON string via `argv.custom_recognition_param` |

### Custom Action fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `custom_action` | string | required | Registered name of the CustomAction |
| `custom_action_param` | any JSON | `{}` | Passed to callback as JSON string via `argv.custom_action_param` |

### Example node

```json
{
  "MyNode": {
    "recognition": "Custom",
    "custom_recognition": "FindRedButton",
    "custom_recognition_param": {"expected": "PLAY", "threshold": 0.8},
    "action": "Custom",
    "custom_action": "ClickAndWait",
    "custom_action_param": {"delay_ms": 500},
    "next": ["NextNode"]
  }
}
```

> **Note on param serialization**: MaaFW serializes the param value to a JSON string before passing it to your callback. If you write `{"expected": "PLAY"}` (a JSON object) in the pipeline, your callback receives the string `'{"expected": "PLAY"}'`. Use `json.loads(argv.custom_recognition_param)` to get a dict.

Custom nodes also support all [common node fields](node-params.md) (`roi`, `timeout`, `next`, `pre_delay`, `post_delay`, etc.) and all standard action fields (`target`, `target_offset`) when mixed with builtin actions.

## Writing callback scripts

A callback script is a plain `.py` file. Define subclasses of `CustomRecognition` or `CustomAction` — `custom load` discovers and instantiates them automatically.

### CustomRecognition

```python
from maa.custom_recognition import CustomRecognition
import json

class FindRedButton(CustomRecognition):
    name = "FindRedButton"  # registered name (omit → class name)

    def analyze(self, context, argv):
        # argv fields:
        #   argv.task_detail      - TaskDetail: current task info
        #   argv.node_name        - str: current node name
        #   argv.custom_recognition_name - str: this recognizer's name
        #   argv.custom_recognition_param - str: JSON string from pipeline
        #   argv.image            - numpy.ndarray: BGR screenshot
        #   argv.roi              - Rect(x, y, w, h): region of interest

        params = json.loads(argv.custom_recognition_param) if argv.custom_recognition_param else {}
        expected = params.get("expected", "")

        # Use context to run builtin recognition
        reco = context.run_recognition(
            "___ocr___", argv.image,
            {"___ocr___": {"recognition": "OCR", "expected": expected, "roi": list(argv.roi)}},
        )
        if reco is None:
            return None

        # Return AnalyzeResult(box, detail) or None
        return self.AnalyzeResult(
            box=reco.box,            # Rect or [x,y,w,h] or None
            detail={"found": True},  # dict, recorded in recognition result
        )
```

**Return value**: `AnalyzeResult(box, detail)` on match, `None` on no match. `box` can also be a bare `Rect`/`[x,y,w,h]` for simpler cases.

### CustomAction

```python
from maa.custom_action import CustomAction
import json

class ClickAndWait(CustomAction):
    name = "ClickAndWait"

    def run(self, context, argv):
        # argv fields:
        #   argv.task_detail      - TaskDetail: current task info
        #   argv.node_name        - str: current node name
        #   argv.custom_action_name - str: this action's name
        #   argv.custom_action_param - str: JSON string from pipeline
        #   argv.reco_detail      - RecognitionDetail: preceding recognition result
        #   argv.box              - Rect(x, y, w, h): recognized box

        params = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        text = params.get("text", "")

        # Use context to interact with the device
        if text:
            context.tasker.controller.post_input_text(text).wait()
        else:
            x = argv.box[0] + argv.box[2] // 2
            y = argv.box[1] + argv.box[3] // 2
            context.tasker.controller.post_click(x, y).wait()

        return True  # success
```

**Return value**: `True` for success, `False` for failure.

### Context API

The `context` object provides access to the full MaaFW runtime:

| Method | Description |
|--------|-------------|
| `context.tasker` | Access the Tasker (and `.controller` for device I/O) |
| `context.run_recognition(name, image, pipeline)` | Run a builtin or custom recognition |
| `context.run_action(name, box, reco_detail, pipeline)` | Run a builtin or custom action |
| `context.run_task(name, pipeline)` | Run a full sub-task |
| `context.override_pipeline(pipeline)` | Override pipeline definitions at runtime |
| `context.override_next(name, next_list)` | Override a node's next list |
| `context.override_image(name, image)` | Inject a numpy image as template |
| `context.clone()` | Clone the context for parallel operations |

## Complete example

### 1. Write the script

```python
# my_customs.py
import json
from maa.custom_recognition import CustomRecognition
from maa.custom_action import CustomAction

class FindTextCustom(CustomRecognition):
    name = "FindTextCustom"

    def analyze(self, context, argv):
        params = json.loads(argv.custom_recognition_param) if argv.custom_recognition_param else {}
        expected = params.get("expected", "")
        reco = context.run_recognition(
            "___ocr___", argv.image,
            {"___ocr___": {"recognition": "OCR", "expected": expected, "roi": list(argv.roi)}},
        )
        if reco is None:
            return None
        return self.AnalyzeResult(box=reco.box, detail={"text": expected})

class InputTextCustom(CustomAction):
    name = "InputTextCustom"

    def run(self, context, argv):
        params = json.loads(argv.custom_action_param) if argv.custom_action_param else {}
        text = params.get("text", "")
        context.tasker.controller.post_input_text(text).wait()
        return True
```

### 2. Write the pipeline JSON

```json
{
  "FindAndType": {
    "recognition": "Custom",
    "custom_recognition": "FindTextCustom",
    "custom_recognition_param": {"expected": "Username"},
    "action": "Custom",
    "custom_action": "InputTextCustom",
    "custom_action_param": {"text": "admin"},
    "next": ["VerifyInput"]
  },
  "VerifyInput": {
    "recognition": "OCR",
    "expected": "admin",
    "action": "DoNothing"
  }
}
```

### 3. Run it

```bash
maafw-cli --on game custom load ./my_customs.py
maafw-cli --on game pipeline load ./my_pipeline/
maafw-cli --on game pipeline run ./my_pipeline/ FindAndType
```

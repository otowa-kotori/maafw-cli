# Node parameters reference

Shared by `reco` command and `pipeline` nodes. Full spec:
- 中文: <https://maafw.com/docs/3.1-PipelineProtocol>
- English: <https://maafw.com/en/docs/3.1-PipelineProtocol>

## Common fields (all node types)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `roi` | `[x,y,w,h]` \| string | `[0,0,0,0]` | Region of interest |
| `roi_offset` | `[x,y,w,h]` | `[0,0,0,0]` | Adjustment applied to ROI |
| `next` | list\<string\> | `[]` | Successor nodes (pipeline only) |
| `timeout` | uint | 20000 | Max wait time ms (pipeline only) |
| `pre_delay` | uint | 0 | Delay before action ms |
| `post_delay` | uint | 0 | Delay after action ms |
| `rate_limit` | uint | 1000 | Min interval between recognition attempts ms |
| `post_wait_freezes` | uint | 0 | After action, wait until screen freezes for this many ms; 0 = disabled. Default in MaaFW is 0, but combined with `rate_limit` may add implicit delay |
| `inverse` | bool | false | Match when NOT found |
| `order_by` | string | `Horizontal` | Result sorting: `Horizontal` / `Vertical` / `Score` / `Area` / `Random` |
| `index` | int | 0 | Which result to select |

---

## Recognition types

### TemplateMatch

Exact pixel matching. Template must be loaded via `resource load-image` first.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `template` | string \| list\<string\> | required | Image filename(s), relative to image folder |
| `threshold` | double \| list\<double\> | 0.7 | Matching confidence |
| `method` | int | 5 | `cv::TemplateMatchModes` |
| `green_mask` | bool | false | Treat pure green `(0,255,0)` as transparent |

### FeatureMatch

Scale/rotation-invariant matching via feature points.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `template` | string \| list\<string\> | required | Image filename(s) |
| `count` | uint | 4 | Min matching feature points |
| `detector` | string | `SIFT` | Feature detector: `SIFT` / `SURF` / `ORB` / `BRISK` / `KAZE` / `AKAZE` |
| `ratio` | double | 0.6 | KNN distance ratio (higher = more lenient) |
| `green_mask` | bool | false | Green area masking |

### ColorMatch

Find regions by pixel color range.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lower` | list\<int\> | required | Lower bound, e.g. `[200,0,0]` |
| `upper` | list\<int\> | required | Upper bound, e.g. `[255,50,50]` |
| `method` | int | 4 | Color space (`cv::ColorConversionCodes`); 4=RGB, 40=HSV |
| `count` | uint | 1 | Min matching pixels |
| `connected` | bool | false | Only count connected pixel regions |

### OCR

Text recognition with optional filtering.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `expected` | string \| list\<string\> | — | Expected text (regex). Omit to match all |
| `threshold` | double | 0.3 | Model confidence threshold |
| `replace` | list\<[pattern, replacement]\> | — | Text replacement before matching |
| `only_rec` | bool | false | Recognition without text detection (full ROI) |
| `model` | string | — | Custom OCR model folder |

### NeuralNetworkClassify

Fixed-position NN classification.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | string | required | ONNX model path |
| `expected` | int \| list\<int\> | required | Expected category index(es) |
| `labels` | list\<string\> | — | Category names (for debugging) |

### NeuralNetworkDetect

YOLOv8/v11 object detection.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | string | required | ONNX model path |
| `expected` | int \| list\<int\> | required | Target category index(es) |
| `threshold` | double \| list\<double\> | 0.3 | Confidence threshold |
| `labels` | list\<string\> | — | Category names (for debugging) |

### DirectHit

Always matches — no extra parameters beyond common fields.

---

## Action types

### Click

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `target` | true \| string \| `[x,y,w,h]` | true | Click position; `true` = recognized region center |
| `target_offset` | `[x,y,w,h]` | `[0,0,0,0]` | Offset added to target |

### LongPress

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `target` | true \| string \| `[x,y,w,h]` | true | Press position |
| `target_offset` | `[x,y,w,h]` | `[0,0,0,0]` | Position offset |
| `duration` | uint | 1000 | Press duration ms |

### Swipe

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `begin` | true \| string \| `[x,y,w,h]` | true | Start point; `true` = recognized region |
| `begin_offset` | `[x,y,w,h]` | `[0,0,0,0]` | Start offset |
| `end` | true \| string \| `[x,y,w,h]` | true | End point |
| `end_offset` | `[x,y,w,h]` | `[0,0,0,0]` | End offset |
| `duration` | uint | 200 | Swipe duration ms |

### Key

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `key` | int \| list\<int\> | required | Virtual key code(s) |

### InputText

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `input_text` | string | required | Text to type |

### StartApp / StopApp

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `package` | string | required | Package name or activity |

### DoNothing / StopTask

No parameters.

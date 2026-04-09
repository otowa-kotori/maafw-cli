# Recognition — reco command

For template matching, feature matching, and color matching beyond OCR.

## Load template images first

```bash
maafw-cli resource load-image ./templates/       # load directory
maafw-cli resource load-image ./button.png       # load single file
```

## Recognition types

### TemplateMatch (exact size match, high precision)

```bash
maafw-cli reco TemplateMatch template=button.png threshold=0.8
maafw-cli reco TemplateMatch template=button.png roi=0,200,960,400
```

### FeatureMatch (robust to scale/rotation/occlusion)

```bash
maafw-cli reco FeatureMatch template=icon.png
```

### ColorMatch (find regions by RGB range)

```bash
maafw-cli reco ColorMatch lower=200,0,0 upper=255,50,50
```

### OCR (with filters)

```bash
maafw-cli reco OCR expected=PLAY roi=0,0,400,200
```

## Raw JSON mode

Pass a full JSON recognition spec directly:

```bash
maafw-cli reco --raw '{"recognition":"TemplateMatch","template":["button.png"]}'
```

## CLI parameter passing

Use one of these two forms:

```bash
maafw-cli reco <Type> key=value key=value ...
maafw-cli reco --raw '{"recognition":"Type", ...}'
```

Rules:

- Each `key=value` must be a **separate shell argument**.
- If a value itself contains spaces or JSON, quote the **whole `key=value` token**.
- Prefer `--raw` when the parameter structure is nested or hard to express with flat `key=value` pairs.
- When `--raw` is provided, `<Type>` and `key=value` args are ignored.

### Custom recognition examples

```bash
# Flat key=value form
maafw-cli --on game reco Custom custom_recognition=FindTextCustom 'custom_recognition_param={"expected":"START"}'

# key=value form with spaces preserved inside JSON
maafw-cli --on game reco Custom custom_recognition=FindTextCustom 'custom_recognition_param={"expected": "START", "threshold": 0.8}'

# Raw JSON form (recommended for nested params)
maafw-cli --on game reco --raw '{"recognition":"Custom","custom_recognition":"FindTextCustom","custom_recognition_param":{"expected":"START","threshold":0.8}}'
```

`custom_recognition_param` can be any JSON value. CLI turns the JSON text into a structured value for MaaFW, and MaaFW then serializes it back to a JSON string before passing it to your callback (`argv.custom_recognition_param`). Inside the callback, use `json.loads(...)` to decode it.

## Parameters

Each recognition type accepts additional parameters (threshold, count, method, etc.).
Full parameter lists: [node-params.md](node-params.md)

## Results

Results produce Element refs (`e1`, `e2`, ...) just like OCR — use `click e1` to act on them.
Refs reset on every reco call.

Each `reco` call also auto-saves a screenshot; the path is printed at the end of the output (or in the `"screenshot"` JSON field).

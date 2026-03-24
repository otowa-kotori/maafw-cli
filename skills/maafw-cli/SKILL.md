---
name: maafw-cli
description: >
  Control Android (ADB) and Win32 devices via maafw-cli.
  Use when the user asks to interact with a device, emulator, or window:
  click, OCR, screenshot, swipe, type, key press, scroll.
argument-hint: "[action description]"
---

# maafw-cli Device Automation

You have `maafw-cli` to control Android and Win32 devices.

## Workflow

```
connect → ocr (see screen) → act → ocr (verify)
```

Always OCR before acting — never guess coordinates.

## Connect

```bash
maafw-cli connect adb 127.0.0.1:16384 --as phone
maafw-cli connect win32 "记事本" --as notepad
```

If you get "No active session", connect first.

## OCR — see the screen

```bash
maafw-cli ocr                          # human-readable, good for showing user
maafw-cli --json ocr                   # structured, good for parsing in scripts
maafw-cli --on phone ocr               # target specific session
maafw-cli ocr --roi 0,0,400,300        # region only
```

OCR results look like:
```
Screen OCR
────────────────────────────────────────
 e1   设置                 [ 120,  45,  80,  24]  97%
 e2   显示                 [ 120,  89,  72,  24]  95%
 e3   亮度                 [ 120, 133,  96,  24]  93%
```

Each `e1`, `e2`, `e3`... is a clickable reference. **Refs reset on every OCR call.**

## Actions

```bash
maafw-cli click e3                # click Element ref (preferred)
maafw-cli click 452,387           # click coordinates
maafw-cli swipe 100,800 100,200   # swipe (from, to)
maafw-cli swipe e1 e3             # swipe between refs
maafw-cli type "hello world"      # type text
maafw-cli key enter               # key: enter/back/home/esc/f1-f12/tab/space
maafw-cli scroll 0 -360           # scroll (dx, dy)
maafw-cli screenshot              # save to current directory
```

## Observe — act + sense in one step

```bash
maafw-cli --observe click e3      # clicks, then auto-OCR and shows result
```

## Multi-device

```bash
maafw-cli --on phone ocr
maafw-cli --on notepad click e1
maafw-cli session list            # see all sessions
```

## Rules

1. **OCR first** — never assume screen state or guess coordinates
2. **Use Element refs** — `click e3` not `click 120,45`; refs point to exact center
3. **Refs are ephemeral** — each OCR resets them; run OCR right before acting
4. **Verify** — OCR after actions to confirm effect
5. **Use `--json` only when you need to parse** — default human output is fine for display
6. **Show the user what you see** — when OCR results come back, summarize what's on screen

## Exit codes

0 = success, 1 = action failed, 2 = recognition failed (missing OCR model?), 3 = connection error

## First-time setup

```bash
maafw-cli resource download-ocr    # download OCR model (one-time)
```

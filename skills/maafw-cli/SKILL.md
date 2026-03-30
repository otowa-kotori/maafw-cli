---
name: maafw-cli
description: >
  Control Android (ADB) and Win32 devices via maafw-cli.
  Use when the user asks to interact with a device, emulator, or window:
  click, OCR, screenshot, swipe, type, key press, scroll, template match, color match.
argument-hint: "[action description]"
---

# maafw-cli Device Automation

You have `maafw-cli` to control Android and Win32 devices.

## Workflow

```
screenshot (perceive) -> decide approach -> act -> screenshot (verify)
```

Always screenshot first to perceive the screen, then decide whether to use OCR, reco, or coordinates.

## First-time setup

```bash
uvx maafw-cli --help              # run without install
maafw-cli resource download-ocr   # one-time OCR model download
```

## Discover & Connect

```bash
maafw-cli device adb               # list ADB devices
maafw-cli device win32 chrome      # filter Win32 windows by name
maafw-cli connect adb 127.0.0.1:16384
maafw-cli connect win32 "Notepad"
```

If "No active session" -> connect first. Single-device use doesn't need `--on`.

## Perceive

- **`screenshot`** — save screenshot to file, then show it to the user or view it yourself to understand the screen (general-purpose)
- **`ocr`** — extract text and get Element refs (`e1`, `e2`...); preferred when operating on text
- **`reco`** — template/feature/color matching; see [reco.md](reco.md)

```bash
maafw-cli screenshot                       # save screenshot
maafw-cli ocr                              # full-screen OCR
maafw-cli ocr --roi 0,0,400,300            # OCR a region
```

Reco or OCR returns refs like `e1`, `e2`, `e3` — use them for clicks. **Refs reset on every OCR/reco call.**

## Actions

```bash
maafw-cli click e3                # click Element ref (preferred)
maafw-cli click 452,387           # click coordinates
maafw-cli swipe 100,800 100,200   # swipe (from, to)
maafw-cli swipe e1 e3             # swipe between refs
maafw-cli type "hello world"      # type text
maafw-cli key enter               # key: enter/back/home/esc/f1-f12/tab/space
maafw-cli scroll 0 -360           # scroll (dx, dy) [Win32/PC only]
maafw-cli screenshot              # save to current directory
```

## Rules

1. **Screenshot first** — screenshot to perceive the screen before acting; never guess coordinates
2. **OCR for text** — when operating on text elements, use `ocr` to get Element refs, then `click e3`
3. **Refs are ephemeral** — each OCR/reco call resets refs; run it right before acting
4. **Verify** — screenshot after actions to confirm effect
5. **Show the user what you see** — summarize what's on screen when you perceive it

## More

- [reco.md](reco.md) — template, feature, color matching & raw JSON mode
- [pipeline.md](pipeline.md) — multi-node automation pipelines
- [node-params.md](node-params.md) — recognition & action parameter reference (shared by reco and pipeline)
- [advanced.md](advanced.md) — multi-device, REPL, daemon, `--size`, global options
- [troubleshooting.md](troubleshooting.md) — exit codes, platform notes, common issues
- MaaFramework Offcial Document (When you need more information for specialized usage): [中文](https://maafw.com/docs/1.1-QuickStarted) | [English](https://maafw.com/en/docs/1.1-QuickStarted)

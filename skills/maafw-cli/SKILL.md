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
connect → ocr (see screen) → act → ocr (verify)
```

Always OCR before acting — never guess coordinates.

## First-time setup

```bash
# Install (pick one)
uvx maafw-cli --help              # run directly without install
uv tool install maafw-cli         # install globally via uv
pip install maafw-cli             # or via pip

# Download OCR model (one-time)
maafw-cli resource download-ocr
```

## Discover devices

```bash
maafw-cli device adb               # show available ADB devices
maafw-cli device win32             # show available Win32 windows
maafw-cli device win32 chrome      # filter by name substring
```

Run this first if you don't know the device address or window title.

## Connect

```bash
maafw-cli connect adb 127.0.0.1:16384
maafw-cli connect win32 "记事本"
maafw-cli connect win32 0x1A2B3C
```

If you get "No active session", connect first. Single-device use doesn't need `--on`.

## OCR — see the screen

```bash
maafw-cli ocr                          # human-readable, good for showing user
maafw-cli --json ocr                   # structured, good for parsing in scripts
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
maafw-cli scroll 0 -360           # scroll (dx, dy) [Win32/PC only]
maafw-cli screenshot              # save to current directory
```

## Recognition — reco command

For template matching, feature matching, and color matching beyond OCR:

```bash
# Load template images first
maafw-cli resource load-image ./templates/       # load directory
maafw-cli resource load-image ./button.png       # load single file

# Template match (exact size match, high precision)
maafw-cli reco TemplateMatch template=button.png threshold=0.8

# Feature match (robust to scale/rotation/occlusion)
maafw-cli reco FeatureMatch template=icon.png

# Color match (find regions by RGB range)
maafw-cli reco ColorMatch lower=200,0,0 upper=255,50,50

# OCR with filters (same as ocr command)
maafw-cli reco OCR expected=设置 roi=0,0,400,200

# Raw JSON mode
maafw-cli reco --raw '{"recognition":"TemplateMatch","template":["button.png"]}'
```

Results produce Element refs (e1, e2, ...) just like OCR — use `click e1` to act on them.

## Multi-device (only when needed)

Use `--on NAME` to name sessions and switch between them. Not needed for single-device use.

```bash
# Name sessions when connecting
maafw-cli --on phone connect adb 127.0.0.1:16384
maafw-cli --on notepad connect win32 "记事本"

# Target a session (--on can go before or after the subcommand)
maafw-cli --on phone ocr
maafw-cli ocr --on phone            # equivalent — global options work at any position
maafw-cli session list               # see all sessions
maafw-cli session close phone        # close a session
```

## Global options

Global options (`--on`, `--json`, `--quiet`, `-v`) can be placed at **any position** in the command line:

```bash
maafw-cli --on game ocr              # before subcommand
maafw-cli ocr --on game              # after subcommand — same effect
maafw-cli --json ocr --on game       # mixed positions — also fine
```

## Screenshot resolution

Use `--size` when connecting to control screenshot resolution:

```bash
maafw-cli connect adb 127.0.0.1:16384 --size short:720     # short-side scaled to 720px (default)
maafw-cli connect win32 "记事本" --size short:720            # same default for win32
maafw-cli connect adb 127.0.0.1:16384 --size raw            # original resolution
maafw-cli connect adb 127.0.0.1:16384 --size long:1920      # long-side scaled to 1920px
```

## REPL — interactive mode

```bash
maafw-cli repl                    # interactive mode via daemon
maafw-cli repl --local            # in-process, no daemon needed
maafw> connect adb 127.0.0.1:16384
maafw> ocr
maafw> click e1
maafw> screenshot
maafw> quit
```

All CLI commands are available inside the REPL.

## Daemon management

```bash
maafw-cli daemon status            # check daemon status
maafw-cli daemon start             # start daemon
maafw-cli daemon stop              # stop daemon
maafw-cli daemon restart           # restart daemon
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

## Platform notes

- **swipe** works on both ADB and Win32; on Win32 it acts as a drag
- **scroll** is for Win32/PC only (uses WHEEL_DELTA); on ADB, use **swipe** to simulate scrolling
- **key** maps differ by platform: ADB sends Android keycodes, Win32 sends PC keys

## Troubleshooting

```bash
maafw-cli daemon status            # check daemon is running
maafw-cli resource status          # check OCR model is downloaded
```

- "No active session" → run `connect` first
- Exit code 2 (recognition failed) → run `resource download-ocr`
- Exit code 3 (connection error) → check device is on, run `device adb` or `device win32`
- Daemon not responding → `maafw-cli daemon stop` then retry (auto-restarts)

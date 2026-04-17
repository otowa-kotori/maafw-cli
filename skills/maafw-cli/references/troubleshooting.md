# Troubleshooting

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Action failed |
| 2 | Recognition failed (missing OCR model?) |
| 3 | Connection error |
| 4 | Version mismatch (CLI ≠ daemon, run `daemon restart`) |

## Platform notes

- **swipe** works on both ADB and Win32; on Win32 it acts as a drag
- **scroll** is for Win32/PC only (uses WHEEL_DELTA); on ADB, use **swipe** to simulate scrolling
- **key** maps differ by platform: ADB sends Android keycodes, Win32 sends PC keys

## Common issues

### Win32 input not working

If click / type / key has no effect on a Win32 window (action succeeds but nothing happens on screen), the **first thing to try** is reconnecting with `--input-method Seize`:

```bash
maafw-cli --on <session> connect win32 <hwnd-or-title> --input-method Seize
```

Seize takes exclusive control of the window's input, which is required for certain apps (e.g. games, tkinter windows, DirectX surfaces) that ignore standard Win32 `SendMessage` / `PostMessage` input. Trade-off: mouse control is seized during the session, so avoid moving the mouse while Seize is active.

If Seize still doesn't work, check:
- The window is in the foreground and not minimized
- The process is not running at a higher privilege level than the CLI

---

### "No active session"

Run `connect` first:

```bash
maafw-cli connect adb 127.0.0.1:16384
```

### Exit code 2 (recognition failed)

Download the OCR model:

```bash
maafw-cli resource download-ocr
maafw-cli resource status          # verify model is available
```

### Exit code 3 (connection error)

Check the device is on and reachable:

```bash
maafw-cli device adb               # list ADB devices
maafw-cli device win32             # list Win32 windows
```

### Daemon not responding

Stop and retry (it auto-restarts on next command):

```bash
maafw-cli daemon stop
maafw-cli daemon status            # check daemon status
```

### Exit code 4 (version mismatch)

CLI 更新后 daemon 仍在跑旧版本：

```bash
maafw-cli daemon restart           # 重启 daemon 以匹配新 CLI
```

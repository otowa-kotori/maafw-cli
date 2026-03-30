# Troubleshooting

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Action failed |
| 2 | Recognition failed (missing OCR model?) |
| 3 | Connection error |

## Platform notes

- **swipe** works on both ADB and Win32; on Win32 it acts as a drag
- **scroll** is for Win32/PC only (uses WHEEL_DELTA); on ADB, use **swipe** to simulate scrolling
- **key** maps differ by platform: ADB sends Android keycodes, Win32 sends PC keys

## Common issues

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

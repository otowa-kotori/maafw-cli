# Advanced usage

## Multi-device (`--on`)

Use `--on NAME` to name sessions and switch between them. Not needed for single-device use.

You can also set `MAAFW_SESSION=NAME` as an environment variable (CLI `--on` takes precedence).

```bash
# Name sessions when connecting
maafw-cli --on phone connect adb 127.0.0.1:16384
maafw-cli --on notepad connect win32 "Notepad"

# Target a session
maafw-cli --on phone ocr
maafw-cli --on notepad screenshot

# Session management
maafw-cli session list               # see all sessions
maafw-cli session default phone      # set default session
maafw-cli session close phone        # close a session
maafw-cli session close-all          # close all sessions
```

## Global options

Global options (`--on`, `--json`, `--quiet`, `-v`) can be placed at **any position** in the command line:

```bash
maafw-cli --on game ocr              # before subcommand
maafw-cli ocr --on game              # after subcommand — same effect
maafw-cli --json ocr --on game       # mixed positions — also fine
```

| Option | Description |
|--------|-------------|
| `--on SESSION` | Target a named session |
| `--json` | Strict JSON output |
| `--quiet` | Suppress non-error output |
| `--color` | Enable colored terminal output (off by default) |
| `-v` | DEBUG-level logging |

## Screenshot resolution (`--size`)

Use `--size` when connecting to control screenshot resolution:

```bash
maafw-cli connect adb 127.0.0.1:16384 --size short:720     # short-side scaled to 720px (default)
maafw-cli connect win32 "Notepad" --size short:720           # same default for win32
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
maafw-cli daemon restart           # restart daemon (required after CLI update)
```

> If you see exit code 4 (version mismatch), run `maafw-cli daemon restart` to align daemon with CLI.

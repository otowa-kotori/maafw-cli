# maafw-cli 工程结构

```
maafw-cli/
├── pyproject.toml
├── doc/
│   ├── SPEC.md              # 设计规格（愿景、架构决策、分阶段计划）
│   ├── USAGE.md             # 使用指南（命令参考、参数说明）
│   ├── ARCHITECTURE.md      # 本文件（工程结构、模块职责）
│   └── TODO.md              # 待办事项
├── src/maafw_cli/
│   ├── __init__.py          # 版本号 (0.1.0)
│   ├── __main__.py          # python -m 入口
│   ├── cli.py               # Click 根命令、全局选项、子命令注册
│   ├── paths.py             # 跨平台路径（MaaXYZ/maafw-cli）
│   ├── download.py          # OCR 模型下载
│   ├── commands/            # CLI 命令层（依赖 core/ 和 maafw/）
│   │   ├── device.py        # device list [--adb|--win32]
│   │   ├── connect.py       # connect adb|win32
│   │   ├── ocr.py           # ocr [--roi] [--text-only]
│   │   ├── screenshot.py    # screenshot [-o FILE]
│   │   └── click_cmd.py     # click TARGET
│   ├── core/                # 共享基础设施（不依赖 MaaFW）
│   │   ├── session.py       # SessionInfo 序列化 + 文件读写
│   │   ├── reconnect.py     # 从 session.json 重建 Controller
│   │   ├── textref.py       # TextRef 系统 (t1, t2, ...)
│   │   ├── target.py        # 目标解析 (t3 / 452,387)
│   │   ├── output.py        # OutputFormatter (human/json/quiet)
│   │   └── log.py           # 日志 + Timer 计时器
│   └── maafw/               # MaaFramework 薄封装（不依赖 CLI）
│       ├── adb.py           # ADB 设备发现 + 连接
│       ├── win32.py         # Win32 窗口发现 + 连接
│       ├── vision.py        # 截图 + OCR
│       └── control.py       # 点击（post_click）
└── tests/
    ├── test_cli.py           # CLI 结构测试（CliRunner，无需真实设备）
    ├── test_textref.py       # TextRef 单元测试
    ├── test_target.py        # 目标解析单元测试
    ├── test_adb_manual.py    # ADB 手动集成测试（pytest -m manual）
    ├── test_win32_manual.py  # Win32 手动集成测试（pytest -m manual）
    └── mock_win32_window.py  # Win32 测试用 tkinter mock 窗口
```

## 分层职责

```
commands/    →  CLI 参数解析、调用 core/ 和 maafw/、格式化输出
core/        →  会话管理、TextRef、目标解析、输出格式、日志
maafw/       →  MaaFramework API 封装（可独立于 CLI 使用）
```

- `commands/` 依赖 `core/` 和 `maafw/`
- `core/` 不依赖 `maafw/`（reconnect.py 除外，它桥接两层）
- `maafw/` 不依赖 `commands/`，仅依赖 `core/log.py`

## 数据流

```
connect → session.json
                ↓
ocr → reconnect → Controller → screencap → OCR → textrefs.json
                                                       ↓
click → parse_target(t3) → resolve from textrefs → reconnect → post_click
```

## 会话机制（Phase 1）

文件持久化，每条命令独立重连：
- `connect` 写 `session.json`（连接参数）
- `ocr` / `screenshot` / `click` 读 `session.json` → 重新发现设备 → 重建 Controller
- Win32 重连按窗口标题匹配（hwnd 不稳定）
- ADB 重连按设备名或地址匹配

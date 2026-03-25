# maafw-cli 工程结构

## 分层概览

```
src/maafw_cli/
├── cli.py               # Click 根命令 + 全局选项 + CliContext（daemon/direct 路由）
├── paths.py             # 跨平台路径（MaaXYZ/maafw-cli）
├── commands/            # CLI 薄壳：调用 services/，格式化输出
├── services/            # 纯业务逻辑：@service 注册到 DISPATCH table
├── core/                # 共享基础设施：IPC、会话、Element、日志、keymap
├── daemon/              # 后台守护进程：持久连接 + 命名会话 + JSON-line IPC
└── maafw/               # MaaFramework API 薄封装 + init_toolkit()
```

依赖方向：`commands/ → services/ → core/ + maafw/`，`daemon/ → services/ + core/`，禁止反向引用。

## 数据流

### 默认模式（daemon）

```
connect adb "..." ──→ ensure_daemon() ──→ daemon._connect_adb_inner()
                                              ↓
                                    SessionManager.add("device", controller)
                                              ↓
ocr / click / ... ──→ DaemonClient.send() ──→ daemon.execute(action, session)
                         (同步 socket)              ↓
                                    SessionManager.get(session).controller → MaaFW
```

### --no-daemon 模式

```
connect → session.json
                ↓
ocr → reconnect() → Controller → screencap → OCR → elements.json
                                                       ↓
click → parse_target(e3) → resolve from elements → reconnect() → post_click
```

## 会话机制

### Daemon 模式（默认）

- `connect` 自动启动 daemon，创建命名会话（`--as name` 或默认用设备地址）
- Controller 在 daemon 进程中持久存在，零重连开销
- 每个 session 有独立的 ElementStore（内存模式）和 asyncio Lock
- Idle watchdog：5 分钟无活动自动退出
- PID/port 文件：`~data_dir/daemon.pid`、`~data_dir/daemon.port`
- 日志：`~data_dir/daemon.log`（每次启动清空）

### --no-daemon 模式

文件持久化，每条命令独立重连：
- `connect` 写 `session.json`
- 后续命令读 `session.json` → 重新发现设备 → 重建 Controller

## IPC 架构

- **Server（daemon 端）**：asyncio TCP server，处理 JSON-line 请求
- **Client（CLI 端）**：同步 socket，发送请求等待响应，无 asyncio 依赖
- **端口**：默认 19799-19809 范围，实际端口写入 `daemon.port`
- **协议**：JSON-line（每条消息一行 JSON + `\n`）

---

## 完整目录树

```
maafw-cli/
├── pyproject.toml
├── AGENTS.md                      # AI agent 协作指南
├── doc/
│   ├── SPEC.md                    # 设计规格（愿景、架构决策）
│   ├── ARCHITECTURE.md            # 本文件
│   ├── USAGE.md                   # 命令参考
│   └── TODO.md                    # 待办事项
├── src/maafw_cli/
│   ├── __init__.py                # 版本号
│   ├── __main__.py                # python -m 入口
│   ├── cli.py                     # Click 根命令 + 全局选项 + CliContext.run()
│   ├── paths.py                   # 跨平台路径（MaaXYZ/maafw-cli）
│   ├── download.py                # OCR 模型下载
│   ├── commands/
│   │   ├── connection.py          # device adb/win32/all (with FILTER), connect adb/win32
│   │   ├── vision.py              # ocr, screenshot
│   │   ├── interaction.py         # click, swipe, scroll, type, key
│   │   ├── recognition.py         # reco (TemplateMatch/FeatureMatch/ColorMatch/OCR)
│   │   ├── resource.py            # resource download-ocr, resource status, resource load-image
│   │   ├── repl_cmd.py            # REPL 模式
│   │   ├── daemon_cmd.py          # daemon start/stop/status
│   │   └── session_cmd.py         # session list/default/close
│   ├── services/
│   │   ├── connection.py          # do_connect_adb/win32, do_device_list (with filter)
│   │   ├── vision.py              # do_ocr, do_screenshot
│   │   ├── interaction.py         # do_click, do_swipe, do_scroll, do_type, do_key
│   │   ├── recognition.py         # do_reco (通用感知服务)
│   │   ├── resource.py            # do_download_ocr, do_resource_status, do_load_image
│   │   ├── context.py             # ServiceContext (controller 缓存 + target 解析)
│   │   └── registry.py            # @service decorator + DISPATCH table
│   ├── core/
│   │   ├── errors.py              # MaafwError / ActionError / RecognitionError / DeviceConnectionError
│   │   ├── ipc.py                 # DaemonClient (同步 socket), ensure_daemon(), get_daemon_info()
│   │   ├── keymap.py              # VK_MAP / AK_MAP / resolve_keycode
│   │   ├── session.py             # SessionInfo + 文件持久化（--no-daemon 模式）
│   │   ├── reconnect.py           # reconnect() — 从 session.json 重建 Controller
│   │   ├── element.py             # Element 系统，支持内存模式
│   │   ├── target.py              # 目标解析 (e3 / 452,387)
│   │   ├── output.py              # OutputFormatter (human/json/quiet) + format_ocr_table/format_reco_table
│   │   └── log.py                 # 日志 + Timer
│   ├── daemon/
│   │   ├── __main__.py            # python -m maafw_cli.daemon 入口（auto-import services）
│   │   ├── protocol.py            # JSON-line IPC 协议
│   │   ├── server.py              # asyncio TCP server + idle watchdog
│   │   ├── session_mgr.py         # SessionManager（命名会话 + Controller 持久连接）
│   │   └── log.py                 # daemon 专用日志（RotatingFileHandler）
│   └── maafw/
│       ├── __init__.py            # init_toolkit() — MaaFW 全局初始化（幂等）
│       ├── adb.py                 # ADB 设备发现 + 连接
│       ├── win32.py               # Win32 窗口发现 + 连接
│       ├── vision.py              # 截图 + OCR + load_image/override_image（Resource 缓存）
│       ├── recognition.py         # 通用感知：TemplateMatch/FeatureMatch/ColorMatch/OCR
│       └── control.py             # click/swipe/scroll/type/key
└── tests/
    ├── conftest.py                # 共享 fixtures
    ├── mock_controller.py         # MockController
    ├── mock_win32_window.py       # tkinter mock 窗口（OCR/交互测试）
    ├── mock_reco_window.py        # tkinter mock 窗口（感知测试，含 fixture 图标）
    ├── fixtures/                  # 测试图片（icon_plus, icon_lenna 等）
    ├── test_cli.py                # CLI 结构 + help + keymap
    ├── test_cli_context.py        # CliContext 路由 + observe
    ├── test_services.py           # Service 层业务逻辑 + @service 装饰器
    ├── test_recognition.py        # 感知层 build_params + recognize pipeline
    ├── test_reconnect.py          # reconnect 重连逻辑（mock）
    ├── test_output.py             # OutputFormatter + format_ocr_table + format_reco_table
    ├── test_repl.py               # REPL dispatch
    ├── test_target.py             # 目标解析
    ├── test_element.py            # Element (含 count 字段 + build_from_results)
    ├── test_protocol.py           # IPC 协议
    ├── test_session_mgr.py        # SessionManager
    ├── test_daemon_server.py      # Daemon server (in-process)
    ├── test_ipc.py                # Client IPC + 进程生命周期
    ├── test_ipc_and_download.py   # get_daemon_info + download 逻辑
    ├── test_daemon_e2e.py         # Daemon E2E (manual)
    └── integration/               # 集成测试（需 mock window）
        ├── conftest.py            # mock_window + reco_window fixtures
        ├── test_win32_manual.py   # Win32 自动化集成测试
        └── test_reco.py           # reco 集成测试（OCR/Color/Template/Feature）
```

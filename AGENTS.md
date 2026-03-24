# AGENTS.md

## 项目定位

MaaFramework 命令行界面。让 Human / AI / Script / Cron 都能直接操作设备，不依赖 MCP server。

## 四层架构（严格分层）

```
commands/    CLI 薄壳：Click 参数声明 + 输出格式化。调用 services/。
services/    纯业务逻辑：入参简单类型，返回 dict，抛异常。不碰 Click / OutputFormatter / sys.exit。
core/        共享基础设施：会话、TextRef、目标解析、日志、keymap、错误类型。不依赖 maafw/（reconnect.py 例外）。
maafw/       MaaFramework API 薄封装。不依赖 commands/ 或 services/。
```

依赖方向：`commands/ → services/ → core/ + maafw/`，禁止反向引用。

## 目录布局

```
maafw-cli/
├── pyproject.toml
├── AGENTS.md                      # 本文件
├── doc/
│   ├── SPEC.md                    # 设计规格
│   ├── ARCHITECTURE.md            # 工程结构
│   ├── USAGE.md                   # 命令参考
│   └── TODO.md                    # 待办事项
├── src/maafw_cli/
│   ├── cli.py                     # Click 根命令 + 全局选项 + CliContext.run()
│   ├── commands/                  # CLI 薄壳（与 services/ 结构对齐）
│   │   ├── connection.py          # device list, connect adb/win32
│   │   ├── vision.py              # ocr, screenshot
│   │   ├── interaction.py         # click, swipe, scroll, type, key
│   │   ├── resource.py            # resource download-ocr, resource status
│   │   └── repl_cmd.py            # REPL 模式
│   ├── services/                  # 业务逻辑（与 commands/ 结构对齐）
│   │   ├── connection.py          # do_connect_adb, do_connect_win32, do_device_list
│   │   ├── vision.py              # do_ocr, do_screenshot
│   │   ├── interaction.py         # do_click, do_swipe, do_scroll, do_type, do_key
│   │   ├── resource.py            # do_download_ocr, do_resource_status
│   │   ├── context.py             # ServiceContext (controller 缓存 + target 解析)
│   │   └── registry.py            # @service decorator + DISPATCH table
│   ├── core/
│   │   ├── errors.py              # MaafwError / ActionError / RecognitionError / ConnectionError
│   │   ├── keymap.py              # VK_MAP / AK_MAP / resolve_keycode / method lists
│   │   ├── session.py             # SessionInfo + 文件持久化
│   │   ├── reconnect.py           # 从 session.json 重建 Controller
│   │   ├── textref.py             # TextRef 系统
│   │   ├── target.py              # 目标解析 (t3 / 452,387)
│   │   ├── output.py              # OutputFormatter (human/json/quiet)
│   │   └── log.py                 # 日志 + Timer
│   └── maafw/                     # MaaFW 封装
│       ├── adb.py                 # ADB 设备发现 + 连接
│       ├── win32.py               # Win32 窗口发现 + 连接
│       ├── vision.py              # 截图 + OCR
│       └── control.py             # click/swipe/scroll/type/key
└── tests/
    ├── conftest.py                # 共享 fixtures
    ├── mock_controller.py         # MockController (service 测试用)
    ├── mock_win32_window.py       # tkinter mock 窗口
    ├── test_cli.py                # CLI 结构 + help + keymap 测试
    ├── test_services.py           # Service 层业务逻辑测试
    ├── test_repl.py               # REPL dispatch 测试
    ├── test_target.py             # 目标解析测试
    ├── test_textref.py            # TextRef 测试
    ├── test_win32_manual.py       # Win32 自动化集成测试
    └── test_adb_manual.py         # ADB 集成测试（需真机，manual 标记）
```

## 关键设计模式

### Service 函数

每个 service 用 `@service` decorator 注册到 `DISPATCH` table：

```python
@service(human=lambda r: f"Clicked ({r['x']}, {r['y']})")
def do_click(ctx: ServiceContext, target: str) -> dict:
    resolved = ctx.resolve_target(target)
    ok = click(ctx.controller, resolved.x, resolved.y)
    if not ok:
        raise ActionError("Click failed.")
    return {"action": "click", "x": resolved.x, "y": resolved.y, ...}
```

- 入参：`ServiceContext` + 简单类型
- 返回：`dict`
- 错误：抛 `ActionError` / `RecognitionError` / `ConnectionError`
- 不碰 Click、fmt、sys.exit
- 同时被 CLI oneshot / REPL / 未来 daemon 复用

### Command 薄壳

```python
@click.command("click")
@click.argument("target")
@pass_ctx
def click_cmd(ctx: CliContext, target: str) -> None:
    ctx.run(do_click, target=target)
```

`ctx.run()` 统一处理：ServiceContext 构建 → 调用 service → 异常→退出码 → 输出 → --observe 追加 OCR。

### 三种运行模式

```
CLI oneshot:  ctx.run(do_click, ...) → reconnect 每次
REPL:         repl.execute_line("click t1") → controller 缓存复用
Daemon (未来): handler(do_click, ...) → 连接池
```

### 输出约定

- `--json`：stdout 输出严格 JSON
- `--quiet`：抑制非错误输出
- `--observe`：动作命令后自动追加 OCR
- stderr 放日志/进度，stdout 放数据
- 退出码：0=成功, 1=操作失败, 2=识别失败, 3=连接错误

## 工具链

- **包管理 / 运行**：`uv`（不用 pip / venv）
  ```bash
  uv sync                          # 安装依赖
  uv run pytest tests/ -v          # 跑测试
  uv run ruff check src/           # lint
  uv run maafw-cli --help          # 运行 CLI
  ```
- **搜索文件**：`fd`（替代 find）
- **搜索内容**：`rg`（ripgrep，替代 grep）
- **Lint**：`ruff`
- **测试**：`pytest`

## 测试策略

| 层级 | 文件 | 说明 | 默认运行 |
|------|------|------|---------|
| Unit | `test_cli.py`, `test_target.py`, `test_textref.py` | CLI 结构、keymap、解析 | ✅ |
| Service | `test_services.py` | MockController，纯业务逻辑 | ✅ |
| REPL | `test_repl.py` | dispatch、observe 切换 | ✅ |
| Win32 集成 | `test_win32_manual.py` | mock tkinter 窗口，OCR→交互→OCR 闭环 | ✅ (Windows) |
| ADB 集成 | `test_adb_manual.py` | 需真实设备 | ❌ manual |

## 新增功能 checklist

1. `maafw/` 层加底层函数（如需要）
2. `services/xxx.py` 加 `@service` 函数
3. `commands/xxx.py` 加 Click 薄壳，调用 `ctx.run()`
4. `cli.py` 注册命令
5. `tests/test_services.py` 加 service 测试
6. `tests/test_cli.py` 加 help 测试
7. `doc/USAGE.md` 补充命令参考
8. 验证：`uv run pytest tests/ -v` + `uv run ruff check src/`

## Commit 规范

格式：`<type>: <简短描述>`

- **type**：`feat`, `fix`, `refactor`, `docs`, `test`, `chore`
- 描述用英文，祈使语气，首字母小写，不加句号
- 不附加 Co-Authored-By 或 AI 署名
- 一次 commit 聚焦一个逻辑变更

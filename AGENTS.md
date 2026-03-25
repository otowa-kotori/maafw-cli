# AGENTS.md

## 项目定位

MaaFramework 命令行界面。让 Human / AI / Script / Cron 都能直接操作设备，不依赖 MCP server。

## 分层架构

```
commands/    CLI 薄壳：Click 参数 + 输出格式化，调用 services/
services/    纯业务逻辑：@service 注册，返回 dict，抛异常，不碰 Click/sys.exit
core/        共享基础设施：IPC、会话、Element、日志、keymap、错误类型
daemon/      后台守护进程：asyncio TCP server，持久连接，命名会话
maafw/       MaaFramework API 薄封装 + init_toolkit()
```

依赖方向：`commands/ → services/ → core/ + maafw/`，`daemon/ → services/ + core/`，禁止反向引用。

详细目录树见 [ARCHITECTURE.md](doc/ARCHITECTURE.md)。

## 关键模式

### @service 装饰器

```python
# needs_session=True（默认）：需要 ServiceContext，操作已连接的设备
@service(human=lambda r: f"Clicked ({r['x']}, {r['y']})")
def do_click(ctx: ServiceContext, target: str) -> dict:
    ...

# needs_session=False：全局操作，不需要设备连接
@service(name="device_list", needs_session=False)
def do_device_list(*, adb: bool = True, win32: bool = False) -> dict:
    ...
```

装饰器自动挂载 `fn.dispatch_key`、`fn.needs_session`、`fn.human_fmt`。

### Command 薄壳

```python
@click.command("click")
@click.argument("target")
@pass_ctx
def click_cmd(ctx: CliContext, target: str) -> None:
    ctx.run(do_click, target=target)
```

`ctx.run()` 根据 `needs_session` 自动分派：daemon IPC（默认）或 direct 直连（`--no-daemon`）。

### 错误类型

`ActionError`(1) / `RecognitionError`(2) / `DeviceConnectionError`(3)，括号内为退出码。

### 输出

stdout 放数据，stderr 放日志。`--json` 严格 JSON，`--quiet` 抑制非错误输出，`--observe` 动作后追加 OCR。

## 常用命令

```bash
uv sync                          # 安装依赖
uv run pytest tests/ -v          # 跑测试
uv run ruff check src/           # lint
uv run maafw-cli --help          # 运行 CLI
```

## 测试注意事项

- 集成测试（`test_win32_manual.py`、`test_daemon_e2e.py`）会自动启动 daemon。
- 测试结束后 fixture teardown 会 `daemon stop`，保证不留残留进程。
- 若手动中断测试导致 daemon 残留，先 `uv run maafw-cli daemon stop` 再重跑。

## 新增功能 checklist

1. `services/xxx.py` 加 `@service` 函数（不需要 session 时设 `needs_session=False`）
2. `commands/xxx.py` 加 Click 薄壳，调用 `ctx.run()`
3. `cli.py` 注册命令
4. 加测试，更新 `doc/USAGE.md`

## Commit 规范

`<type>: <简短描述>`（feat/fix/refactor/docs/test/chore），英文祈使语气，不加 AI 署名。

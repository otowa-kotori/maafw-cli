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

## CLI 快速开始

操作设备的完整流程：查找 → 连接 → 感知 → 操作。

### 1. 查找设备

```bash
maafw-cli device win32 记事本       # 按名字子串过滤 Win32 窗口
maafw-cli device win32 MaafwGame    # 过滤含 "MaafwGame" 的窗口
maafw-cli device adb 127            # 过滤含 "127" 的 ADB 设备
maafw-cli --json device win32 Game  # JSON 输出，方便脚本解析 hwnd
```

> **注意**：`device` 的 FILTER 参数是位置参数，不是 `--filter`。

### 2. 连接

```bash
maafw-cli connect win32 "记事本" --as notepad         # 按标题子串连接
maafw-cli connect win32 0x2217ae --as game            # 按 hwnd 连接
maafw-cli connect win32 0x2217ae --as game --input-method Seize  # tkinter 按钮需要 Seize
maafw-cli connect adb 127.0.0.1:16384 --as phone
```

### 3. 感知（OCR / 识别）

```bash
maafw-cli --on game ocr                               # 全屏 OCR
maafw-cli --on game ocr --roi 0,0,400,300             # ROI 内 OCR
maafw-cli --on game --json reco OCR expected=PLAY     # OCR 匹配特定文本
maafw-cli --on game reco TemplateMatch template=icon.png threshold=0.8  # 模板匹配
maafw-cli --on game reco TemplateMatch template=icon.png roi=0,200,960,400  # ROI 内模板匹配
```

### 4. 操作

```bash
maafw-cli --on game click e1                          # 点击 Element 引用
maafw-cli --on game click 452,387                     # 点击坐标
maafw-cli --on game type "hello"                      # 输入文本
maafw-cli --on game key enter                         # 按键
```

### 5. 资源 & Pipeline

```bash
maafw-cli resource load-image ./tests/fixtures/       # 加载模板图片目录
maafw-cli --on game resource load-image ./templates/  # 指定会话加载
maafw-cli --on game pipeline load ./pipeline/         # 加载 pipeline JSON
maafw-cli --on game pipeline list                     # 列出已加载节点
maafw-cli --on game pipeline show NodeName            # 查看节点定义
maafw-cli --on game pipeline validate ./pipeline/     # 验证 pipeline
maafw-cli --on game pipeline run ./pipeline/ EntryNode # 运行 pipeline
```

### 6. 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | 输出严格 JSON |
| `--on SESSION` | 指定目标会话 |
| `--observe` | 动作后自动 OCR |
| `--quiet` | 抑制非错误输出 |
| `-v` | DEBUG 日志 |

详细用法见 [USAGE.md](doc/USAGE.md)。

## 测试注意事项

- 单元测试：`uv run pytest tests/ --ignore=tests/integration -v`
- 集成测试：`uv run pytest tests/integration/ -v -s`（自动启动 mock 窗口，仅 Windows）
- 全部一起跑：`uv run pytest tests/ -v`（单元测试先跑，集成测试排最后）
- 集成测试结束后 fixture teardown 会 `daemon stop`，保证不留残留进程。
- 若手动中断测试导致 daemon 残留，先 `uv run maafw-cli daemon stop` 再重跑。

## CI 制品

- CI 产出 `test-report.xml` 和 `daemon.log` 作为 artifact 上传。
- 拉取到本地：`gh run download <RUN_ID> --dir .local/artifacts`
- `.local/` 已在 `.gitignore` 中，不会提交。

## 新增功能 checklist

1. `services/xxx.py` 加 `@service` 函数（不需要 session 时设 `needs_session=False`）
2. `commands/xxx.py` 加 Click 薄壳，调用 `ctx.run()`
3. `cli.py` 注册命令
4. 加测试，更新 `doc/USAGE.md`

## Commit 规范

`<type>: <简短描述>`（feat/fix/refactor/docs/test/chore），英文祈使语气，不加 AI 署名。

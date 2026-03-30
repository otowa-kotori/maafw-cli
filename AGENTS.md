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

`ctx.run()` 统一通过 daemon IPC 分派。

### 错误类型

`ActionError`(1) / `RecognitionError`(2) / `DeviceConnectionError`(3)，括号内为退出码。

### 输出

stdout 放数据，stderr 放日志。`--json` 严格 JSON，`--quiet` 抑制非错误输出。

## 常用命令

```bash
uv sync                          # 安装依赖
uv run pytest -v                 # 跑单元测试（默认跳过集成测试）
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
maafw-cli --on notepad connect win32 "记事本"                        # 按标题子串连接，命名为 notepad
maafw-cli --on game connect win32 0x2217ae                           # 按 hwnd 连接
maafw-cli --on game connect win32 0x2217ae --input-method Seize      # tkinter 按钮需要 Seize
maafw-cli --on phone connect adb 127.0.0.1:16384
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
| `--quiet` | 抑制非错误输出 |
| `-v` | DEBUG 日志 |

详细用法见 [USAGE.md](doc/USAGE.md)。

## 测试

### 单元测试

```bash
uv run pytest -v                 # 默认只跑单元测试
```

### 集成测试

集成测试需要 Windows 桌面环境（自动启动 mock 窗口），CI 上跳过。

```bash
# 跑全部（单元 + 集成）
uv run pytest -v -s

# 只跑集成测试
uv run pytest tests/integration/ -m integration -v -s

# 只跑某个模块
uv run pytest tests/integration/test_clicking_game.py -m integration -v -s
```

**注意事项**：
- 集成测试使用 `integration` marker，CI 通过 `-m "not integration"` 跳过
- 每个 mock 窗口的 fixture 是 module-scoped：模块结束后自动关闭 session 和杀进程
- Seize 输入法会抢鼠标，测试运行期间不要移动鼠标
- 若手动中断测试导致 daemon 残留，先 `uv run maafw-cli daemon stop` 再重跑

## CI

- CI 只跑单元测试（`-m "not integration"`），集成测试需要桌面环境无法在 CI 运行
- CI 产出 `test-report.xml` 和 `daemon.log` 作为 artifact 上传
- 拉取到本地：`gh run download <RUN_ID> --dir .local/artifacts`
- `.local/` 已在 `.gitignore` 中，不会提交

## 新增功能 checklist

1. `services/xxx.py` 加 `@service` 函数（不需要 session 时设 `needs_session=False`）
2. `commands/xxx.py` 加 Click 薄壳，调用 `ctx.run()`
3. `cli.py` 注册命令
4. 加测试，更新 `doc/USAGE.md`

## Commit 规范

`<type>: <简短描述>`（feat/fix/refactor/docs/test/chore），英文祈使语气，不加 AI 署名如 Coauthor by。

## 问题排查原则

1. **不逃避问题**——不加 retry/fallback/延长等待 来绕过，而是找到真正的根因
2. **控制变量**——每次只改一个因素，用对照组确认是哪个环节出了问题
3. **向下追溯**——CLI 正常？查 daemon。daemon 正常？查 vision.ocr()。vision.ocr() 正常？查 maafw 原生接口。直到定位到最小触发代码
4. **必现复现**——写出纯 API 级别的最小复现脚本，多轮跑确保不是偶发，才能确认根因、才能报上游
5. **记录归档**——排查过程和复现脚本放 `investigations/<日期>-<问题>/`（已 gitignore），留 README 记录根因和排查路径

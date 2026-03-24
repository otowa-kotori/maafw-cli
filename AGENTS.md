# AGENTS.md

## 项目定位

MaaFramework 命令行界面。让 Human / AI / Script / Cron 都能直接操作设备，不依赖 MCP server。

## 三层架构（严格分层）

```
commands/    CLI 参数解析、输出格式化。依赖 core/ 和 maafw/。
core/        会话管理、TextRef、目标解析、日志。不依赖 maafw/（reconnect.py 例外）。
maafw/       MaaFramework API 薄封装。不依赖 commands/，仅依赖 core/log.py。
```

添加新功能时**必须遵守依赖方向**：`commands/ → core/ + maafw/`，禁止反向引用。

## 目录布局

```
maafw-cli/
├── pyproject.toml            # 构建配置、pytest 标记
├── doc/
│   ├── SPEC.md               # 设计规格（愿景、架构决策、分阶段路线）
│   ├── ARCHITECTURE.md       # 工程结构、模块职责、数据流
│   ├── USAGE.md              # 用户使用指南、命令参考
│   └── TODO.md               # 待办事项
├── src/maafw_cli/
│   ├── cli.py                # Click 根命令 + 子命令注册
│   ├── commands/             # 每个命令一个文件（click_cmd.py, swipe_cmd.py, ...）
│   ├── core/                 # 共享基础设施（无 MaaFW 依赖）
│   └── maafw/                # MaaFW 封装（adb/win32/control/vision）
└── tests/
    ├── test_cli.py           # 单元测试（无设备）— 默认跑
    ├── test_textref.py       # 单元测试
    ├── test_target.py        # 单元测试
    ├── test_win32_manual.py  # Win32 集成测试（带 mock 窗口，自动化）
    ├── test_adb_manual.py    # ADB 集成测试（需真实设备）
    └── mock_win32_window.py  # tkinter mock 窗口，供 Win32 测试使用
```

## 关键设计模式

### 命令模板

每个命令文件遵循同一模式：

```python
@click.command("name")
@pass_ctx
def name_cmd(ctx: CliContext, ...) -> None:
    fmt = ctx.fmt
    # 1. 解析参数（如需要，加载 TextRefStore + parse_target）
    # 2. reconnect(fmt) 重建 Controller
    # 3. 调用 maafw/ 层执行操作
    # 4. fmt.error() 报错（自动 exit）或 fmt.success() 输出结果
```

### 会话机制

- `connect` 写 `session.json`，后续命令读取并重连
- 每条命令独立重连（无守护进程，Phase 1）
- Win32 按窗口标题子串匹配，ADB 按设备名/地址匹配

### 输出约定

- `--json`：stdout 输出严格 JSON
- `--quiet`：抑制非错误输出
- 默认：人类友好的格式化文本
- stderr 放日志/进度，stdout 放数据

### 退出码

0=成功, 1=操作失败, 2=识别失败, 3=连接错误

## 工具链

- **包管理 / 运行**：`uv`（不用 pip / venv）
  ```bash
  uv sync                          # 安装依赖
  uv run pytest tests/ -v          # 跑测试
  uv run ruff check src/           # lint
  uv run maafw-cli --help          # 运行 CLI
  ```
- **搜索文件**：`fd`（替代 find）
  ```bash
  fd "\.py$" src/                  # 找所有 Python 文件
  fd click_cmd                     # 找文件名含 click_cmd 的文件
  ```
- **搜索内容**：`rg`（ripgrep，替代 grep）
  ```bash
  rg "post_click" src/             # 搜代码
  rg "def swipe" --type py         # 按文件类型过滤
  ```
- **Lint**：`ruff`
- **测试**：`pytest`

## 测试策略

| 类型 | 文件 | 运行方式 | 说明 |
|------|------|----------|------|
| 单元测试 | `test_cli.py`, `test_textref.py`, `test_target.py` | `uv run pytest tests/ -v` | 无需设备，默认运行 |
| Win32 集成 | `test_win32_manual.py` | `uv run pytest tests/test_win32_manual.py -v -s -m manual` | 自动启动 tkinter mock 窗口，验证 OCR→交互→OCR 闭环 |
| ADB 集成 | `test_adb_manual.py` | `uv run pytest tests/test_adb_manual.py -v -s -m manual` | 需真实 ADB 设备/模拟器 |

- `pytest -m 'not manual'` 是默认配置（pyproject.toml），CI 安全
- Win32 测试已实现**自动化验证**：mock 窗口响应交互后改变 label，通过 OCR 检测变化

## 新增命令 checklist

1. `maafw/control.py` 加底层函数
2. `commands/xxx_cmd.py` 新建命令文件（参照模板）
3. `cli.py` 注册命令（import + `cli.add_command`）
4. `tests/test_cli.py` 加 help 测试
5. `tests/test_win32_manual.py` 加集成测试（如适用）
6. `doc/USAGE.md` 补充命令参考
7. 验证：`uv run pytest tests/ -v` + `uv run ruff check src/`

## Commit 规范

格式：`<type>: <简短描述>`

- **type**：`feat`, `fix`, `refactor`, `docs`, `test`, `chore`
- 描述用英文，祈使语气，首字母小写，不加句号
- 不附加 Co-Authored-By 或 AI 署名
- 一次 commit 聚焦一个逻辑变更

```
feat: add swipe/scroll/type/key interaction commands
fix: scroll negative args parsed as Click options
docs: update USAGE.md with key command platform mapping
test: promote Win32 tests to automated with mock window
refactor: extract dual keymap for ADB/Win32 key resolution
```

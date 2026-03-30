# `maafw-cli` 设计规格书（Spec）

> 独立 Python 包，MaaFramework 命令行界面。

## 1. 背景与动机

通过与MaaMCP不同的方式，将MaaFramework的功能暴露给命令行，供AI、用户和脚本使用。
让AI可以直接无需启动MCP服务器，使用skill调用MaaFramework的功能，从而解决将功能和MCP服务器耦合，MCP提示词占用大量AI上下文的问题。

```
今天:    AI → MCP Protocol → FastMCP Server → MaaFramework → 设备
目标:    Human | AI | Script | Cron → maafw-cli → MaaFramework → 设备
```

**maafw-cli 解决的问题**：
1. 无法在终端里直接截图、OCR、点击——必须启动 MCP server + AI 客户端
2. 不能 pipe、grep、组合——MCP tools 是不透明的函数调用，不是 Unix 公民
3. 运行 Pipeline 需要 AI 在场，没有 cron/CI 友好的方式
4. Controller ID 是不透明 UUID，无人类友好的会话管理

---

## 2. 设计原则

### 2.1 Element 系统

每次 OCR 结果赋予短引用 `e1`, `e2`, `e3`...，用户/AI 用引用而非裸坐标操作：

```bash
$ maafw-cli ocr
 e1  "设置"    [120, 45, 80, 24]   97%
 e2  "显示"    [120, 89, 72, 24]   95%
 e3  "亮度"    [120,133, 96, 24]   93%

$ maafw-cli click e2    # 点击"显示"——无需坐标
```

**目标寻址**三种方式：
- **引用**：`click e3`（快速，需先 OCR）
- **坐标**：`click 452,387`（精确）
- **文本搜索**：`click "text:设置"`（便捷，自动 OCR→查找→点击）

**Element 稳定性**：V1 每次 OCR 重置引用。未来可探索：若新旧 box 重叠面积大且文本相似，视为同一 ref。此问题留 TODO。

### 2.2 结构化输出优先

- `ocr` 返回可解析文本（默认人类友好，`--json` 机器友好）
- `screenshot` 是昂贵的备选

### 2.3 Unix 可组合性

- **stdout** 给数据，**stderr** 给进度/状态
- **退出码**有语义：0=成功, 1=动作失败, 2=识别失败, 3=连接错误
- `--json` 每个命令都支持
- `--quiet` 抑制非必要输出

### 2.4 命名会话

```bash
$ maafw-cli --on phone connect adb "emulator-5554"
$ maafw-cli --on phone ocr
$ maafw-cli --on notepad click e2
$ maafw-cli ocr          # 省略 --on → 使用默认（最近连接的）会话
```

**无自动连接**——必须显式 `connect`，因为无法猜测用户想连哪个设备。

### 2.5 渐进式复杂度

```bash
# Level 1: 显式连接 + 基本操作
$ maafw-cli connect adb "emulator-5554"
$ maafw-cli ocr
$ maafw-cli click e3

# Level 2: 命名会话 + 多设备
$ maafw-cli --on phone connect adb "emulator-5554"
$ maafw-cli --on notepad connect win32 "记事本"
$ maafw-cli --on phone ocr

# Level 3: Pipeline 自动化
$ maafw-cli pipeline run workflow.json --on phone

# Level 4: 脚本化
$ maafw-cli pipeline run workflow.json --on phone --json | process_results.py
```

### 2.6 AI 友好但非 AI 专属

- `--json` 可预测可解析
- Element 减少 AI 坐标幻觉
- 默认输出始终人类可读

---

## 3. 技术决策

| 决策项 | 选择 | 理由 |
|---|---|---|
| **包定位** | 独立包 `maafw-cli` | 与 maa-mcp 解耦，不同依赖 profile |
| **CLI 框架** | `click` | 成熟稳定，子命令优雅，CliRunner 测试友好，自定义参数类型灵活（Element 解析需要） |
| **会话架构** | 按需守护进程 | 首次 CLI 调用自动启动 daemon，手动停止。跨平台 IPC 方案需专项调研 |
| **serve 功能** | 不做 | 不保留 MCP 兼容，专注 CLI |
| **自动连接** | 不做 | 用户必须显式 connect |
| **Python 版本** | 3.10+ | 与 MaaFramework Python 绑定一致 |
| **核心依赖** | `maafw>=5.2.6`, `click`, `opencv-python`, `platformdirs` | 最小依赖集 |

---

## 4. 命令层级（完整规划）

> 已实现的命令标 ✅，其余为规划中。
> 实际参数以 `maafw-cli <cmd> --help` 和 [USAGE.md](USAGE.md) 为准。

```
maafw-cli
├── device                           # 设备发现
│   ├── adb [FILTER]                 ✅
│   ├── win32 [FILTER]               ✅
│   └── all [FILTER]                 ✅
│
├── connect                          # 连接
│   ├── adb <device>                 ✅ [--screenshot-size]
│   └── win32 <window>               ✅ [--screencap-method] [--input-method]
│
├── ocr                              ✅ [--roi] [--text-only]
├── reco <type> [params...]          ✅ [--raw] (TemplateMatch/FeatureMatch/ColorMatch/OCR)
├── screenshot                       ✅ [--output]
├── click <target>                   ✅ (e引用 / x,y坐标)
│
├── session list/default/close       ✅ (命名会话)
├── reco <type> [params...]          ✅ (原生感知)
├── swipe / scroll / type / key      ✅ (交互命令)
├── pipeline run/validate            （Phase 4: 工作流）
├── resource download-ocr/status/load-image  ✅
└── daemon start/stop/status         ✅ (守护进程)
```

### 4.1 `reco` 命令详解（✅ 已实现）

`reco` 暴露 MaaFramework 的原生感知接口，比 `ocr` 更底层、更灵活。

**支持的识别类型**：

| 类型 | 必填参数 | 说明 |
|------|---------|------|
| TemplateMatch | `template` | 模板匹配（尺寸敏感） |
| FeatureMatch | `template` | 特征匹配（缩放/旋转鲁棒） |
| ColorMatch | `lower`, `upper` | 颜色范围匹配 |
| OCR | (无必填) | 等同 `ocr` 命令 |

**主要形式**——结构化参数：
```bash
# 模板匹配
$ maafw-cli reco TemplateMatch template=button.png roi=0,0,400,200 threshold=0.8

# 特征匹配（对缩放/旋转鲁棒）
$ maafw-cli reco FeatureMatch template=icon.png

# 颜色匹配
$ maafw-cli reco ColorMatch lower=200,0,0 upper=255,50,50 roi=100,100,300,300

# OCR 识别特定文本
$ maafw-cli reco OCR expected=设置 roi=0,0,400,200
```

**备选形式**——原始 JSON（高级/AI 场景）：
```bash
$ maafw-cli reco --raw '{"recognition": "TemplateMatch", "template": ["button.png"], "threshold": 0.8}'
```

**模板图片加载**：TemplateMatch / FeatureMatch 需要先将模板图片加载到 Resource：
```bash
$ maafw-cli resource load-image ./templates/    # 加载目录下所有图片
$ maafw-cli reco TemplateMatch template=button.png
```

**Element 系统**：所有 `reco` 结果和 `ocr` 一样赋予 Element 引用（e1, e2, ...），可直接 `click e1`。

`ocr` 是 `reco OCR` 的全屏快捷方式，返回所有结果并赋予 Element。

---

## 5. 输出模式

每个命令支持三种输出模式：

| 标志 | 模式 | 受众 | 格式 |
|---|---|---|---|
| *(默认)* | Human | 终端用户 | 格式化、对齐、彩色 |
| `--json` | Machine | AI agent、脚本 | 严格 JSON 到 stdout |
| `--quiet` | Minimal | 只关心退出码 | 抑制除错误外所有输出 |

**ocr 输出示例**：

Human 模式：
```
Screen OCR — phone (emulator-5554)
──────────────────────────────────────
 e1  设置          [120, 45, 80, 24]    97%
 e2  显示          [120, 89, 72, 24]    95%
 e3  亮度          [120,133, 96, 24]    93%
──────────────────────────────────────
3 results | 287ms
```

JSON 模式：
```json
{
  "session": "phone",
  "results": [
    {"ref": "e1", "text": "设置", "box": [120, 45, 80, 24], "score": 0.97},
    {"ref": "e2", "text": "显示", "box": [120, 89, 72, 24], "score": 0.95},
    {"ref": "e3", "text": "亮度", "box": [120, 133, 96, 24], "score": 0.93}
  ],
  "elapsed_ms": 287
}
```

---

## 6. 会话管理架构：按需守护进程

```
┌─────────────────┐        ┌──────────────────────────┐
│  maafw-cli ocr  │──IPC──▶│  maafw-daemon (长存)      │
│  (thin client)  │◀───────│  ├─ Session "phone"       │──▶ ADB Device
└─────────────────┘        │  │  ├─ Controller          │
                           │  │  ├─ Resource            │
┌─────────────────┐        │  │  └─ ElementStore        │
│  maafw-cli ...  │──IPC──▶│  └─ Session "notepad"     │──▶ Win32 Window
│  (另一终端)      │◀───────│     ├─ Controller          │
└─────────────────┘        │     ├─ Resource            │
                           │     └─ ElementStore        │
                           └──────────────────────────┘
```

**生命周期**：
1. `maafw-cli connect ...` → 检测 daemon 是否运行 → 未运行则自动启动
2. CLI 命令通过 IPC 发送请求到 daemon
3. `maafw-cli daemon stop` 手动停止

### 6.1 IPC 方案：localhost TCP

**选型结论**（调研对比后）：

| 方案 | 优点 | 缺点 |
|---|---|---|
| **localhost TCP** ✅ | 跨平台零差异，可用 nc/curl 调试 | 需管理端口 |
| `multiprocessing.Listener` | stdlib 无依赖 | Windows Named Pipe 文档差，调试困难 |
| Unix socket + Named Pipe | 性能最优 | 需两套代码路径，Windows pipe 诡异 |
| gRPC | 功能丰富 | 依赖重，protobuf 学习曲线 |

**实现**：
- **Server（daemon 端）**：asyncio TCP server，并发处理多客户端
- **Client（CLI 端）**：同步 socket（`socket.create_connection`），无 asyncio 依赖，兼容所有环境（Jupyter、pytest 等）

**端口管理**：
- 默认端口 `19799`，可配置
- 端口冲突时自动尝试 `19799-19810` 范围
- 实际使用的端口写入 `platformdirs("maafw-cli", "MaaXYZ")/daemon.port`
- 安全：仅绑定 `127.0.0.1`

**通信协议**：JSON 行协议（每条消息一行 JSON + `\n`）
```
→ {"action": "ocr", "session": "phone", "params": {...}}
← {"ok": true, "data": {"results": [...], "elapsed_ms": 287}}
```

### 6.2 守护进程生命周期

**启动**（CLI thin client 端）：
```python
def ensure_daemon():
    pidfile = ~/.maafw/daemon.pid
    portfile = ~/.maafw/daemon.port

    # 1. 检查 PID 文件 → 进程是否存活 → 端口是否可连
    if pidfile.exists() and is_alive(pid) and can_connect(port):
        return port

    # 2. 清理残留，启动新 daemon
    cleanup_stale_files()
    subprocess.Popen(
        [sys.executable, "-m", "maafw_cli.daemon"],
        # Windows: creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        # Unix: start_new_session=True
        stdout=DEVNULL, stderr=DEVNULL
    )

    # 3. 轮询等待就绪（最多 5s）
    wait_for_pidfile_and_port()
```

**存活检测**（跨平台）：
- Unix: `os.kill(pid, 0)` — signal 0 不杀进程，仅检查是否存在
- Windows: `ctypes.windll.kernel32.OpenProcess()` 或 `psutil.pid_exists()`（如果有 psutil 依赖）
- 备选：直接尝试 TCP 连接，失败即视为不存活

**崩溃恢复**：

| 故障 | 检测方式 | 恢复 |
|---|---|---|
| daemon 崩溃 | PID 存在但进程死亡 | 删除残留文件，重新启动 |
| 端口被占用 | `Address already in use` | 尝试下一个端口 |
| PID 文件残留 | 启动时检查 | 验证进程存活，不存活则清理 |
| 客户端连接超时 | TCP connect timeout | 假设 daemon 死亡，尝试重启 |

### 6.3 调试支持

- daemon 日志输出到 `~/.maafw/daemon.log`
- `maafw-cli daemon status` 显示 PID、端口、连接数、uptime、会话列表

### 6.4 预估代码量（历史参考，已超出）

| 组件 | 行数 |
|---|---|
| Thin client IPC 层（ensure_daemon, send_command） | ~100 |
| Daemon 核心（asyncio server, 命令路由） | ~200 |
| PID/端口管理 + 崩溃恢复 | ~60 |
| 跨平台进程启动 | ~30 |
| **合计** | **~400 LOC** |

---

## 7. 实现分阶段计划

### Phase 0：守护进程 IPC 调研 ✅ 已完成

结论：**localhost TCP**（server 用 asyncio，client 用同步 socket），详见第 6 节。约 400 行代码，Phase 3 实现。

### Phase 1：最小可验证核心 ✅ 已完成（已被 daemon 模式取代）

**目标**：能跑通 `connect → ocr → click` 链路，端到端可测试。

**会话方案（无 daemon）**：状态文件重连（已移除，统一走 daemon）
- `connect` 将连接参数写入 `~/.maafw/session.json`（设备类型、ADB 地址等）
- `ocr` 读取 session.json → 重新建立 MaaFW 连接 → 执行 OCR → 将 Element 写入 `~/.maafw/elements.json`
- `click e2` 读取 session.json + elements.json → 重连 → 执行点击
- ADB 重连开销约 ~200ms，可接受
- Phase 3 上 daemon 后此层被替换，CLI 命令接口不变

**session.json 示例**：
```json
{
  "type": "adb",
  "device": "emulator-5554",
  "adb_path": "/usr/bin/adb",
  "address": "127.0.0.1:5554"
}
```

**elements.json 示例**：
```json
{
  "timestamp": "2026-03-23T10:30:00",
  "refs": [
    {"ref": "e1", "text": "设置", "box": [120, 45, 80, 24], "score": 0.97},
    {"ref": "e2", "text": "显示", "box": [120, 89, 72, 24], "score": 0.95}
  ]
}
```

**已实现范围**：
- 项目脚手架（pyproject.toml, click 骨架, 入口点）
- `device adb` — 扫描 ADB 设备
- `connect adb <device>` — 连接设备，写 session.json
- `ocr` — 重连 + 截图 + OCR，输出 Element 列表，写 elements.json
- `screenshot` — 重连 + 截图保存到文件
- `click <target>` — 支持 e引用 和 x,y 坐标
- `--json` 和 `--quiet` 全局选项
- 基础退出码
- 28 个单元测试全部通过

**验证**：
```bash
$ maafw-cli device adb
$ maafw-cli connect adb "emulator-5554"
$ maafw-cli ocr
$ maafw-cli ocr --json
$ maafw-cli click e1
$ maafw-cli click 200,300
$ maafw-cli screenshot --output test.png
```

### Phase 2：交互命令扩展 ✅ 已完成

- ~~`dblclick`,~~ `swipe`, `scroll`, `type`, `key` ~~, `shortcut`~~
- ~~`text:` 目标寻址（自动 OCR + 查找 + 点击）~~
- `reco` 命令（MaaFW 原生感知接口：TemplateMatch / FeatureMatch / ColorMatch / OCR）
- `resource load-image` 命令（加载图片模板到 Resource）
- `device` 命令支持名字过滤（`device win32 chrome`）
- ~~Win32 支持：`device win32`, `connect win32`~~ ✅ 已实现
- daemon 自动发现 service 模块（pkgutil 扫描，无需显式 import）
- 完善错误信息和帮助文档

#### Win32 窗口支持（✅ 已实现）

**新增文件**：`maafw/win32.py`
**修改文件**：`commands/device.py`, `commands/connect.py`, `core/session.py`, `core/reconnect.py`, `core/log.py`, `maafw/control.py`

**命令**：
```bash
# 列出有标题的 Win32 窗口
$ maafw-cli device win32
Win32 windows (5):
  0x000A0B2C  原神                     UnityWndClass
  0x001204FA  Visual Studio Code       Chrome_WidgetWin_1

# 按标题子串连接（大小写不敏感）
$ maafw-cli connect win32 "记事本"

# 按窗口句柄精确连接
$ maafw-cli connect win32 0x000A0B2C

# 指定截图和输入方式
$ maafw-cli connect win32 "游戏" --screencap-method FramePool --input-method Seize
```

**截图方式**（`--screencap-method`，默认 `FramePool`）：

| 方式 | 速度 | 后台支持 | 备注 |
|------|------|---------|------|
| GDI | 快 | ❌ | |
| **FramePool** ✅ | 非常快 | ✅ | 需 Win10 1903+，推荐 |
| DXGI_DesktopDup | 非常快 | ❌ | 全屏桌面复制 |
| DXGI_DesktopDup_Window | 非常快 | ❌ | 桌面复制后裁剪到窗口 |
| PrintWindow | 中 | ✅ | 兼容性较好 |
| ScreenDC | 快 | ❌ | 兼容性最高 |

**输入方式**（`--input-method`，默认 `PostMessage`）：

| 方式 | 抢鼠标 | 后台 | 兼容性 | 备注 |
|------|--------|------|--------|------|
| Seize | ✅ 持续 | ❌ | 最高 | UWP/所有窗口均有效 |
| SendMessage | ❌ | ✅ | 中 | 部分窗口（UWP、tkinter 等）无效 |
| **PostMessage** ✅ | ❌ | ✅ | 中 | 同 SendMessage，异步投递 |
| SendMessageWithCursorPos | 短暂 | ✅ | 中 | 短暂移光标后恢复 |
| PostMessageWithCursorPos | 短暂 | ✅ | 中 | 同上，异步 |
| SendMessageWithWindowPos | ❌ | ✅ | 中 | 移窗口到光标位置后恢复 |
| PostMessageWithWindowPos | ❌ | ✅ | 中 | 同上，异步 |

> **选择建议**：
> - 纯截图/OCR（不需要点击）：默认即可
> - 需要点击传统 Win32 应用（模拟器、游戏客户端）：`PostMessage` 或 `SendMessage` 通常有效
> - 需要点击 UWP 应用（计算器、设置等）：必须用 `Seize`
> - 自动化时不想被干扰：优先 `PostMessage`；若无效，退而求其次用 `SendMessageWithCursorPos`（短暂移光标）；最后选 `Seize`

**重连策略**：使用保存的 HWND 直接重连。HWND 在窗口生命周期内稳定，无需按标题重新搜索。

**session.json 示例**：
```json
{
  "type": "win32",
  "device": "记事本",
  "address": "0x000A0B2C",
  "screencap_methods": 2,
  "input_methods": 4,
  "window_name": "记事本"
}
```

**其它改动**：
- `click` 命令改用 `Controller.post_click()`（原 `post_touch_down/up` 对 Win32 SendMessage 系列无效）
- `setup_logging()` 每次清理旧 handler，修复 CliRunner 多次调用后日志写入已关闭流的问题

### Phase 3：守护进程 + 多会话 ✅ 已完成

- 守护进程实现（基于 Phase 0 调研结论）
- 命名会话 `--on <name>` (connect 时命名 + 操作时指定)
- `session list/default/close`
- `daemon start/stop/status`
- `--no-daemon` 调试模式（已移除，所有操作统一走 daemon）
- Element 缓存跨命令持久（daemon 内存中）

### Phase 4：Pipeline + 资源管理

- `pipeline run/validate/show/list`
- `resource download-ocr/status`
- Pipeline 执行结果的结构化输出

### 未来考虑（不在当前 scope）

- Element 跨 OCR 稳定性（box 重叠 + 文本相似性）
- `pipeline record`（交互式录制）
- Shell 补全（click 内置支持）
- 彩色 human 输出（Rich 库）

---

## 8. 相关文档

- [USAGE.md](USAGE.md) — 命令参考与使用指南
- [ARCHITECTURE.md](ARCHITECTURE.md) — 工程结构与模块职责
- [TODO.md](TODO.md) — 待办事项

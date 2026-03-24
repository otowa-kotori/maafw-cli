# maafw-cli 使用指南

## 安装

```bash
cd maafw-cli
uv sync
```

## 快速开始

```bash
# 1. 连接设备
maafw-cli connect adb emulator-5554           # Android 模拟器
maafw-cli connect win32 "记事本"               # Win32 窗口

# 2. 截图 / OCR / 点击
maafw-cli screenshot                           # 截图保存到文件
maafw-cli ocr                                  # OCR，输出带 TextRef
maafw-cli click t3                             # 按引用点击
maafw-cli click 452,387                        # 按坐标点击
```

## 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | 输出严格 JSON 到 stdout |
| `--quiet` | 抑制非错误输出 |
| `-v` / `--verbose` | 显示 DEBUG 级别日志（含耗时） |
| `--observe` | 动作命令执行后自动 OCR，输出识别结果 |

## 命令参考

### `device list`

列出可用设备。

```bash
maafw-cli device list              # 默认 --adb
maafw-cli device list --adb        # ADB 设备
maafw-cli device list --win32      # Win32 窗口
```

### `connect adb <DEVICE>`

连接 ADB 设备。DEVICE 是 `device list` 输出的设备名或地址。

| 选项 | 默认 | 说明 |
|------|------|------|
| `--screenshot-size` | 720 | 截图短边分辨率 |

### `connect win32 <WINDOW>`

连接 Win32 窗口。WINDOW 是窗口标题子串（大小写不敏感）或 `0x` 开头的 hwnd。

| 选项 | 默认 | 说明 |
|------|------|------|
| `--screencap-method` | FramePool | 截图方式 |
| `--input-method` | PostMessage | 输入方式 |

**截图方式**：

| 方式 | 速度 | 后台 | 备注 |
|------|------|------|------|
| **FramePool** | 非常快 | ✅ | Win10 1903+，推荐默认 |
| GDI | 快 | ❌ | |
| DXGI_DesktopDup | 非常快 | ❌ | 截全屏 |
| DXGI_DesktopDup_Window | 非常快 | ❌ | 全屏后裁剪 |
| PrintWindow | 中 | ✅ | 兼容性好 |
| ScreenDC | 快 | ❌ | 兼容性最高 |

**输入方式**：

| 方式 | 抢鼠标 | 后台 | 适用场景 |
|------|--------|------|----------|
| **PostMessage** | ❌ | ✅ | 默认，传统 Win32 应用 |
| SendMessage | ❌ | ✅ | 同上，同步版 |
| Seize | ✅ 持续 | ❌ | UWP 等对消息无响应的窗口 |
| SendMessageWithCursorPos | 短暂 | ✅ | 折中：短暂移光标 |
| PostMessageWithCursorPos | 短暂 | ✅ | 同上，异步 |
| SendMessageWithWindowPos | ❌ | ✅ | 移窗口到光标位置 |
| PostMessageWithWindowPos | ❌ | ✅ | 同上，异步 |

> **选择建议**：纯截图/OCR 用默认即可。需要点击时，先试 PostMessage；若无效试 Seize。UWP 应用必须 Seize。

### `ocr`

对连接的设备/窗口执行全屏 OCR。结果赋予 TextRef（t1, t2, ...），可供 `click` 使用。

| 选项 | 说明 |
|------|------|
| `--roi x,y,w,h` | 限定识别区域 |
| `--text-only` | 仅输出识别文本，不含表格格式 |

```bash
maafw-cli ocr                         # 全屏 OCR
maafw-cli ocr --roi 0,0,400,300       # 只识别左上角区域
```

### `screenshot`

截图保存到文件。

| 选项 | 说明 |
|------|------|
| `-o` / `--output` | 输出路径，省略则自动命名 |

### `click <TARGET>`

点击目标。TARGET 支持：
- TextRef：`t3`（需先运行 ocr）
- 坐标：`452,387`

### `swipe <FROM> <TO>`

从 FROM 滑动到 TO。FROM/TO 支持 TextRef 或坐标。

| 选项 | 默认 | 说明 |
|------|------|------|
| `--duration` | 300 | 滑动持续时间（毫秒） |

```bash
maafw-cli swipe 100,800 100,200              # 从下往上滑
maafw-cli swipe 100,800 100,200 --duration 500
maafw-cli swipe t1 t3                         # 从 TextRef t1 滑到 t3
```

### `scroll <DX> <DY>`

滚动操作。建议使用 120 的整数倍（WHEEL_DELTA）。正 DY 向上滚，负 DY 向下滚。

```bash
maafw-cli scroll 0 -360    # 向下滚 3 格
maafw-cli scroll 0 360     # 向上滚 3 格
maafw-cli scroll 120 0     # 向右滚 1 格
```

> **注意**：scroll 主要支持 Win32 控制器。

### `type <TEXT>`

向当前焦点控件输入文本。

```bash
maafw-cli type "Hello World"
maafw-cli type 你好
```

### `key <KEYCODE>`

按下一个虚拟按键。

**自动码表切换**：命令根据当前 session 类型（`adb` 或 `win32`）自动选择正确的键码表。同一名称在不同平台映射到不同的底层码：

| 名称 | ADB (Android AKEYCODE) | Win32 (VK) |
|------|----------------------|------------|
| `enter` | 66 | 0x0D |
| `back` | 4 | —（仅 Android） |
| `home` | 3（Android Home） | 0x24（文本 Home） |
| `tab` | 61 | 0x09 |
| `space` | 62 | 0x20 |
| `esc` | 111 | 0x1B |

KEYCODE 支持：
- **名称**（自动适配平台）：`enter`, `tab`, `esc`, `space`, `backspace`, `delete`, `up`, `down`, `left`, `right`, `f1`-`f12`, `ctrl`, `alt`, `shift` 等
- **Android 专属名称**（仅 ADB）：`back`, `home`, `recent`, `volume_up`, `volume_down`, `power`, `camera`, `wakeup`, `sleep`
- **Win32 专属名称**（仅 Win32）：`win`, `lwin`, `rwin`, `insert`, `numlock`, `scrolllock`, `printscreen`, `pause`, `apps`
- **整数直传**（不经过码表）：`66`（十进制）、`0x42`（十六进制）

```bash
maafw-cli key enter          # ADB → 66, Win32 → 0x0D（自动）
maafw-cli key back           # ADB → 4（Android 返回键）
maafw-cli key f5
maafw-cli key 66             # 直传整数，不查表
maafw-cli key 0x0D           # 直传十六进制
```

### `resource download-ocr`

下载 OCR 模型（ppocr_v5 zh_cn）。如已存在则跳过。

```bash
maafw-cli resource download-ocr
```

### `resource status`

显示资源就绪状态。

```bash
maafw-cli resource status
```

### `repl`

启动交互式 REPL。连接一次，后续操作复用 controller，零重连开销。

```bash
maafw-cli repl
maafw> connect adb 127.0.0.1:16384
maafw> ocr
maafw> click t1
maafw> observe on        # 开启 --observe 模式
maafw> click t2          # 点击后自动 OCR
maafw> quit
```

## `--observe` 模式

在动作命令（click/swipe/scroll/type/key）执行后自动追加 OCR，一条命令完成"操作+感知"。

```bash
maafw-cli --observe click t3          # 点击后立即输出 OCR 结果
maafw-cli --observe --json click t3   # JSON 中含 OCR 结果
```

REPL 中用 `observe on` / `observe off` 切换。

## 退出码

| 码 | 含义 |
|----|------|
| 0 | 成功 |
| 1 | 操作失败 |
| 2 | 识别失败 |
| 3 | 连接错误 |

## 数据目录

| 内容 | 路径 |
|------|------|
| OCR 模型、截图 | `platformdirs("MaaMCP", "MaaXYZ")`（与 MaaMCP 共享） |
| Session、TextRef | `platformdirs("maafw-cli", "MaaXYZ")` |

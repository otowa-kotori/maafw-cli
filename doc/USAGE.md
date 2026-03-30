# maafw-cli 使用指南

## 安装

```bash
cd maafw-cli
uv sync
```

## 快速开始

```bash
# 1. 连接设备（自动启动 daemon）
maafw-cli connect adb 127.0.0.1:16384                  # Android 模拟器
maafw-cli --on notepad connect win32 "记事本"           # Win32 窗口，命名为 notepad

# 2. 操作（通过 daemon，零重连）
maafw-cli ocr                                    # OCR，输出带 Element
maafw-cli click e3                               # 按引用点击
maafw-cli click 452,387                          # 按坐标点击
maafw-cli screenshot                             # 截图保存到当前目录

# 3. 多设备
maafw-cli --on notepad ocr                       # 指定会话
maafw-cli session list                           # 查看所有会话
maafw-cli daemon status                          # 查看 daemon 状态
```

## 全局选项

| 选项 | 说明 |
|------|------|
| `--version` | 显示版本号并退出 |
| `--json` | 输出严格 JSON 到 stdout |
| `--quiet` | 抑制非错误输出 |
| `-v` / `--verbose` | 显示 DEBUG 级别日志（含耗时） |
| `--on SESSION` | 指定目标 daemon 会话（默认使用最近连接的） |

## 命令参考

### `device`

列出可用设备。可选 FILTER 参数按名字子串过滤（大小写不敏感）。

```bash
maafw-cli device adb          # 全部 ADB 设备
maafw-cli device win32        # 全部 Win32 窗口
maafw-cli device win32 chrome # 只显示含 "chrome" 的窗口
maafw-cli device all          # 两者都列
maafw-cli device adb 127      # 只显示地址含 "127" 的设备
```

### `connect adb <DEVICE>`

连接 ADB 设备。DEVICE 是 `device adb` 输出的设备名或地址。

| 选项 | 默认 | 说明 |
|------|------|------|
| `--size` | `short:720` | 截图分辨率：`short:<px>`（短边缩放）、`long:<px>`（长边缩放）、`raw`（原尺寸） |

会话名通过全局 `--on NAME` 指定，省略则默认为 `default`。

```bash
maafw-cli connect adb 127.0.0.1:16384                        # 会话名 = default
maafw-cli --on phone connect adb 127.0.0.1:16384              # 会话名 = phone
maafw-cli connect adb 127.0.0.1:16384 --size long:1920        # 长边缩放到 1920
maafw-cli connect adb 127.0.0.1:16384 --size raw              # 原尺寸
```

### `connect win32 <WINDOW>`

连接 Win32 窗口。WINDOW 是窗口标题子串（大小写不敏感）或 `0x` 开头的 hwnd。

| 选项 | 默认 | 说明 |
|------|------|------|
| `--size` | `raw` | 截图分辨率：`raw`（原尺寸）、`short:<px>`（短边缩放）、`long:<px>`（长边缩放） |
| `--screencap-method` | FramePool | 截图方式 |
| `--input-method` | PostMessage | 输入方式 |

会话名通过全局 `--on NAME` 指定，省略则默认为 `default`。

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

对连接的设备/窗口执行全屏 OCR。结果赋予 Element（e1, e2, ...），可供 `click` 使用。

| 选项 | 说明 |
|------|------|
| `--roi x,y,w,h` | 限定识别区域 |
| `--text-only` | 仅输出识别文本，不含表格格式 |

```bash
maafw-cli ocr                         # 全屏 OCR
maafw-cli ocr --roi 0,0,400,300       # 只识别左上角区域
```

### `reco <TYPE> [params...]`

通用感知命令，暴露 MaaFramework 原生识别接口。TYPE 为识别类型，params 为 `key=value` 格式参数。

**支持的识别类型**：

| 类型 | 必填参数 | 说明 |
|------|---------|------|
| `TemplateMatch` | `template` | 模板匹配（尺寸敏感，精确匹配） |
| `FeatureMatch` | `template` | 特征匹配（对缩放/旋转/遮挡鲁棒） |
| `ColorMatch` | `lower`, `upper` | 颜色范围匹配 |
| `OCR` | (无) | 等同 `ocr` 命令 |

**参数格式**：

| 参数 | 格式 | 适用类型 |
|------|------|---------|
| `template` | `icon.png` 或 `a.png,b.png` | TemplateMatch, FeatureMatch |
| `roi` | `x,y,w,h` | 所有类型 |
| `threshold` | `0.8` | TemplateMatch, OCR |
| `lower` / `upper` | `R,G,B` | ColorMatch |
| `expected` | `设置,显示` | OCR |

```bash
# 模板匹配（需先 resource load-image）
maafw-cli reco TemplateMatch template=button.png threshold=0.8

# 特征匹配（对缩放/旋转鲁棒）
maafw-cli reco FeatureMatch template=icon.png

# 颜色匹配
maafw-cli reco ColorMatch lower=200,0,0 upper=255,50,50

# OCR（等同 ocr 命令）
maafw-cli reco OCR expected=设置 roi=0,0,400,200

# 原始 JSON 模式
maafw-cli reco --raw '{"recognition":"TemplateMatch","template":["button.png"]}'
```

所有结果赋予 Element 引用（e1, e2, ...），可直接 `click e1`。

### `screenshot`

截图保存到文件。

| 选项 | 说明 |
|------|------|
| `-o` / `--output` | 输出路径，省略则自动命名 |

### `click <TARGET>`

点击目标。TARGET 支持：
- Element：`e3`（需先运行 ocr）
- 坐标：`452,387`

### `swipe <FROM> <TO>`

从 FROM 滑动到 TO。FROM/TO 支持 Element 或坐标。

| 选项 | 默认 | 说明 |
|------|------|------|
| `--duration` | 300 | 滑动持续时间（毫秒） |

```bash
maafw-cli swipe 100,800 100,200              # 从下往上滑
maafw-cli swipe 100,800 100,200 --duration 500
maafw-cli swipe e1 e3                         # 从 Element e1 滑到 e3
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

### `resource load-image <PATH>`

加载图片资源到 Resource，供 TemplateMatch / FeatureMatch 使用。PATH 可以是目录（加载全部图片）或单个文件。

```bash
maafw-cli resource load-image ./templates/         # 加载目录
maafw-cli resource load-image ./button.png         # 加载单个文件
```

### `pipeline`

Pipeline 自动化命令——加载、验证、执行 JSON 定义的多节点流程。

#### `pipeline load <PATH>`

加载 pipeline JSON 文件或目录到 Resource。

```bash
maafw-cli --on game pipeline load ./pipeline/
```

#### `pipeline list`

列出当前已加载的所有节点名称。

```bash
maafw-cli --on game pipeline list
```

#### `pipeline show <NODE>`

显示某个节点的完整 JSON 定义。

```bash
maafw-cli --on game pipeline show GameLoop
```

#### `pipeline validate <PATH>`

验证 pipeline JSON 是否合法（不执行）。

```bash
maafw-cli --on game pipeline validate ./pipeline/
```

#### `pipeline run <PATH> [ENTRY] [--override JSON]`

执行 pipeline。从 ENTRY 节点开始（默认第一个），沿 `next` 链自动推进。

| 选项 | 说明 |
|------|------|
| `ENTRY` | 起始节点名，省略则用第一个节点 |
| `--override` | 运行时覆盖参数，JSON 格式 |

```bash
maafw-cli --on game pipeline run ./pipeline/ ClickPlay
maafw-cli --on game --json pipeline run ./pipeline/ ClickPlay   # JSON 输出含每个节点详情
maafw-cli --on game pipeline run ./pipeline/ ClickPlay --override '{"NodeA": {"timeout": 5000}}'
```

Pipeline JSON 格式示例：

```json
{
    "NodeName": {
        "recognition": "OCR|TemplateMatch|ColorMatch|DirectHit",
        "expected": "text",
        "template": ["icon.png"],
        "green_mask": true,
        "roi": [x, y, w, h],
        "threshold": 0.7,
        "action": "Click|DoNothing|InputText|StopTask",
        "timeout": 1500,
        "rate_limit": 0,
        "next": ["NextNode1", "NextNode2"]
    }
}
```

### `repl`

启动交互式 REPL。连接一次，后续操作复用 controller，零重连开销。

```bash
maafw-cli repl
maafw> connect adb 127.0.0.1:16384
maafw> ocr
maafw> click e1
maafw> quit
```

### `daemon start`

启动后台 daemon（如未运行）。

### `daemon stop`

停止后台 daemon。

### `daemon restart`

重启后台 daemon（先停止再启动）。

### `daemon status`

查看 daemon 状态（PID、端口、uptime、活跃会话）。

```bash
maafw-cli daemon status
maafw-cli --json daemon status
```

### `session list`

列出所有活跃的 daemon 会话。`*` 标记默认会话。

### `session default <NAME>`

设置默认会话。

### `session close <NAME>`

关闭并销毁一个会话。

```bash
maafw-cli session list
maafw-cli session default phone
maafw-cli session close tablet
```

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
| 所有数据（session、OCR 模型、daemon 等） | `platformdirs("maafw-cli", "MaaXYZ")` |
| 截图默认输出 | 当前工作目录 |

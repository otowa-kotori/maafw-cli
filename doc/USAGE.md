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
| `--roi x,y,w,h` | 限定识别区域（暂未实现过滤） |
| `--text-only` | 仅输出识别文本，不含表格格式 |

### `screenshot`

截图保存到文件。

| 选项 | 说明 |
|------|------|
| `-o` / `--output` | 输出路径，省略则自动命名 |

### `click <TARGET>`

点击目标。TARGET 支持：
- TextRef：`t3`（需先运行 ocr）
- 坐标：`452,387`

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

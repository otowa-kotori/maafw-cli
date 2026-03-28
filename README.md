<!-- markdownlint-disable MD033 MD041 MD024 -->
<p align="center">
  <img alt="LOGO" src="doc/logo.png" width="256" height="256" />
</p>

<div align="center">

# maafw-cli

![license](https://img.shields.io/github/license/otowa-kotori/maafw-cli)
![activity](https://img.shields.io/github/commit-activity/m/otowa-kotori/maafw-cli?color=%23ff69b4)
![stars](https://img.shields.io/github/stars/otowa-kotori/maafw-cli?style=social)  
[![MaaFramework](https://img.shields.io/badge/MaaFramework-v5-green)](https://github.com/MaaXYZ/MaaFramework)
[![PyPI](https://img.shields.io/pypi/v/maafw-cli?logo=pypi&logoColor=white)](https://pypi.org/project/maafw-cli/)

MaaFramework 命令行界面。让人、AI、脚本都能直接操作 Android / Win32 设备。

**MaaFW CLI vs [MaaMCP](https://github.com/MAA-AI/MaaMCP)**

**CLI**：现代 coding agent 更适合通过 CLI + skill 的方式驱动设备自动化。相比 MCP，CLI 调用通常只需要一条简洁命令，不必把庞大的工具 schema、持续会话状态或额外协议开销带进模型上下文，因此更省 token，也更容易和代码库分析、测试、脚本、定时任务组合。对于需要高频执行“识别 → 操作 → 校验”的 agent，`maafw-cli` 往往是更直接的选择。

**MCP**：MCP 仍然适合需要持久连接的场景。如果你需要维持持续会话，进行探索性的自动化，自修复测试，动态维护pipeline节点图等，或许使用具有持久状态的MCP是更好地选择。你可以了解更多有关 [MaaMCP](https://github.com/MAA-AI/MaaMCP) 的信息。
</div>

## 特性

- **后台守护进程** — 后台 daemon 持有 Controller 连接以降低操作延迟
- **Element 引用** — OCR / reco 结果赋予 e1, e2, e3…，后续命令直接 `click e3`
- **多种感知方式** — OCR、模板匹配、特征匹配、颜色匹配，统一通过 `reco` 命令暴露
- **多设备** — `--as phone` 命名会话，`--on phone` 指定操作目标
- **`--json` 输出** — 严格 JSON，方便脚本解析

## 安装

```bash
# 直接运行
uvx maafw-cli

# 或从源码
git clone https://github.com/otowa-kotori/maafw-cli.git
cd maafw-cli
uv sync
```

首次使用需要下载 OCR 模型：

```bash
maafw-cli resource download-ocr
```

## 30 秒上手

```bash
# 连接设备（自动启动后台 daemon）
maafw-cli connect adb 127.0.0.1:16384
maafw-cli connect win32 "记事本" --as notepad

# OCR — 识别屏幕文字，输出 e1, e2, e3...
maafw-cli ocr

# 原生感知 — 模板匹配、颜色匹配等
maafw-cli reco TemplateMatch template=button.png threshold=0.8
maafw-cli reco ColorMatch lower=200,0,0 upper=255,50,50

# 点击 — 用 Element 引用或坐标
maafw-cli click e3
maafw-cli click 452,387

# 更多操作
maafw-cli swipe 100,800 100,200
maafw-cli type "hello world"
maafw-cli key enter
maafw-cli screenshot
```

## 命令速览

| 命令 | 说明 |
|------|------|
| `device [adb\|win32\|all] [FILTER]` | 列出可用设备（可按名字过滤） |
| `connect adb <DEVICE> [--as NAME]` | 连接 ADB 设备 |
| `connect win32 <WINDOW> [--as NAME]` | 连接 Win32 窗口 |
| `ocr [--roi x,y,w,h] [--text-only]` | 屏幕 OCR |
| `reco <TYPE> [params...] [--raw JSON]` | 原生感知（TemplateMatch / FeatureMatch / ColorMatch / OCR） |
| `screenshot [-o FILE]` | 截图（默认保存到当前目录） |
| `click <TARGET>` | 点击（e3 或 452,387） |
| `swipe <FROM> <TO> [--duration MS]` | 滑动 |
| `scroll <DX> <DY>` | 滚动（仅 Win32） |
| `type <TEXT>` | 输入文本 |
| `key <KEYCODE>` | 按键（enter / back / f5 / 0x0D） |
| `resource download-ocr / status / load-image` | 管理资源（OCR 模型、图片模板） |
| `session list / default / close` | 管理命名会话 |
| `daemon start / stop / status` | 管理后台 daemon |
| `repl` | 交互式 REPL |

## 全局选项

| 选项 | 说明 |
|------|------|
| `--json` | 输出严格 JSON |
| `--quiet` | 抑制非错误输出 |
| `-v` | 显示耗时和调试信息 |
| `--observe` | 动作后自动 OCR |
| `--on SESSION` | 指定目标会话 |
| `--no-daemon` | 跳过 daemon，每次直连 |

## Daemon 模式

默认所有命令通过后台 daemon 执行，Controller 连接持久保持：

```bash
maafw-cli connect adb 127.0.0.1:16384 --as phone    # 创建命名会话
maafw-cli connect win32 "记事本" --as notepad         # 第二个设备
maafw-cli --on phone ocr                              # 操作指定设备
maafw-cli session list                                # 查看会话
maafw-cli daemon status                               # 查看 daemon 状态
```

daemon 空闲 5 分钟自动退出，下次命令自动重启。

## 给 AI / 脚本用

```bash
# JSON 输出，方便脚本解析
maafw-cli --json ocr | jq '.results[] | .ref + " " + .text'

# 模板匹配 + JSON
maafw-cli resource load-image ./templates/
maafw-cli --json reco TemplateMatch template=button.png threshold=0.8

# 操作链
maafw-cli ocr
maafw-cli click e3
maafw-cli --observe click e1    # 点击后自动 OCR，一条命令完成操作+感知
```

## 文档

- [命令参考](doc/USAGE.md)
- [工程结构](doc/ARCHITECTURE.md)
- [设计规格](doc/SPEC.md)

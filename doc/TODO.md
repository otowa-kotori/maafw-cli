# maafw-cli TODO

## 近期

- [ ] `text:设置` 目标寻址——自动 OCR → 查找 → 点击
- [ ] `--observe` 标志——动作后自动 OCR 返回结果
- [ ] `ocr --roi` 实际过滤（目前参数存在但未生效）
- [ ] `swipe`, `scroll`, `type`, `key` 等交互命令
- [ ] `reco` 命令——暴露 MaaFW 原生感知接口（TemplateMatch / ColorMatch 等）
- [ ] `resource download-ocr` 命令（download.py 已实现逻辑，缺 CLI 入口）

## 中期

- [ ] 守护进程 + 命名会话（`--as phone`, `--on notepad`）
- [ ] `session list/default/close` 管理
- [ ] `daemon start/stop/status`
- [ ] TextRef 跨 OCR 稳定性（box 重叠 + 文本相似性保持引用不变）

## 远期

- [ ] `pipeline run/validate/show/list`
- [ ] Shell 补全
- [ ] 彩色终端输出

# maafw-cli TODO

## 近期

- [ ] Tasker 缓存优化（当前每次 OCR 创建新 Tasker，__del__ 会清理但有 GC 延迟）

## 已知问题

- MaaFW `ColorMatch` 的 lower/upper 参数使用 **RGB** 顺序（非 BGR），与 OpenCV 约定不同
- Seize 输入法点击后鼠标光标停留在点击位置，会干扰后续 TemplateMatch 识别——pipeline 中需要 CursorReset 节点移开光标

## 搁置

- [ ] FramePool 截图在多 DPI 环境下的稳定性——默认 `FramePool,PrintWindow` fallback 在高 DPI 非 DPI-aware 窗口上可能 fallback 到 PrintWindow 导致截图异常，需调查根因

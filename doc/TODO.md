# maafw-cli TODO

## 已完成 ✅

- [x] `--observe` 标志——动作后自动 OCR 返回结果（daemon + direct 模式均支持）
- [x] `ocr --roi` 实际过滤
- [x] `swipe`, `scroll`, `type`, `key` 等交互命令
- [x] `resource download-ocr` 命令
- [x] 守护进程 + 命名会话（`--as phone`, `--on notepad`）
- [x] `session list/default/close` 管理
- [x] `daemon start/stop/status`
- [x] `reco` 命令——暴露 MaaFW 原生感知接口（TemplateMatch / FeatureMatch / ColorMatch / OCR）
- [x] `resource load-image` 命令——加载图片模板到 Resource
- [x] `device` 命令按名字过滤（`device win32 chrome`）
- [x] daemon 自动发现 service 模块（pkgutil 扫描）
- [x] `pipeline run/validate/show/list` 命令
- [x] Pipeline 集成测试——12 节点 demo_flow 线性流程
- [x] Pipeline 点击游戏集成测试——13 节点循环分支（TemplateMatch + green_mask + ColorMatch + DirectHit）

## 近期

- [ ] `text:设置` 目标寻址——自动 OCR → 查找 → 点击
- [ ] `ocr` 顺便保存截图（已截图，可附带输出）
- [ ] Daemon IPC heartbeat 机制——长时间 pipeline 运行时保持连接活跃（当前 socket timeout 改为 300s 作为临时方案）
- [ ] Pipeline `post_wait_freezes` / `rate_limit` 优化——当前 MaaFW 每个 action 后默认 200ms sleep，需要确认正确的字段名来消除不必要延迟

## 安全与健壮性

- [ ] Daemon TCP 认证——启动时生成 token 写入仅用户可读的文件，客户端请求必须携带
- [ ] Daemon 启动竞争条件——对 PID 文件加文件锁（Windows: msvcrt.locking, POSIX: fcntl.flock）
- [ ] 下载 OCR 模型后校验 SHA256（需确定校验和来源）
- [ ] CI/CD——添加 GitHub Actions 基础流水线（lint + test）
- [ ] `daemon start --verbose` 参数传递给 daemon 进程
- [ ] FramePool 截图在多 DPI 环境下的稳定性——默认 `FramePool,PrintWindow` fallback 在高 DPI 非 DPI-aware 窗口上可能 fallback 到 PrintWindow 导致截图异常，需调查根因

## 已知问题

- MaaFW `ColorMatch` 的 lower/upper 参数使用 **RGB** 顺序（非 BGR），与 OpenCV 约定不同
- Seize 输入法点击后鼠标光标停留在点击位置，会干扰后续 TemplateMatch 识别——pipeline 中需要 CursorReset 节点移开光标

## 中期

- [ ] Element 跨 OCR 稳定性（box 重叠 + 文本相似性保持引用不变）
- [ ] 下载 URL 可配置——支持环境变量 `MAAFW_OCR_MIRROR` 或配置文件覆盖
- [ ] 各 `__init__.py` 添加 `__all__` 导出声明
- [ ] 版本号单一来源（pyproject.toml + `__init__.py` 目前双源）
- [ ] Tasker 缓存优化（当前每次 OCR 创建新 Tasker，__del__ 会清理但有 GC 延迟）

## 远期

- [ ] Shell 补全
- [ ] 彩色终端输出

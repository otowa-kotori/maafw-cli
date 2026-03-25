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

## 近期

- [ ] `text:设置` 目标寻址——自动 OCR → 查找 → 点击
- [ ] `ocr` 顺便保存截图（已截图，可附带输出）

## 安全与健壮性

- [ ] Daemon TCP 认证——启动时生成 token 写入仅用户可读的文件，客户端请求必须携带
- [ ] Daemon 启动竞争条件——对 PID 文件加文件锁（Windows: msvcrt.locking, POSIX: fcntl.flock）
- [ ] 下载 OCR 模型后校验 SHA256（需确定校验和来源）
- [ ] CI/CD——添加 GitHub Actions 基础流水线（lint + test）
- [ ] `daemon start --verbose` 参数传递给 daemon 进程

## 中期

- [ ] Element 跨 OCR 稳定性（box 重叠 + 文本相似性保持引用不变）
- [ ] 下载 URL 可配置——支持环境变量 `MAAFW_OCR_MIRROR` 或配置文件覆盖
- [ ] 各 `__init__.py` 添加 `__all__` 导出声明
- [ ] 版本号单一来源（pyproject.toml + `__init__.py` 目前双源）
- [ ] Tasker 缓存优化（当前每次 OCR 创建新 Tasker，__del__ 会清理但有 GC 延迟）

## 远期

- [ ] `pipeline run/validate/show/list`
- [ ] Shell 补全
- [ ] 彩色终端输出

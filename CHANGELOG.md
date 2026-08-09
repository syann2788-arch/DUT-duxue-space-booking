# Changelog

本项目采用 Keep a Changelog 风格；在首个正式校内试点发布前版本均可能发生契约调整。

## [Unreleased]

### Security

- 增加生产配置启动守卫、关闭生产开放注册并移除固定管理员密码。
- 拆分预约本人/管理员响应模型，收紧清扫照片 URL 前缀。
- 禁用正式项目的旧云开发入口，增加安全报告流程与 Dependabot。
- 用 PyJWT cryptography 替换带未修复公告的 python-jose/ecdsa，并升级 FastAPI、multipart 与测试依赖。

### Added

- GitHub Actions 后端、小程序与容器质量门禁。
- 60% 后端覆盖率基线、阻断级依赖审计和 CycloneDX SBOM 产物。
- 小程序命令行测试、环境化构建及版本/提交信息产物。
- 数据库就绪检查、请求 ID 日志、非 root 容器和 Compose 重启策略。
- 评审整改台账、贡献规范、支持范围与发布路线图。

### Changed

- 统一正式运行链路为原生微信小程序 `miniprogram/` + FastAPI `backend/`；移除工作树中的旧 uni-app 与微信云函数实现，并将 AI 开发规范统一到 `AGENTS.md`。
- 通知 access token 增加缓存；无法投递的配置错误不再永久 pending。
- 状态刷新只扫描最近仍可能流转的预约，列表接口增加有界分页参数。
- pytest 使用进程唯一临时数据库和上传目录。

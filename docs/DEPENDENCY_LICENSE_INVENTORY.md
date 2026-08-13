# 依赖与许可证盘点

盘点日期：2026-08-13。本文只记录项目直接依赖的版本和上游声明，不替项目版权方选择整体许可证，也不构成法律意见。正式发布前仍需由学校或项目权利人复核素材、字体、校名校徽和第三方代码授权。

## 正式后端直接依赖

| 依赖 | 锁定版本 | 上游许可证声明 | 项目用途 |
|---|---:|---|---|
| FastAPI | 0.141.1 | MIT | API 框架 |
| Uvicorn | 0.34.0 | BSD-3-Clause | ASGI 服务 |
| SQLAlchemy | 2.0.36 | MIT | 数据库访问 |
| aiosqlite | 0.20.0 | MIT | 本地演示数据库 |
| Pydantic / pydantic-settings | 2.10.3 / 2.7.0 | MIT | 校验与配置 |
| PyJWT | 2.13.0 | MIT | JWT |
| passlib | 1.7.4 | BSD | 密码哈希封装 |
| bcrypt | 4.0.1 | Apache-2.0 | 密码哈希 |
| python-multipart | 0.0.31 | Apache-2.0 | 文件上传 |
| HTTPX | 0.28.1 | BSD-3-Clause | 微信接口请求 |
| APScheduler | 3.10.4 | MIT | 后台定时任务 |
| openpyxl | 3.1.5 | MIT | Excel 导出 |
| qrcode | 8.2 | BSD | 管理端签到二维码 |
| Pillow | 12.3.0 | HPND | PNG 图片生成 |
| asyncpg | 0.30.0 | Apache-2.0 | PostgreSQL 驱动 |
| Alembic | 1.14.0 | MIT | 数据库迁移 |

`pytest` 9.0.3 与 `pytest-asyncio` 1.3.0 仅用于测试，分别为 MIT 和 Apache-2.0。实际安装时应同时保留各上游包随附的许可证文本；自动扫描不能替代上游原文。

## 微信小程序主线

正式 `miniprogram/` 不包含 npm 运行时依赖。二维码由后端生成，避免把额外第三方运行时代码打入小程序。

## 参考前端

`frontend/` 不是微信交付主线。其直接依赖及锁定版本包括 Vue 3.4.21、Pinia 2.1.7、Vite 5.2.8（MIT），以及 DCloud uni-app 相关 alpha 包（Apache-2.0）。完整传递依赖以 `frontend/package-lock.json` 为准。

## 发布前人工决策

- 项目自身采用何种许可证，必须由代码及素材权利人决定；当前不得擅自新增根目录 `LICENSE`。
- 确认校名、书院名称、标识和空间照片是否允许随代码或发行包公开。
- 运行依赖漏洞审计并记录未修复项；网络扫描结果具有时效性。
- 若更换二维码、图像或字体库，必须同步更新本清单。

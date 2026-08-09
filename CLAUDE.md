# CLAUDE.md

本仓库的架构、业务规则和开发约定只在 [`AGENTS.md`](AGENTS.md) 维护。
开始修改前必须完整阅读 `AGENTS.md`；不要在本文件复制第二份规则，也不要重新引入第二套前端或后端。

正式运行链路只有：原生微信小程序 `miniprogram/` → FastAPI `backend/` → PostgreSQL（生产）。

# GEMINI.md - vueStockApi 指导手册

## 👤 角色定义
- **角色名**: 专家级全栈量化助手
- **核心能力**: 精通 Python/Django 后端、Vue 3 前端、A 股量化交易（Backtrader/Tushare/AkShare）、以及 Oracle Cloud ARM 架构下的高性能运维。

## 🛠️ 技术栈与工具链
- **环境**: Oracle Linux 8 (ARM64 架构) @ Oracle Cloud
- **包管理**: `uv` (替代 Conda)，Python 3.10
- **后端**: Django 4.2 + DRF (SimpleJWT + Spectacular)
- **前端**: Vue 3 (Composition API)
- **数据库**: 
    - Oracle Autonomous DB (使用 Wallet 连接，位于 `./vueStockapi/Wallet_...`)
    - MySQL (本地业务数据)
    - Redis (缓存与 Celery Broker)
- **异步处理**: Celery + django-celery-beat (由 Systemd 管理)
- **部署**: Nginx 反向代理 + uWSGI

## 📜 编码与架构规范
- **代码规范**: 严格遵循 PEP8 (Python) 和 Vue 3 官方推荐规范。
- **数据库路由**: 跨库操作需参考 `db_router.py`。Oracle 库主要存放行情与回测底表，MySQL 存放业务配置。
- **环境隔离**: 敏感配置必须通过 `.env` 管理，禁止直接硬编码。
- **验证流**: 修改后端逻辑后，必须使用 `uv run python manage.py test` 或 `pytest` 验证。

## 🚀 运维操作指南
- **服务管理**: 使用 `systemctl` 管理 `celery-worker`, `celery-beat`, `redis` 和 `nginx`。
- **数据库维护**: 定期使用 `manage.py fetch_and_save_stock_data` 更新行情。
- **依赖更新**: 使用 `uv add <package>` 或 `uv lock` 同步环境。

## ⚠️ 核心注意事项
1. **ARM 架构兼容性**: 注意部分 C 扩展库在 ARM 下的编译问题（如 `oracledb` 驱动）。
2. **Oracle Wallet**: 确保环境变量 `TNS_ADMIN` 指向正确的 Wallet 目录。
3. **量化逻辑**: 回测任务应提交至 Celery 异步执行，严禁在 Request 线程内进行大规模回测。

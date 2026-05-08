
# vueStockapi 项目

`vueStockapi` 是一个基于 Django 和 Django REST Framework 构建的 Web 应用程序，旨在提供一个强大的后端服务，用于处理与股票数据和称重系统相关的业务逻辑。项目集成了 Celery 用于异步任务处理，并支持 Oracle 和 MySQL 双数据库环境。

## ✨ 功能特性

- **RESTful API**：使用 Django REST Framework 提供标准化、高性能的 API 接口。
- **双数据库支持**：通过自定义的数据库路由（`db_router.py`），同时支持 Oracle 和 MySQL 数据库，实现了不同业务数据的分离存储。
- **异步任务处理**：集成 Celery 及 `django-celery-beat`，用于执行耗时的后台任务（如数据抓取、分析等）和周期性任务调度。
- **模块化应用**：项目包含 `basic` 和 `weighing` 两个核心 Django 应用，分别处理基础数据和称重相关业务，结构清晰，易于扩展。
- **自定义管理命令**：提供了一系列实用的 `manage.py` 命令，用于数据库清理、迁移重建、数据获取等，简化了日常开发和维护工作。
- **环境变量管理**：使用 `python-decouple` 管理项目配置，将敏感信息与代码分离，增强了项目的安全性与可移植性。
- **CORS 支持**：通过 `django-cors-headers` 中间件，轻松处理跨域资源共享问题，方便前后端分离开发。
- **静态文件服务**：集成了 Django 静态文件处理，并为 Admin 和 DRF 提供了必要的静态资源。

## 🏗️ 技术架构

- **环境**: Oracle Cloud ARM (Oracle Linux 8)
- **后端框架**: Django 4.2
- **API 框架**: Django REST Framework + SimpleJWT
- **前端框架**: Vue 3 (Composition API)
- **异步任务**: Celery + Redis
- **数据库**: Oracle Autonomous DB (Wallet) & MySQL
- **环境管理**: [uv](https://github.com/astral-sh/uv)
- **进程管理**: Systemd (Celery, Redis)
- **Web 服务器**: Nginx + uWSGI

## 🚀 快速开始

### 1. 环境准备

本项目已放弃 Conda，改用 **uv** 进行极速依赖管理。

```bash
# 安装 uv (如果尚未安装)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 克隆项目
git clone <your-repository-url>
cd vueStockapi

# 同步环境并安装依赖
uv sync
```

### 2. 配置与运行

- **环境变量**: 参考 `settings.py` 配置 `.env` 文件。
- **Oracle Wallet**: 确保 Wallet 文件位于 `vueStockapi/` 目录下，并配置 `TNS_ADMIN` 环境变量。
- **运行服务**:

```bash
# 启动 Django
uv run python manage.py runserver

# 启动 Celery (生产环境推荐使用 systemctl)
uv run celery -A vueStockapi worker -l info
```

## 🤖 开发规范

本项目遵循 `GEMINI.md` 中定义的开发规范。所有 AI 辅助开发应首先读取该文件以了解：
- 专家级全栈量化助手的角色定位。
- 数据库路由与跨库操作规范。
- 运维与部署的最佳实践。


现在，您可以通过浏览器访问 `http://127.0.0.1:8000` 来查看项目运行情况。

## 📋 API 端点说明

本项目提供以下API端点来支持回测功能：

### 1. 启动批量回测

- **URL**: `/api/backtest/batch-run/`
- **Method**: `POST`
- **说明**: 启动一个异步的批量回测任务。请求成功后，会返回一个任务ID。
- **请求体示例**:
  ```json
  {
      "filters": {
          "stock_code": "000001.SZ",
          "start_date": "2023-01-01",
          "end_date": "2023-03-31"
      },
      "backtest_params": {
          "buy_timeout_days": 10,
          "hold_timeout_days": 60,
          "db_alias": "default"
      }
  }
  ```
- **成功响应**:
  ```json
  {
      "message": "批处理回测任务已启动",
      "task_id": "e2b73bbe-23af-4305-b2c4-895e932a82a6"
  }
  ```

### 2. 查看回测结果

- **URL**: `/api/backtest/results/`
- **Method**: `GET`
- **说明**: 获取所有已完成的回测结果列表。结果按创建时间倒序排列。
- **成功响应 (示例)**:
  ```json
  [
      {
          "id": 1,
          "policy_id": 123,
          "policy_db": "default",
          "buy_timeout_days": 10,
          "hold_timeout_days": 60,
          "strategy_name": "MyStrategy",
          "stock_code": "000001.SZ",
          "start_date": "2023-01-01",
          "end_date": "2023-03-31",
          "initial_cash": "100000.00",
          "final_value": "115000.00",
          "total_return": "0.1500",
          "sharpe_ratio": "1.2000",
          "max_drawdown": "0.0500",
          "created_at": "2025-11-20T10:00:00Z"
      }
  ]
  ```

## ⚙️ 项目管理命令

项目提供了一些自定义的 `manage.py` 命令以简化维护工作：

- **清理数据库（删除所有表）**:
  ```bash
  python manage.py cleanup_db
  ```

- **清理所有表数据（保留表结构）**:
  ```bash
  python manage.py cleanup_tables
  ```

- **重建数据库迁移记录**:
  ```bash
  python manage.py rebuild_migrations
  ```

- **检查数据库表文件**:
  ```bash
  python manage.py check_tables
  ```

- **手动执行策略分析**:
  ```bash
  python manage.py manual_analysis
  ```

- **获取或更新股票数据**:
  ```bash
  python manage.py fetch_and_save_stock_data
  ```

## 部署

项目包含 `uwsgi.ini` 配置文件，表明可以很方便地通过 uWSGI 进行部署。通常与 Nginx 配合使用，实现高性能的生产环境部署。

## 🤝 贡献

欢迎对本项目做出贡献。如果您有任何问题或建议，请随时提交 Issue 或 Pull Request。

## 📄 许可证

本项目采用 [MIT](LICENSE) 许可证。

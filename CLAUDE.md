# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 高层次代码架构

- 本项目是一个基于 Django 的 Web 应用程序，使用 Django REST Framework 构建 RESTful API。
- 代码库主要由 `basic` 和 `weighing` 两个 Django 应用组成，每个应用负责特定的业务逻辑和数据模型。
- 项目配置支持 Oracle 和 MySQL 两种数据库，通过 `db_router.py` 进行数据库路由管理。
- 使用 Celery 作为异步任务队列，配合 `django-celery-beat` 进行周期性任务调度，`django-celery-results` 存储任务结果。Redis 作为 Celery 的消息代理和结果后端。
- 环境变量通过 `python-decouple` 进行管理，提高了配置的灵活性和安全性。
- 跨域资源共享 (CORS) 通过 `django-cors-headers` 中间件进行处理。
- 静态文件（CSS, JavaScript, Images）集中在 `static` 目录下，并为 Django Admin 和 Django REST Framework 提供了资源。

## 常用命令

### 环境设置 (使用 Conda)

1.  **创建 Conda 环境**: `conda env create -f environment.yml`
2.  **激活环境**: `conda activate vueStockapi`

### Django 管理命令

- **运行开发服务器**: `python manage.py runserver`
- **数据库迁移**:
    - `python manage.py makemigrations`
    - `python manage.py migrate`
- **创建超级用户**: `python manage.py createsuperuser`

### 项目特定管理命令

- **清理数据库全部数据**: `python manage.py cleanup_db`
- **清理数据库表（保留表结构，删除所有数据）**: `python manage.py cleanup_tables`
- **重新构建迁移记录**: `python manage.py rebuild_migrations`
- **检查数据库表文件**: `python manage.py check_tables`
- **手动策略分析**: `python manage.py manual_analysis`
- **获取或更新股票代码/日线数据**: `python manage.py fetch_and_save_stock_data`

### Celery 命令

- **启动 Celery Worker**: `celery -A vueStockapi worker -l info`
- **启动 Celery Beat (任务调度器)**: `celery -A vueStockapi beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler`

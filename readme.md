# vueStockapi 项目运维与部署手册 (2026.01.28 更新)

## 🏗 环境架构
本项目已从 Conda 全面迁移至 **uv** 包管理器，并由 **systemd** 进行进程守护。

* **Python 版本**: 3.10
* **包管理**: [uv](https://astral.sh/uv/) (极速依赖同步与环境隔离)
* **Web 服务器**: uWSGI (运行于项目 `.venv` 环境)
* **任务队列**: Celery + Redis
* **定时任务**: django-celery-beat (数据库驱动调度)
* **反向代理**: Nginx (处理 HTTPS 与 静态资源映射)



---

## 🚀 日常运维命令

### 1. 服务状态检查
使用系统标准指令查看 Web 和 异步任务是否运行正常：
```bash
# 查看 Web 服务状态
sudo systemctl status vuestock-uwsgi

# 查看 Celery 任务状态
sudo systemctl status vuestock-celery
2. 重启服务 (代码更新/配置修改后执行)
当你执行了 git pull 或是修改了 .env 后，必须重启服务：
# 重启所有组件
sudo systemctl restart vuestock-uwsgi vuestock-celery

# 如果修改了数据库模型，重启前需执行：
uv run python manage.py migrate
3. 环境同步与静态资源
如果代码中新增了依赖包（如 drf-spectacular）：
uv sync                          # 同步依赖到 .venv
uv run python manage.py collectstatic --noinput  # 收集静态文件
错误日志排查 (快速定位)
当网站访问异常时，按以下顺序排查日志：

第一步：检查 Nginx 日志 (连接层)
如果报 (2: No such file or directory)，通常是 uwsgi.sock 路径权限或 Nginx 无法穿透上级目录。

Bash
sudo tail -f /var/log/nginx/error.log
第二步：检查 uWSGI 日志 (Django 应用层)
检查业务代码逻辑、MySQL 连接或环境变量错误。

Bash
sudo journalctl -u vuestock-uwsgi -f
第三步：检查 Celery 日志 (异步/定时任务层)
检查股票数据更新任务、Oracle Wallet 证书连接等。

Bash
sudo journalctl -u vuestock-celery -f
🛠 核心配置备忘录
1. Oracle Wallet 证书配置
Oracle Wallet 存放于 /home/opc/oracle_wallet。

sqlnet.ora: 必须使用绝对路径：DIRECTORY="/home/opc/oracle_wallet"。

权限: 必须确保 sudo chmod -R 755 /home/opc/oracle_wallet。

Systemd: Celery 服务已通过 TNS_ADMIN 环境变量强制指向该目录。

2. 环境变量 (.env)
项目使用 python-decouple 强制读取以下变量，缺一不可：

WALLET_DIRECTORY: 指向 Wallet 目录（用于应用逻辑）。

WALLET_LOCATION: 同上（用于旧驱动兼容）。

DB_NAME_MYSQL / DB_USER_MYSQL: 业务数据库。

3. API 文档支持 (Redoc/Swagger)
为解决国内 CDN (jsdelivr) 加载缓慢导致的“页面空白”问题：

已启用 Sidecar 模式：drf-spectacular-sidecar。

settings.py 中 REDOC_DIST 和 SWAGGER_UI_DIST 均已设置为 'SIDECAR'。

📂 路径说明
项目根目录: /home/opc/vueStockapi

虚拟环境: /home/opc/vueStockapi/.venv

Unix Socket: /home/opc/vueStockapi/uwsgi.sock (权限 666，用户 opc:nginx)

静态资源: /home/opc/vueStockapi/static

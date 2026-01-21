# 服务器 Redis 问题修复指南

## 问题原因

`AttributeError: 'NoneType' object has no attribute 'Redis'` 通常由以下原因引起：

1. **conda 环境中未安装 redis 包**
2. **Django 进程使用了错误的 Python 环境**
3. **redis 包版本与 celery 不兼容**

## 修复步骤

### 步骤 1: 确认当前 conda 环境

在服务器上运行：

```bash
# 查看当前激活的 conda 环境
conda info --envs

# 激活正确的环境（替换为你的环境名）
conda activate your_env_name
```

### 步骤 2: 安装 redis 包

```bash
# 在激活的 conda 环境中安装
pip install redis

# 或使用 conda 安装
conda install -c conda-forge redis-py
```

### 步骤 3: 运行诊断脚本

```bash
# 在项目目录下运行诊断脚本
python diagnose_redis.py
```

诊断脚本会检查：
- Python 环境路径
- redis 模块是否正确安装
- Django 配置是否正确
- Redis 服务连接是否正常
- Celery 配置是否正确

### 步骤 4: 验证 Redis 服务

```bash
# 检查 Redis 是否运行（Linux/Mac）
redis-cli ping
# 应返回: PONG

# Windows 上检查
redis-cli.exe ping
```

### 步骤 5: 重启 Django 服务

```bash
# 杀掉现有的 Django 进程
pkill -f "python.*runserver"
pkill -f "python.*gunicorn"
pkill -f "python.*uwsgi"

# 重新启动 Django
python manage.py runserver 0.0.0.0:8000

# 或使用生产服务器
gunicorn vueStockapi.wsgi:application --bind 0.0.0.0:8000
```

### 步骤 6: 重启 Celery Worker（如果使用）

```bash
# 停止现有 Celery worker
pkill -f "celery.*worker"

# 重启 Celery worker
celery -A vueStockapi worker -l info
```

## 常见问题排查

### 问题 A: 多个 Python 环境

**症状**: 安装了 redis 但仍然报错

**解决方案**:
```bash
# 找到 Django 实际使用的 Python
which python
python -c "import sys; print(sys.executable)"

# 在那个环境中安装 redis
/path/to/actual/python -m pip install redis
```

### 问题 B: Redis 连接被拒绝

**症状**: `redis.exceptions.ConnectionError`

**解决方案**:
1. 检查 Redis 是否监听正确的端口
```bash
netstat -tlnp | grep 6379
```

2. 检查防火墙设置
```bash
# 允许 6379 端口
sudo ufw allow 6379
```

3. 修改 Redis 配置（如果需要远程连接）
```bash
# 编辑 redis.conf
bind 0.0.0.0
protected-mode no
```

### 问题 C: 版本不兼容

**症状**: 安装后仍有错误

**解决方案**:
```bash
# 完全卸载后重新安装
pip uninstall redis -y
pip install redis==4.5.1

# 同时确保 celery 版本兼容
pip install celery==5.3.4
```

## 生产环境建议

### 使用虚拟环境

```bash
# 创建专门的 conda 环境
conda create -n vuestockapi python=3.11
conda activate vuestockapi

# 安装所有依赖
pip install -r requirements.txt
```

### 使用 Supervisor 管理进程

```ini
# /etc/supervisor/conf.d/django.conf
[program:django]
command=/path/to/conda/envs/vuestockapi/bin/gunicorn vueStockapi.wsgi:application
directory=/path/to/vueStockapi
user=youruser
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/django.log

[program:celery]
command=/path/to/conda/envs/vuestockapi/bin/celery -A vueStockapi worker -l info
directory=/path/to/vueStockapi
user=youruser
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery.log
```

### 使用 systemd（推荐）

```ini
# /etc/systemd/system/django.service
[Unit]
Description=Django Application
After=network.target

[Service]
Type=notify
User=youruser
WorkingDirectory=/path/to/vueStockapi
Environment="PATH=/path/to/conda/envs/vuestockapi/bin"
ExecStart=/path/to/conda/envs/vuestockapi/bin/gunicorn vueStockapi.wsgi:application
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

启用服务:
```bash
sudo systemctl enable django
sudo systemctl start django
sudo systemctl status django
```

## 快速验证清单

在服务器上依次运行：

```bash
# 1. 确认 conda 环境
conda activate your_env_name

# 2. 验证 Python 路径
which python

# 3. 验证 redis 安装
python -c "import redis; print(redis.__version__)"

# 4. 验证 Redis 服务
redis-cli ping

# 5. 运行诊断脚本
python diagnose_redis.py

# 6. 重启服务
# 杀掉旧进程，启动新进程
```

全部通过后，再次测试 Postman 请求。

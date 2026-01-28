# Redis 安装和配置指南 (macOS M2)

## 🚀 快速开始

### 方法 1：使用 Homebrew 安装（推荐）

#### 步骤 1：安装 Redis

```bash
# 安装 Redis
brew install redis
```

#### 步骤 2：启动 Redis 服务

有两种启动方式：

**选项 A：作为后台服务启动（推荐）**
```bash
# 启动 Redis 服务并设置为开机自启动
brew services start redis

# 查看服务状态
brew services list | grep redis
```

**选项 B：前台运行（用于测试）**
```bash
# 前台运行 Redis（关闭终端会停止）
redis-server

# 或者使用配置文件
redis-server /opt/homebrew/etc/redis.conf
```

#### 步骤 3：验证 Redis 是否运行

```bash
# 测试连接
redis-cli ping

# 应该返回：PONG
```

#### 步骤 4：启动 Celery Worker

```bash
# 回到项目目录
cd /Users/xiejunliang/Documents/stock/vueStockapi

# 启动 Celery Worker
uv run celery -A vueStockapi worker -l info -P solo
```

---

### 方法 2：使用 Docker 运行 Redis（可选）

如果您已经安装了 Docker：

```bash
# 启动 Redis 容器
docker run -d \
  --name redis-server \
  -p 6379:6379 \
  redis:latest

# 查看容器状态
docker ps | grep redis

# 停止 Redis
docker stop redis-server

# 重新启动
docker start redis-server
```

---

## 🔧 常用 Redis 命令

### 服务管理

```bash
# 启动 Redis 服务
brew services start redis

# 停止 Redis 服务
brew services stop redis

# 重启 Redis 服务
brew services restart redis

# 查看所有 brew 服务状态
brew services list
```

### 连接和测试

```bash
# 连接到 Redis CLI
redis-cli

# 在 CLI 中执行命令
> ping                # 应返回 PONG
> set test "hello"    # 设置键值
> get test            # 获取值
> keys *              # 查看所有键
> flushall            # 清空所有数据（谨慎使用！）
> exit                # 退出 CLI
```

### 查看 Redis 信息

```bash
# 查看 Redis 服务器信息
redis-cli info

# 查看特定信息
redis-cli info server
redis-cli info memory
redis-cli info stats
```

---

## 📊 Celery 相关命令

### 启动 Celery Worker

```bash
# 基本启动（macOS M2 必须使用 -P solo）
uv run celery -A vueStockapi worker -l info -P solo

# 后台运行（使用 nohup）
nohup uv run celery -A vueStockapi worker -l info -P solo > celery_worker.log 2>&1 &

# 查看后台进程
ps aux | grep celery

# 停止后台 Celery
pkill -f "celery worker"
```

### 启动 Celery Beat（定时任务调度器）

```bash
# 启动 Beat 调度器
uv run celery -A vueStockapi beat -l info

# 同时启动 Worker 和 Beat
uv run celery -A vueStockapi worker -l info -P solo --beat
```

### 查看任务状态

```bash
# 查看注册的任务
uv run celery -A vueStockapi inspect registered

# 查看活跃的任务
uv run celery -A vueStockapi inspect active

# 查看计划任务
uv run celery -A vueStockapi inspect scheduled

# 查看 Worker 状态
uv run celery -A vueStockapi inspect stats
```

---

## 🐛 常见问题排查

### 问题 1：Redis 连接被拒绝

**错误信息**：
```
Error 61 connecting to 127.0.0.1:6379. Connection refused.
```

**解决方案**：
```bash
# 检查 Redis 是否运行
brew services list | grep redis

# 如果没有运行，启动它
brew services start redis

# 验证连接
redis-cli ping
```

### 问题 2：端口被占用

**检查端口占用**：
```bash
lsof -i :6379
```

**解决方案**：
```bash
# 找到占用端口的进程并杀死
lsof -i :6379 | grep LISTEN | awk '{print $2}' | xargs kill -9

# 重新启动 Redis
brew services restart redis
```

### 问题 3：macOS M2 芯片 Celery 启动失败

**错误信息**：
```
ValueError: not enough values to unpack (expected 3, got 0)
```

**解决方案**：
必须使用 `-P solo` 参数！
```bash
uv run celery -A vueStockapi worker -l info -P solo
```

### 问题 4：Celery 找不到任务

**检查任务是否注册**：
```bash
uv run celery -A vueStockapi inspect registered
```

**确保任务文件被正确导入**：
检查 `vueStockapi/celery.py` 中的 `autodiscover_tasks()` 配置。

---

## 📝 Redis 配置文件

Redis 配置文件位置（Homebrew 安装）：
```
/opt/homebrew/etc/redis.conf
```

### 常用配置项

```bash
# 查看配置
cat /opt/homebrew/etc/redis.conf

# 重要配置项：
# port 6379                    # 端口
# bind 127.0.0.1               # 绑定地址
# maxmemory 256mb              # 最大内存
# maxmemory-policy allkeys-lru # 内存淘汰策略
```

### 修改配置

```bash
# 编辑配置文件
nano /opt/homebrew/etc/redis.conf

# 修改后重启 Redis
brew services restart redis
```

---

## 🔒 安全建议

1. **生产环境**：
   - 修改默认端口
   - 设置密码：在 `redis.conf` 中添加 `requirepass your_password`
   - 绑定到内网 IP，不要暴露到公网

2. **开发环境**：
   - 当前配置（127.0.0.1:6379）已经足够安全
   - 仅本机可访问

---

## 📊 监控 Redis

### 使用 redis-cli 监控

```bash
# 实时监控 Redis 命令
redis-cli monitor

# 查看慢查询日志
redis-cli slowlog get 10

# 查看内存使用
redis-cli info memory
```

### 使用 RedisInsight（GUI 工具）

可以下载 RedisInsight 来可视化管理 Redis：
https://redis.com/redis-enterprise/redis-insight/

---

## ✅ 完整启动流程

### 1. 启动 Redis
```bash
brew services start redis
```

### 2. 验证 Redis
```bash
redis-cli ping
# 应返回: PONG
```

### 3. 启动 Celery Worker
```bash
cd /Users/xiejunliang/Documents/stock/vueStockapi
uv run celery -A vueStockapi worker -l info -P solo
```

### 4. （可选）启动 Celery Beat
```bash
# 在另一个终端窗口
cd /Users/xiejunliang/Documents/stock/vueStockapi
uv run celery -A vueStockapi beat -l info
```

### 5. 启动 Django 开发服务器
```bash
# 在另一个终端窗口
cd /Users/xiejunliang/Documents/stock/vueStockapi
uv run python manage.py runserver 0.0.0.0:8000
```

---

## 🎯 快速命令参考

```bash
# === Redis ===
brew install redis                          # 安装
brew services start redis                   # 启动
brew services stop redis                    # 停止
brew services restart redis                 # 重启
redis-cli ping                             # 测试连接
redis-cli                                  # 进入 CLI

# === Celery ===
uv run celery -A vueStockapi worker -l info -P solo              # 启动 Worker
uv run celery -A vueStockapi beat -l info                        # 启动 Beat
uv run celery -A vueStockapi inspect registered                  # 查看任务
uv run celery -A vueStockapi inspect active                      # 查看活跃任务
pkill -f "celery worker"                                         # 停止 Worker

# === Django ===
uv run python manage.py runserver                                # 启动服务器
uv run python manage.py migrate                                  # 运行迁移
```

---

## 📚 参考文档

- Redis 官方文档: https://redis.io/docs/
- Celery 官方文档: https://docs.celeryq.dev/
- Django + Celery 集成: https://docs.celeryq.dev/en/stable/django/

---

**提示**: 在 macOS M2 芯片上运行 Celery 时，**必须使用 `-P solo` 参数**，否则会出现错误！

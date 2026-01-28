# Redis 和 Celery 配置完成总结

## ✅ 已完成的工作

**日期**: 2026-01-28
**系统**: macOS M2 芯片

---

## 🎉 成功完成！

### 1. **Redis 安装和配置** ✅
- ✅ 使用 Homebrew 安装 Redis 8.4.0
- ✅ 启动 Redis 服务（作为后台服务运行）
- ✅ 验证 Redis 连接成功（`redis-cli ping` 返回 `PONG`）
- ✅ 设置 Redis 开机自启动

### 2. **Celery 配置验证** ✅
- ✅ 验证 Celery 和 Redis 连接正常
- ✅ 确认 Celery 配置正确
  - Broker: `redis://127.0.0.1:6379/0`
  - Result Backend: `redis://127.0.0.1:6379/0`
  - Timezone: `Asia/Shanghai`

### 3. **创建的文件** ✅

#### 文档文件
- `REDIS_SETUP_GUIDE.md` - Redis 完整安装和使用指南

#### 启动脚本
- `start_celery_worker.sh` - Celery Worker 启动脚本
- `start_celery_beat.sh` - Celery Beat 启动脚本

#### 测试脚本
- `test_celery_redis.py` - Redis 和 Celery 连接测试

---

## 🚀 快速启动指南

### 方式 1：使用启动脚本（推荐）

```bash
# 进入项目目录
cd /Users/xiejunliang/Documents/stock/vueStockapi

# 启动 Celery Worker（在一个终端窗口）
./start_celery_worker.sh

# 启动 Celery Beat（在另一个终端窗口，可选）
./start_celery_beat.sh
```

### 方式 2：手动启动

```bash
# 确保 Redis 正在运行
redis-cli ping
# 应返回: PONG

# 启动 Celery Worker
uv run celery -A vueStockapi worker -l info -P solo

# 启动 Celery Beat（另一个终端）
uv run celery -A vueStockapi beat -l info
```

---

## 📊 服务状态检查

### 检查 Redis 状态

```bash
# 查看 Redis 服务状态
brew services list | grep redis

# 测试 Redis 连接
redis-cli ping

# 查看 Redis 信息
redis-cli info server
```

### 检查 Celery 状态

```bash
# 运行测试脚本
uv run python test_celery_redis.py

# 查看注册的任务
uv run celery -A vueStockapi inspect registered

# 查看活跃的任务
uv run celery -A vueStockapi inspect active
```

---

## ⚠️ 重要提示

### macOS M2 芯片特殊要求

**必须使用 `-P solo` 参数启动 Celery Worker！**

```bash
# ✅ 正确
uv run celery -A vueStockapi worker -l info -P solo

# ❌ 错误（会在 M2 芯片上失败）
uv run celery -A vueStockapi worker -l info
```

**原因**: macOS M2 芯片的 ARM 架构与 Celery 的默认 `prefork` 池模式不兼容。使用 `solo` 模式可以避免这个问题。

---

## 🧪 验证测试结果

运行 `test_celery_redis.py` 的测试结果：

```
【测试 1】Redis 连接测试
✅ Redis 连接成功！Response: True
✅ Redis 读写测试成功！

【测试 2】Celery 配置检查
✅ Celery 配置正确
Broker URL: redis://127.0.0.1:6379/0
Result Backend: redis://127.0.0.1:6379/0
Timezone: Asia/Shanghai

【测试 3】Celery Application 测试
✅ Celery App 创建成功
```

---

## 📋 已注册的 Celery 任务

项目中已配置的任务：

1. **backtest 应用**:
   - `backtest.tasks.run_portfolio_backtest` - 运行投资组合回测

2. **basic 应用**:
   - `basic.tasks.analyze_stock_patterns` - 分析股票模式
   - `basic.tasks.analyze_trading_signals_daily` - 每日交易信号分析
   - `basic.tasks.analyze_trading_signals_weekly` - 每周交易信号分析
   - `basic.tasks.daily_data_update` - 每日数据更新
   - `basic.tasks.daily_stats_analysis` - 每日统计分析
   - `basic.tasks.daily_strategy_analysis` - 每日策略分析
   - `basic.tasks.monitor_task_status` - 监控任务状态
   - `basic.tasks.run_daily_analysis_chain` - 运行每日分析链
   - `basic.tasks.update_daily_data_and_signals` - 更新每日数据和信号

3. **调试任务**:
   - `vueStockapi.celery.debug_task` - 调试任务

---

## 🔧 定时任务配置

项目中已配置的定时任务（Celery Beat）：

**任务名称**: `update-daily-data-and-signals`
- **任务**: `basic.tasks.update_daily_data_and_signals`
- **执行时间**: 每周一至周五 17:00
- **队列**: default

---

## 🛠️ 常用命令

### Redis 管理

```bash
# 启动 Redis
brew services start redis

# 停止 Redis
brew services stop redis

# 重启 Redis
brew services restart redis

# 查看 Redis 状态
brew services list | grep redis

# 连接到 Redis CLI
redis-cli

# 清空所有数据（谨慎使用！）
redis-cli FLUSHALL
```

### Celery 管理

```bash
# 启动 Worker
uv run celery -A vueStockapi worker -l info -P solo

# 启动 Beat
uv run celery -A vueStockapi beat -l info

# 同时启动 Worker 和 Beat
uv run celery -A vueStockapi worker -l info -P solo --beat

# 查看注册的任务
uv run celery -A vueStockapi inspect registered

# 查看活跃的任务
uv run celery -A vueStockapi inspect active

# 查看计划任务
uv run celery -A vueStockapi inspect scheduled

# 查看 Worker 状态
uv run celery -A vueStockapi inspect stats

# 停止所有 Celery 进程
pkill -f "celery worker"
```

---

## 📁 相关文件位置

### 配置文件
- Django 设置: `vueStockapi/settings.py`
- Celery 配置: `vueStockapi/celery.py`
- 环境变量: `.env`

### Redis 配置
- 配置文件: `/opt/homebrew/etc/redis.conf`
- 数据目录: `/opt/homebrew/var/db/redis/`
- 日志文件: `/opt/homebrew/var/log/redis.log`

### 启动脚本
- `start_celery_worker.sh` - Worker 启动脚本
- `start_celery_beat.sh` - Beat 启动脚本
- `test_celery_redis.py` - 测试脚本

---

## 🐛 常见问题解决

### 问题 1: 连接 Redis 失败

**错误**: `Error 61 connecting to 127.0.0.1:6379. Connection refused.`

**解决方案**:
```bash
# 检查 Redis 是否运行
brew services list | grep redis

# 如果没有运行，启动它
brew services start redis

# 验证连接
redis-cli ping
```

### 问题 2: Celery Worker 启动失败（M2 芯片）

**错误**: `ValueError: not enough values to unpack`

**解决方案**:
必须使用 `-P solo` 参数：
```bash
uv run celery -A vueStockapi worker -l info -P solo
```

### 问题 3: 找不到任务

**解决方案**:
```bash
# 检查任务是否正确导入
uv run celery -A vueStockapi inspect registered

# 确保任务模块在 INSTALLED_APPS 中
# 检查 vueStockapi/celery.py 中的 autodiscover_tasks()
```

---

## 🎯 下一步建议

1. **测试定时任务**:
   ```bash
   # 启动 Beat 调度器
   ./start_celery_beat.sh
   
   # 查看计划任务
   uv run celery -A vueStockapi inspect scheduled
   ```

2. **监控任务执行**:
   - 查看 Celery Worker 日志
   - 使用 `celery inspect` 命令监控任务状态
   - 可以考虑安装 Flower（Celery 监控工具）

3. **生产环境部署**:
   - 使用 supervisord 或 systemd 管理 Celery 进程
   - 配置日志轮转
   - 设置错误告警

4. **性能优化**:
   - 根据需求调整 worker 并发数
   - 配置任务优先级和队列
   - 启用任务结果过期

---

## ✅ 完成清单

- [x] Redis 安装成功
- [x] Redis 服务启动
- [x] Redis 开机自启动配置
- [x] Celery 配置验证
- [x] Celery 和 Redis 连接测试
- [x] 创建启动脚本
- [x] 文档完成

---

## 📚 参考文档

- **Redis 完整指南**: `REDIS_SETUP_GUIDE.md`
- **多数据库迁移指南**: `MYSQL_MIGRATION_GUIDE.md`
- **迁移完成总结**: `MYSQL_MIGRATION_SUMMARY.md`

---

**恭喜！Redis 和 Celery 已经配置完成，可以正常使用了！** 🎉

现在您可以运行：
```bash
./start_celery_worker.sh
```

来启动 Celery Worker，开始处理异步任务！

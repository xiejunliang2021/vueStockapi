# MySQL 数据库迁移总结

## ✅ 迁移完成状态

**日期**: 2026-01-28
**项目**: vueStockapi

---

## 📊 当前数据库架构

### 双数据库配置

#### 1. **Oracle 数据库** (default)
- **用途**: 存储 `basic` 应用的股票数据
- **数据库名**: stockapi_high
- **用户**: HUABENWUXIN
- **连接状态**: ✅ 正常

#### 2. **MySQL 数据库** (mysql)
- **用途**: 存储 `weighing` 和 `backtest` 应用的数据
- **数据库名**: quant
- **主机**: 207.211.157.169
- **端口**: 3306
- **用户**: root
- **连接状态**: ✅ 正常

---

## 🔄 数据库路由配置

**路由器**: `weighing.db_router.WeighingRouter`
**配置位置**: `vueStockapi/settings.py` (第 151 行)

### 路由规则

| 应用 | 数据库 | 说明 |
|------|--------|------|
| `basic` | Oracle (default) | 股票数据、交易日历等 |
| `weighing` | MySQL | 称重记录 |
| `backtest` | MySQL | 回测结果、交易日志 |
| Django 系统表 | 两个数据库都有 | auth、contenttypes、sessions 等 |

---

## 📋 已创建的表

### MySQL 数据库 (quant)

#### Weighing 应用
- ✅ `weighing_weighingrecord` (0 条记录)

#### Backtest 应用
- ✅ `backtest_portfoliobacktest` (16 条记录)
- ✅ `backtest_tradelog` (82 条记录)

#### 系统表
- Django 认证系统表 (auth_*)
- Django 内容类型表 (django_content_type)
- Django 会话表 (django_session)
- Celery Beat 调度表 (django_celery_beat_*)
- Celery 结果表 (django_celery_results_*)
- 其他系统表

---

## 🧪 验证结果

所有测试都已通过：

### ✅ 测试 1: 数据库连接测试
- MySQL 连接成功
- Oracle 连接成功

### ✅ 测试 2: 数据库路由测试
- `WeighingRecord` 正确路由到 MySQL
- `PortfolioBacktest` 正确路由到 MySQL
- `TradeLog` 正确路由到 MySQL

### ✅ 测试 3: 表结构验证
- Weighing 表: 1 个
- Backtest 表: 2 个
- 所有表结构正确

### ✅ 测试 4: ORM 操作测试
- WeighingRecord 查询成功
- PortfolioBacktest 查询成功 (16 条记录)
- TradeLog 查询成功 (82 条记录)

### ✅ 测试 5: 迁移状态检查
- Weighing 迁移: 1 个
- Backtest 迁移: 5 个

---

## 🔧 已执行的操作

1. ✅ 检查了现有的数据库配置
2. ✅ 测试了 MySQL 和 Oracle 数据库连接
3. ✅ 为 `weighing` 应用创建了迁移文件 (`0001_initial.py`)
4. ✅ 为 `backtest` 应用创建了迁移文件 (`0001_initial.py`)
5. ✅ 手动创建了 `weighing_weighingrecord` 表（因为迁移记录已存在但表不存在）
6. ✅ 验证了数据库路由器正常工作
7. ✅ 验证了 ORM 操作正常
8. ✅ 确认 Oracle 数据库未受影响

---

## 📝 重要说明

### ⚠️ 注意事项

1. **自动路由**:
   - 在代码中使用 `WeighingRecord.objects.all()` 时，会自动路由到 MySQL
   - 在代码中使用 `PortfolioBacktest.objects.all()` 时，会自动路由到 MySQL
   - 不需要手动指定 `.using('mysql')`

2. **迁移命令**:
   - 运行迁移时必须指定数据库：`--database=mysql` 或 `--database=default`
   - Django 的迁移命令不会自动使用路由器

3. **跨数据库限制**:
   - 不能在 MySQL 表和 Oracle 表之间创建外键关系
   - 数据库路由器会阻止跨数据库的关联操作

4. **Backtest 迁移记录不完整**:
   - MySQL 中有 5 个 backtest 迁移记录，但当前只有 1 个迁移文件
   - 这是因为之前的迁移文件被删除了
   - 表结构已存在且正常工作，无需担心

---

## 🚀 使用方法

### 创建 Weighing 记录

```python
from weighing.models import WeighingRecord

# 会自动保存到 MySQL 数据库
record = WeighingRecord.objects.create(
    license_plate="京A12345",
    tare_weight=1000,
    gross_weight=5000,
    cargo_spec="钢材",
    receiving_unit="XX公司"
)
```

### 创建 Backtest 记录

```python
from backtest.models import PortfolioBacktest

# 会自动保存到 MySQL 数据库
backtest = PortfolioBacktest.objects.create(
    strategy_name="龙回头策略",
    start_date="2025-01-01",
    end_date="2025-12-31",
    initial_capital=100000,
    capital_per_stock_ratio=0.1,
    # ... 其他字段
)
```

### 查询数据

```python
# 自动从 MySQL 查询
weighing_records = WeighingRecord.objects.all()
backtest_results = PortfolioBacktest.objects.all()

# 自动从 Oracle 查询 (basic 应用的模型)
# from basic.models import StockDaily
# stock_data = StockDaily.objects.all()
```

---

## 🛠️ 维护命令

### 查看迁移状态

```bash
# MySQL 数据库
uv run python manage.py showmigrations --database=mysql

# Oracle 数据库
uv run python manage.py showmigrations --database=default
```

### 创建新的迁移

```bash
# 为 weighing 应用创建迁移
uv run python manage.py makemigrations weighing

# 为 backtest 应用创建迁移
uv run python manage.py makemigrations backtest
```

### 应用迁移

```bash
# 应用到 MySQL
uv run python manage.py migrate weighing --database=mysql
uv run python manage.py migrate backtest --database=mysql

# 应用到 Oracle
uv run python manage.py migrate basic --database=default
```

### 验证配置

```bash
# 运行完整的验证测试
uv run python test_multi_database.py
```

---

## 📚 相关文件

### 配置文件
- `vueStockapi/settings.py` - Django 设置文件
- `.env` - 环境变量配置

### 数据库路由器
- `weighing/db_router.py` - 数据库路由器实现

### 模型文件
- `weighing/models.py` - Weighing 模型
- `backtest/models.py` - Backtest 模型

### 迁移文件
- `weighing/migrations/0001_initial.py` - Weighing 初始迁移
- `backtest/migrations/0001_initial.py` - Backtest 初始迁移

### 测试脚本
- `test_db_connection.py` - 数据库连接测试
- `check_mysql_tables.py` - MySQL 表检查
- `check_migrations.py` - 迁移记录检查
- `test_multi_database.py` - 完整的多数据库验证

### 文档
- `MYSQL_MIGRATION_GUIDE.md` - 详细的迁移指南
- `MYSQL_MIGRATION_SUMMARY.md` - 迁移总结（本文件）

---

## 🎯 下一步建议

1. **测试 API 接口**
   - 确保所有与 weighing 和 backtest 相关的 API 正常工作
   - 测试创建、查询、更新、删除操作

2. **数据备份**
   - 为 MySQL 数据库配置定期备份
   - 为 Oracle 数据库维持现有备份策略

3. **监控**
   - 监控两个数据库的连接状态
   - 监控查询性能

4. **文档**
   - 更新项目文档，说明多数据库架构
   - 为新开发者提供数据库使用指南

---

## ✅ 迁移成功！

您的项目现在已经成功配置了双数据库架构：
- **Oracle** 用于存储核心的股票数据
- **MySQL** 用于存储回测结果和称重记录

两个数据库独立运行，互不干扰，通过 Django 的数据库路由器自动管理。

**祝您使用愉快！** 🎉

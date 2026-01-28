# MySQL 数据库迁移指南

## 📊 项目数据库架构

### 当前配置
- **Oracle 数据库（default）**：存储 `basic` 应用的数据（股票数据、交易信号等）
- **MySQL 数据库（mysql）**：存储 `weighing` 和 `backtest` 应用的数据

### 数据库配置位置
- 配置文件：`vueStockapi/settings.py`（第 116-149 行）
- 环境变量：`.env` 文件
- 数据库路由器：`weighing/db_router.py`

---

## 🚀 迁移步骤

### 步骤 1：检查 MySQL 数据库连接

首先确认 MySQL 数据库可以正常连接：

```bash
# 在项目根目录执行
cd /Users/xiejunliang/Documents/stock/vueStockapi

# 使用 Django shell 测试连接
python manage.py shell
```

在 shell 中执行：
```python
from django.db import connections
conn = connections['mysql']
conn.ensure_connection()
print("MySQL 连接成功！")
```

### 步骤 2：检查已有的迁移文件

```bash
# 查看 weighing 应用的迁移文件
ls -la weighing/migrations/

# 查看 backtest 应用的迁移文件
ls -la backtest/migrations/
```

### 步骤 3：为 MySQL 应用创建迁移文件（如果需要）

如果 models.py 有更新，需要创建新的迁移文件：

```bash
# 为 weighing 应用创建迁移（指定使用 mysql 数据库）
python manage.py makemigrations weighing

# 为 backtest 应用创建迁移
python manage.py makemigrations backtest
```

### 步骤 4：执行迁移到 MySQL 数据库

**重要：使用 `--database=mysql` 参数指定目标数据库**

```bash
# 查看将要执行的迁移（不实际执行）
python manage.py migrate --database=mysql --plan

# 执行 weighing 应用的迁移到 MySQL
python manage.py migrate weighing --database=mysql

# 执行 backtest 应用的迁移到 MySQL
python manage.py migrate backtest --database=mysql

# 执行 Django 内置应用的迁移到 MySQL（如果需要）
python manage.py migrate --database=mysql
```

### 步骤 5：验证迁移结果

```bash
# 查看 MySQL 数据库的迁移状态
python manage.py showmigrations --database=mysql

# 使用 Django shell 验证表是否创建成功
python manage.py shell
```

在 shell 中执行：
```python
from weighing.models import WeighingRecord
from backtest.models import PortfolioBacktest, TradeLog

# 检查表是否存在
print(WeighingRecord.objects.using('mysql').count())
print(PortfolioBacktest.objects.using('mysql').count())
print(TradeLog.objects.using('mysql').count())
```

### 步骤 6：验证 Oracle 数据库不受影响

```bash
# 查看 Oracle 数据库的迁移状态
python manage.py showmigrations --database=default

# 使用 Django shell 验证
python manage.py shell
```

在 shell 中执行：
```python
from basic.models import *  # 导入 basic 应用的模型

# 验证 Oracle 数据库仍然正常工作
# 例如：检查股票数据
# StockDaily.objects.count()
```

---

## 📌 重要提示

### ⚠️ 注意事项

1. **数据库路由器会自动处理**：
   - 当您操作 `weighing` 或 `backtest` 模型时，Django 会自动使用 MySQL 数据库
   - 当您操作 `basic` 模型时，Django 会自动使用 Oracle 数据库

2. **不需要手动指定数据库**：
   ```python
   # ✅ 正确：会自动路由到 MySQL
   WeighingRecord.objects.all()
   
   # ❌ 不推荐：除非特殊需求，否则不需要手动指定
   WeighingRecord.objects.using('mysql').all()
   ```

3. **迁移命令必须指定数据库**：
   - Django 的迁移不会自动使用路由器
   - 必须显式指定 `--database=mysql` 或 `--database=default`

4. **跨数据库关系限制**：
   - 不能在 MySQL 表和 Oracle 表之间建立外键关系
   - 数据库路由器会阻止跨数据库的关联操作

### 🔍 常见问题排查

#### 问题 1：迁移时找不到 MySQL 数据库

**解决方案**：
```bash
# 检查 .env 文件中的 MySQL 配置
cat .env | grep MYSQL

# 确保以下变量已设置：
# USER_MYSQL=root
# PASSWORD_MYSQL=你的密码
# HOST=207.211.157.169
```

#### 问题 2：MySQL 连接被拒绝

**解决方案**：
```bash
# 测试 MySQL 连接
mysql -h 207.211.157.169 -u root -p

# 如果连接失败，检查：
# 1. MySQL 服务是否运行
# 2. 防火墙是否开放 3306 端口
# 3. MySQL 用户是否有远程访问权限
```

#### 问题 3：提示数据库 'quant' 不存在

**解决方案**：
```bash
# 连接到 MySQL 服务器
mysql -h 207.211.157.169 -u root -p

# 创建数据库
CREATE DATABASE quant CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

---

## 🧪 测试脚本

创建一个测试脚本验证多数据库配置：

```python
# test_multi_db.py
from django.db import connections
from weighing.models import WeighingRecord
from backtest.models import PortfolioBacktest

def test_databases():
    print("=== 测试数据库连接 ===")
    
    # 测试 MySQL 连接
    try:
        conn = connections['mysql']
        conn.ensure_connection()
        print("✅ MySQL 连接成功")
        print(f"   数据库名称: {conn.settings_dict['NAME']}")
        print(f"   主机: {conn.settings_dict['HOST']}")
    except Exception as e:
        print(f"❌ MySQL 连接失败: {e}")
    
    # 测试 Oracle 连接
    try:
        conn = connections['default']
        conn.ensure_connection()
        print("✅ Oracle 连接成功")
        print(f"   数据库名称: {conn.settings_dict['NAME']}")
    except Exception as e:
        print(f"❌ Oracle 连接失败: {e}")
    
    print("\n=== 测试数据库路由 ===")
    
    # 测试 weighing 模型路由
    db = WeighingRecord.objects.db
    print(f"WeighingRecord 模型使用数据库: {db}")
    
    # 测试 backtest 模型路由
    db = PortfolioBacktest.objects.db
    print(f"PortfolioBacktest 模型使用数据库: {db}")
    
    print("\n=== 测试完成 ===")

if __name__ == '__main__':
    import django
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')
    django.setup()
    test_databases()
```

运行测试：
```bash
python test_multi_db.py
```

---

## 📝 快速命令参考

```bash
# 1. 创建迁移文件
python manage.py makemigrations weighing backtest

# 2. 查看迁移计划（MySQL）
python manage.py migrate --database=mysql --plan

# 3. 执行迁移到 MySQL
python manage.py migrate --database=mysql

# 4. 查看迁移状态
python manage.py showmigrations --database=mysql
python manage.py showmigrations --database=default

# 5. 测试数据库连接
python manage.py shell
>>> from django.db import connections
>>> connections['mysql'].ensure_connection()
>>> connections['default'].ensure_connection()
```

---

## ✅ 迁移完成检查清单

- [ ] MySQL 数据库连接测试通过
- [ ] 迁移文件已创建（如有需要）
- [ ] 迁移已成功执行到 MySQL 数据库
- [ ] MySQL 数据库中的表已创建成功
- [ ] Oracle 数据库仍然正常工作
- [ ] 数据库路由器正确工作
- [ ] 应用程序可以正常读写两个数据库

---

## 🎯 下一步

迁移完成后，您可以：

1. **测试 API 接口**：确保应用可以正常访问两个数据库
2. **数据迁移**（如需要）：如果需要从 Oracle 迁移数据到 MySQL
3. **性能优化**：根据实际使用情况优化数据库配置
4. **备份策略**：为两个数据库设置定期备份

---

**需要帮助？** 如果遇到任何问题，请检查：
- Django 日志：`logs/db_debug.log`
- uWSGI 日志：`uwsgi.log.*`
- MySQL 日志：通常在 `/var/log/mysql/`

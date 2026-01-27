# UV 包管理器迁移指南

本项目已从 conda 环境迁移到 uv 包管理器。

## 什么是 UV?

uv 是一个极快的 Python 包管理器和项目管理工具,用 Rust 编写,比 pip 和 conda 快 10-100 倍。

## 安装 UV

```powershell
# 使用 pip 安装
pip install uv

# 或使用 PowerShell 脚本安装(推荐)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## 初始化项目环境

```powershell
# 进入项目目录
cd d:\xszr-stock\vueStockapi

# 创建 Python 3.10 虚拟环境
uv venv --python 3.10

# 激活虚拟环境
.venv\Scripts\activate

# 安装所有依赖
uv pip install -e .
```

## 日常使用

### 安装新包

```powershell
# 安装单个包
uv pip install package-name

# 安装并添加到 pyproject.toml
# 需要手动编辑 pyproject.toml 添加依赖
```

### 更新依赖

```powershell
# 更新所有包
uv pip install --upgrade -e .

# 更新单个包
uv pip install --upgrade package-name
```

### 同步环境

```powershell
# 重新安装所有依赖(清理环境)
uv pip sync
```

## 运行项目

### 启动 Django 开发服务器

```powershell
.venv\Scripts\activate
python manage.py runserver
```

### 启动 Celery Worker

```powershell
.venv\Scripts\activate
celery -A vueStockapi worker -l info -P eventlet
```

### 启动 Celery Beat

```powershell
.venv\Scripts\activate
celery -A vueStockapi beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

## 数据库迁移

```powershell
.venv\Scripts\activate

# MySQL 数据库迁移
python manage.py migrate --database=mysql

# 检查配置
python manage.py check
```

## 常见问题

### Q: mysqlclient 安装失败?

**A:** 在 Windows 上,`mysqlclient` 需要 Visual C++ 编译器。解决方案:

1. 安装 Visual Studio Build Tools
2. 或使用预编译的 wheel: https://www.lfd.uci.edu/~gohlke/pythonlibs/#mysqlclient
3. 或在 Django settings 中配置使用 `pymysql`:

```python
import pymysql
pymysql.install_as_MySQLdb()
```

### Q: Oracle 连接失败?

**A:** 确保已安装 Oracle Instant Client 并配置了钱包:

```powershell
# 检查环境变量
echo $env:WALLET_LOCATION
echo $env:WALLET_DIRECTORY
```

### Q: 如何回退到 conda?

**A:** conda 环境仍然保留,可以随时切换:

```powershell
conda activate stockapi
```

## 性能对比

| 操作 | conda | uv |
|------|-------|-----|
| 安装所有依赖 | ~5-10 分钟 | ~30-60 秒 |
| 安装单个包 | ~10-30 秒 | ~1-3 秒 |
| 解析依赖 | ~30 秒 | ~1 秒 |

## 迁移前后对比

### 之前 (conda)

```bash
conda env create -f environment.yml
conda activate stockapi
```

### 现在 (uv)

```powershell
uv venv --python 3.10
.venv\Scripts\activate
uv pip install -e .
```

## 更多资源

- UV 官方文档: https://docs.astral.sh/uv/
- UV GitHub: https://github.com/astral-sh/uv

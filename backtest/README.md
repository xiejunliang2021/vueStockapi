# Backtest 应用使用手册

**股票回测系统 - 完整功能文档**

## 📋 目录

- [系统概述](#系统概述)
- [核心功能](#核心功能)
- [架构设计](#架构设计)
- [快速开始](#快速开始)
- [API 接口](#api-接口)
- [回测策略](#回测策略)
- [数据模型](#数据模型)
- [配置说明](#配置说明)
- [高级功能](#高级功能)
- [故障排查](#故障排查)

---

## 系统概述

`backtest` 应用是一个专业的量化交易回测系统，支持多种回测引擎和交易策略。系统基于 Django + Celery + Backtrader 构建，提供完整的组合管理、资金控制和绩效分析功能。

### 主要特点

- ✅ **双引擎支持**：自定义引擎 + Backtrader 专业引擎
- ✅ **多策略实现**：龙回头、连续涨停等成熟策略
- ✅ **异步执行**：基于 Celery 的异步任务队列
- ✅ **组合回测**：真实模拟投资组合资金管理
- ✅ **完整记录**：详细的交易日志和绩效指标
- ✅ **自动筛选**：排除 ST 股票、创业板等

---

## 核心功能

### 1. 组合级别回测

以统一资金池进行组合回测，模拟真实投资场景：
- 初始资金统一管理
- 按比例分配单票资金
- 动态跟踪可用现金
- 自动计算持仓市值

### 2. 双引擎架构

**自定义引擎** (`BacktestService`)
- 基于 Pandas 实现
- 轻量级、灵活度高
- 适合快速验证策略逻辑

**Backtrader 引擎** (`BacktraderBacktestService`)
- 专业回测框架
- 完整的订单管理系统
- 精确的滑点和佣金模拟
- 丰富的技术指标支持

### 3. 策略库

#### 龙回头策略 (`DragonTurnStrategy`)
**信号逻辑**：
1. 检测强势股票信号
2. 设定第一/第二买点
3. 止盈/止损点位管理
4. 超时自动平仓

**适用场景**：短线强势股回调买入

#### 连续涨停策略 (`LimitBreakStrategy`)
**形态识别**：
1. 连续 ≥2 天涨停
2. 随后连续 2 天阴线下跌
3. 回溯 15 天计算平均买点
4. 触达买点时限价买入

**适用场景**：追涨停板后的回调机会

### 4. 资金管理

- **初始资金**：`total_capital` 参数设定
- **单票占比**：`capital_per_stock_ratio` 控制（如 0.1 = 10%）
- **持仓控制**：同时持有多只股票
- **现金管理**：买入扣款、卖出回款自动处理

### 5. 风险控制

- **止盈止损**：每个策略独立设定
- **持仓超时**：`hold_timeout_days` 强制平仓
- **股票过滤**：自动排除 ST、创业板（300开头）
- **最大回撤**：实时监控组合最大回撤

### 6. 绩效分析

**组合指标**：
- 最终资金 (`final_capital`)
- 总盈利 (`total_profit`)
- 总收益率 (`total_return`)
- 最大回撤 (`max_drawdown`)
- 最大盈利 (`max_profit`)
- 胜率 (`win_rate`)

**交易明细**：
- 买入/卖出日期、价格
- 持仓数量、天数
- 单笔盈亏、收益率
- 卖出原因（止盈/止损/超时）

---

## 架构设计

### 系统架构图

```
┌─────────────┐      ┌──────────────┐      ┌─────────────┐
│   前端 API   │─────▶│  Django View │─────▶│ Celery Task │
│   请求      │      │   验证参数   │      │  异步执行   │
└─────────────┘      └──────────────┘      └─────────────┘
                                                   │
                     ┌─────────────────────────────┼─────────────────────┐
                     ▼                             ▼                     ▼
              ┌─────────────┐            ┌──────────────────┐   ┌──────────────┐
              │BacktestService│          │BacktraderService │   │StrategyService│
              │  自定义引擎  │            │  Backtrader引擎  │   │  信号获取   │
              └─────────────┘            └──────────────────┘   └──────────────┘
                     │                             │                     │
                     └─────────────────────────────┼─────────────────────┘
                                                   ▼
                                          ┌─────────────────┐
                                          │  数据库持久化  │
                                          │ PortfolioBacktest│
                                          │    TradeLog     │
                                          └─────────────────┘
```

### 目录结构

```
backtest/
├── models.py                    # 数据模型（回测结果、交易日志）
├── views.py                     # API 视图
├── tasks.py                     # Celery 异步任务
├── serializers.py               # 请求/响应序列化器
├── urls.py                      # 路由配置
├── services/
│   ├── backtest_service.py     # 自定义回测引擎
│   ├── backtrader_service.py   # Backtrader 回测引擎
│   └── oracle_data_service.py  # Oracle 数据源服务
├── strategies.py                # Backtrader 基础策略
├── strategies_backtrader.py    # 龙回头策略（Backtrader版）
├── strategies_limit_break.py   # 连续涨停策略（Backtrader版）
├── data_feeds.py               # 自定义数据源
├── utils.py                    # 工具函数
├── bt_test_01.py               # 独立测试脚本（连续涨停）
└── tests.py                    # 单元测试
```

### 核心类说明

**Portfolio** (`backtest_service.py`)
- 管理投资组合资金
- 执行买入/卖出操作
- 计算总资产和收益

**Position** (`backtest_service.py`)
- 单只股票持仓信息
- 买入日期、价格、数量
- 策略类型标记

**BacktestStrategy** (`backtest_service.py`)
- 策略基类
- 定义买入/卖出判断接口
- 各策略继承实现具体逻辑

---

## 快速开始

### 环境准备

1. **安装依赖**
```bash
pip install django celery redis backtrader pandas
```

2. **启动 Redis**
```bash
# Windows
cd C:\Redis
redis-server.exe

# Linux/Mac
redis-server
```

3. **启动 Celery Worker**
```bash
cd D:\xszr-stock\vueStockapi
celery -A vueStockapi worker -l info -P eventlet
```

4. **（可选）启动 Celery Beat**
```bash
celery -A vueStockapi beat -l info
```

### 第一次回测

```bash
curl -X POST http://127.0.0.1:8000/api/backtest/portfolio/run/ \
-H "Content-Type: application/json" \
-d '{
    "filters": {
        "strategy_name": "测试回测-龙回头",
        "strategy_type": "龙回头",
        "start_date": "2023-01-01",
        "end_date": "2023-06-30"
    },
    "backtest_params": {
        "total_capital": 1000000,
        "capital_per_stock_ratio": 0.1,
        "hold_timeout_days": 60,
        "db_alias": "default",
        "use_backtrader": false
    }
}'
```

---

## API 接口

### 1. 执行组合回测

**端点**：`POST /api/backtest/portfolio/run/`

**请求体**：
```json
{
    "filters": {
        "strategy_name": "策略名称",
        "strategy_type": "龙回头",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31"
    },
    "backtest_params": {
        "total_capital": 1000000,
        "capital_per_stock_ratio": 0.1,
        "hold_timeout_days": 60,
        "db_alias": "default",
        "use_backtrader": false,
        "commission": 0.0003
    }
}
```

**参数说明**：

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `filters.strategy_name` | string | ✅ | - | 回测策略名称（唯一标识） |
| `filters.strategy_type` | string | ❌ | "龙回头" | 策略类型 |
| `filters.start_date` | date | ✅ | - | 回测开始日期 (YYYY-MM-DD) |
| `filters.end_date` | date | ✅ | - | 回测结束日期 (YYYY-MM-DD) |
| `backtest_params.total_capital` | number | ✅ | - | 初始资金（元） |
| `backtest_params.capital_per_stock_ratio` | number | ✅ | - | 单票资金占比 (0.0-1.0) |
| `backtest_params.hold_timeout_days` | integer | ✅ | - | 最大持仓天数 |
| `backtest_params.db_alias` | string | ✅ | "default" | 数据库别名 |
| `backtest_params.use_backtrader` | boolean | ❌ | false | 是否使用 Backtrader 引擎 |
| `backtest_params.commission` | number | ❌ | 0.0003 | 佣金率（仅 Backtrader） |

**响应示例**：
```json
{
    "message": "组合回测任务已启动",
    "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

### 2. 查询回测结果

**端点**：`GET /api/backtest/portfolio/results/`

**查询参数**：
- `strategy_name`: 策略名称过滤
- `start_date`: 开始日期过滤
- `end_date`: 结束日期过滤

**响应示例**：
```json
[
    {
        "id": 1,
        "strategy_name": "龙回头策略-2023上半年",
        "start_date": "2023-01-01",
        "end_date": "2023-06-30",
        "initial_capital": "1000000.00",
        "final_capital": "1085000.00",
        "total_profit": "85000.00",
        "total_return": "0.0850",
        "max_drawdown": "-0.0320",
        "max_profit": "120000.00",
        "total_trades": 45,
        "winning_trades": 28,
        "losing_trades": 17,
        "win_rate": "0.6222",
        "created_at": "2023-07-01T10:30:00Z"
    }
]
```

---

## 回测策略

### 龙回头策略详解

**策略原理**：
在强势股票回调到关键支撑位时买入，设定明确的止盈止损。

**信号来源**：
从 `basic_policydetails` 表读取预先计算的买卖点信号。

**买入条件**：
1. 当日最低价 ≤ 第一买点 (`first_buy_point`)
2. 未超过买入期限（信号日后 10 天内）
3. 有足够资金（单票占比 × 当前现金）

**卖出条件**（优先级从高到低）：
1. **止盈**：最高价 ≥ 止盈点 (`take_profit_point`)
2. **止损**：最低价 ≤ 止损点 (`stop_loss_point`)
3. **超时**：持仓天数 ≥ `hold_timeout_days`

**参数配置**：
```python
{
    "first_buy_point": 12.50,      # 第一买点
    "second_buy_point": 11.80,     # 第二买点（暂未启用）
    "take_profit_point": 14.20,    # 止盈点
    "stop_loss_point": 11.00,      # 止损点
    "signal_date": "2023-03-15"    # 信号产生日期
}
```

### 连续涨停策略详解

**策略原理**：
识别连续涨停后的回调形态，在回调到平均成本位时买入。

**形态识别**：
```
┌──────┬──────┬──────┬──────┬──────┐
│ ZT1  │ ZT2  │ D1   │ D2   │等待买入│
│涨停  │涨停  │阴线  │阴线  │触达买点│
└──────┴──────┴──────┴──────┴──────┘
```

**买点计算**：
1. 从第一个涨停日（ZT1）向前回溯 15 天
2. 计算这 15 天的平均收盘价
3. 作为目标买入价 (`target_buy_price`)

**买入条件**：
1. 形态确认：ZT1 → ZT2 → D1 → D2
2. 当日最低价 ≤ 目标买入价
3. 优先使用开盘价（如果开盘价 < 买点）

**卖出条件**：
- 持仓超时：默认 30 天强制平仓
- 止盈目标：收益率达到设定值

**涨停判定**：
```python
up_limit = 1 if (close - prev_close) / prev_close > 0.096 else 0
```

**特殊逻辑**：
- 买入后记录与买点的最小差值
- 跟踪最小差值出现的日期
- 统计从买点确定到最小差值的天数

---

## 数据模型

### PortfolioBacktest（组合回测结果）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | AutoField | 主键 |
| `strategy_name` | CharField(100) | 策略名称（索引） |
| `start_date` | DateField | 回测开始日期 |
| `end_date` | DateField | 回测结束日期 |
| `initial_capital` | Decimal(15,2) | 初始资金 |
| `capital_per_stock_ratio` | Decimal(5,4) | 单票资金占比 |
| `final_capital` | Decimal(15,2) | 最终资金 |
| `total_profit` | Decimal(15,2) | 总盈利 |
| `total_return` | Decimal(10,4) | 总收益率 |
| `max_drawdown` | Decimal(10,4) | 最大回撤 |
| `max_profit` | Decimal(15,2) | 最大盈利 |
| `total_trades` | Integer | 总交易次数 |
| `winning_trades` | Integer | 盈利次数 |
| `losing_trades` | Integer | 亏损次数 |
| `win_rate` | Decimal(5,4) | 胜率 |
| `created_at` | DateTimeField | 创建时间 |

### TradeLog（交易日志）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | AutoField | 主键 |
| `portfolio_backtest` | ForeignKey | 所属回测（外键） |
| `stock_code` | CharField(20) | 股票代码 |
| `buy_date` | DateField | 买入日期 |
| `buy_price` | Decimal(10,2) | 买入价格 |
| `sell_date` | DateField | 卖出日期 |
| `sell_price` | Decimal(10,2) | 卖出价格 |
| `sell_reason` | CharField(20) | 卖出原因（止盈/止损/超时） |
| `quantity` | Integer | 买入数量 |
| `profit` | Decimal(15,2) | 单笔盈利 |
| `return_rate` | Decimal(10,4) | 单笔收益率 |
| `strategy_type` | CharField(50) | 策略类型 |
| `hold_days` | Integer | 持仓天数 |
| `min_diff_to_target` | Decimal(10,2) | 最小差值（连续涨停策略） |
| `min_diff_date` | DateField | 最小差值日期 |
| `days_to_min_diff` | Integer | 距买点确定天数 |

---

## 配置说明

### Celery 配置

**vueStockapi/settings.py**：
```python
# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Shanghai'
```

### 数据库配置

**多数据库支持**：
```python
DATABASES = {
    'default': {  # MySQL - 回测结果
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'stock_db',
        ...
    },
    'oracle': {   # Oracle - 历史数据
        'ENGINE': 'django.db.backends.oracle',
        'NAME': 'ORCL',
        ...
    }
}
```

### 策略参数配置

**自定义引擎**（`backtest_service.py`）：
```python
class DragonTurnStrategy(BacktestStrategy):
    def __init__(self, hold_timeout_days: int = 60):
        self.hold_timeout_days = hold_timeout_days
```

**Backtrader 引擎**（`strategies_backtrader.py`）：
```python
class DragonTurnBacktraderStrategy(bt.Strategy):
    params = (
        ('first_buy_point', None),
        ('take_profit_point', None),
        ('stop_loss_point', None),
        ('hold_timeout_days', 60),
        ...
    )
```

---

## 高级功能

### 1. 切换回测引擎

**使用自定义引擎**：
```json
{
    "backtest_params": {
        "use_backtrader": false
    }
}
```

**使用 Backtrader 引擎**：
```json
{
    "backtest_params": {
        "use_backtrader": true,
        "commission": 0.0003
    }
}
```

### 2. 运行连续涨停策略

目前连续涨停策略主要通过独立脚本 `bt_test_01.py` 运行：

```bash
cd D:\xszr-stock\vueStockapi\backtest
python bt_test_01.py
```

**关键配置**：
```python
# bt_test_01.py 中的参数
INITIAL_CASH = 1000000        # 初始资金
PROFIT_TARGET = 0.05          # 止盈目标 5%
MAX_HOLD_DAYS = 30            # 最大持仓天数
LOOKBACK_DAYS = 15            # 买点回溯天数
MAX_WAIT_DAYS = 100           # 最大等待买入天数
POSITION_PCT = 0.02           # 单票仓位 2%
COMMISSION = 0.001            # 佣金率 0.1%
```

### 3. 自定义策略开发

**步骤**：
1. 继承 `BacktestStrategy` 基类
2. 实现 `should_buy()` 和 `should_sell()` 方法
3. 在 `BacktestService.run_backtest()` 中注册

**示例**：
```python
class MyCustomStrategy(BacktestStrategy):
    def __init__(self, my_param: int = 10):
        self.my_param = my_param
    
    def should_sell(self, position, current_price_data, current_date, signal=None):
        # 自定义卖出逻辑
        ...
        return (should_sell, sell_reason)
    
    def should_buy(self, signal, current_price_data, current_date):
        # 自定义买入逻辑
        ...
        return (should_buy, buy_price)
```

### 4. Oracle 数据源集成

**OracleDataService** (`oracle_data_service.py`)：
- 从 Oracle 数据库读取历史行情
- 支持批量股票数据加载
- 转换为 Pandas DataFrame 格式

**使用示例**：
```python
oracle_service = OracleDataService()
data = oracle_service.fetch_stock_data(
    stock_code='600000',
    start_date=date(2023, 1, 1),
    end_date=date(2023, 12, 31)
)
```

---

## 故障排查

### 常见问题

**1. Celery Worker 无法启动**
```
错误：Celery.exceptions.ImproperlyConfigured
```
解决：检查 Redis 是否启动
```bash
redis-cli ping  # 应返回 PONG
```

**2. 回测任务一直等待**
```
状态：PENDING
```
解决：确认 Worker 正在运行并监听正确的队列
```bash
celery -A vueStockapi inspect active
```

**3. 数据库连接错误**
```
错误：InterfaceError: ORA-xxxxx
```
解决：
- 检查 Oracle 客户端安装
- 验证数据库配置（`settings.py` 中的 `DATABASES`）
- 确认 `db_alias` 参数正确

**4. 找不到策略信号**
```
日志：找到 0 个信号
```
解决：
- 确认 `basic_policydetails` 表有数据
- 检查日期范围是否正确
- 验证 `db_alias` 参数

**5. 回测结果为空**
```
final_capital = initial_capital
total_trades = 0
```
可能原因：
- 所有股票被过滤（ST、创业板）
- 日期范围内无符合条件的交易
- 买点设置不合理

### 调试建议

**1. 启用详细日志**
```python
# settings.py
LOGGING = {
    'version': 1,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'backtest': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

**2. 查看 Celery 日志**
Worker 启动时添加 `-l debug`：
```bash
celery -A vueStockapi worker -l debug -P eventlet
```

**3. 数据库查询验证**
```sql
-- 检查信号数据
SELECT COUNT(*) FROM basic_policydetails
WHERE signal_date BETWEEN '2023-01-01' AND '2023-06-30';

-- 检查回测结果
SELECT * FROM backtest_portfoliobacktest
ORDER BY created_at DESC
LIMIT 5;
```

**4. 单独测试组件**
```python
# 测试策略服务
from datetime import date
from basic.services.strategy_service import StrategyService

service = StrategyService(db_alias='default')
signals = service.get_signals_for_backtest(
    start_date=date(2023, 1, 1),
    end_date=date(2023, 6, 30),
    strategy_type='龙回头'
)
print(f"找到 {len(signals)} 个信号")
```

---

## 附录

### 相关文档

- [longhuitou.md](longhuitou.md) - 龙回头策略详细需求文档
- [bt_test_01.py](bt_test_01.py) - 连续涨停策略独立测试脚本

### 依赖版本

- Django >= 3.2
- Celery >= 5.0
- Redis >= 5.0
- Backtrader >= 1.9
- Pandas >= 1.3
- cx_Oracle >= 8.0 (如使用 Oracle)

### 联系方式

如有问题或建议，请通过项目 Issue 反馈。

---

**最后更新**：2026-01-23

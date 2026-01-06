# backtest 应用使用文档 (v2.0 - 组合回测)

本文档旨在详细说明 `backtest` 应用最新的**组合回测**功能、使用方法和技术细节，以帮助开发者和用户更好地理解和使用本应用。

## 1. 核心功能

`backtest` 应用提供了一个事件驱动的、基于投资组合的量化回测框架。它不再使用 `backtrader`，而是通过原生的 Pandas 和 Python 实现，以支持更灵活的组合管理和策略。

其核心功能如下：

1.  **组合级别回测**：以统一的资金（`total_capital`）开始，模拟真实的投资组合操作，所有买卖决策都会影响总资金。
2.  **资金管理**：支持设置单只股票的资金分配比例（`capital_per_stock_ratio`），实现仓位控制。
3.  **股票筛选**：在回测开始时，会自动从信号源中排除 **ST 股票**和**创业板股票**（代码以 '300' 开头）。
4.  **丰富的指标计算**：除了单笔交易的盈亏，还能计算整个投资组合在回测期间的：
    *   **总盈利 / 总亏损**
    *   **最终资金**
    *   **最大回撤 (Max Drawdown)**
    *   **最大盈利 (Max Profit)**
    *   **胜率**
5.  **异步执行**：所有回测任务都通过 Celery 异步执行，API 调用会立即返回，不阻塞前端。
6.  **结构化结果存储**：回测结果被存储在两个新的数据表中：
    *   `portfolio_backtest`: 存储每一次组合回测的总览报告和核心指标。
    *   `trade_log`: 存储该次组合回测下的每一笔详细交易记录。

## 2. 使用前的准备

在调用回测接口之前，请确保完成以下准备工作：

1.  **准备基础数据**：回测策略依赖于历史数据。请确保以下数据表中有完整的数据：
    *   `basic_coded` (Code): 股票基础信息。
    *   `basic_stockdailydata` (StockDailyData): 股票的每日交易数据。
    *   `basic_policydetails` (PolicyDetails): 策略信号数据。

2.  **启动 Redis**：Redis 作为 Celery 的消息代理（Broker），必须处于运行状态。
    *   **启动 Redis 服务** (需进入 Redis 安装目录):
        ```bash
        redis-server.exe
        ```
    *   **关闭 Redis 服务**:
        ```bash
        redis-cli.exe shutdown
        ```

3.  **启动 Celery**：你需要分别启动 **Worker** 和 **Beat** 两个进程。
    *   **Celery Worker (任务执行者)**: 负责执行回测任务。
        - **启动 Worker** (在项目根目录 `D:\vueStockapi` 运行):
          ```bash
          celery -A vueStockapi worker -l info -P eventlet
          ```
        - **关闭 Worker**: 在运行 Worker 的命令行窗口中，按下 `Ctrl + C`。

    *   **Celery Beat (定时任务调度器)**: 负责触发项目中的其他定时任务（当前回测功能不依赖它，但建议保持运行）。
        - **启动 Beat** (在项目根目录 `D:\vueStockapi` 运行):
          ```bash
          celery -A vueStockapi beat -l info
          ```
        - **关闭 Beat**: 在运行 Beat 的命令行窗口中，按下 `Ctrl + C`。

## 3. API 接口与参数

通过调用新的 API 端点发起组合回测任务。

-   **Endpoint**: `POST /api/backtest/portfolio/run/`
-   **Content-Type**: `application/json`

### 请求体 (Request Body)

```json
{
    "filters": {
        "strategy_name": "我的第一次组合回测",
        "start_date": "2023-01-01",
        "end_date": "2023-06-30"
    },
    "backtest_params": {
        "total_capital": 1000000,
        "capital_per_stock_ratio": 0.1,
        "hold_timeout_days": 20,
        "db_alias": "default"
    }
}
```

### 参数详解

| 字段路径                      | 类型    | 是否必须 | 描述                                                               |
| ----------------------------- | ------- | -------- | ------------------------------------------------------------------ |
| `filters.strategy_name`       | string  | 是       | 为本次回测命名，方便后续查询结果。                                 |
| `filters.start_date`          | string  | 是       | 回测开始日期，格式 `YYYY-MM-DD`。                                  |
| `filters.end_date`            | string  | 是       | 回测结束日期，格式 `YYYY-MM-DD`。                                  |
| `backtest_params.total_capital` | number  | 是       | 初始总资金，例如 `1000000`。                                       |
| `backtest_params.capital_per_stock_ratio` | number  | 是       | 单只股票资金占比，0到1之间的小数。例如 `0.1` 代表每次最多用10%的总资金。 |
| `backtest_params.hold_timeout_days` | integer | 是       | 单只股票的最大持有天数，超过后将强制卖出。                         |
| `backtest_params.db_alias`    | string  | 是       | 存放策略信号 (`PolicyDetails`) 的数据库别名，通常是 `default`。    |

## 4. 如何使用及示例

### 步骤

1.  确保 Redis 和 Celery Worker 正在运行。
2.  使用 HTTP 客户端（如 `curl`）向 `POST /api/backtest/portfolio/run/` 发送请求。
3.  API 返回成功信息和 `task_id` 后，等待后台任务执行完成。
4.  任务完成后，在数据库的 `backtest_portfoliobacktest` 和 `backtest_tradelog` 表中查询结果。

### 使用 `curl` 的示例

```bash
curl -X POST http://127.0.0.1:8000/api/backtest/portfolio/run/ \
-H "Content-Type: application/json" \
-d '{
    "filters": {
        "strategy_name": "龙回头策略-2023上半年",
        "start_date": "2023-01-01",
        "end_date": "2023-06-30"
    },
    "backtest_params": {
        "total_capital": 1000000,
        "capital_per_stock_ratio": 0.1,
        "hold_timeout_days": 20,
        "db_alias": "default"
    }
}'
```

### 查询结果示例

1.  **查询总览报告**:
    ```sql
    SELECT * FROM backtest_portfoliobacktest WHERE strategy_name = '龙回头策略-2023上半年';
    ```

2.  **查询详细交易记录** (假设上面查询到的总览报告 ID 为 1):
    ```sql
    SELECT * FROM backtest_tradelog WHERE portfolio_backtest_id = 1;
    ```

## 5. 结果指标释义

在 `backtest_portfoliobacktest` 表中，你可以找到以下关键性能指标：

-   `final_capital`: 回测结束时，组合的总资产（现金+股票市值）。
-   `total_profit`: 总盈利 (`final_capital` - `initial_capital`)。
-   `total_return`: 总收益率 (`total_profit` / `initial_capital`)。
-   `max_drawdown`: **最大回撤**。衡量策略可能面临的最大亏损风险。值越小越好（例如 -0.1 代表最大亏损为 10%）。
-   `max_profit`: **最大盈利**。衡量策略在回测期间达到的最高浮动盈利。
-   `win_rate`: **胜率**。在所有已完成的交易中，盈利交易的占比。

## 6. 内部工作流程

1.  **API 接收请求**：`views.BatchPortfolioBacktestView` 接收请求并验证参数。
2.  **创建异步任务**：视图调用 `tasks.run_portfolio_backtest.delay()`，将所有参数传递给 Celery 任务。
3.  **Celery Worker 执行**：
    a.  **数据准备**: 任务首先根据日期范围和筛选条件（排除ST、创业板），从数据库中一次性加载所有需要的策略信号和日线数据到 Pandas DataFrame 中。
    b.  **初始化组合**: 创建一个 `Portfolio` 对象，包含初始资金等。
    c.  **每日循环**: 任务按交易日遍历所有数据。在每一天，它会检查持仓（是否卖出），并根据当天的信号寻找买入机会。所有买卖操作都会实时更新 `Portfolio` 对象的状态。
    d.  **指标计算**: 在每日循环中，持续记录组合的总市值，用于后续计算最大回撤等指标。
    e.  **保存结果**: 循环结束后，计算最终的各项指标，并将总览报告存入 `PortfolioBacktest` 表，详细交易记录存入 `TradeLog` 表。

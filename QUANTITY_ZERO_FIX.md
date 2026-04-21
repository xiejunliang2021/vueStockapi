# 数量为0问题修复说明

## 问题现象（第二次测试）

用户反馈修改后测试仍然出现相同错误，查看截图和日志发现：

- **数量**: 0股（而不是之前的100股）
- **盈亏**: ¥0.00
- **收益率**: +0.00%

## 根本原因定位

通过查看服务器Celery日志（`sudo journalctl -u vuestock-celery`），发现：

```log
💰 交易完成 | 买入:3.68 | 卖出:4.32 | 数量:0股 | 盈亏:0.00 | 收益率:0.00% | 原因:止盈
```

**关键发现**：日志中有💰 emoji，说明修改后的代码**已经执行**，但数量仍然是0！

### 代码分析

**原策略代码**（L439）：
```python
quantity = abs(trade.size)  # 交易数量
```

**问题**：Backtrader的`trade.size`在某些情况下返回0，导致后续所有计算都基于0数量。

### 为什么trade.size是0？

Backtrader的`trade`对象在某些配置下，`size`字段可能不正确。虽然订单成交时`order.executed.size`有正确的值，但在`notify_trade`回调时`trade.size`可能已经是0。

## 最终解决方案

### 修改1：添加数量记录字段

在`__init__`方法中添加字段：

```python
def __init__(self):
    self.buy_quantity = 0  # ✅ 实际买入数量
```

### 修改2：买入成交时记录数量

在`notify_order`方法中：

```python
def notify_order(self, order):
    if order.status in [order.Completed]:
        if order.isbuy():
            # ✅ 记录实际买入数量
            self.buy_quantity = int(abs(order.executed.size))
            self.log(f'✅ 买入成交 | 价格:{order.executed.price:.2f} | 数量:{self.buy_quantity}股 | 成本:{order.executed.value:.2f}')
```

**关键点**：`order.executed.size`在订单成交时是可靠的，此时立即记录。

### 修改3：交易完成时使用记录的数量

在`notify_trade`方法中：

```python
def notify_trade(self, trade):
    if trade.isclosed:
        # ✅ 使用记录的买入数量，而不是trade.size（可能为0）
        quantity = self.buy_quantity if self.buy_quantity > 0 else abs(trade.size)
```

## 部署步骤

### 1. 清除Python缓存

```bash
ssh oracle114 "cd /home/opc/vueStockapi && find . -type d -name '__pycache__' -exec rm -rf {} +"
ssh oracle114 "cd /home/opc/vueStockapi && find . -name '*.pyc' -delete"
```

**原因**：Python会缓存编译后的.pyc文件，即使源代码更新，如果不清除缓存，Celery可能仍然加载旧代码。

### 2. 上传新文件

```bash
scp backtest/strategies_limit_break.py oracle114:/home/opc/vueStockapi/backtest/strategies_limit_break.py
```

### 3. 完全重启Celery

```bash
ssh oracle114 "sudo systemctl stop vuestock-celery && sleep 5 && sudo systemctl start vuestock-celery"
```

**关键**：等待5秒确保进程完全退出。

## 验证要点

### 日志标识

修复后的日志应该显示：
```
✅ 买入成交 | 价格:3.68 | 数量:27173股 | 成本:99996.64
💸 卖出成交 | 价格:4.32 | 数量:27173股 | 收益:18205.91
💰 交易完成 | 买入:3.68 | 卖出:4.32 | 数量:27173股 | 盈亏:17396.52 | 收益率:17.40% | 原因:止盈
```

**关键emoji标识**：
- ✅ 买入成交
- 💸 卖出成交  
- 💰 交易完成

如果看到这些emoji且数量>0，说明新代码已成功执行！

### 预期数据

基于日志中的一个实际案例：
- 股票代码: 000076.SZ
- 买入价格: ¥3.68
- 卖出价格: ¥4.32
- 初始资金: ¥10,000,000
- 单票占比: 10% → 买入金额: ¥1,000,000
- 预期数量: int(1,000,000 / 3.68) = **27,173股**
- 预期盈亏: (4.32 - 3.68) × 27,173 = **¥17,390.72**
- 预期收益率: 17,390.72 / 99,996.64 = **17.40%**

## 本次修复总结

1. **第一次修复**：添加了数量和收益率字段到`trade_record`
2. **第二次修复**：使用`buy_quantity`字段记录并使用实际买入数量

完整的数据流：
```
buy() → order.executed.size → self.buy_quantity(notify_order) → notify_trade → trade_record['数量']
```

关键是不依赖`trade.size`，而是在订单成交时立即记录`order.executed.size`。

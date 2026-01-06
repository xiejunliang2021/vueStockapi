# 回测优化实施说明

## 📋 已完成的修改

### 1. 创建服务层

✅ **basic/services/strategy_service.py** - 策略数据服务
- `StrategySignal`: 策略信号DTO类
- `StrategyService`: 策略数据访问服务
  - `get_signals_for_backtest()`: 获取回测信号
  - `get_price_data()`: 获取价格数据
  - `update_strategy_result()`: 更新策略执行结果

✅ **backtest/services/backtest_service.py** - 回测执行服务
- `Position`: 持仓类
- `Portfolio`: 投资组合类
- `BacktestStrategy`: 策略基类
- `DragonTurnStrategy`: 龙回头策略实现
- `BacktestService`: 回测服务
  - `run_backtest()`: 执行完整回测流程

### 2. 重构现有代码

✅ **backtest/tasks.py** - 简化为调用服务层
- 从250行代码简化到80行
- 移除直接的数据库查询逻辑
- 使用BacktestService执行回测

✅ **backtest/models.py** - 扩展模型字段
- `TradeLog` 新增字段：
  - `sell_reason`: 卖出原因（止盈/止损/超时）
  - `strategy_type`: 策略类型

### 3. 测试代码

✅ **backtest/tests.py** - 完整的单元测试
- `StrategyServiceTest`: 测试策略服务
- `BacktestServiceTest`: 测试回测服务

---

## 🚀 实施步骤

### 步骤1：激活环境并创建迁移

```powershell
# 激活Conda环境
conda activate stockapi

# 创建数据库迁移
python manage.py makemigrations backtest

# 应用迁移
python manage.py migrate backtest
```

### 步骤2：运行测试

```powershell
# 运行单元测试
python manage.py test backtest.tests -v 2

# 或者运行特定测试
python manage.py test backtest.tests.StrategyServiceTest -v 2
python manage.py test backtest.tests.BacktestServiceTest -v 2
```

### 步骤3：启动Celery Worker（用于异步回测）

```powershell
# 在新的终端窗口启动Worker
conda activate stockapi
celery -A vueStockapi worker -l info -P eventlet
```

### 步骤4：测试API调用

```powershell
# 方式1：使用curl测试
curl -X POST http://127.0.0.1:8000/api/backtest/portfolio/run/ \
-H "Content-Type: application/json" \
-d '{
    "filters": {
        "strategy_name": "测试回测-20240101-20240630",
        "strategy_type": "龙回头",
        "start_date": "2024-01-01",
        "end_date": "2024-06-30"
    },
    "backtest_params": {
        "total_capital": 1000000,
        "capital_per_stock_ratio": 0.1,
        "hold_timeout_days": 60,
        "db_alias": "default"
    }
}'

# 方式2：使用Python requests
python test_api.py
```

---

## 📝 测试API示例（test_api.py）

创建一个测试脚本来验证API：

```python
import requests
import json
from datetime import date, timedelta

def test_backtest_api():
    """测试回测API"""
    
    # API地址
    url = "http://127.0.0.1:8000/api/backtest/portfolio/run/"
    
    # 构建请求数据
    end_date = date.today()
    start_date = end_date - timedelta(days=180)  # 最近6个月
    
    payload = {
        "filters": {
            "strategy_name": f"自动测试-{start_date}至{end_date}",
            "strategy_type": "龙回头",
            "start_date": start_date.strftime('%Y-%m-%d'),
            "end_date": end_date.strftime('%Y-%m-%d')
        },
        "backtest_params": {
            "total_capital": 1000000,
            "capital_per_stock_ratio": 0.1,
            "hold_timeout_days": 60,
            "db_alias": "default"
        }
    }
    
    print("=" * 60)
    print("发送回测请求...")
    print(f"时间范围: {start_date} 至 {end_date}")
    print("=" * 60)
    
    # 发送请求
    response = requests.post(url, json=payload)
    
    if response.status_code == 202:
        result = response.json()
        print("\n✅ 回测任务已启动！")
        print(f"任务ID: {result['task_id']}")
        print(f"策略名称: {result['filters']['strategy_name']}")
        
        # 查询结果列表
        print("\n等待5秒后查询结果...")
        import time
        time.sleep(5)
        
        results_url = "http://127.0.0.1:8000/api/backtest/portfolio/results/"
        results_response = requests.get(results_url)
        
        if results_response.status_code == 200:
            results = results_response.json()
            print(f"\n找到 {len(results)} 个回测结果")
            
            if results:
                latest = results[0]
                print("\n最新回测结果:")
                print(f"  策略名称: {latest['strategy_name']}")
                print(f"  总收益率: {float(latest['total_return']) * 100:.2f}%")
                print(f"  胜率: {float(latest['win_rate']) * 100:.2f}%")
                print(f"  交易次数: {latest['total_trades']}")
                print(f"  最大回撤: {float(latest['max_drawdown']) * 100:.2f}%")
    else:
        print(f"\n❌ 请求失败: {response.status_code}")
        print(response.text)

if __name__ == '__main__':
    test_backtest_api()
```

---

## 🔍 验证优化效果

### 优化前（直接跨库查询）

```python
# 在tasks.py中直接导入basic.models
from basic.models import PolicyDetails, StockDailyData, Code

# 直接查询Oracle数据库
signals = PolicyDetails.objects.using('default').filter(...)
```

**问题**：
- ❌ 应用间强耦合
- ❌ 跨库查询性能差
- ❌ 代码重复
- ❌ 难以测试

### 优化后（服务层架构）

```python
# 使用服务层
from backtest.services.backtest_service import BacktestService

service = BacktestService()
result = service.run_backtest(...)
```

**优势**：
- ✅ 应用解耦
- ✅ 数据访问统一管理
- ✅ 易于测试和维护
- ✅ 支持策略结果反馈

---

## 📊 架构对比

### 优化前

```
backtest/tasks.py (250行)
  ├─ 直接导入 basic.models
  ├─ 硬编码业务逻辑
  ├─ 跨库查询
  └─ 无法复用
```

### 优化后

```
backtest/tasks.py (80行)
  └─ BacktestService
       ├─ StrategyService (策略数据)
       │   ├─ get_signals_for_backtest()
       │   ├─ get_price_data()
       │   └─ update_strategy_result()
       └─ DragonTurnStrategy (回测逻辑)
           ├─ should_buy()
           └─ should_sell()
```

---

## 🎯 核心优势

### 1. 数据流完整性

```
策略生成 → 回测验证 → 结果反馈 → 策略优化
   ↓           ↓           ↓           ↓
PolicyDetails → BacktestService → update_strategy_result() → PolicyDetails更新
```

### 2. 扩展性

添加新策略只需：

```python
class NewStrategy(BacktestStrategy):
    def should_buy(self, signal, price_data, date):
        # 自定义买入逻辑
        pass
    
    def should_sell(self, position, price_data, date, signal):
        # 自定义卖出逻辑
        pass
```

### 3. 可测试性

```python
# 单元测试
service = BacktestService()
result = service.run_backtest(...)
assert result['status'] == 'SUCCESS'

# 集成测试
response = client.post('/api/backtest/portfolio/run/', data)
assert response.status_code == 202
```

---

## ⚠️ 注意事项

### 1. 环境准备

确保已安装所有依赖：
- Django
- Celery
- Redis
- pandas
- basic应用的所有模型

### 2. 数据准备

回测需要以下数据：
- Code: 股票基本信息
- PolicyDetails: 策略信号
- StockDailyData: 价格数据
- TradingCalendar: 交易日历（可选）

### 3. 性能优化

如果回测数据量大：
- 考虑添加数据缓存
- 使用批量查询
- 限制回测时间范围

---

## 📚 下一步

### 立即执行

1. ✅ 激活环境
2. ✅ 创建迁移
3. ✅ 运行测试

### 短期优化

1. 添加更多策略类型
2. 实现参数优化
3. 添加性能监控

### 长期规划

1. 实时回测支持
2. 可视化图表
3. 报告生成

---

## 🆘 故障排查

### 问题1：ImportError: No module named 'django'

**解决**：
```powershell
conda activate stockapi
```

### 问题2：数据库迁移失败

**解决**：
```powershell
python manage.py makemigrations backtest --empty
# 手动编辑迁移文件
python manage.py migrate backtest
```

### 问题3：Celery任务不执行

**解决**：
```powershell
# 检查Redis是否运行
redis-cli ping

# 重启Celery Worker
celery -A vueStockapi worker -l info -P eventlet
```

### 问题4：回测结果为空

**解决**：
- 检查是否有策略信号数据
- 检查价格数据是否覆盖回测时间范围
- 检查日志输出：`logs/app.log`

---

## ✅ 验收标准

### 功能验收

- [ ] 服务层代码正常工作
- [ ] 单元测试全部通过
- [ ] API可以正常调用
- [ ] 回测结果正确保存
- [ ] 策略状态正确更新

### 性能验收

- [ ] 回测1000个信号 < 30秒
- [ ] 内存使用 < 500MB
- [ ] 无数据库连接泄漏

### 代码质量验收

- [ ] 代码可读性强
- [ ] 注释完整
- [ ] 无重复代码
- [ ] 符合PEP8规范

---

**实施完成后，您将获得**：

✅ 清晰的服务层架构
✅ 完整的回测闭环
✅ 易于扩展的策略系统
✅ 完善的测试覆盖
✅ 更好的代码维护性

祝您实施顺利！🎉

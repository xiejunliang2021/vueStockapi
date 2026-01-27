"""
回测API测试脚本

使用方法:
1. 确保Django服务已启动: python manage.py runserver
2. 确保Celery Worker已启动: celery -A vueStockapi worker -l info -P eventlet
3. 运行此脚本: python test_api.py
"""

import requests
import json
from datetime import date, timedelta
import time


def test_backtest_api():
    """测试回测API"""
    
    base_url = "http://127.0.0.1:8000"
    
    # 构建回测请求
    end_date = date(2024, 6, 30)  # 使用固定日期以确保有数据
    start_date = date(2024, 1, 1)
    
    payload = {
        "filters": {
            "strategy_name": f"API测试-{start_date}至{end_date}",
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
    
    print("=" * 70)
    print("🧪 回测API测试")
    print("=" * 70)
    print(f"\n时间范围: {start_date} 至 {end_date}")
    print(f"初始资金: {payload['backtest_params']['total_capital']:,}")
    print(f"单票比例: {payload['backtest_params']['capital_per_stock_ratio'] * 100}%")
    print(f"最大持仓: {payload['backtest_params']['hold_timeout_days']}天")
    
    # 1. 发送回测请求
    print("\n" + "-" * 70)
    print("【步骤1】发送回测请求...")
    print("-" * 70)
    
    try:
        response = requests.post(
            f"{base_url}/api/backtest/portfolio/run/",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 202:
            result = response.json()
            print("✅ 回测任务已成功启动！")
            print(f"\n任务信息:")
            print(f"  任务ID: {result['task_id']}")
            print(f"  策略名称: {result['filters']['strategy_name']}")
            
            task_id = result['task_id']
            
        else:
            print(f"❌ 请求失败: HTTP {response.status_code}")
            print(f"错误信息: {response.text}")
            return
            
    except requests.ConnectionError:
        print("❌ 连接失败！请确保Django服务已启动 (python manage.py runserver)")
        return
    except Exception as e:
        print(f"❌ 请求失败: {e}")
        return
    
    # 2. 等待任务完成
    print("\n" + "-" * 70)
    print("【步骤2】等待回测任务完成...")
    print("-" * 70)
    print("提示: 回测是异步执行的，需要等待Celery Worker处理")
    print("等待中", end="")
    
    for i in range(10):
        print(".", end="", flush=True)
        time.sleep(1)
    
    print(" 完成等待")
    
    # 3. 查询回测结果列表
    print("\n" + "-" * 70)
    print("【步骤3】查询回测结果列表...")
    print("-" * 70)
    
    try:
        results_response = requests.get(f"{base_url}/api/backtest/portfolio/results/")
        
        if results_response.status_code == 200:
            results = results_response.json()
            print(f"✅ 找到 {len(results)} 个回测结果\n")
            
            if results:
                # 显示最新的3个结果
                print("最新回测结果（前3条）:")
                for idx, result in enumerate(results[:3], 1):
                    print(f"\n  【结果 #{idx}】")
                    print(f"    ID: {result['id']}")
                    print(f"    策略名称: {result['strategy_name']}")
                    print(f"    时间范围: {result['start_date']} ~ {result['end_date']}")
                    print(f"    初始资金: {float(result['initial_capital']):,.2f}")
                    print(f"    最终资金: {float(result['final_capital']):,.2f}")
                    print(f"    总收益率: {float(result['total_return']) * 100:,.2f}%")
                    print(f"    交易次数: {result['total_trades']}")
                    print(f"    胜率: {float(result['win_rate']) * 100:.2f}%")
                    print(f"    最大回撤: {float(result['max_drawdown']) * 100:.2f}%")
                    print(f"    创建时间: {result['created_at']}")
                    
                # 4. 查询详细结果
                if results:
                    latest_id = results[0]['id']
                    print("\n" + "-" * 70)
                    print(f"【步骤4】查询详细结果 (ID: {latest_id})...")
                    print("-" * 70)
                    
                    detail_response = requests.get(
                        f"{base_url}/api/backtest/portfolio/results/{latest_id}/"
                    )
                    
                    if detail_response.status_code == 200:
                        detail = detail_response.json()
                        trades = detail.get('trades', [])
                        
                        print(f"✅ 获取到详细交易记录\n")
                        print(f"交易明细（前5条）:")
                        
                        for idx, trade in enumerate(trades[:5], 1):
                            print(f"\n  【交易 #{idx}】")
                            print(f"    股票代码: {trade['stock_code']}")
                            print(f"    买入日期: {trade['buy_date']}")
                            print(f"    买入价格: {float(trade['buy_price']):.2f}")
                            print(f"    卖出日期: {trade['sell_date']}")
                            print(f"    卖出价格: {float(trade['sell_price']):.2f}")
                            if 'sell_reason' in trade and trade['sell_reason']:
                                reasons = {
                                    'take_profit': '止盈',
                                    'stop_loss': '止损',
                                    'timeout': '超时'
                                }
                                print(f"    卖出原因: {reasons.get(trade['sell_reason'], trade['sell_reason'])}")
                            print(f"    数量: {trade['quantity']}")
                            print(f"    盈亏: {float(trade['profit']):,.2f}")
                            print(f"    收益率: {float(trade['return_rate']) * 100:.2f}%")
                        
                        if len(trades) > 5:
                            print(f"\n  ... 还有 {len(trades) - 5} 条交易记录")
                    
            else:
                print("⚠️  当前没有回测结果")
                print("提示: 请确保:")
                print("  1. Celery Worker正在运行")
                print("  2. 数据库中有策略信号数据")
                print("  3. 等待足够的时间让任务完成")
        else:
            print(f"❌ 查询失败: HTTP {results_response.status_code}")
            
    except Exception as e:
        print(f"❌ 查询失败: {e}")
    
    print("\n" + "=" * 70)
    print("✅ 测试完成！")
    print("=" * 70)


def test_simple_call():
    """简单的服务层调用测试（需要在Django环境中运行）"""
    print("\n" + "=" * 70)
    print("🧪 服务层直接调用测试")
    print("=" * 70)
    print("\n提示: 这需要在Django环境中运行")
    print("可以通过Django shell测试:")
    print("\n  python manage.py shell")
    print("\n然后输入以下代码:\n")
    
    test_code = """
from datetime import date
from decimal import Decimal
from backtest.services.backtest_service import BacktestService

# 创建服务实例
service = BacktestService()

# 执行回测
result = service.run_backtest(
    strategy_name='Shell测试回测',
    start_date=date(2024, 1, 1),
    end_date=date(2024, 6, 30),
    initial_capital=Decimal('1000000'),
    capital_per_stock_ratio=Decimal('0.1'),
    strategy_type='龙回头',
    hold_timeout_days=60,
    db_alias='default'
)

print(result)
"""
    
    print(test_code)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'shell':
        test_simple_call()
    else:
        test_backtest_api()

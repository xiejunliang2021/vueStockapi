"""
测试Backtrader版本的回测功能
"""
import requests
import json
from datetime import date

def test_backtrader():
    """测试使用Backtrader引擎的回测"""
    
    url = "http://127.0.0.1:8000/api/backtest/portfolio/run/"
    
    # 测试数据
    payload = {
        "filters": {
            "strategy_name": "Backtrader测试-2025下半年",
            "strategy_type": "龙回头",
            "start_date": "2025-07-01",
            "end_date": "2025-12-31"
        },
        "backtest_params": {
            "total_capital": 1000000,
            "capital_per_stock_ratio": 0.1,
            "hold_timeout_days": 60,
            "db_alias": "default",
            "use_backtrader": True,  # ⭐ 使用Backtrader引擎
            "commission": 0.0003  # 佣金率0.03%
        }
    }
    
    print("=" * 70)
    print("🧪 测试Backtrader引擎回测")
    print("="* 70)
    print(f"\n策略: {payload['filters']['strategy_name']}")
    print(f"时间: {payload['filters']['start_date']} ~ {payload['filters']['end_date']}")
    print(f"资金: {payload['backtest_params']['total_capital']:,}")
    print(f"引擎: Backtrader (专业回测框架)")
    print(f"佣金: {payload['backtest_params']['commission'] * 100:.2f}%")
    
    try:
        response = requests.post(url, json=payload)
        
        if response.status_code == 202:
            result = response.json()
            print("\n✅ 成功！Backtrader回测任务已启动")
            print(f"任务ID: {result['task_id']}")
            print("\n提示:")
            print("  1. 查看Celery Worker窗口，观察Backtrader回测执行过程")
            print("  2. Backtrader会显示更详细的订单和交易信息")
            print("  3. 等待几秒后运行以下命令查看结果:")
            print("     python test_full.py")
        else:
            print(f"\n❌ 请求失败: {response.status_code}")
            print(response.text)
            
    except requests.ConnectionError:
        print("\n❌ 无法连接到Django服务")
        print("请确保运行: python manage.py runserver")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
    
    print("\n" + "=" * 70)


def test_custom_engine():
    """测试使用自定义引擎的回测（对比）"""
    
    url = "http://127.0.0.1:8000/api/backtest/portfolio/run/"
    
    payload = {
        "filters": {
            "strategy_name": "自定义引擎测试-2025下半年",
            "strategy_type": "龙回头",
            "start_date": "2025-07-01",
            "end_date": "2025-12-31"
        },
        "backtest_params": {
            "total_capital": 1000000,
            "capital_per_stock_ratio": 0.1,
            "hold_timeout_days": 60,
            "db_alias": "default",
            "use_backtrader": False  # 使用自定义引擎
        }
    }
    
    print("\n" + "=" * 70)
    print("🧪 测试自定义引擎回测（对比）")
    print("=" * 70)
    print(f"\n策略: {payload['filters']['strategy_name']}")
    print(f"引擎: 自定义引擎")
    
    try:
        response = requests.post(url, json=payload)
        
        if response.status_code == 202:
            result = response.json()
            print("\n✅ 自定义引擎回测任务已启动")
            print(f"任务ID: {result['task_id']}")
        else:
            print(f"\n❌ 请求失败: {response.status_code}")
            
    except Exception as e:
        print(f"\n❌ 错误: {e}")
    
    print("\n" + "=" * 70)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'both':
        # 测试两个引擎并对比
        test_backtrader()
        import time
        time.sleep(2)
        test_custom_engine()
        
        print("\n" + "=" * 70)
        print("📊 两个引擎都已启动，可以对比结果")
        print("=" * 70)
        print("\n提示：")
        print("  等待1-2分钟后，查看数据库中的回测结果")
        print("  SELECT * FROM backtest_portfoliobacktest ORDER BY created_at DESC LIMIT 2;")
    else:
        # 默认只测试Backtrader
        test_backtrader()

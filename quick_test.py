"""
快速测试修复后的回测功能
"""
import requests
import json
from datetime import date

def quick_test():
    """快速测试回测API"""
    
    url = "http://127.0.0.1:8000/api/backtest/portfolio/run/"
    
    # 测试数据：使用2024年前半年的数据
    payload = {
        "filters": {
            "strategy_name": "修复测试-2024上半年",
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
    }
    
    print("=" * 60)
    print("🧪 测试修复后的回测功能")
    print("=" * 60)
    print(f"\n策略: {payload['filters']['strategy_name']}")
    print(f"时间: {payload['filters']['start_date']} ~ {payload['filters']['end_date']}")
    print(f"资金: {payload['backtest_params']['total_capital']:,}")
    
    try:
        response = requests.post(url, json=payload)
        
        if response.status_code == 202:
            result = response.json()
            print("\n✅ 成功！回测任务已启动")
            print(f"任务ID: {result['task_id']}")
            print("\n提示: 查看Celery Worker窗口，应该能看到回测正在执行")
            print("     没有错误信息就说明修复成功了！")
        else:
            print(f"\n❌ 请求失败: {response.status_code}")
            print(response.text)
            
    except requests.ConnectionError:
        print("\n❌ 无法连接到Django服务")
        print("请确保运行: python manage.py runserver")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    quick_test()

import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')
import django
django.setup()

from backtest.tasks import run_portfolio_backtest

filters = {
    'strategy_name': '测试',
    'strategy_type': '连续涨停',
    'start_date': '2026-01-01',
    'end_date': '2026-01-10'
}
backtest_params = {
    'total_capital': 100000,
    'capital_per_stock_ratio': 0.1,
    'hold_timeout_days': 5,
    'db_alias': 'default',
    'use_backtrader': False
}

print("开始测试 Celery 任务执行...")
result = run_portfolio_backtest(filters, backtest_params)
print("测试结束，结果：", result['status'])

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')
django.setup()

from backtest.models import PortfolioBacktest, TradeLog

print(f"回测记录总数: {PortfolioBacktest.objects.count()}")
print(f"交易日志总数: {TradeLog.objects.count()}")

if PortfolioBacktest.objects.exists():
    latest = PortfolioBacktest.objects.first()
    print(f"\n最新回测: {latest.strategy_name}")
    print(f"ID: {latest.id}")
    print(f"总交易次数: {latest.total_trades}")
    
    trade_count = TradeLog.objects.filter(portfolio_backtest_id=latest.id).count()
    print(f"该回测的交易日志数: {trade_count}")
    
    if trade_count > 0:
        print("\n前3条交易日志:")
        for log in TradeLog.objects.filter(portfolio_backtest_id=latest.id)[:3]:
            print(f"  {log.stock_code}: {log.buy_date} -> {log.sell_date}, 盈利: {log.profit}")
    else:
        print("\n警告: 该回测没有交易日志!")
else:
    print("\n数据库中没有回测记录!")

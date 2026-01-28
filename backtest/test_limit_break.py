"""
连续涨停策略回测测试脚本
在 Django Shell 中运行此脚本测试整合后的系统
"""

from backtest.services.backtrader_service import BacktraderBacktestService
from datetime import date
from decimal import Decimal


def test_limit_break_backtest():
    """测试连续涨停策略回测"""
    
    print("=" * 60)
    print("连续涨停策略回测测试")
    print("=" * 60)
    
    # 创建服务实例
    service = BacktraderBacktestService()
    
    # 运行回测 - 测试少量股票
    print("\n开始运行回测...")
    result = service.run_limit_break_backtest(
        strategy_name="连续涨停测试_20260121",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 15),
        initial_capital=Decimal('1000000'),  # 每只股票初始资金100万
        stock_ids=None,  # None表示查询所有L状态股票
        profit_target=0.05,  # 止盈目标5%
        max_hold_days=30,    # 最大持仓30天
        lookback_days=15,    # 买点回溯15天
        max_wait_days=100,   # 买点等待超时100天
        position_pct=0.02,   # 单次买入占总资金2%
        commission=0.001,    # 佣金0.1%
    )
    
    # 打印结果
    print("\n" + "=" * 60)
    print("回测结果")
    print("=" * 60)
    print(f"状态: {result['status']}")
    print(f"消息: {result['message']}")
    print(f"结果ID: {result['result_id']}")
    
    if result['result_id']:
        metrics = result['metrics']
        print("\n指标汇总:")
        print(f"  总收益率: {metrics['total_return'] * 100:.2f}%")
        print(f"  胜率: {metrics['win_rate'] * 100:.2f}%")
        print(f"  总交易次数: {metrics['total_trades']}")
        print(f"  最大回撤: {metrics['max_drawdown'] * 100:.2f}%")
        print(f"  测试股票数: {metrics['stocks_tested']}")
        print(f"  有交易股票数: {metrics['stocks_with_trades']}")
        
        # 查询详细交易记录
        print("\n" + "=" * 60)
        print("详细交易记录（前5条）")
        print("=" * 60)
        
        from backtest.models import PortfolioBacktest, TradeLog
        
        # 显式指定使用 mysql 数据库
        backtest = PortfolioBacktest.objects.using('mysql').get(id=result['result_id'])
        trades = backtest.trades.using('mysql').all()[:5]
        
        for trade in trades:
            print(f"\n股票: {trade.stock_code}")
            print(f"  买入: {trade.buy_date} @ {trade.buy_price}")
            print(f"  卖出: {trade.sell_date} @ {trade.sell_price}")
            print(f"  收益: {trade.profit} ({trade.return_rate * 100:.2f}%)")
            print(f"  原因: {trade.sell_reason}")
            print(f"  持仓天数: {trade.hold_days}")
            if trade.min_diff_to_target is not None:
                print(f"  最小差值: {trade.min_diff_to_target} (第{trade.days_to_min_diff}天)")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    # 在 Django shell 中运行:
    # python manage.py shell
    # exec(open('backtest/test_limit_break.py').read())
    # test_limit_break_backtest()
    
    print("请在 Django Shell 中运行此脚本:")
    print("1. python manage.py shell")
    print("2. exec(open('backtest/test_limit_break.py').read())")
    print("3. test_limit_break_backtest()")

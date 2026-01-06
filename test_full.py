"""
完整的回测功能测试脚本
根据实际数据库中的策略信号日期自动调整测试范围
"""
import os
import sys
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')
django.setup()

from datetime import date, timedelta
from decimal import Decimal
from basic.models import Code, PolicyDetails, StockDailyData
from basic.services.strategy_service import StrategyService
from backtest.services.backtest_service import BacktestService


def get_actual_date_range():
    """获取实际存在策略信号的日期范围"""
    try:
        # 获取最早和最晚的策略信号日期
        earliest = PolicyDetails.objects.order_by('date').first()
        latest = PolicyDetails.objects.order_by('-date').first()
        
        if earliest and latest:
            return earliest.date, latest.date
        return None, None
    except Exception as e:
        print(f"获取日期范围失败: {e}")
        return None, None


def check_data():
    """检查数据库中的数据"""
    print("\n" + "=" * 70)
    print("📊 数据库状态检查")
    print("=" * 70)
    
    # 检查股票数据
    stock_count = Code.objects.count()
    print(f"\n✓ 股票数量: {stock_count:,}")
    
    # 检查策略信号
    policy_count = PolicyDetails.objects.count()
    print(f"✓ 策略信号数量: {policy_count:,}")
    
    # 检查价格数据
    price_count = StockDailyData.objects.count()
    print(f"✓ 价格数据条数: {price_count:,}")
    
    if policy_count == 0:
        print("\n⚠️  警告: 没有策略信号数据，回测将无法执行")
        return False
    
    if price_count == 0:
        print("\n⚠️  警告: 没有价格数据，回测将无法执行")
        return False
    
    # 获取日期范围
    earliest_date, latest_date = get_actual_date_range()
    if earliest_date and latest_date:
        print(f"\n策略信号日期范围:")
        print(f"  最早: {earliest_date}")
        print(f"  最晚: {latest_date}")
        print(f"  时间跨度: {(latest_date - earliest_date).days} 天")
    
    # 显示最近的策略信号
    recent_policies = PolicyDetails.objects.order_by('-date')[:5]
    if recent_policies:
        print(f"\n最近的策略信号（前5条）:")
        for p in recent_policies:
            print(f"  • {p.stock.name} ({p.stock.ts_code}) @ {p.date} - {p.strategy_type}")
    
    return True


def test_strategy_service():
    """测试策略服务"""
    print("\n" + "=" * 70)
    print("🧪 测试1：策略服务功能")
    print("=" * 70)
    
    service = StrategyService()
    
    # 使用实际的日期范围
    earliest_date, latest_date = get_actual_date_range()
    
    if not earliest_date or not latest_date:
        print("❌ 无法获取策略日期范围")
        return False
    
    # 使用最近3个月的数据进行测试
    test_end_date = latest_date
    test_start_date = test_end_date - timedelta(days=90)
    if test_start_date < earliest_date:
        test_start_date = earliest_date
    
    print(f"\n使用日期范围: {test_start_date} ~ {test_end_date}")
    
    # 测试1：获取策略信号
    print("\n【子测试1.1】获取策略信号...")
    try:
        signals = service.get_signals_for_backtest(
            start_date=test_start_date,
            end_date=test_end_date,
            exclude_st=True,
            exclude_cyb=True
        )
        print(f"✅ 成功获取 {len(signals)} 个策略信号")
        
        if signals:
            print(f"\n前3个信号示例:")
            for i, signal in enumerate(signals[:3], 1):
                print(f"  #{i} {signal.stock_name} ({signal.stock_code})")
                print(f"     日期: {signal.signal_date}, 策略: {signal.strategy_type}")
                print(f"     买点: {signal.first_buy_point}, 止盈: {signal.take_profit_point}")
        else:
            print("⚠️  在指定范围内没有找到策略信号")
            return False
            
    except Exception as e:
        print(f"❌ 失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试2：获取价格数据
    print("\n【子测试1.2】获取价格数据...")
    try:
        if signals:
            stock_codes = [signals[0].stock_code, signals[1].stock_code if len(signals) > 1 else signals[0].stock_code]
            price_data = service.get_price_data(
                stock_codes=stock_codes,
                start_date=test_start_date,
                end_date=test_start_date + timedelta(days=30)
            )
            print(f"✅ 成功获取 {len(price_data)} 个交易日的价格数据")
            
            if price_data:
                sample_date = list(price_data.keys())[0]
                print(f"   示例日期 {sample_date}:")
                for stock_code, prices in list(price_data[sample_date].items())[:2]:
                    print(f"     {stock_code}: 开{prices['close']:.2f}")
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False
    
    return True


def test_backtest_service():
    """测试回测服务"""
    print("\n" + "=" * 70)
    print("🧪 测试2：回测服务功能")
    print("=" * 70)
    
    service = BacktestService()
    
    # 使用实际的日期范围
    earliest_date, latest_date = get_actual_date_range()
    
    if not earliest_date or not latest_date:
        print("❌ 无法获取策略日期范围")
        return False
    
    # 使用最近2个月的数据进行快速测试
    test_end_date = latest_date
    test_start_date = test_end_date - timedelta(days=60)
    if test_start_date < earliest_date:
        test_start_date = earliest_date
    
    print(f"\n回测配置:")
    print(f"  策略名称: 完整功能测试")
    print(f"  时间范围: {test_start_date} ~ {test_end_date}")
    print(f"  初始资金: 1,000,000")
    print(f"  单票比例: 10%")
    print(f"  最大持仓: 60天")
    
    print("\n执行回测...")
    print("⏳ 这可能需要几秒到几分钟，请耐心等待...\n")
    
    try:
        result = service.run_backtest(
            strategy_name='完整功能测试',
            start_date=test_start_date,
            end_date=test_end_date,
            initial_capital=Decimal('1000000'),
            capital_per_stock_ratio=Decimal('0.1'),
            strategy_type='龙回头',
            hold_timeout_days=60,
            db_alias='default'
        )
        
        if result['status'] == 'SUCCESS':
            print("✅ 回测执行成功!\n")
            print("=" * 70)
            print("📈 回测结果")
            print("=" * 70)
            print(f"\n消息: {result['message']}")
            
            if 'result_id' in result and result['result_id']:
                print(f"结果ID: {result['result_id']}")
                
                # 查询详细结果
                from backtest.models import PortfolioBacktest, TradeLog
                try:
                    backtest_result = PortfolioBacktest.objects.get(id=result['result_id'])
                    print(f"\n财务指标:")
                    print(f"  初始资金: {backtest_result.initial_capital:,.2f}")
                    print(f"  最终资金: {backtest_result.final_capital:,.2f}")
                    print(f"  总盈利: {backtest_result.total_profit:,.2f}")
                    print(f"  总收益率: {float(backtest_result.total_return) * 100:.2f}%")
                    print(f"  最大回撤: {float(backtest_result.max_drawdown) * 100:.2f}%")
                    print(f"  最大盈利: {backtest_result.max_profit:,.2f}")
                    
                    print(f"\n交易统计:")
                    print(f"  总交易次数: {backtest_result.total_trades}")
                    print(f"  盈利次数: {backtest_result.winning_trades}")
                    print(f"  亏损次数: {backtest_result.losing_trades}")
                    print(f"  胜率: {float(backtest_result.win_rate) * 100:.2f}%")
                    
                    # 显示交易明细
                    trades = TradeLog.objects.filter(portfolio_backtest=backtest_result).order_by('-profit')[:5]
                    if trades:
                        print(f"\n最佳交易（前5笔）:")
                        for i, trade in enumerate(trades, 1):
                            sell_reason_dict = {
                                'take_profit': '止盈',
                                'stop_loss': '止损',
                                'timeout': '超时'
                            }
                            reason = sell_reason_dict.get(trade.sell_reason, trade.sell_reason or '未知')
                            print(f"  #{i} {trade.stock_code}")
                            print(f"      买入: {trade.buy_date} @ {trade.buy_price:.2f}")
                            print(f"      卖出: {trade.sell_date} @ {trade.sell_price:.2f} ({reason})")
                            print(f"      盈亏: {float(trade.profit):,.2f} ({float(trade.return_rate) * 100:.2f}%)")
                            
                except Exception as e:
                    print(f"\n⚠️  无法查询详细结果: {e}")
                    
            elif 'metrics' in result:
                metrics = result['metrics']
                print(f"\n关键指标:")
                print(f"  总收益率: {metrics.get('total_return', 0) * 100:.2f}%")
                print(f"  交易次数: {metrics.get('total_trades', 0)}")
                print(f"  胜率: {metrics.get('win_rate', 0) * 100:.2f}%")
                print(f"  最大回撤: {metrics.get('max_drawdown', 0) * 100:.2f}%")
        else:
            print(f"\n⚠️  回测完成但未找到交易:")
            print(f"  状态: {result['status']}")
            print(f"  消息: {result.get('message', '无')}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 回测执行失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试流程"""
    print("\n" + "=" * 70)
    print("🚀 回测功能完整测试")
    print("=" * 70)
    print("\n这个测试会:")
    print("  1. 检查数据库数据状态")
    print("  2. 测试策略服务功能")
    print("  3. 执行完整回测流程")
    print("  4. 展示回测结果")
    
    # 检查数据
    if not check_data():
        print("\n" + "=" * 70)
        print("⚠️  数据库中没有足够的数据，无法执行测试")
        print("=" * 70)
        print("\n建议:")
        print("  1. 运行策略分析生成信号")
        print("  2. 确保有股票价格数据")
        return
    
    # 测试策略服务
    if not test_strategy_service():
        print("\n❌ 策略服务测试失败，停止后续测试")
        return
    
    # 测试回测服务
    if not test_backtest_service():
        print("\n❌ 回测服务测试失败")
        return
    
    print("\n" + "=" * 70)
    print("✅ 所有测试完成!")
    print("=" * 70)
    print("\n后续操作:")
    print("  • 通过API测试: python quick_test.py")
    print("  • 查看回测结果: 访问 /api/backtest/portfolio/results/")
    print("  • 查看Swagger文档: 访问 /api/docs/")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程出错: {e}")
        import traceback
        traceback.print_exc()

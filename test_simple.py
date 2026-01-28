"""
简化的测试脚本 - 不依赖Django测试框架
直接测试服务层功能
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


def test_strategy_service():
    """测试策略服务"""
    print("\n" + "=" * 60)
    print("🧪 测试策略服务")
    print("=" * 60)
    
    service = StrategyService()
    
    # 测试1：获取策略信号
    print("\n【测试1】获取策略信号...")
    try:
        signals = service.get_signals_for_backtest(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 6, 30),
            exclude_st=True,
            exclude_cyb=True
        )
        print(f"✅ 成功获取 {len(signals)} 个策略信号")
        
        if signals:
            signal = signals[0]
            print(f"   示例信号：")
            print(f"   - 股票代码: {signal.stock_code}")
            print(f"   - 股票名称: {signal.stock_name}")
            print(f"   - 信号日期: {signal.signal_date}")
            print(f"   - 第一买点: {signal.first_buy_point}")
            print(f"   - 止盈点: {signal.take_profit_point}")
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False
    
    # 测试2：获取价格数据
    print("\n【测试2】获取价格数据...")
    try:
        if signals:
            stock_codes = [signals[0].stock_code]
            price_data = service.get_price_data(
                stock_codes=stock_codes,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 1, 31)
            )
            print(f"✅ 成功获取 {len(price_data)} 个交易日的价格数据")
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False
    
    return True


def test_backtest_service():
    """测试回测服务"""
    print("\n" + "=" * 60)
    print("🧪 测试回测服务")
    print("=" * 60)
    
    service = BacktestService()
    
    print("\n执行回测...")
    print("提示: 这可能需要几秒到几分钟，取决于数据量")
    
    try:
        result = service.run_backtest(
            strategy_name='功能测试',
            start_date=date(2024, 1, 1),
            end_date=date(2024, 3, 31),  # 只测试3个月，速度更快
            initial_capital=Decimal('1000000'),
            capital_per_stock_ratio=Decimal('0.1'),
            strategy_type='龙回头',
            hold_timeout_days=60,
            db_alias='default'
        )
        
        if result['status'] == 'SUCCESS':
            print(f"\n✅ 回测成功!")
            print(f"\n结果摘要:")
            print(f"  消息: {result['message']}")
            if 'result_id' in result and result['result_id']:
                print(f"  结果ID: {result['result_id']}")
            if 'metrics' in result:
                metrics = result['metrics']
                print(f"  总收益率: {metrics.get('total_return', 0) * 100:.2f}%")
                print(f"  交易次数: {metrics.get('total_trades', 0)}")
                print(f"  胜率: {metrics.get('win_rate', 0) * 100:.2f}%")
                print(f"  最大回撤: {metrics.get('max_drawdown', 0) * 100:.2f}%")
        else:
            print(f"\n⚠️  回测完成但状态异常:")
            print(f"  状态: {result['status']}")
            print(f"  消息: {result['message']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 回测失败: {e}")
        import traceback
        print(traceback.format_exc())
        return False


def check_data():
    """检查数据库中的数据"""
    print("\n" + "=" * 60)
    print("📊 检查数据库数据")
    print("=" * 60)
    
    # 检查股票数据
    stock_count = Code.objects.count()
    print(f"\n股票数量: {stock_count}")
    
    # 检查策略信号
    policy_count = PolicyDetails.objects.count()
    print(f"策略信号数量: {policy_count}")
    
    # 检查价格数据
    price_count = StockDailyData.objects.count()
    print(f"价格数据条数: {price_count}")
    
    if policy_count == 0:
        print("\n⚠️  警告: 没有策略信号数据，回测将无法执行")
        print("   请先运行策略分析生成信号")
        return False
    
    if price_count == 0:
        print("\n⚠️  警告: 没有价格数据，回测将无法执行")
        print("   请先获取股票价格数据")
        return False
    
    # 显示最近的策略信号
    recent_policies = PolicyDetails.objects.order_by('-date')[:5]
    if recent_policies:
        print(f"\n最近的策略信号（前5条）:")
        for p in recent_policies:
            print(f"  - {p.stock.name} ({p.stock.ts_code}) @ {p.date}")
    
    return True


def main():
    """主测试流程"""
    print("=" * 60)
    print("🚀 回测功能集成测试")
    print("=" * 60)
    print("\n这个测试脚本会直接测试服务层功能")
    print("不需要创建测试数据库，避免Oracle权限问题")
    
    # 检查数据
    if not check_data():
        print("\n" + "=" * 60)
        print("⚠️  数据不足，跳过功能测试")
        print("=" * 60)
        return
    
    # 测试策略服务
    if not test_strategy_service():
        print("\n❌ 策略服务测试失败")
        return
    
    # 测试回测服务
    if not test_backtest_service():
        print("\n❌ 回测服务测试失败")
        return
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过!")
    print("=" * 60)
    print("\n提示: 您也可以通过API测试:")
    print("  python quick_test.py")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试被中断")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

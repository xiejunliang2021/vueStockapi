"""
回测功能测试代码
"""
from django.test import TestCase
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from basic.models import Code, PolicyDetails, StockDailyData
from basic.services.strategy_service import StrategyService, StrategySignal
from backtest.services.backtest_service import BacktestService
from backtest.models import PortfolioBacktest, TradeLog


class StrategyServiceTest(TestCase):
    """策略服务测试"""
    
    def setUp(self):
        """设置测试数据"""
        # 创建测试股票
        self.stock1 = Code.objects.create(
            ts_code='600000.SH',
            symbol='600000',
            name='浦发银行',
            area='上海',
            industry='银行',
            market='主板',
            list_status='L',
            list_date='1999-11-10'
        )
        
        self.stock2 = Code.objects.create(
            ts_code='000001.SZ',
            symbol='000001',
            name='平安银行',
            area='深圳',
            industry='银行',
            market='主板',
            list_status='L',
            list_date='1991-04-03'
        )
        
        # 创建ST股票（应被排除）
        self.st_stock = Code.objects.create(
            ts_code='600001.SH',
            symbol='600001',
            name='ST测试',
            area='上海',
            industry='测试',
            market='主板',
            list_status='L',
            list_date='2000-01-01'
        )
        
        # 创建创业板股票（应被排除）
        self.cyb_stock = Code.objects.create(
            ts_code='300001.SZ',
            symbol='300001',
            name='创业板测试',
            area='深圳',
            industry='测试',
            market='创业板',
            list_status='L',
            list_date='2009-10-30'
        )
        
        # 创建策略信号
        self.signal_date = date(2024, 1, 10)
        self.policy1 = PolicyDetails.objects.create(
            stock=self.stock1,
            date=self.signal_date,
            first_buy_point=Decimal('10.50'),
            second_buy_point=Decimal('10.00'),
            stop_loss_point=Decimal('9.00'),
            take_profit_point=Decimal('12.00'),
            strategy_type='龙回头',
            current_status='L'
        )
        
        self.policy2 = PolicyDetails.objects.create(
            stock=self.stock2,
            date=self.signal_date,
            first_buy_point=Decimal('15.50'),
            second_buy_point=Decimal('15.00'),
            stop_loss_point=Decimal('14.00'),
            take_profit_point=Decimal('17.00'),
            strategy_type='龙回头',
            current_status='L'
        )
        
        # 创建ST股票策略（应被排除）
        self.policy_st = PolicyDetails.objects.create(
            stock=self.st_stock,
            date=self.signal_date,
            first_buy_point=Decimal('5.00'),
            stop_loss_point=Decimal('4.00'),
            take_profit_point=Decimal('6.00'),
            strategy_type='龙回头',
            current_status='L'
        )
        
        # 创建价格数据
        for i in range(30):
            trade_date = self.signal_date + timedelta(days=i)
            
            # 浦发银行价格数据
            StockDailyData.objects.create(
                stock=self.stock1,
                trade_date=trade_date,
                open=Decimal('10.50'),
                high=Decimal('10.80'),
                low=Decimal('10.20'),
                close=Decimal('10.60') + Decimal(str(i * 0.1)),
                volume=1000000,
                amount=Decimal('10000000')
            )
            
            # 平安银行价格数据
            StockDailyData.objects.create(
                stock=self.stock2,
                trade_date=trade_date,
                open=Decimal('15.50'),
                high=Decimal('15.80'),
                low=Decimal('15.20'),
                close=Decimal('15.60') + Decimal(str(i * 0.05)),
                volume=2000000,
                amount=Decimal('30000000')
            )
    
    def test_get_signals_for_backtest(self):
        """测试获取回测信号"""
        service = StrategyService()
        
        signals = service.get_signals_for_backtest(
            start_date=self.signal_date,
            end_date=self.signal_date + timedelta(days=30),
            exclude_st=True,
            exclude_cyb=True
        )
        
        # 应该只获取到2个信号（排除ST和创业板）
        self.assertEqual(len(signals), 2)
        
        # 验证信号数据
        signal1 = next(s for s in signals if s.stock_code == '600000.SH')
        self.assertEqual(signal1.stock_name, '浦发银行')
        self.assertEqual(signal1.first_buy_point, Decimal('10.50'))
        self.assertEqual(signal1.strategy_type, '龙回头')
        
        print(f"✅ 测试通过：获取到 {len(signals)} 个策略信号")
    
    def test_get_price_data(self):
        """测试获取价格数据"""
        service = StrategyService()
        
        price_data = service.get_price_data(
            stock_codes=['600000.SH', '000001.SZ'],
            start_date=self.signal_date,
            end_date=self.signal_date + timedelta(days=10)
        )
        
        # 验证数据结构
        self.assertGreater(len(price_data), 0)
        
        # 验证某一天的数据
        if self.signal_date in price_data:
            day_data = price_data[self.signal_date]
            self.assertIn('600000.SH', day_data)
            self.assertIn('close', day_data['600000.SH'])
            self.assertIn('high', day_data['600000.SH'])
            self.assertIn('low', day_data['600000.SH'])
        
        print(f"✅ 测试通过：获取到 {len(price_data)} 个交易日的价格数据")
    
    def test_update_strategy_result(self):
        """测试更新策略结果"""
        service = StrategyService()
        
        # 更新第一买点时间
        execution_date = self.signal_date + timedelta(days=1)
        service.update_strategy_result(
            stock_code='600000.SH',
            signal_date=self.signal_date,
            result_type='first_buy',
            execution_date=execution_date
        )
        
        # 验证更新
        self.policy1.refresh_from_db()
        self.assertEqual(self.policy1.first_buy_time, execution_date)
        
        # 更新止盈
        profit_date = self.signal_date + timedelta(days=10)
        service.update_strategy_result(
            stock_code='600000.SH',
            signal_date=self.signal_date,
            result_type='take_profit',
            execution_date=profit_date,
            profit_rate=0.15
        )
        
        # 验证状态更新
        self.policy1.refresh_from_db()
        self.assertEqual(self.policy1.take_profit_time, profit_date)
        self.assertEqual(self.policy1.current_status, 'S')
        self.assertEqual(self.policy1.holding_profit, Decimal('15.00'))
        
        print("✅ 测试通过：策略结果更新成功")


class BacktestServiceTest(TestCase):
    """回测服务测试"""
    
    def setUp(self):
        """设置测试数据"""
        # 创建测试股票
        self.stock = Code.objects.create(
            ts_code='600000.SH',
            symbol='600000',
            name='浦发银行',
            area='上海',
            industry='银行',
            market='主板',
            list_status='L',
            list_date='1999-11-10'
        )
        
        # 创建策略信号
        self.signal_date = date(2024, 1, 10)
        self.policy = PolicyDetails.objects.create(
            stock=self.stock,
            date=self.signal_date,
            first_buy_point=Decimal('10.00'),
            stop_loss_point=Decimal('9.00'),
            take_profit_point=Decimal('11.50'),
            strategy_type='龙回头',
            current_status='L'
        )
        
        # 创建价格数据：模拟一个盈利的交易
        prices = [
            (0, 10.50, 10.80, 9.80, 10.30),  # 信号日：可以买入
            (1, 10.30, 10.50, 10.10, 10.20),
            (2, 10.20, 10.40, 10.00, 10.30),
            (3, 10.30, 10.60, 10.20, 10.50),
            (4, 10.50, 11.00, 10.40, 10.80),
            (5, 10.80, 11.50, 10.70, 11.20),  # 触发止盈
            (6, 11.20, 11.40, 11.00, 11.30),
        ]
        
        for days, open_price, high, low, close in prices:
            trade_date = self.signal_date + timedelta(days=days)
            StockDailyData.objects.create(
                stock=self.stock,
                trade_date=trade_date,
                open=Decimal(str(open_price)),
                high=Decimal(str(high)),
                low=Decimal(str(low)),
                close=Decimal(str(close)),
                volume=1000000,
                amount=Decimal('10000000')
            )
    
    def test_run_backtest(self):
        """测试运行完整回测"""
        service = BacktestService()
        
        result = service.run_backtest(
            strategy_name='测试回测',
            start_date=self.signal_date,
            end_date=self.signal_date + timedelta(days=10),
            initial_capital=Decimal('1000000'),
            capital_per_stock_ratio=Decimal('0.1'),
            strategy_type='龙回头',
            hold_timeout_days=60,
            db_alias='default'
        )
        
        # 验证回测结果
        self.assertEqual(result['status'], 'SUCCESS')
        self.assertIn('result_id', result)
        
        # 验证数据库记录
        if result['result_id']:
            backtest_result = PortfolioBacktest.objects.get(id=result['result_id'])
            self.assertEqual(backtest_result.strategy_name, '测试回测')
            self.assertGreater(backtest_result.total_trades, 0)
            
            # 验证交易日志
            trades = TradeLog.objects.filter(portfolio_backtest=backtest_result)
            print(f"\n回测结果：")
            print(f"  总交易次数: {backtest_result.total_trades}")
            print(f"  胜率: {backtest_result.win_rate * 100:.2f}%")
            print(f"  总收益率: {backtest_result.total_return * 100:.2f}%")
            print(f"  最大回撤: {backtest_result.max_drawdown * 100:.2f}%")
            
            for trade in trades:
                print(f"\n  交易记录:")
                print(f"    股票: {trade.stock_code}")
                print(f"    买入: {trade.buy_date} @ {trade.buy_price}")
                print(f"    卖出: {trade.sell_date} @ {trade.sell_price}")
                print(f"    原因: {trade.get_sell_reason_display()}")
                print(f"    盈亏: {trade.profit} ({trade.return_rate * 100:.2f}%)")
        
        print("\n✅ 测试通过：回测执行成功")


def run_manual_test():
    """手动测试函数"""
    from django.core.management import call_command
    
    print("=" * 60)
    print("开始手动测试")
    print("=" * 60)
    
    # 运行测试
    call_command('test', 'backtest.tests', verbosity=2)
    
    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == '__main__':
    run_manual_test()

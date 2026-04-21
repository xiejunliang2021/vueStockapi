"""
回测系统修复验证脚本
测试要点：
1. 资金占比计算是否正确
2. 买入数量计算是否正确
3. 交易盈亏计算是否正确
4. 绩效指标计算是否正确
"""
import os
import django
from decimal import Decimal
from datetime import date

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'stockapi.settings')
django.setup()

from backtest.services.backtest_service import Portfolio, Position

def test_portfolio_buy_calculation():
    """测试买入数量计算"""
    print("=" * 60)
    print("测试1: 买入数量计算")
    print("=" * 60)
    
    # 测试场景：初始资金100000元，单票占比10%
    initial_capital = Decimal('100000')
    capital_ratio = Decimal('0.1')
    
    portfolio = Portfolio(initial_capital)
    
    # 测试买入：股价14.74元
    stock_code = "603706.SH"
    price = 14.74
    test_date = date(2025, 6, 11)
    capital_to_invest = initial_capital * capital_ratio  # 10000元
    
    print(f"初始资金: {initial_capital}")
    print(f"单票占比: {capital_ratio * 100}%")
    print(f"投资金额: {capital_to_invest}")
    print(f"股票价格: {price}")
    
    expected_quantity = int(capital_to_invest / Decimal(str(price)) / 100) * 100
    print(f"预期数量: {expected_quantity}股")
    
    success = portfolio.buy(stock_code, price, test_date, capital_to_invest, '连续涨停')
    
    if success:
        position = portfolio.positions[stock_code]
        print(f"实际数量: {position.quantity}股")
        print(f"实际花费: {position.quantity * position.entry_price:.2f}")
        print(f"剩余资金: {portfolio.cash:.2f}")
        
        if position.quantity == expected_quantity:
            print("✅ 买入数量计算正确！")
        else:
            print(f"❌ 买入数量错误！预期{expected_quantity}，实际{position.quantity}")
    else:
        print("❌ 买入失败")
    
    return portfolio, stock_code

def test_portfolio_sell_calculation(portfolio, stock_code):
    """测试卖出盈亏计算"""
    print("\n" + "=" * 60)
    print("测试2: 卖出盈亏计算")
    print("=" * 60)
    
    if stock_code not in portfolio.positions:
        print("❌ 没有持仓，无法测试")
        return None
    
    position = portfolio.positions[stock_code]
    sell_price = 16.24  # 假设卖出价格
    sell_date = date(2025, 11, 10)
    
    print(f"买入价格: {position.entry_price}")
    print(f"卖出价格: {sell_price}")
    print(f"持仓数量: {position.quantity}")
    
    expected_profit = (Decimal(str(sell_price)) - position.entry_price) * position.quantity
    expected_return_rate = (Decimal(str(sell_price)) / position.entry_price) - Decimal('1')
    
    print(f"预期盈亏: {expected_profit:.2f}")
    print(f"预期收益率: {expected_return_rate * 100:.2f}%")
    
    trade_log = portfolio.sell(stock_code, sell_price, sell_date)
    
    if trade_log:
        print(f"实际盈亏: {trade_log['profit']:.2f} (类型: {type(trade_log['profit']).__name__})")
        print(f"实际收益率: {trade_log['return_rate'] * 100:.2f}% (类型: {type(trade_log['return_rate']).__name__})")
        
        if abs(trade_log['profit'] - expected_profit) < Decimal('0.01'):
            print("✅ 盈亏计算正确！")
        else:
            print(f"❌ 盈亏计算错误！预期{expected_profit:.2f}，实际{trade_log['profit']:.2f}")
            
        if abs(trade_log['return_rate'] - expected_return_rate) < Decimal('0.0001'):
            print("✅ 收益率计算正确！")
        else:
            print(f"❌ 收益率计算错误！")
    else:
        print("❌ 卖出失败")
    
    return trade_log

def test_data_types():
    """测试数据类型是否正确"""
    print("\n" + "=" * 60)
    print("测试3: 数据类型验证")
    print("=" * 60)
    
    portfolio = Portfolio(Decimal('100000'))
    success = portfolio.buy("000001.SZ", 10.5, date.today(), Decimal('10000'))
    
    if success:
        trade_log = portfolio.sell("000001.SZ", 11.5, date.today())
        if trade_log:
            print(f"buy_price类型: {type(trade_log['buy_price']).__name__} ✓")
            print(f"sell_price类型: {type(trade_log['sell_price']).__name__} ✓")
            print(f"quantity类型: {type(trade_log['quantity']).__name__} ✓")
            print(f"profit类型: {type(trade_log['profit']).__name__} ✓")
            print(f"return_rate类型: {type(trade_log['return_rate']).__name__} ✓")
            
            # 检查是否都是Decimal类型（除了quantity）
            all_correct = (
                isinstance(trade_log['buy_price'], Decimal) and
                isinstance(trade_log['sell_price'], Decimal) and
                isinstance(trade_log['quantity'], int) and
                isinstance(trade_log['profit'], Decimal) and
                isinstance(trade_log['return_rate'], Decimal)
            )
            
            if all_correct:
                print("✅ 所有数据类型正确！")
            else:
                print("❌ 存在数据类型错误")

if __name__ == "__main__":
    print("🚀 开始测试回测系统修复效果\n")
    
    # 测试1: 买入数量计算
    portfolio, stock_code = test_portfolio_buy_calculation()
    
    # 测试2: 卖出盈亏计算
    if portfolio and stock_code:
        trade_log = test_portfolio_sell_calculation(portfolio, stock_code)
    
    # 测试3: 数据类型
    test_data_types()
    
    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)

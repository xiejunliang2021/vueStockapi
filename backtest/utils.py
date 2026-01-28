import backtrader as bt
import pandas as pd
from datetime import datetime

# 从 Django 环境中导入模型
from basic.models import StockDailyData, Code
from .models import BacktestResult

# 导入策略
from .strategies import PointBasedStrategy

# 策略注册表
STRATEGY_REGISTRY = {
    'PointBased': PointBasedStrategy,
    # 'SMACrossover': SMACrossoverStrategy, # 如果需要，可以保留旧策略
}

def run_backtest(strategy_name, stock_code, start_date, end_date, initial_cash, strategy_params=None):
    """
    运行回测的核心函数
    :param strategy_name: 策略名称 (例如 'PointBased')
    :param stock_code: 股票代码 (ts_code)
    :param start_date: 开始日期
    :param end_date: 结束日期
    :param initial_cash: 初始资金
    :param strategy_params: 传递给策略的参数字典
    :return: 回测结果字典
    """
    if strategy_params is None:
        strategy_params = {}

    cerebro = bt.Cerebro()

    # 从注册表中获取策略类
    strategy_class = STRATEGY_REGISTRY.get(strategy_name)
    if not strategy_class:
        raise ValueError(f"策略 '{strategy_name}' 不存在或未在注册表中定义.")
    
    # 添加策略，并将参数解包传入
    cerebro.addstrategy(strategy_class, **strategy_params)

    # 从默认数据库(MySQL)获取日线数据
    try:
        # 注意：这里的 .get() 和 .filter() 默认使用 'default' 数据库
        stock = Code.objects.get(ts_code=stock_code)
        queryset = StockDailyData.objects.filter(
            stock=stock,
            trade_date__gte=start_date,
            trade_date__lte=end_date
        ).order_by('trade_date')
        
        if not queryset.exists():
            print(f"跳过回测：在指定日期范围内没有找到股票 {stock_code} 的数据.")
            return None

        df = pd.DataFrame.from_records(queryset.values(
            'trade_date', 'open', 'high', 'low', 'close', 'volume'
        ))
        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df.set_index('trade_date', inplace=True)
        # backtrader 需要列名为小写
        df.rename(columns={
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        }, inplace=True)
        df['openinterest'] = 0

        data_feed = bt.feeds.PandasData(dataname=df)
        cerebro.adddata(data_feed)

    except Code.DoesNotExist:
        print(f"跳过回测：股票代码 {stock_code} 在默认数据库中不存在.")
        return None

    # 设置初始资金和佣金
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=0.001)

    # 添加分析器
    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')

    print(f'开始策略回测: {strategy_name} on {stock_code}...')
    results = cerebro.run()
    print('回测结束。')

    # 提取分析结果
    strat = results[0]
    analysis = strat.analyzers
    final_value = cerebro.broker.getvalue()
    total_return = (final_value - initial_cash) / initial_cash if initial_cash > 0 else 0
    
    # 夏普比率可能在短期回测中为None
    sharpe_analysis = analysis.sharpe.get_analysis()
    sharpe_ratio = sharpe_analysis.get('sharperatio') if sharpe_analysis else 0

    # 最大回撤
    drawdown_analysis = analysis.drawdown.get_analysis()
    max_drawdown = drawdown_analysis.get('max', {}).get('drawdown', 0)

    # 准备结果字典
    result_data = {
        'strategy_name': strategy_name,
        'stock_code': stock_code,
        'start_date': start_date,
        'end_date': end_date,
        'initial_cash': initial_cash,
        'final_value': final_value,
        'total_return': total_return,
        'sharpe_ratio': sharpe_ratio if sharpe_ratio is not None else 0,
        'max_drawdown': max_drawdown if max_drawdown is not None else 0,
    }

    return result_data

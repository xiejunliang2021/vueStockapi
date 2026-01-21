"""
自定义 Backtrader 数据源
支持额外的 up_limit 字段
"""
import backtrader as bt


class LimitBreakDataFeed(bt.feeds.PandasData):
    """
    连续涨停策略专用数据源
    扩展标准 PandasData，添加 up_limit 字段
    """
    
    # 定义额外的 line
    lines = ('up_limit',)
    
    # 定义参数映射
    params = (
        ('datetime', None),      # 使用索引作为日期
        ('open', 'open'),        # 开盘价列名
        ('high', 'high'),        # 最高价列名
        ('low', 'low'),          # 最低价列名
        ('close', 'close'),      # 收盘价列名
        ('volume', 'volume'),    # 成交量列名
        ('up_limit', -1),        # 涨停标记列名（-1表示使用默认列名'up_limit'）
        ('openinterest', -1),    # 不使用持仓量
    )

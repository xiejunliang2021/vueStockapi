"""
基于Backtrader的回测策略实现
"""
import backtrader as bt
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class DragonTurnBacktraderStrategy(bt.Strategy):
    """
    龙回头策略 - Backtrader版本
    
    策略逻辑：
    1. 根据信号的第一买点买入
    2. 设置止盈点和止损点
    3. 持仓超时强制平仓
    """
    
    params = (
        ('signal_data', None),  # 策略信号数据 {date: [signals]}
        ('hold_timeout_days', 60),  # 最大持仓天数
        ('capital_per_stock_ratio', 0.1),  # 单只股票资金占比
        ('update_callback', None),  # 策略结果更新回调
    )
    
    def __init__(self):
        """初始化策略"""
        self.orders = {}  # {data._name: order}
        self.positions_info = {}  # {data._name: {'entry_date': date, 'signal': signal}}
        self.trade_logs = []  # 交易记录
        
        logger.info("策略初始化完成")
        logger.info(f"持仓超时: {self.p.hold_timeout_days}天")
        logger.info(f"单票比例: {self.p.capital_per_stock_ratio * 100}%")
    
    def log(self, txt, dt=None):
        """日志记录"""
        dt = dt or self.datas[0].datetime.date(0)
        logger.info(f'{dt.isoformat()} {txt}')
    
    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        data_name = order.data._name
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(
                    f'买入完成 {data_name}: '
                    f'价格={order.executed.price:.2f}, '
                    f'数量={order.executed.size:.0f}, '
                    f'成本={order.executed.value:.2f}, '
                    f'佣金={order.executed.comm:.2f}'
                )
                
                # 记录持仓信息
                current_date = self.datas[0].datetime.date(0)
                if data_name in self.positions_info:
                    self.positions_info[data_name]['entry_date'] = current_date
                    
                    # 更新策略结果（买入）
                    if self.p.update_callback and 'signal' in self.positions_info[data_name]:
                        signal = self.positions_info[data_name]['signal']
                        try:
                            self.p.update_callback(
                                stock_code=signal.stock_code,
                                signal_date=signal.signal_date,
                                result_type='first_buy',
                                execution_date=current_date
                            )
                        except Exception as e:
                            logger.warning(f"更新策略状态失败: {e}")
                        
            elif order.issell():
                self.log(
                    f'卖出完成 {data_name}: '
                    f'价格={order.executed.price:.2f}, '
                    f'数量={order.executed.size:.0f}, '
                    f'价值={order.executed.value:.2f}, '
                    f'佣金={order.executed.comm:.2f}'
                )
                
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log(f'订单失败 {data_name}: {order.status}')
        
        # 清除订单
        if data_name in self.orders:
            self.orders.pop(data_name)
    
    def notify_trade(self, trade):
        """交易完成通知"""
        if not trade.isclosed:
            return
        
        data_name = trade.data._name
        
        # 计算盈亏
        profit = trade.pnl
        profit_rate = trade.pnlcomm / trade.value if trade.value != 0 else 0
        
        self.log(
            f'交易完成 {data_name}: '
            f'总盈亏={profit:.2f}, '
            f'净盈亏={trade.pnlcomm:.2f}, '
            f'收益率={profit_rate*100:.2f}%'
        )
        
        # 记录交易日志
        if data_name in self.positions_info:
            pos_info = self.positions_info[data_name]
            current_date = self.datas[0].datetime.date(0)
            
            trade_log = {
                'stock_code': data_name,
                'buy_date': pos_info.get('entry_date'),
                'buy_price': Decimal(str(trade.price)),
                'sell_date': current_date,
                'sell_price': Decimal(str(self.getdatabyname(data_name).close[0])),
                'quantity': int(abs(trade.size)),
                'profit': Decimal(str(trade.pnlcomm)),
                'return_rate': Decimal(str(profit_rate)),
                'sell_reason': pos_info.get('sell_reason', 'unknown'),
                'strategy_type': pos_info.get('signal').strategy_type if 'signal' in pos_info else '龙回头',
            }
            self.trade_logs.append(trade_log)
            
            # 更新策略结果（卖出）
            if self.p.update_callback and 'signal' in pos_info:
                signal = pos_info['signal']
                sell_reason = pos_info.get('sell_reason', 'unknown')
                try:
                    self.p.update_callback(
                        stock_code=signal.stock_code,
                        signal_date=signal.signal_date,
                        result_type=sell_reason,
                        execution_date=current_date,
                        profit_rate=float(profit_rate)
                    )
                except Exception as e:
                    logger.warning(f"更新策略状态失败: {e}")
    
    def next(self):
        """每个交易日的策略逻辑"""
        current_date = self.datas[0].datetime.date(0)
        
        # 1. 检查卖出条件（已持有的股票）
        for data in self.datas:
            data_name = data._name
            position = self.getposition(data)
            
            if position.size > 0:  # 有持仓
                # 获取持仓信息
                pos_info = self.positions_info.get(data_name, {})
                signal = pos_info.get('signal')
                entry_date = pos_info.get('entry_date')
                
                if not signal or not entry_date:
                    continue
                
                high = data.high[0]
                low = data.low[0]
                close = data.close[0]
                
                should_sell = False
                sell_reason = ''
                
                # 检查持仓天数
                days_held = (current_date - entry_date).days
                if days_held >= self.p.hold_timeout_days:
                    should_sell = True
                    sell_reason = 'timeout'
                # 检查止盈
                elif high >= float(signal.take_profit_point):
                    should_sell = True
                    sell_reason = 'take_profit'
                # 检查止损
                elif low <= float(signal.stop_loss_point):
                    should_sell = True
                    sell_reason = 'stop_loss'
                
                if should_sell:
                    self.log(f'触发卖出 {data_name}: {sell_reason}')
                    pos_info['sell_reason'] = sell_reason
                    self.close(data=data)
        
        # 2. 检查买入信号
        if current_date in self.p.signal_data:
            signals = self.p.signal_data[current_date]
            
            for signal in signals:
                stock_code = signal.stock_code
                
                # 找到对应的数据
                data = None
                for d in self.datas:
                    if d._name == stock_code:
                        data = d
                        break
                
                if not data:
                    continue
                
                # 检查是否已经持有
                position = self.getposition(data)
                if position.size > 0:
                    continue
                
                # 检查是否有未完成订单
                if stock_code in self.orders:
                    continue
                
                # 检查买入条件：最低价触及第一买点
                low = data.low[0]
                if low <= float(signal.first_buy_point):
                    # 计算买入金额
                    total_value = self.broker.getvalue()
                    buy_amount = total_value * self.p.capital_per_stock_ratio
                    
                    # 计算买入数量（100股为一手）
                    buy_price = float(signal.first_buy_point)
                    size = int(buy_amount / buy_price / 100) * 100
                    
                    if size > 0:
                        self.log(f'发送买入订单 {stock_code}: 价格={buy_price:.2f}, 数量={size}')
                        order = self.buy(data=data, size=size, price=buy_price)
                        self.orders[stock_code] = order
                        
                        # 记录持仓信息
                        self.positions_info[stock_code] = {
                            'signal': signal,
                            'entry_date': current_date,
                        }


class PandasData(bt.feeds.PandasData):
    """自定义Pandas数据源"""
    params = (
        ('datetime', None),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
        ('openinterest', -1),
    )

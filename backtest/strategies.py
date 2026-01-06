import backtrader as bt
from datetime import timedelta

class PointBasedStrategy(bt.Strategy):
    """
    基于预设点位进行交易的策略。

    该策略从参数接收买入、止盈、止损点位，并结合超时逻辑执行交易。
    """
    params = (
        ('first_buy_point', None),
        ('second_buy_point', None), # 暂未实现二次买入逻辑
        ('take_profit_point', None),
        ('stop_loss_point', None),
        ('signal_date', None),
        ('buy_timeout_days', 10),   # 信号日后多少天内买入有效
        ('hold_timeout_days', 60),  # 买入后最长持仓天数
    )

    def __init__(self):
        # 检查关键参数是否存在
        if not all([self.p.first_buy_point, self.p.take_profit_point, 
                    self.p.stop_loss_point, self.p.signal_date]):
            raise ValueError("策略缺少关键参数：买点、止盈、止损或信号日期")

        self.order = None
        self.buy_price = 0
        self.buy_date = None
        
        # 计算买入操作的截止日期
        self.buy_deadline = self.p.signal_date + timedelta(days=self.p.buy_timeout_days)

    def log(self, txt, dt=None):
        """策略日志记录"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f'{dt.isoformat()}, {txt}')

    def next(self):
        current_date = self.datas[0].datetime.date(0)

        # 确保只在信号日之后开始交易
        if current_date < self.p.signal_date:
            return

        # 如果有订单正在处理，则不执行任何操作
        if self.order:
            return

        # 如果当前持有仓位
        if self.position:
            # 检查持仓是否超时
            days_held = (current_date - self.buy_date).days
            if days_held >= self.p.hold_timeout_days:
                self.log(f'持仓超时 ({self.p.hold_timeout_days}天)，强制平仓')
                self.close()
                return

            # 检查止盈条件
            if self.data.high[0] >= self.p.take_profit_point:
                self.log(f'触发止盈点 {self.p.take_profit_point}，卖出')
                self.close() # 以市价单卖出
                return

            # 检查止损条件
            if self.data.low[0] <= self.p.stop_loss_point:
                self.log(f'触发止损点 {self.p.stop_loss_point}，卖出')
                self.close() # 以市价单卖出
                return
        
        # 如果没有持有仓位
        else:
            # 检查是否已超过买入的最后期限
            if current_date > self.buy_deadline:
                # 如果过了最后期限还没买入，就停止策略
                self.log(f'超过买入期限 {self.buy_deadline.isoformat()}，停止策略')
                # cerebro.runstop() # 停止整个回测，如果多标的可能不适用
                return 

            # 检查买入条件
            if self.data.low[0] <= self.p.first_buy_point:
                self.log(f'触发第一买点 {self.p.first_buy_point}，买入')
                # 计算买入数量 (这里使用固定95%的资金)
                size = (self.broker.get_cash() * 0.95) / self.p.first_buy_point
                self.order = self.buy(size=size)
                self.buy_price = self.p.first_buy_point
                self.buy_date = current_date

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            # 订单已提交/接受 - 无需操作
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'买入执行, 价格: {order.executed.price:.2f}, '
                         f'成本: {order.executed.value:.2f}, '
                         f'佣金: {order.executed.comm:.2f}')
            elif order.issell():
                self.log(f'卖出执行, 价格: {order.executed.price:.2f}, '
                         f'成本: {order.executed.value:.2f}, '
                         f'佣金: {order.executed.comm:.2f}')
                
            self.bar_executed = len(self)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log('订单取消/保证金不足/拒绝')

        # 重置订单跟踪
        self.order = None

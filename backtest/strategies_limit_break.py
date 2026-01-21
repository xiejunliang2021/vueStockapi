"""
连续涨停策略 - Backtrader 实现
迁移自 bt_test_01.py 中的 LimitBreakStrategy
"""
import backtrader as bt
import logging
from decimal import Decimal

logger = logging.getLogger(__name__)


class LimitBreakStrategy(bt.Strategy):
    """
    连续涨停 + 回调阴线策略
    
    策略逻辑:
    1. 形态识别: 连续≥2天涨停 + 随后连续2天阴线下跌
    2. 买点计算: 从第一个涨停日之前回溯15天，计算平均收盘价作为买点
    3. 买入触发: 当最低价 <= 买点时触发，优先使用开盘价
    4. 卖出条件: 止盈(5%)、超期(30天)
    5. 跟踪指标: 买点确定后，跟踪最低价与买点的最小差值
    """
    
    params = dict(
        profit_target=0.05,          # 止盈目标: 5%
        max_hold_days=30,            # 最大持仓天数
        lookback_days=15,            # 买点计算回溯天数
        max_wait_days=100,           # 买点等待超时天数
        debug_mode=False,            # 调试模式（打印详细日志）
        position_pct=0.02,           # 每次买入占总资金比例: 2%
    )
    
    def __init__(self):
        """初始化策略变量"""
        self.order = None
        self.buy_price = None
        self.buy_date = None
        self.hold_days = 0
        self.sell_reason = None
        self.limit = 0.096  # 涨停判定阈值
        
        # 买点状态机
        self.target_buy_price = None       # 目标买入价格(买点)
        self.pattern_found_date = None     # 形态确认日期
        
        # 买点差值跟踪
        self.min_diff_to_target = None     # 最小差值（最低价 - 买点）
        self.min_diff_date = None          # 最小差值出现日期
        self.days_to_min_diff = None       # 从买点确定到最小差值天数
        
        # 交易记录
        self.trades_record = []
        self.daily_values = []
        
        # 统计
        self.total_profit = 0
        self.win_count = 0
        self.loss_count = 0
    
    def log(self, msg, level=logging.INFO, dt=None):
        """日志输出"""
        dt = dt or self.datas[0].datetime.date(0)
        message = f'[{dt.isoformat()}] {msg}'
        logger.log(level, message)
    
    def calc_limit_up_price(self, idx):
        """
        计算涨停价
        
        Args:
            idx: 数据索引，0=今天，-1=昨天
            
        Returns:
            涨停价 = 前一天收盘价 * 1.10
        """
        prev_close = self.data.close[idx - 1]
        limit_price = round(prev_close * (1 + self.limit), 2)
        return limit_price
    
    def next(self):
        """每个交易日执行"""
        # === 已持仓: 检查卖点 ===
        if self.position:
            self.hold_days += 1
            
            # 止盈
            profit_rate = (self.data.close[0] - self.buy_price) / self.buy_price
            self.log(f'计算止盈点位 {self.data.close[0]} / {self.buy_price}', level=logging.DEBUG)
            
            if profit_rate >= self.p.profit_target:
                self.sell_reason = '止盈'
                self.log(f'止盈卖出 | 收益率: {profit_rate:.2%} | 价格: {self.data.close[0]:.2f}', level=logging.WARNING)
                self.close()
                return
            
            # 超期
            if self.hold_days >= self.p.max_hold_days:
                self.sell_reason = f'超期({self.hold_days}天)'
                self.log(f'超期卖出 | 持仓 {self.hold_days} 天 | 价格: {self.data.close[0]:.2f}', level=logging.WARNING)
                self.close()
                return
        
        # === 未持仓: 寻找/等待买点 ===
        else:
            # 情况1: 已有买点，等待触发
            if self.target_buy_price is not None:
                current_price = self.data.close[0]
                current_date = self.datas[0].datetime.date(0)
                wait_days = (current_date - self.pattern_found_date).days
                
                # 检查超时
                if wait_days > self.p.max_wait_days:
                    self.log(f'买点等待超时({wait_days}天)，放弃 | 买点:{self.target_buy_price:.2f} | 当前:{current_price:.2f}', level=logging.INFO)
                    self.target_buy_price = None
                    self.pattern_found_date = None
                    return
                
                # 检查触发
                current_low = self.data.low[0]
                current_open = self.data.open[0]
                
                if current_low <= self.target_buy_price:
                    # 优先使用开盘价
                    if current_open < self.target_buy_price:
                        actual_buy_price = current_open
                        buy_reason = "开盘价触发"
                    else:
                        actual_buy_price = self.target_buy_price
                        buy_reason = "买点价格触发"
                    
                    self.buy_price = actual_buy_price
                    self.buy_date = current_date
                    self.hold_days = 0
                    self.sell_reason = None
                    
                    self.log(f'价格触发买点! ({buy_reason}) | 买点:{self.target_buy_price:.2f} | 开盘:{current_open:.2f} | 最低:{current_low:.2f} | 收盘:{current_price:.2f} | 成交价:{actual_buy_price:.2f} | 等待:{wait_days}天', level=logging.WARNING)
                    
                    # 计算买入股数
                    total_value = self.broker.getvalue()
                    buy_amount = total_value * self.p.position_pct
                    size = int(buy_amount / actual_buy_price)
                    
                    if size > 0:
                        self.log(f'买入股数 | 总资金:{total_value:.2f} | 买入金额:{buy_amount:.2f} | 价格:{actual_buy_price:.2f} | 股数:{size}', level=logging.DEBUG)
                        self.buy(price=actual_buy_price, size=size, exectype=bt.Order.Limit)
                    else:
                        self.log(f'资金不足 | 总资金:{total_value:.2f} | 需要:{buy_amount:.2f}', level=logging.ERROR)
                    
                    # 买入当天更新最小差值
                    diff = current_low - self.target_buy_price
                    if self.min_diff_to_target is None or diff < self.min_diff_to_target:
                        self.min_diff_to_target = diff
                        self.min_diff_date = current_date
                        self.days_to_min_diff = (current_date - self.pattern_found_date).days
                        self.log(f'买入日更新最小差值 | 差值:{diff:.2f} | 距买点确定:{self.days_to_min_diff}天', level=logging.DEBUG)
                    
                    # 清除买点状态
                    self.target_buy_price = None
                    self.pattern_found_date = None
                else:
                    # 未触发，更新最小差值
                    diff = current_low - self.target_buy_price
                    if self.min_diff_to_target is None or diff < self.min_diff_to_target:
                        self.min_diff_to_target = diff
                        self.min_diff_date = current_date
                        self.days_to_min_diff = (current_date - self.pattern_found_date).days
                        self.log(f'更新最小差值 | 差值:{diff:.2f} | 日期:{current_date} | 距买点确定:{self.days_to_min_diff}天', level=logging.DEBUG)
                    
                    self.log(f'等待买点 | 买点:{self.target_buy_price:.2f} | 开盘:{current_open:.2f} | 最低:{current_low:.2f} | 收盘:{current_price:.2f} | 差异:{((current_low - self.target_buy_price) / self.target_buy_price * 100):+.2f}% | 已等待:{wait_days}天', level=logging.DEBUG)
            
            # 情况2: 尚未确定买点，检查形态
            else:
                if self.check_pattern():
                    buy_point = self.calculate_buy_price()
                    if buy_point:
                        self.target_buy_price = buy_point
                        self.pattern_found_date = self.datas[0].datetime.date(0)
                        # 初始化差值跟踪
                        self.min_diff_to_target = None
                        self.min_diff_date = None
                        self.days_to_min_diff = None
                        self.log(f'形态确认，买点已设定! | 买点:{buy_point:.2f} | 确认日期:{self.pattern_found_date} | 当前价:{self.data.close[0]:.2f}', level=logging.WARNING)
            
            # 记录每日资金
            current_date = self.datas[0].datetime.date(0)
            current_value = self.broker.getvalue()
            self.daily_values.append({
                'date': current_date,
                'value': current_value
            })
    
    def check_pattern(self):
        """
        形态检测: 连续≥2天涨停 + 随后连续2天阴线下跌
        """
        current_date = self.datas[0].datetime.date(0)
        
        if self.p.debug_mode:
            self.log(f'检查形态...', level=logging.DEBUG)
        
        # 至少需要5根K线
        if len(self.data) < 5:
            if self.p.debug_mode:
                self.log(f'数据不足，只有{len(self.data)}根K线', level=logging.DEBUG)
            return False
        
        # 检查最近两天是否连续下跌
        day0_open = self.data.open[0]
        day0_close = self.data.close[0]
        day1_open = self.data.open[-1]
        day1_close = self.data.close[-1]
        day2_close = self.data.close[-2]
        
        day0_is_bearish = day0_close < day0_open
        day1_is_bearish = day1_close < day1_open
        day1_lower_than_day2 = day1_close < day2_close
        
        if self.p.debug_mode:
            self.log(f'今天: 开{day0_open:.2f} 收{day0_close:.2f} 阴线:{day0_is_bearish}', level=logging.DEBUG)
            self.log(f'昨天: 开{day1_open:.2f} 收{day1_close:.2f} 阴线:{day1_is_bearish}', level=logging.DEBUG)
            self.log(f'前天: 收{day2_close:.2f}, 昨天<前天:{day1_lower_than_day2}', level=logging.DEBUG)
        
        if not (day0_is_bearish and day1_is_bearish and day1_lower_than_day2):
            if self.p.debug_mode:
                self.log(f'不满足连续下跌', level=logging.DEBUG)
            return False
        
        self.log(f'✓ 连续两天阴线下跌 | 今天: 开{day0_open:.2f}→收{day0_close:.2f} | 昨天: 开{day1_open:.2f}→收{day1_close:.2f}', level=logging.INFO)
        
        # 检查往前是否至少连续2天涨停
        limit_count = 0
        idx = -2  # 从前天开始
        limit_dates = []
        limit_details = []
        
        while abs(idx) <= len(self.data):
            is_limit = self.data.up_limit[idx] == 1
            close_price = self.data.close[idx]
            
            if is_limit:
                limit_count += 1
                limit_dates.append(f"前{abs(idx)}天")
                limit_details.append(f"前{abs(idx)}天(收:{close_price:.2f})")
                idx -= 1
            else:
                if self.p.debug_mode:
                    self.log(f'前{abs(idx)}天非涨停: 收{close_price:.2f}, up_limit={self.data.up_limit[idx]}', level=logging.DEBUG)
                break
        
        self.log(f'涨停天数: {limit_count} 天', level=logging.INFO)
        if limit_details:
            self.log(f"详情: {', '.join(limit_details[:3])}", level=logging.INFO)
        
        if limit_count >= 2:
            self.log(f'✅ 满足买点形态：{limit_count}天涨停 + 2天连续阴线下跌', level=logging.INFO)
            return True
        else:
            self.log(f'涨停天数不足2天({limit_count}天)', level=logging.INFO)
            return False
    
    def calculate_buy_price(self):
        """
        计算买点: 从第一个涨停日之前回溯15天，计算平均收盘价
        """
        current_date = self.datas[0].datetime.date(0)
        self.log(f'计算买点价格:', level=logging.DEBUG)
        
        # 找到第一个涨停日
        first_limit_idx = None
        idx = -2  # 从前天开始
        
        while idx >= -len(self.data):
            is_limit = self.data.up_limit[idx] == 1
            
            if is_limit:
                first_limit_idx = idx
                idx -= 1
            else:
                self.log(f'最早非涨停日: {self.datas[0].datetime.date(idx)}', level=logging.DEBUG)
                break
        
        if first_limit_idx is None:
            self.log(f'未找到涨停日', level=logging.WARNING)
            return None
        
        self.log(f'最早涨停日: 前{abs(first_limit_idx)}天 (收:{self.data.close[first_limit_idx]:.2f})', level=logging.DEBUG)
        
        # 从连续涨停之前的第一个非涨停日开始回溯
        first_non_limit_idx = first_limit_idx - 1
        
        if abs(first_non_limit_idx) >= len(self.data):
            self.log(f'连续涨停之前没有数据', level=logging.WARNING)
            return None
        
        if self.data.up_limit[first_non_limit_idx] == 1:
            self.log(f'错误：应为非涨停日', level=logging.ERROR)
            return None
        
        self.log(f'第一个非涨停日: 前{abs(first_non_limit_idx)}天 (收:{self.data.close[first_non_limit_idx]:.2f})', level=logging.DEBUG)
        
        # 从非涨停日开始往前回溯15天
        start_idx = first_non_limit_idx - (self.p.lookback_days - 1)
        end_idx = first_non_limit_idx
        
        self.log(f'回溯区间: 前{abs(start_idx)}天 至 前{abs(end_idx)}天 (共{self.p.lookback_days}天)', level=logging.DEBUG)
        
        # 收集收盘价
        lookback_closes = []
        for i in range(start_idx, end_idx + 1):
            if abs(i) >= len(self.data):
                break
            close_price = self.data.close[i]
            lookback_closes.append(close_price)
        
        if not lookback_closes:
            self.log(f'回溯期没有数据', level=logging.WARNING)
            return None
        
        # 计算平均价格
        avg_price = sum(lookback_closes) / len(lookback_closes)
        
        self.log(f'买点计算 | 回溯天数:{len(lookback_closes)}天 | 买点价格: {avg_price:.2f}', level=logging.INFO)
        
        return avg_price
    
    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return
        
        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f'买入成交 | 价格: {order.executed.price:.2f} | 成本: {order.executed.value:.2f}', level=logging.INFO)
            elif order.issell():
                self.log(f'卖出成交 | 价格: {order.executed.price:.2f} | 收益: {order.executed.pnl:.2f}', level=logging.INFO)
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            if order.status == order.Margin:
                self.log(f'订单失败: 资金不足', level=logging.ERROR)
            else:
                self.log(f'订单失败: {order.getstatusname()}', level=logging.ERROR)
        
        self.order = None
    
    def notify_trade(self, trade):
        """交易完成通知"""
        if trade.isclosed:
            profit = trade.pnlcomm
            if trade.value != 0:
                profit_rate = (trade.pnl / trade.value) * 100
            else:
                profit_rate = 0.0
                self.log(f'警告：交易金额为0', level=logging.WARNING)
            
            # 记录交易
            trade_record = {
                '买入日期': self.buy_date.strftime('%Y-%m-%d') if self.buy_date else 'N/A',
                '卖出日期': self.datas[0].datetime.date(0).strftime('%Y-%m-%d'),
                '买入价格': self.buy_price if self.buy_price else 0,
                '卖出价格': trade.price,
                '持仓天数': self.hold_days,
                '卖出原因': self.sell_reason or '未知',
                '盈亏金额': round(profit, 2),
                '收益率': f'{profit_rate:.2f}%',
                # 买点差值跟踪
                '最小差值': round(self.min_diff_to_target, 2) if self.min_diff_to_target is not None else 'N/A',
                '最小差值日期': self.min_diff_date.strftime('%Y-%m-%d') if self.min_diff_date else 'N/A',
                '距买点确定天数': self.days_to_min_diff if self.days_to_min_diff is not None else 'N/A'
            }
            self.trades_record.append(trade_record)
            
            # 更新统计
            self.total_profit += profit
            if profit > 0:
                self.win_count += 1
            else:
                self.loss_count += 1
            
            self.log(f'交易完成 | 盈亏: {profit:.2f} | 收益率: {profit_rate:.2f}% | 原因: {self.sell_reason}', level=logging.INFO)

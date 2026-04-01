"""
连续涨停策略 - Backtrader 实现
完全同步自 bt_test_01.py
"""
import backtrader as bt
import logging
import datetime

logger = logging.getLogger(__name__)


class LimitBreakStrategy(bt.Strategy):
    """
    连续涨停 + 回调阴线后的买卖策略
    同步自 bt_test_01.py
    """

    params = dict(
        profit_target=0.10,     # 止盈目标: 10%
        stop_loss=-0.05,        # 止损: -5%（新增）
        max_hold_days=30,       # 最大持仓天数
        lookback_days=20,       # 买点计算回溯天数: 20天
        max_wait_days=100,      # 买点等待最大天数(超过则放弃该买点)
        debug_mode=False,       # 调试模式:是否打印所有形态检测日志
        position_pct=0.02,      # 每次买入占总资金的比例（2%）
    )

    def __init__(self):
        """初始化策略变量"""
        self.order = None              # 当前订单
        self.buy_price = None          # 实际买入价
        self.buy_quantity = 0          # ✅ 实际买入数量
        self.sell_price = None         # 实际卖出价
        self.buy_date = None           # 买入日期
        self.sell_date = None          # 卖出决定日期（调用close的日期）
        self.hold_days = 0             # 持仓天数
        self.sell_reason = None        # 卖出原因
        self.limit = 0.096
        
        # 买点状态机
        self.target_buy_price = None   # 目标买入价格(买点)
        self.pattern_found_date = None # 形态确认日期
        
        # 买点差值跟踪（买点确定后开始跟踪）
        self.min_diff_to_target = None      # 最小差值（最低价 - 买点）
        self.min_diff_date = None           # 最小差值出现的日期
        self.days_to_min_diff = None        # 从买点确定到最小差值出现的天数
        
        # 交易记录列表
        self.trades_record = []
        
        # 每日资金记录（日期，总资金）
        self.daily_values = []
        
        # 统计变量
        self.total_profit = 0
        self.win_count = 0
        self.loss_count = 0

    def log(self, msg, level=logging.INFO, dt=None):
        """
        日志输出方法
        :param msg: 日志消息
        :param level: 日志级别，默认 logging.INFO
        :param dt: 日期时间，默认为当前回测日期
        """
        dt = dt or self.datas[0].datetime.date(0)
        # 将回测时间添加到日志消息中
        message = f'[{dt.isoformat()}] {msg}'
        logger.log(level, message)

    def calc_limit_up_price(self, idx):
        """
        计算涨停价
        idx: 数据索引,0表示今天,-1表示昨天
        返回: 涨停价 = 前一天收盘价 * 1.10
        """
        # 获取前一天的收盘价
        prev_close = self.data.close[idx - 1]
        # 计算涨停价(10%涨停)
        limit_price = round(prev_close * (1+self.limit), 2)
        return limit_price

    def next(self):
        """
        每个交易日执行一次
        """
        # === 已持仓:检查卖点 ===
        if self.position:
            self.hold_days += 1

            # 计算当前盈亏率
            profit_rate = (self.data.close[0] - self.buy_price) / self.buy_price
            self.log(f'持仓检查 | 当前价:{self.data.close[0]:.2f} | 买入价:{self.buy_price:.2f} | 盈亏率:{profit_rate:.2%} | 持仓天数:{self.hold_days}', level=logging.DEBUG)
            
            # 1. 止损检查（优先级最高）
            # 注意：stop_loss 参数是正数（如 0.05 表示 5%），但判断时需要转为负数
            if profit_rate <= -self.p.stop_loss:
                self.sell_reason = '止损'
                self.sell_date = self.datas[0].datetime.date(0)  # ✅ 记录决定卖出的日期
                self.log(f'🛑 止损卖出 | 亏损率: {profit_rate:.2%} | 止损线: {-self.p.stop_loss:.2%} | 价格: {self.data.close[0]:.2f}', level=logging.WARNING)
                self.close()
                return

            # 2. 止盈检查
            if profit_rate >= self.p.profit_target:
                self.sell_reason = '止盈'
                self.sell_date = self.datas[0].datetime.date(0)  # ✅ 记录决定卖出的日期
                self.log(f'💰 止盈卖出 | 收益率: {profit_rate:.2%} | 价格: {self.data.close[0]:.2f}', level=logging.WARNING)
                self.close()
                return

            # 3. 超期检查
            if self.hold_days >= self.p.max_hold_days:
                self.sell_reason = f'超期({self.hold_days}天)'
                self.sell_date = self.datas[0].datetime.date(0)  # ✅ 记录决定卖出的日期
                self.log(f'⏰ 超期卖出 | 持仓 {self.hold_days} 天 | 价格: {self.data.close[0]:.2f}', level=logging.WARNING)
                self.close()
                return


        # === 未持仓:寻找买点或等待买点触发 ===
        else:
            # 情况1:已经有买点,等待价格触发
            if self.target_buy_price is not None:
                current_price = self.data.close[0]
                current_date = self.datas[0].datetime.date(0)
                
                # 计算等待天数
                wait_days = (current_date - self.pattern_found_date).days
                
                # 检查是否超时
                if wait_days > self.p.max_wait_days:
                    self.log(f'买点等待超时({wait_days}天),放弃该买点 | 买点价格:{self.target_buy_price:.2f} | 当前价格:{current_price:.2f}', level=logging.INFO)
                    # 清除买点状态
                    self.target_buy_price = None
                    self.pattern_found_date = None
                    return
                
                # 检查是否达到买点(当天最低价 <= 买点价格)
                current_low = self.data.low[0]  # 当天最低价
                current_open = self.data.open[0]  # 当天开盘价
                
                if current_low <= self.target_buy_price:
                    # 触发买入,优先使用开盘价(如果开盘价<买点)
                    if current_open < self.target_buy_price:
                        # 开盘价低于买点,用开盘价买入
                        actual_buy_price = current_open
                        buy_reason = "开盘价触发"
                    else:
                        # 开盘价不低于买点,用买点价格买入
                        actual_buy_price = self.target_buy_price
                        buy_reason = "买点价格触发"
                    
                    self.buy_price = actual_buy_price  # 记录实际买入价
                    self.buy_date = current_date
                    self.hold_days = 0
                    self.sell_reason = None
                    self.log(f'价格触发买点! ({buy_reason}) | 买点:{self.target_buy_price:.2f} | 开盘:{current_open:.2f} | 最低:{current_low:.2f} | 收盘:{current_price:.2f} | 成交价:{actual_buy_price:.2f} | 等待天数:{wait_days}天', level=logging.WARNING)
                    
                    # 计算买入股数：使用总资金的position_pct比例
                    total_value = self.broker.getvalue()  # 当前总资金
                    buy_amount = total_value * self.p.position_pct  # 本次买入金额
                    size = int(buy_amount / actual_buy_price)  # 买入股数（向下取整）
                    
                    if size > 0:
                        self.log(f'买入股数计算 | 总资金:{total_value:.2f} | 买入金额:{buy_amount:.2f} | 买入价:{actual_buy_price:.2f} | 股数:{size}', level=logging.DEBUG)
                        # 使用限价单,以实际买入价买入指定数量的股票
                        self.buy(price=actual_buy_price, size=size, exectype=bt.Order.Limit)
                    else:
                        self.log(f'资金不足,无法买入 | 总资金:{total_value:.2f} | 需要金额:{buy_amount:.2f}', level=logging.ERROR)
                    
                    # 买入当天也更新一次最小差值（在清除买点状态前）
                    diff = current_low - self.target_buy_price
                    if self.min_diff_to_target is None or diff < self.min_diff_to_target:
                        self.min_diff_to_target = diff
                        self.min_diff_date = current_date
                        self.days_to_min_diff = (current_date - self.pattern_found_date).days
                        self.log(f'买入日更新最小差值 | 差值:{diff:.2f} | 距买点确定:{self.days_to_min_diff}天', level=logging.DEBUG)
                    
                    # 买入后清除买点状态（注意：min_diff相关变量不清除，在notify_trade中使用）
                    self.target_buy_price = None
                    self.pattern_found_date = None
                else:
                    # 未触发,继续等待
                    # 更新买点到最低价的最小差值
                    current_date = self.datas[0].datetime.date(0)
                    diff = current_low - self.target_buy_price  # 当天最低价 - 买点
                    
                    # 如果是第一次记录或者当前差值更小，则更新
                    if self.min_diff_to_target is None or diff < self.min_diff_to_target:
                        self.min_diff_to_target = diff
                        self.min_diff_date = current_date
                        self.days_to_min_diff = (current_date - self.pattern_found_date).days
                        self.log(f'更新最小差值 | 差值:{diff:.2f} | 日期:{current_date} | 距买点确定:{self.days_to_min_diff}天', level=logging.DEBUG)
                    
                    self.log(f'等待买点触发 | 买点:{self.target_buy_price:.2f} | 开盘:{current_open:.2f} | 最低:{current_low:.2f} | 收盘:{current_price:.2f} | 差异:{((current_low - self.target_buy_price) / self.target_buy_price * 100):+.2f}% | 已等待:{wait_days}天', level=logging.DEBUG)
            
            # 情况2:尚未确定买点,检查形态
            else:
                if self.check_pattern():
                    buy_point = self.calculate_buy_price()
                    if buy_point:
                        self.target_buy_price = buy_point
                        self.pattern_found_date = self.datas[0].datetime.date(0)
                        # 初始化买点差值跟踪
                        self.min_diff_to_target = None
                        self.min_diff_date = None
                        self.days_to_min_diff = None
                        self.log(f'形态确认,买点已设定! | 买点价格:{buy_point:.2f} | 确认日期:{self.pattern_found_date} | 当前价:{self.data.close[0]:.2f}', level=logging.WARNING)
            
            # 记录每日账户总价值（在所有逻辑最后）
            current_date = self.datas[0].datetime.date(0)
            current_value = self.broker.getvalue()
            self.daily_values.append({
                'date': current_date,
                'value': current_value
            })


    def check_pattern(self):
        """
        判断形态：
        - 连续 ≥2 天涨停
        - 随后连续 2 天下跌:
          1. 今天是阴线: close[0] < open[0]
          2. 昨天是阴线: close[-1] < open[-1]
          3. 昨天收盘 < 前天收盘(连续涨停的最后一天)
        """
        current_date = self.datas[0].datetime.date(0)
        
        # 打印每日检测状态（调试用）
        if self.p.debug_mode:
            self.log(f'检查形态...', level=logging.DEBUG)

        # 至少需要 5 根 K 线
        if len(self.data) < 5:
            if self.p.debug_mode:
                self.log(f'数据不足,只有{len(self.data)}根K线', level=logging.DEBUG)
            return False

        # 检查最近两天是否连续下跌（阴线）
        day0_open = self.data.open[0]     # 今天开盘
        day0_close = self.data.close[0]   # 今天收盘
        day1_open = self.data.open[-1]    # 昨天开盘
        day1_close = self.data.close[-1]  # 昨天收盘
        day2_close = self.data.close[-2]  # 前天收盘

        # 今天是阴线
        day0_is_bearish = day0_close < day0_open
        # 昨天是阴线
        day1_is_bearish = day1_close < day1_open
        # 昨天收盘 < 前天收盘
        day1_lower_than_day2 = day1_close < day2_close

        if self.p.debug_mode:
            self.log(f'今天: 开{day0_open:.2f} 收{day0_close:.2f} 阴线:{day0_is_bearish}', level=logging.DEBUG)
            self.log(f'昨天: 开{day1_open:.2f} 收{day1_close:.2f} 阴线:{day1_is_bearish}', level=logging.DEBUG)
            self.log(f'前天: 收{day2_close:.2f}, 昨天<前天:{day1_lower_than_day2}', level=logging.DEBUG)

        if not (day0_is_bearish and day1_is_bearish and day1_lower_than_day2):
            if self.p.debug_mode:
                self.log(f'不满足连续下跌条件 | 今天阴线:{day0_is_bearish}, 昨天阴线:{day1_is_bearish}, 昨天<前天:{day1_lower_than_day2}', level=logging.DEBUG)
            return False

        # 如果到这里,说明连续两天阴线下跌了,打印详情
        self.log(f'✓ 连续两天阴线下跌 | 今天(阴线): 开{day0_open:.2f}→收{day0_close:.2f} | 昨天(阴线): 开{day1_open:.2f}→收{day1_close:.2f} | 前天: 收{day2_close:.2f}', level=logging.INFO)

        # 再往前是否至少连续 2 天涨停
        # 涨停判断：直接使用 up_limit 列
        limit_count = 0
        idx = -2  # 从前天开始检查（前天应该是连续涨停的最后一天）
        limit_dates = []
        limit_details = []

        while abs(idx) <= len(self.data):
            # 直接读取 up_limit 列
            is_limit = self.data.up_limit[idx] == 1
            close_price = self.data.close[idx]

            if is_limit:
                limit_count += 1
                limit_dates.append(f"前{abs(idx)}天")
                limit_details.append(f"前{abs(idx)}天(收:{close_price:.2f}, up_limit=1)")
                idx -= 1
            else:
                if self.p.debug_mode:
                    self.log(f'前{abs(idx)}天非涨停: 收{close_price:.2f}, up_limit={self.data.up_limit[idx]}', level=logging.DEBUG)
                break

        self.log(f'涨停天数: {limit_count} 天', level=logging.INFO)
        if limit_details:
            self.log(f"详情: {', '.join(limit_details[:3])}", level=logging.INFO)  # 只显示前3天

        if limit_count >= 2:
            self.log(f'✅ 满足买点形态：{limit_count}天涨停 + 2天连续阴线下跌', level=logging.INFO)
            return True
        else:
            self.log(f'涨停天数不足2天({limit_count}天)，不满足条件', level=logging.INFO)
            return False


    def calculate_buy_price(self):
        """
        计算买点价格 - 新策略
        
        步骤：
        1. 找到连续涨停序列的第一个涨停日 t0
        2. 检查 t0 之前的 20 个交易日是否有涨停
        3. 场景A（无涨停）：买点 = max(High[t-1], High[t-2], High[t-3])
        4. 场景B（有涨停）：买点 = avg(Close[t-1] ... Close[t-20])
        """
        current_date = self.datas[0].datetime.date(0)
        self.log(f'📊 开始计算买点价格', level=logging.INFO)
        
        # ========== 步骤1：找到第一个涨停日 t0 ==========
        # 从前天（idx=-2）开始往前搜索，因为今天和昨天是连续下跌的形态确认日
        first_limit_idx = None
        idx = -2
        
        while idx >= -len(self.data):
            is_limit = self.data.up_limit[idx] == 1
            
            if is_limit:
                first_limit_idx = idx  # 记录当前涨停日
                idx -= 1  # 继续往前找，找到最早的涨停日
            else:
                # 遇到非涨停日，说明已经找到了连续涨停序列的边界
                break

        if first_limit_idx is None:
            self.log(f'❌ 未找到涨停日，无法计算买点', level=logging.WARNING)
            return None
        
        # t0 就是第一个涨停日的索引
        t0_idx = first_limit_idx
        t0_date = self.datas[0].datetime.date(t0_idx)
        t0_close = self.data.close[t0_idx]
        
        self.log(f'✅ 第一个涨停日 t0: 前{abs(t0_idx)}天 | 日期:{t0_date} | 收盘:{t0_close:.2f}', level=logging.INFO)
        
        # ========== 步骤2：检查 t0 之前的 20 个交易日是否有涨停 ==========
        # 检查范围：[t0-20, t0-1]，即 t0 之前的 20 天
        lookback_start_idx = t0_idx - self.p.lookback_days  # t0 - 20
        lookback_end_idx = t0_idx - 1  # t0 - 1
        
        self.log(f'🔍 检查回溯区间: 前{abs(lookback_start_idx)}天 至 前{abs(lookback_end_idx)}天 (共{self.p.lookback_days}天)', level=logging.DEBUG)
        
        # 检查数据是否充足
        if abs(lookback_start_idx) >= len(self.data):
            self.log(f'⚠️ 数据不足，无法回溯{self.p.lookback_days}天', level=logging.WARNING)
            return None
        
        # 统计回溯区间内的涨停天数
        has_limit_in_lookback = False
        limit_dates_in_lookback = []
        
        for i in range(lookback_start_idx, lookback_end_idx + 1):
            if abs(i) >= len(self.data):
                break
            
            if self.data.up_limit[i] == 1:
                has_limit_in_lookback = True
                limit_dates_in_lookback.append(self.datas[0].datetime.date(i))
        
        # ========== 步骤3 & 4：根据场景计算买点 ==========
        if has_limit_in_lookback:
            # 【场景B】回溯区间内有涨停，取 20 天平均收盘价
            self.log(f'📈 场景B: 回溯区间内发现 {len(limit_dates_in_lookback)} 个涨停日', level=logging.INFO)
            if self.p.debug_mode and limit_dates_in_lookback:
                self.log(f'涨停日期: {limit_dates_in_lookback[:5]}', level=logging.DEBUG)
            
            # 收集 20 天的收盘价
            close_prices = []
            for i in range(lookback_start_idx, lookback_end_idx + 1):
                if abs(i) >= len(self.data):
                    break
                close_prices.append(self.data.close[i])
            
            if not close_prices:
                self.log(f'❌ 场景B: 无法获取收盘价数据', level=logging.WARNING)
                return None
            
            # 计算平均值
            buy_price = sum(close_prices) / len(close_prices)
            
            self.log(f'💰 场景B买点计算 | 样本数:{len(close_prices)}天 | 收盘价范围:[{min(close_prices):.2f}, {max(close_prices):.2f}] | 平均值:{buy_price:.2f}', level=logging.INFO)
            
        else:
            # 【场景A】回溯区间内无涨停，取前3天最高价的最大值
            self.log(f'📉 场景A: 回溯区间内无涨停', level=logging.INFO)
            
            # 取 t-1, t-2, t-3 的最高价
            # t0_idx - 1 就是 t-1
            high_prices = []
            for i in range(t0_idx - 3, t0_idx):  # [t-3, t-2, t-1]
                if abs(i) >= len(self.data):
                    break
                high_price = self.data.high[i]
                high_prices.append(high_price)
                self.log(f'  前{abs(i)}天最高价: {high_price:.2f}', level=logging.DEBUG)
            
            if not high_prices:
                self.log(f'❌ 场景A: 无法获取前3天最高价', level=logging.WARNING)
                return None
            
            # 取最大值
            buy_price = max(high_prices)
            
            self.log(f'💰 场景A买点计算 | 前3天最高价:{high_prices} | 最大值:{buy_price:.2f}', level=logging.INFO)
        
        return buy_price


    def notify_order(self, order):
        """订单状态通知"""
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                # ✅ 记录实际买入数量
                self.buy_quantity = int(abs(order.executed.size))
                self.log(f'✅ 买入成交 | 价格:{order.executed.price:.2f} | 数量:{self.buy_quantity}股 | 成本:{order.executed.value:.2f}', level=logging.INFO)
            elif order.issell():
                self.sell_price = order.executed.price  # 记录卖出价
                self.log(f'💸 卖出成交 | 价格:{order.executed.price:.2f} | 数量:{self.buy_quantity}股 | 收益:{order.executed.pnl:.2f}', level=logging.INFO)

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            if order.status == order.Margin:
                self.log(f'订单失败: 资金不足', level=logging.ERROR)
            else:
                self.log(f'订单失败: {order.getstatusname()}', level=logging.ERROR)

        self.order = None


    def notify_trade(self, trade):
        """交易完成通知"""
        if trade.isclosed:
            # ✅ 使用记录的买入数量，而不是trade.size（可能为0）
            quantity = self.buy_quantity if self.buy_quantity > 0 else abs(trade.size)
            
            # 使用记录的卖出价，如果没有则使用 trade.price
            actual_sell_price = self.sell_price if self.sell_price else trade.price
            actual_buy_price = self.buy_price if self.buy_price else 0
            
            # 盈亏 = (卖出价 - 买入价) × 数量
            gross_profit = (actual_sell_price - actual_buy_price) * quantity
            
            # 手续费 = (买入金额 + 卖出金额) × 佣金率
            # 从 cerebro 获取佣金率（假设有设置）
            commission_rate = 0.0003  # 默认万三，应该从 cerebro.broker.comminfo 获取
            buy_cost = actual_buy_price * quantity
            sell_value = actual_sell_price * quantity
            commission = (buy_cost + sell_value) * commission_rate
            
            # 净利润 = 毛利润 - 手续费
            profit = gross_profit - commission
            
            # 收益率 = 净利润 / 买入成本
            if buy_cost != 0:
                profit_rate = (profit / buy_cost) * 100
            else:
                profit_rate = 0.0
                self.log(f'警告：买入成本为0，无法计算收益率', level=logging.WARNING)
            
            # 记录交易 - 包含数量和数值类型的盈亏、收益率
            trade_record = {
                '买入日期': self.buy_date.strftime('%Y-%m-%d') if self.buy_date else 'N/A',
                '卖出日期': self.sell_date.strftime('%Y-%m-%d') if self.sell_date else 'N/A',  # ✅ 使用决定卖出的日期
                '买入价格': actual_buy_price,
                '卖出价格': actual_sell_price,
                '数量': quantity,  # ✅ 记录实际买入数量
                '持仓天数': self.hold_days,
                '卖出原因': self.sell_reason or '未知',
                '盈亏金额': round(profit, 2),  # 数值类型
                '收益率': profit_rate / 100,  # ✅ 存储为小数（例如0.1018表示10.18%），而不是字符串
                # 买点差值跟踪数据
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
            
            self.log(f'💰 交易完成 | 买入:{actual_buy_price:.2f} | 卖出:{actual_sell_price:.2f} | 数量:{quantity}股 | 盈亏:{profit:.2f} | 收益率:{profit_rate:.2f}% | 原因:{self.sell_reason}', level=logging.INFO)

# -*- coding: UTF-8 -*-
'''
@Project ：backtrader-test 
@File ：bt_test_01.py
@Author ：Anita_熙烨（路虽远，行则降至！事虽难，做则必成！）
@Date ：2026/1/13 19:53 
@JianShu : 
'''
import backtrader as bt
import datetime
import pandas as pd
from conn_oracle import OracleDB
import matplotlib
import matplotlib.pyplot as plt
import logging
from colorlog import ColoredFormatter

matplotlib.use('TkAgg')  # 使用 TkAgg 后端
plt.rcParams['font.sans-serif'] = ['SimHei']  # 用来正常显示中文标签
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号
from plot_results import plot_backtest_results, plot_individual_trades

# 配置 colorlog
log_format = '%(log_color)s%(asctime)s | %(levelname)-8s | %(message)s%(reset)s'
formatter = ColoredFormatter(
    log_format,
    datefmt='%Y-%m-%d %H:%M:%S',
    log_colors={
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    }
)

# 创建handler并设置格式
handler = logging.StreamHandler()
handler.setFormatter(formatter)

# 获取logger并配置
logger = logging.getLogger('backtrader')
logger.addHandler(handler)

# 日志级别设置：
# logging.DEBUG   - 显示所有日志（包括详细的调试信息）
# logging.INFO    - 显示一般信息及以上（推荐用于正常回测）
# logging.WARNING - 只显示交易信号和错误（适合只关注买卖点）
# logging.ERROR   - 只显示错误信息
logger.setLevel(logging.INFO)  # 默认INFO级别，可根据需要调整


# 1. 策略：连续涨停 + 回调阴线
class LimitBreakStrategy(bt.Strategy):
    """
    连续涨停 + 回调阴线后的买卖策略
    """

    params = dict(
        profit_target=0.05,     # 盈利 5% 止盈
        max_hold_days=30,       # 最大持仓天数
        lookback_days=15,       # 向前回溯天数
        max_wait_days=100,       # 买点等待最大天数(超过则放弃该买点)
        debug_mode=False,       # 调试模式:是否打印所有形态检测日志
        position_pct=0.02,      # 每次买入占总资金的比例（2%）
    )

    def __init__(self):
        """初始化策略变量"""
        self.order = None              # 当前订单
        self.buy_price = None          # 实际买入价
        self.buy_date = None           # 买入日期
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

            # 止盈卖出
            profit_rate = (self.data.close[0] - self.buy_price) / self.buy_price
            self.log(f'计算止盈点位 {self.data.close[0]} / {self.buy_price}', level=logging.DEBUG)
            if profit_rate >= self.p.profit_target:
                self.sell_reason = '止盈'
                self.log(f'止盈卖出 | 收益率: {profit_rate:.2%} | 价格: {self.data.close[0]:.2f}', level=logging.WARNING)
                self.close()
                return

            # 超过最大持仓天数
            if self.hold_days >= self.p.max_hold_days:
                self.sell_reason = f'超期({self.hold_days}天)'
                self.log(f'超期卖出 | 持仓 {self.hold_days} 天 | 价格: {self.data.close[0]:.2f}', level=logging.WARNING)
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
        根据规则计算买点价格
        策略：找到第一个涨停日，从它之前开始回溯15天
        """
        current_date = self.datas[0].datetime.date(0)
        self.log(f'计算买点价格:', level=logging.DEBUG)
        
        # 找到第一个涨停日（从今天往前找）
        first_limit_idx = None
        idx = -2  # 从前天开始（因为前2天是下跌，前天之前才可能是涨停）
        
        while idx >= -len(self.data):
            # 直接读取 up_limit 列
            is_limit = self.data.up_limit[idx] == 1
            close_price = self.data.close[idx]
            
            if is_limit:
                first_limit_idx = idx
                # 继续往前找，找到最早的涨停日
                idx -= 1
            else:
                # 遇到非涨停日，停止
                self.log(f'当前非涨停日期为: {self.datas[0].datetime.date(idx)}', level=logging.DEBUG)
                break

        if first_limit_idx is None:
            self.log(f'未找到涨停日，无法计算买点', level=logging.WARNING)
            return None
        
        self.log(f'最早涨停日: 前{abs(first_limit_idx)}天 (收:{self.data.close[first_limit_idx]:.2f})', level=logging.DEBUG)
        
        # 从连续涨停的最早涨停日之前找第一个非涨停日
        # first_limit_idx - 1 应该就是第一个非涨停日（因为上面的循环已经找到了连续涨停的边界）
        first_non_limit_idx = first_limit_idx - 1
        
        if abs(first_non_limit_idx) >= len(self.data):
            self.log(f'连续涨停之前没有数据', level=logging.WARNING)
            return None
        
        # 验证是否真的是非涨停日
        if self.data.up_limit[first_non_limit_idx] == 1:
            self.log(f'错误：找到的应该是非涨停日，但实际是涨停日', level=logging.ERROR)
            return None
            
        self.log(f'第一个非涨停日: 前{abs(first_non_limit_idx)}天 (收:{self.data.close[first_non_limit_idx]:.2f})', level=logging.DEBUG)

        # 从第一个非涨停日开始，往前回溯15天
        start_idx = first_non_limit_idx - (self.p.lookback_days - 1)  # -14，因为包含first_non_limit_idx自己
        end_idx = first_non_limit_idx
        
        self.log(f'回溯区间: 前{abs(start_idx)}天 至 前{abs(end_idx)}天 (共{self.p.lookback_days}天)', level=logging.DEBUG)

        # 收集这15天的收盘价（不排除涨停日）
        lookback_closes = []
        lookback_info = []

        for i in range(start_idx, end_idx + 1):  # 包含 end_idx
            if abs(i) >= len(self.data):
                # 数据不足，只取能取到的
                break
            
            close_price = self.data.close[i]
            is_limit = self.data.up_limit[i] == 1
            lookback_closes.append(close_price)
            lookback_info.append(f"前{abs(i)}天: 收{close_price:.2f} {'[涨停]' if is_limit else ''}")

        if not lookback_closes:
            self.log(f'回溯期没有数据', level=logging.WARNING)
            return None

        # 计算平均价格（所有收盘价，包括涨停日）
        avg_price = sum(lookback_closes) / len(lookback_closes)
        
        self.log(f'买点计算 | 回溯天数:{len(lookback_closes)}天 | 收盘价:{[round(c, 2) for c in lookback_closes[:5]]}{"..." if len(lookback_closes) > 5 else ""} | 买点价格: {avg_price:.2f}', level=logging.INFO)
        
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
            # 计算盈亏
            profit = trade.pnlcomm  # 扣除手续费后的净利润
            # 避免除零错误
            if trade.value != 0:
                profit_rate = (trade.pnl / trade.value) * 100  # 收益率（%）
            else:
                profit_rate = 0.0
                self.log(f'警告：交易金额为0，无法计算收益率', level=logging.WARNING)
            
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
            
            self.log(f'交易完成 | 盈亏: {profit:.2f} | 收益率: {profit_rate:.2f}% | 原因: {self.sell_reason}', level=logging.INFO)



# 2. 数据获取类
class GetBasicData:
    def __init__(self):
        # 配置信息
        self.db_username = "HUABENWUXIN"
        self.db_password = "19861023Xjl_"
        self.db_dsn = "stockapi_high"
        self.db_wallet_dir = r"D:\miyao\Wallet_stockapi"

        # 在初始化时创建数据库实例并连接
        logger.info('正在连接 Oracle 数据库...')
        self.oracle_instance = OracleDB(
            username=self.db_username,
            password=self.db_password,
            dsn=self.db_dsn,
            wallet_dir=self.db_wallet_dir
        )
        self.db = self.oracle_instance.__enter__()
        logger.info('数据库连接成功！')

    def close(self):
        """手动关闭数据库连接"""
        if self.oracle_instance:
            self.oracle_instance.__exit__(None, None, None)
            logger.info('数据库连接已关闭。')

    def get_strategy_data(self):
        """获取当前进行中的策略详情及对应股票名称"""
        sql = """
              SELECT p.ID,
                     c.NAME AS STOCK_NAME,
                     p.STRATEGY_TYPE,
                     p.STOCK_ID,
                     p."DATE"
              FROM BASIC_POLICYDETAILS p
                       JOIN BASIC_CODE c ON p.STOCK_ID = c.TS_CODE
              WHERE p.CURRENT_STATUS = 'L'
              ORDER BY p.ID DESC
              """

        try:
            rows = self.db.fetch_all(sql)

            if not rows:
                logger.info("未查询到状态为 'L' (进行中) 的策略数据。")
                return []

            logger.info(f'查询成功，共 {len(rows)} 条数据')
            for row in rows:
                logger.info(f"ID: {row[0]} | 股票: {row[1]} ({row[3]}) | 策略: {row[2]} | 策略日期: {row[4]}")
            return rows

        except Exception as e:
            logger.error(f'SQL 执行失败: {e}')
            return []

    def get_stock_daily_data(self, stock_id, anchor_date):
        """获取指定股票日线数据"""
        # 1. 日期预处理
        if isinstance(anchor_date, datetime.datetime):
            anchor_date = anchor_date.date()
        elif isinstance(anchor_date, str):
            try:
                anchor_date = datetime.datetime.strptime(anchor_date, '%Y-%m-%d').date()
            except ValueError:
                try:
                    anchor_date = datetime.datetime.strptime(anchor_date, '%Y-%m-%d %H:%M:%S').date()
                except ValueError:
                    logger.error(f'日期格式错误: {anchor_date}')
                    return None

        # 2. 计算时间范围
        # 策略日期前需要足够的数据：形态检测(5天) + 回溯计算(15天) + 缓冲(10天) ≈ 30天
        # 为保险起见,向前加载60天
        start_date = anchor_date - datetime.timedelta(days=60)  # 扩大到60天
        theoretical_end_date = anchor_date + datetime.timedelta(days=60)
        today = datetime.date.today()
        end_date = min(theoretical_end_date, today)

        logger.debug(f'正在获取 {stock_id} 的数据，时间范围: {start_date} 至 {end_date}')

        # 3. 准备 SQL
        sql = """
              SELECT TRADE_DATE, OPEN, HIGH, LOW, CLOSE, VOLUME
              FROM BASIC_STOCKDAILYDATA
              WHERE STOCK_ID = :stock_id
                AND TRADE_DATE >= :start_date
                AND TRADE_DATE <= :end_date
              ORDER BY TRADE_DATE ASC
              """

        try:
            # 检查连接状态,如果断开则重连
            try:
                # 尝试执行一个简单查询来测试连接
                test_cursor = self.db.connection.cursor()
                test_cursor.close()
            except Exception as conn_err:
                logger.warning(f'检测到连接断开: {conn_err}, 正在重新连接...')
                self.oracle_instance.__exit__(None, None, None)
                self.db = self.oracle_instance.__enter__()
                logger.info('重新连接成功！')
            
            with self.db.connection.cursor() as cursor:
                cursor.execute(sql, {
                    'stock_id': stock_id,
                    'start_date': start_date,
                    'end_date': end_date
                })
                rows = cursor.fetchall()

                if rows:
                    logger.debug(f'成功获取 {len(rows)} 条日线数据')
                    # 转换为 DataFrame
                    df = pd.DataFrame(rows, columns=[
                        'trade_date', 'open', 'high', 'low', 'close', 'volume'
                    ])
                    df['trade_date'] = pd.to_datetime(df['trade_date'])
                    df.set_index('trade_date', inplace=True)
                    
                    # 计算涨停列：(今天收盘-昨天收盘)/昨天收盘 > 0.096
                    df['up_limit'] = ((df['close'] - df['close'].shift(1)) / df['close'].shift(1) > 0.096).astype(int)
                    
                    return df
                else:
                    logger.warning(f'未找到 {stock_id} 在该时间段的数据')
                    return None

        except Exception as e:
            logger.error(f'获取日线数据失败: {e}')
            import traceback
            traceback.print_exc()
            return None


# 3. 自定义数据源
class StockData(bt.feeds.PandasData):
    """自定义数据源"""
    params = (
        ('datetime', None),
        ('open', 'open'),
        ('high', 'high'),
        ('low', 'low'),
        ('close', 'close'),
        ('volume', 'volume'),
        ('up_limit', -1),  # 添加 up_limit 字段
    )
    
    lines = ('up_limit',)  # 声明额外的line


# 4. 主程序
if __name__ == "__main__":
    getter = None
    all_results = []  # 所有股票的回测结果
    
    try:
        # 1. 实例化数据获取类
        getter = GetBasicData()

        # 2. 获取策略列表
        strategy_rows = getter.get_strategy_data()[20:]

        if not strategy_rows:
            logger.info('没有可回测的股票')
        else:
            logger.info(f'========== 开始批量回测 {len(strategy_rows)} 只股票 ==========')
            
            # 3. 遍历每只股票进行回测
            for idx, strategy in enumerate(strategy_rows, 1):
                stock_id = strategy[3]
                stock_name = strategy[1]
                s_date = strategy[4]
                
                logger.info('='*60)
                logger.info(f'[{idx}/{len(strategy_rows)}] 回测股票: {stock_name} ({stock_id})')
                logger.info('='*60)

                # 获取日线数据
                df_data = getter.get_stock_daily_data(stock_id, s_date)

                if df_data is None or df_data.empty:
                    logger.warning(f'{stock_id} 无数据，跳过')
                    continue

                # 创建 Backtrader 引擎
                cerebro = bt.Cerebro()

                # 添加策略
                cerebro.addstrategy(LimitBreakStrategy)

                # 转换数据并添加到引擎
                data_feed = StockData(dataname=df_data)
                cerebro.adddata(data_feed)

                # 设置初始资金
                initial_cash = 1000000.0
                cerebro.broker.setcash(initial_cash)

                # 设置手续费
                cerebro.broker.setcommission(commission=0.001)  # 0.1%
                
                # 添加分析器
                cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
                cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
                cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

                # 运行回测
                logger.info(f'初始资金: {initial_cash:,.2f}')
                results = cerebro.run()
                strategy_instance = results[0]
                final_value = cerebro.broker.getvalue()
                
                # 获取分析器结果
                returns_analyzer = strategy_instance.analyzers.returns.get_analysis()
                drawdown_analyzer = strategy_instance.analyzers.drawdown.get_analysis()
                trades_analyzer = strategy_instance.analyzers.trades.get_analysis()
                
                # 计算总收益
                total_return = final_value - initial_cash
                return_rate = (total_return / initial_cash) * 100
                
                # 最大回撤
                max_drawdown = drawdown_analyzer.get('max', {}).get('drawdown', 0)
                
                # 交易统计
                total_trades = trades_analyzer.get('total', {}).get('closed', 0)
                won_trades = trades_analyzer.get('won', {}).get('total', 0)
                lost_trades = trades_analyzer.get('lost', {}).get('total', 0)
                win_rate = (won_trades / total_trades * 100) if total_trades > 0 else 0
                
                # 输出结果
                logger.info('='*40)
                logger.info('  回测结果汇总')
                logger.info('='*40)
                logger.info(f'最终资金: {final_value:,.2f}')
                logger.info(f'总收益: {total_return:,.2f} ({return_rate:+.2f}%)')
                
                # 获取最小差值相关数据
                # 优先从交易记录获取，如果没有交易则从策略实例获取
                if strategy_instance.trades_record:
                    # 从最后一笔交易获取
                    last_trade = strategy_instance.trades_record[-1]
                    min_diff_display = last_trade['最小差值']
                    min_diff_date_display = last_trade['最小差值日期']
                    days_to_min_diff_display = last_trade['距买点确定天数']
                else:
                    # 从策略实例获取
                    min_diff_display = f'{strategy_instance.min_diff_to_target:.2f}' if strategy_instance.min_diff_to_target is not None else None
                    min_diff_date_display = strategy_instance.min_diff_date.strftime('%Y-%m-%d') if strategy_instance.min_diff_date else None
                    days_to_min_diff_display = strategy_instance.days_to_min_diff
                
                logger.info(f'与买点最近的差值：{min_diff_display}')
                logger.info(f"最小差值出现的日期：{min_diff_date_display}")
                logger.info(f"从买点确定到最小差值出现的天数: {days_to_min_diff_display}")
                logger.info(f'最大回撤: {max_drawdown:.2f}%')
                logger.info(f'交易次数: {total_trades}')
                logger.info(f'胜率: {win_rate:.2f}% ({won_trades}胜/{lost_trades}负)')
                logger.info('='*40)
                
                # 输出交易明细
                if strategy_instance.trades_record:
                    print(f'交易明细 (共{len(strategy_instance.trades_record)}笔):')
                    print(f'{"-"*160}')
                    print(f'{"买入日期":<12} {"卖出日期":<12} {"买入价":<8} {"卖出价":<8} {"持仓天数":<8} '
                          f'{"卖出原因":<15} {"盈亏金额":<10} {"收益率":<10} '
                          f'{"最小差值":<10} {"最小差值日期":<14} {"距买点天数":<10}')
                    print(f'{"-"*160}')
                    for trade in strategy_instance.trades_record:
                        min_diff_str = f'{trade["最小差值"]:.2f}' if isinstance(trade["最小差值"], (int, float)) else str(trade["最小差值"])
                        days_str = str(trade["距买点确定天数"])
                        print(f'{trade["买入日期"]:<12} {trade["卖出日期"]:<12} '
                              f'{trade["买入价格"]:<8.2f} {trade["卖出价格"]:<8.2f} '
                              f'{trade["持仓天数"]:<8} {trade["卖出原因"]:<15} '
                              f'{trade["盈亏金额"]:<10.2f} {trade["收益率"]:<10} '
                              f'{min_diff_str:<10} {trade["最小差值日期"]:<14} {days_str:<10}')
                    print(f'{"-"*160}\n')
                else:
                    print('⚠️ 未产生任何交易\n')
                
                # 保存结果
                all_results.append({
                    'stock_id': stock_id,
                    'stock_name': stock_name,
                    'initial_cash': initial_cash,
                    'final_value': final_value,
                    'total_return': total_return,
                    'return_rate': return_rate,
                    'max_drawdown': max_drawdown,
                    'total_trades': total_trades,
                    'won_trades': won_trades,
                    'lost_trades': lost_trades,
                    'win_rate': win_rate,
                    'trades_detail': strategy_instance.trades_record.copy(),
                    'daily_values': strategy_instance.daily_values.copy(),  # 添加每日资金数据
                    'cerebro': cerebro
                })
            
            # 4. 输出汇总统计
            if all_results:
                logger.info('='*80)
                logger.info(f'{"所有股票回测汇总":^76}')
                logger.info('='*80)
                
                total_initial = sum(r['initial_cash'] for r in all_results)
                total_final = sum(r['final_value'] for r in all_results)
                total_profit = total_final - total_initial
                total_return_rate = (total_profit / total_initial) * 100
                
                logger.info(f'总初始资金: {total_initial:,.2f}')
                logger.info(f'总最终资金: {total_final:,.2f}')
                logger.info(f'总盈利: {total_profit:,.2f} ({total_return_rate:+.2f}%)')
                logger.info(f'平均最大回撤: {sum(r["max_drawdown"] for r in all_results) / len(all_results):.2f}%')
                logger.info(f'总交易次数: {sum(r["total_trades"] for r in all_results)}')
                logger.info(f'总胜率: {sum(r["won_trades"] for r in all_results) / max(sum(r["total_trades"] for r in all_results), 1) * 100:.2f}%')
                
                logger.info(f'{"股票代码":<12} {"股票名称":<10} {"收益":<12} {"收益率":<10} {"最大回撤":<10} {"交易次数":<8} {"胜率":<8}')
                logger.info('-'*80)
                for r in all_results:
                    logger.info(f'{r["stock_id"]:<12} {r["stock_name"]:<10} '
                          f'{r["total_return"]:<12,.2f} {r["return_rate"]:<10.2f}% '
                          f'{r["max_drawdown"]:<10.2f}% {r["total_trades"]:<8} '
                          f'{r["win_rate"]:<8.2f}%')
                logger.info('-'*80)
                
                # 5. 绘制图表
                logger.info('正在生成可视化图表...')
                plot_backtest_results(all_results)
                plot_individual_trades(all_results)
                
                # 导入并绘制每日收益走势
                from plot_results import plot_daily_returns
                plot_daily_returns(all_results)

    except Exception as e:
        logger.error(f'程序运行出错: {e}')
        import traceback
        traceback.print_exc()
    finally:
        if getter:
            getter.close()

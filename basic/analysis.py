import pandas as pd
import numpy as np
from basic.models import StockDailyData, PolicyDetails
from django.db import transaction
from datetime import datetime, timedelta

class TechnicalAnalysis:
    @staticmethod
    def calculate_ma(data, period):
        """计算移动平均线"""
        return data['close'].rolling(window=period).mean()

    @staticmethod
    def generate_signals(stock_code, start_date, end_date):
        """生成交易信号"""
        daily_data = StockDailyData.objects.filter(
            stock__ts_code=stock_code,
            trade_date__range=[start_date, end_date]
        ).order_by('trade_date')
        
        # 将数据转换为DataFrame进行分析
        df = pd.DataFrame(list(daily_data.values()))
        
        # 计算技术指标
        df['MA5'] = TechnicalAnalysis.calculate_ma(df, 5)
        df['MA10'] = TechnicalAnalysis.calculate_ma(df, 10)
        
        # 生成交易信号
        signals = []
        for index, row in df.iterrows():
            if index < 1:
                continue
                
            # 示例：当5日均线上穿10日均线时产生买入信号
            if (df['MA5'][index-1] <= df['MA10'][index-1] and 
                df['MA5'][index] > df['MA10'][index]):
                signals.append({
                    'stock': stock_code,
                    'date': row['trade_date'],
                    'first_buy_point': row['close'],
                    'stop_loss_point': row['low'] * 0.95,
                    'take_profit_point': row['close'] * 1.1,
                    'strategy_type': 'MA_CROSS',
                    'signal_strength': 0.8
                })
        
        return signals 

class ContinuousLimitStrategy:
    """连续涨停策略分析类
    
    该类实现了基于连续涨停的交易策略，包括信号生成和状态更新
    
    主要功能：
    1. 识别连续涨停股票
    2. 生成交易信号
    3. 更新策略状态
    4. 计算持仓收益
    """

    def __init__(self):
        """初始化策略参数"""
        self.LIMIT_UP_THRESHOLD = 0.098  # 涨停阈值（考虑误差）
        self.SUCCESS_PROFIT_THRESHOLD = 0.075  # 成功盈利阈值
        self.TAKE_PROFIT_MULTIPLIER = 1.075  # 止盈倍数

    def is_limit_up(self, row):
        """判断是否涨停
        
        Args:
            row (dict): 包含股票价格数据的字典
            
        Returns:
            bool: True表示涨停，False表示非涨停
        """
        return (row['close'] - row['pre_close']) / row['pre_close'] >= self.LIMIT_UP_THRESHOLD

    def is_negative_day(self, row):
        """判断是否收阴"""
        return row['close'] < row['open']

    def calculate_buy_points(self, data):
        """计算买点价格
        
        Args:
            data (DataFrame): 包含历史价格数据的DataFrame
            
        Returns:
            dict: 包含各个关键价格点位的字典
            {
                'first_buy_point': float,  # 第一买点
                'second_buy_point': float, # 第二买点
                'stop_loss_point': float,  # 止损点
                'take_profit_point': float # 止盈点
            }
        """
        highest = data['high'].max()
        lowest = data['low'].min()
        return {
            'first_buy_point': highest,
            'second_buy_point': (highest + lowest) / 2,
            'stop_loss_point': lowest,
            'take_profit_point': highest * 1.75
        }

    def analyze_stock(self, stock_code, start_date, end_date):
        """分析单个股票的交易信号
        
        Args:
            stock_code (str): 股票代码
            start_date (str): 开始日期
            end_date (str): 结束日期
            
        Returns:
            list: 包含交易信号的列表
            
        功能说明：
        1. 获取指定日期范围内的股票数据
        2. 寻找符合策略条件的交易信号：
           - 连续两天涨停
           - 之后连续两天收阴
           - 前10天内无涨停
        3. 计算相关价格点位
        """
        daily_data = StockDailyData.objects.filter(
            stock__ts_code=stock_code,
            trade_date__range=[start_date, end_date]
        ).order_by('trade_date')
        
        df = pd.DataFrame(list(daily_data.values()))
        if len(df) < 12:  # 确保有足够的数据进行分析
            return []

        signals = []
        for i in range(2, len(df)-2):
            # 检查连续两天涨停
            if (self.is_limit_up(df.iloc[i]) and 
                self.is_limit_up(df.iloc[i-1])):
                
                # 检查之后是否出现连续两天收阴
                if (self.is_negative_day(df.iloc[i+1]) and 
                    self.is_negative_day(df.iloc[i+2])):
                    
                    # 检查前10天是否有涨停
                    previous_10_days = df.iloc[i-11:i-1]
                    has_limit_up = any(self.is_limit_up(row) for _, row in previous_10_days.iterrows())
                    
                    if not has_limit_up:
                        # 分析前3天非涨停的数据
                        buy_points = self.calculate_buy_points(df.iloc[i-4:i-1])
                        signals.append({
                            'stock': stock_code,
                            'date': df.iloc[i]['trade_date'],
                            **buy_points,
                            'strategy_type': 'CONTINUOUS_LIMIT_UP',
                            'signal_strength': 0.9
                        })
        
        return signals

    def save_signals(self, signals):
        """保存信号到数据库"""
        with transaction.atomic():
            for signal in signals:
                PolicyDetails.objects.create(**signal)

    def update_historical_signals(self, days=30):
        """更新历史信号状态
        
        Args:
            days (int): 更新多少天内的信号
            
        功能说明：
        1. 获取指定天数内的所有策略信号
        2. 计算每个信号的持仓价格和盈利情况
        3. 更新信号状态（成功/失败/进行中）
        4. 更新止盈价格
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        signals = PolicyDetails.objects.filter(
            date__gte=cutoff_date,
            strategy_type='龙回头'
        )

        for signal in signals:
            # 获取买点后的价格数据
            subsequent_data = StockDailyData.objects.filter(
                stock=signal.stock,
                trade_date__gt=signal.date
            ).order_by('trade_date')

            if not subsequent_data:
                continue

            # 初始化变量
            holding_price = 0
            latest_close = subsequent_data.latest('trade_date').close

            # 遍历后续数据计算持仓价格
            for data in subsequent_data:
                if data.low <= signal.first_buy_point:
                    if data.low > signal.second_buy_point:
                        holding_price = signal.first_buy_point
                    else:
                        holding_price = (signal.first_buy_point + signal.second_buy_point) / 2
                    break

            # 如果已经有持仓价格，更新相关数据
            if holding_price > 0:
                signal.holding_price = holding_price
                signal.take_profit_point = holding_price * self.TAKE_PROFIT_MULTIPLIER
                
                # 计算持仓盈利
                signal.holding_profit = (latest_close - holding_price) / holding_price * 100
                
                # 更新策略状态
                if signal.holding_profit >= self.SUCCESS_PROFIT_THRESHOLD * 100:
                    signal.current_status = 'S'
                elif latest_close < signal.stop_loss_point:
                    signal.current_status = 'F'
                
                signal.save()

class BacktestAnalysis:
    @staticmethod
    def run_backtest(stock_code, start_date, end_date):
        """执行回测"""
        signals = PolicyDetails.objects.filter(
            stock__ts_code=stock_code,
            date__range=[start_date, end_date]
        ).order_by('date')

        results = []
        for signal in signals:
            # 获取信号后的价格数据
            subsequent_data = StockDailyData.objects.filter(
                stock=signal.stock,
                trade_date__gt=signal.date
            ).order_by('trade_date')

            entry_price = (signal.first_buy_point + signal.second_buy_point) / 2
            
            # 检查是否触及second_buy_point
            touched_second = False
            for data in subsequent_data:
                if data.low <= signal.second_buy_point:
                    touched_second = True
                    break

            if not touched_second:
                signal.second_buy_point = 0
                signal.save()

            results.append({
                'date': signal.date,
                'entry_price': entry_price,
                'touched_second': touched_second
            })

        return results 
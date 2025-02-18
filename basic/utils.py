import tushare as ts
from .models import Code, StockDailyData, TradingCalendar, PolicyDetails
from decouple import config
from django.db import transaction, connection
import pandas as pd
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
import traceback  # 添加这个导入
from django.db.models import F, Count
from django.core.cache import cache
import logging
from decimal import Decimal
from django.db.utils import IntegrityError

# 配置logger
logger = logging.getLogger(__name__)

# 初始化 Tushare
ts.set_token(config("TUSHARE_TOKEN"))
pro = ts.pro_api()


def fetch_and_save_stock_data():
    # 获取股票数据
    df = pro.stock_basic(list_status='L', fields='ts_code,symbol,name,area,industry,market,list_status,list_date')

    for index, row in df.iterrows():
        with transaction.atomic():  # 确保在事务中执行
            # 使用 get_or_create 替代 update_or_create，避免并发问题
            stock_data, created = Code.objects.get_or_create(
                ts_code=row['ts_code'],
                defaults={
                    'symbol': row['symbol'],
                    'name': row['name'],
                    'area': row['area'],
                    'industry': row['industry'],
                    'market': row['market'],
                    'list_status': row['list_status'],
                    'list_date': row['list_date']
                }
            )
            
            if created:
                print(f"新股票 {row['name']} ({row['ts_code']}) 已添加到数据库")
            else:
                print(f"股票 {row['name']} ({row['ts_code']}) 已存在")


class StockDataFetcher:
    """股票数据获取工具类
    
    负责从Tushare获取股票数据并保存到数据库
    
    主要功能：
    1. 获取股票基本信息
    2. 获取日线行情数据
    3. 增量更新数据
    """

    def __init__(self):
        ts.set_token(config("TUSHARE_TOKEN"))
        self.pro = ts.pro_api()

    def fetch_daily_data(self, ts_code, start_date, end_date):
        """获取指定股票的日线数据和涨跌停数据
        
        Args:
            ts_code (str): Tushare股票代码
            start_date (str): 开始日期（YYYYMMDD）
            end_date (str): 结束日期（YYYYMMDD）
            
        Returns:
            DataFrame: 包含合并后的股票数据的DataFrame
        """
        try:
            # 获取日线数据
            df_daily = self.pro.daily(
                ts_code=ts_code, 
                start_date=start_date, 
                end_date=end_date,
                fields='ts_code,trade_date,open,high,low,close,vol,amount'
            )
            
            # 获取涨跌停价格
            df_limit = self.pro.stk_limit(
                ts_code=ts_code,
                start_date=start_date,
                end_date=end_date,
                fields='ts_code,trade_date,up_limit,down_limit'
            )
            
            # 合并数据
            if not df_daily.empty and not df_limit.empty:
                df = pd.merge(
                    df_daily, 
                    df_limit, 
                    on=['ts_code', 'trade_date'],
                    how='inner'
                )
                return df
            return None
        except Exception as e:
            print(f"获取{ts_code}数据失败：{str(e)}")
            return None

    def update_stock_daily_data(self):
        """更新所有股票的日线数据
        
        功能说明：
        1. 获取最新的交易日数据
        2. 保持最近1000个交易日的数据
        3. 删除旧数据并保存新数据
        """
        try:
            with transaction.atomic():
                codes = Code.objects.all()
                for code in codes:
                    # 获取该股票最新的数据日期
                    latest_data = StockDailyData.objects.filter(
                        stock=code
                    ).order_by('-trade_date').first()
                    
                    if latest_data:
                        start_date = (latest_data.trade_date + timedelta(days=1)).strftime('%Y%m%d')
                    else:
                        # 如果没有数据，获取最近1000个交易日的数据
                        calendar = TradingCalendar.objects.filter(
                            is_trading_day=True
                        ).order_by('-date')[:1000]
                        if calendar:
                            start_date = calendar.last().date.strftime('%Y%m%d')
                        else:
                            start_date = '20200101'  # 默认起始日期
                    
                    end_date = datetime.now().strftime('%Y%m%d')
                    
                    # 获取新数据
                    df = self.fetch_daily_data(code.ts_code, start_date, end_date)
                    if df is not None and not df.empty:
                        # 转换数据类型
                        df['trade_date'] = pd.to_datetime(df['trade_date'])
                        
                        # 保存新数据
                        for _, row in df.iterrows():
                            StockDailyData.objects.create(
                                stock=code,
                                trade_date=row['trade_date'],
                                open=row['open'],
                                high=row['high'],
                                low=row['low'],
                                close=row['close'],
                                volume=row['vol'],
                                amount=row['amount'],
                                up_limit=row['up_limit'],
                                down_limit=row['down_limit']
                            )
                        
                        # 检查并删除旧数据
                        old_records = StockDailyData.objects.filter(
                            stock=code
                        ).order_by('-trade_date')[1000:]
                        if old_records.exists():
                            old_records.delete()
                    
                    print(f"股票 {code.name} ({code.ts_code}) 数据更新完成")
                    
        except Exception as e:
            print(f"更新日线数据失败：{str(e)}")
            raise

    def fetch_trading_calendar(self, start_date=None, end_date=None):
        """获取交易日历数据
        
        Args:
            start_date (str): 开始日期，格式：YYYYMMDD
            end_date (str): 结束日期，格式：YYYYMMDD
            
        Returns:
            DataFrame: 包含交易日历数据的DataFrame
        """
        try:
            df = self.pro.trade_cal(
                start_date=start_date,
                end_date=end_date,
                fields='cal_date,is_open,pretrade_date'
            )
            return df
        except Exception as e:
            print(f"获取交易日历数据失败：{str(e)}")
            return None

    def update_trading_calendar(self, date_str=None):
        """更新交易日历数据
        
        Args:
            date_str (str): 指定日期，格式：YYYY-MM-DD，如果为None则获取当年数据
            
        Returns:
            bool: 更新是否成功
        """
        try:
            if date_str:
                # 如果指定了日期，获取该年份的数据
                year = datetime.strptime(date_str, '%Y-%m-%d').year
                start_date = f"{year}0101"
                end_date = f"{year}1231"
            else:
                # 获取当年数据
                current_year = datetime.now().year
                start_date = f"{current_year}0101"
                end_date = f"{current_year}1231"

            df = self.fetch_trading_calendar(start_date, end_date)
            if df is not None:
                with transaction.atomic():
                    for _, row in df.iterrows():
                        date = datetime.strptime(row['cal_date'], '%Y%m%d').date()
                        TradingCalendar.objects.update_or_create(
                            date=date,
                            defaults={
                                'is_trading_day': bool(row['is_open']),
                                'remark': '交易日' if row['is_open'] else '非交易日'
                            }
                        )
                return True
            return False
        except Exception as e:
            print(f"更新交易日历失败：{str(e)}")
            return False

    def fetch_all_stocks_daily_data(self, trade_date=None, start_date=None, end_date=None):
        """获取所有股票的日线数据
        
        Args:
            trade_date (str): 交易日期（YYYYMMDD格式）
            start_date (str): 开始日期（YYYYMMDD格式）
            end_date (str): 结束日期（YYYYMMDD格式）
        
        Returns:
            DataFrame: 包含所有股票数据的DataFrame
        """
        try:
            # 验证日期是否为交易日
            if trade_date:
                date = datetime.strptime(trade_date, '%Y%m%d').date()
                is_trading = TradingCalendar.objects.filter(
                    date=date,
                    is_trading_day=True
                ).exists()
                if not is_trading:
                    print(f"{trade_date} 不是交易日")
                    return None
                
                # 获取单日数据
                df_daily = self.pro.daily(
                    trade_date=trade_date,
                    fields='ts_code,trade_date,open,high,low,close,vol,amount'
                )
                df_limit = self.pro.stk_limit(
                    trade_date=trade_date,
                    fields='ts_code,trade_date,up_limit,down_limit'
                )
            else:
                # 获取日期范围内的数据
                df_daily = self.pro.daily(
                    start_date=start_date,
                    end_date=end_date,
                    fields='ts_code,trade_date,open,high,low,close,vol,amount'
                )
                df_limit = self.pro.stk_limit(
                    start_date=start_date,
                    end_date=end_date,
                    fields='ts_code,trade_date,up_limit,down_limit'
                )
            
            # 合并数据
            if not df_daily.empty and not df_limit.empty:
                df = pd.merge(
                    df_daily,
                    df_limit,
                    on=['ts_code', 'trade_date'],
                    how='inner'
                )
                return df
            return None
        except Exception as e:
            print(f"获取股票数据失败：{str(e)}")
            return None

    def cleanup_old_data(self):
        """清理旧数据
        
        保留最近500个交易日的数据，删除更早的数据
        """
        try:
            with transaction.atomic():
                # 获取最近500个交易日
                trading_days = TradingCalendar.objects.filter(
                    is_trading_day=True
                ).order_by('-date')[:500]
                
                if trading_days:
                    cutoff_date = trading_days.last().date
                    # 删除早于截止日期的数据
                    deleted_count = StockDailyData.objects.filter(
                        trade_date__lt=cutoff_date
                    ).delete()[0]
                    
                    return {
                        'status': 'success',
                        'message': f'已删除 {deleted_count} 条旧数据（{cutoff_date} 之前）'
                    }
                return {
                    'status': 'skipped',
                    'message': '未找到足够的交易日历数据'
                }
        except Exception as e:
            return {
                'status': 'error',
                'message': f'清理旧数据失败：{str(e)}'
            }

    def fetch_and_filter_daily_data(self, trade_date=None, start_date=None, end_date=None):
        """获取并过滤日线数据"""
        try:
            # 1. 一次性获取所有股票代码和对象的映射
            codes_map = {
                code.ts_code: code for code in Code.objects.all()
            }
            valid_codes = set(codes_map.keys())
            
            # 2. 从Tushare获取数据
            if trade_date:
                df_daily = self.pro.daily(
                    trade_date=trade_date,
                    fields='ts_code,trade_date,open,high,low,close,vol,amount'
                )
                df_limit = self.pro.stk_limit(
                    trade_date=trade_date,
                    fields='ts_code,trade_date,up_limit,down_limit'
                )
            else:
                df_daily = self.pro.daily(
                    start_date=start_date,
                    end_date=end_date,
                    fields='ts_code,trade_date,open,high,low,close,vol,amount'
                )
                df_limit = self.pro.stk_limit(
                    start_date=start_date,
                    end_date=end_date,
                    fields='ts_code,trade_date,up_limit,down_limit'
                )
            
            # 3. 合并日线数据和涨跌停数据
            if not df_daily.empty and not df_limit.empty:
                df = pd.merge(
                    df_daily,
                    df_limit,
                    on=['ts_code', 'trade_date'],
                    how='inner'
                )
                
                # 4. 过滤掉不在数据库中的股票代码
                df = df[df['ts_code'].isin(valid_codes)]
                
                # 5. 转换日期格式
                df['trade_date'] = pd.to_datetime(df['trade_date'])
                
                # 6. 添加stock对象到DataFrame
                df['stock'] = df['ts_code'].map(codes_map)
                
                # 7. 记录处理信息
                print("数据处理完成：")
                print(f"- 总记录数：{len(df)}")
                print(f"- 有效股票数：{len(df['ts_code'].unique())}")
                
                return df
            return None
        except Exception as e:
            print("获取股票数据失败：{}".format(str(e)))
            return None

    def fetch_daily_batch(self, trade_date):
        """获取单日所有股票数据"""
        df = self.fetch_and_filter_daily_data(trade_date=trade_date)
        return trade_date, df

    def update_all_stocks_daily_data(self, trade_date=None, start_date=None, end_date=None):
        """更新所有股票的日线数据"""
        try:
            # 定义批处理大小
            batch_size = 1000
            
            if trade_date:
                # 1. 转换日期格式
                check_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
                
                # 2. 检查是否为交易日
                is_trading = TradingCalendar.objects.filter(
                    date=check_date,
                    is_trading_day=True
                ).exists()
                
                if not is_trading:
                    return {
                        'status': 'skipped',
                        'message': f'{trade_date} 不是交易日'
                    }
                
                # 3. 检查是否已有数据
                existing_data = StockDailyData.objects.filter(
                    trade_date=check_date
                ).exists()
                
                if existing_data:
                    return {
                        'status': 'skipped',
                        'message': f'{trade_date} 的数据已存在'
                    }
                
                # 4. 获取当天数据
                tushare_date = check_date.strftime('%Y%m%d')
                df = self.fetch_and_filter_daily_data(trade_date=tushare_date)
                
                if df is not None and not df.empty:
                    try:
                        total_records = len(df)
                        print(f"获取数据: {total_records} 条记录")
                        
                        # 5. 批量保存数据
                        daily_saved = 0  # 记录单日保存数量
                        
                        with transaction.atomic():
                            try:
                                for start_idx in range(0, total_records, batch_size):
                                    try:
                                        end_idx = min(start_idx + batch_size, total_records)
                                        batch_df = df.iloc[start_idx:end_idx]
                                        
                                        bulk_data = [
                                            StockDailyData(
                                                stock=row['stock'],
                                                trade_date=row['trade_date'],
                                                open=row['open'],
                                                high=row['high'],
                                                low=row['low'],
                                                close=row['close'],
                                                volume=row['vol'],
                                                amount=row['amount'],
                                                up_limit=row['up_limit'],
                                                down_limit=row['down_limit']
                                            )
                                            for _, row in batch_df.iterrows()
                                        ]
                                        
                                        StockDailyData.objects.bulk_create(bulk_data)
                                        daily_saved += len(bulk_data)
                                        total_saved += len(bulk_data)
                                        print(f"进度: {daily_saved}/{total_records} (总计: {total_saved})")
                                        
                                    except Exception as batch_error:
                                        print(f"{trade_date} 批量错误: {str(batch_error)}")
                                        raise
                            
                            except Exception as tx_error:
                                print(f"{trade_date} 事务错误: {str(tx_error)}")
                                raise
                            
                        # 6. 清理旧数据
                        cleanup_result = self.cleanup_old_data()
                        
                        return {
                            'status': 'success',
                            'message': f'更新完成: {total_saved}/{total_records} 条记录'
                        }
                        
                    except Exception as save_error:
                        print(f"保存数据错误: {str(save_error)}")
                        raise
                else:
                    return {
                        'status': 'failed',
                        'message': f'没有获取到 {trade_date} 的数据'
                    }
            else:
                # 1. 转换日期格式
                start = datetime.strptime(start_date, '%Y-%m-%d').date()
                end = datetime.strptime(end_date, '%Y-%m-%d').date()
                
                try:
                    # 2. 获取时间段内的交易日
                    trading_days = TradingCalendar.objects.filter(
                        date__range=[start, end],
                        is_trading_day=True
                    ).order_by('date')[:30]  # 最多处理30个交易日
                    
                    if not trading_days:
                        return {
                            'status': 'skipped',
                            'message': f'在 {start_date} 至 {end_date} 期间没有交易日'
                        }
                    
                    # 3. 获取已存在的日期
                    existing_dates = set(StockDailyData.objects.filter(
                        trade_date__range=[start, end]
                    ).values_list('trade_date', flat=True).distinct())
                    
                    # 4. 找出需要获取的日期
                    dates_to_fetch = [
                        d.date for d in trading_days 
                        if d.date not in existing_dates
                    ]
                    
                    if not dates_to_fetch:
                        return {
                            'status': 'skipped',
                            'message': '所选时间段内的数据已存在'
                        }
                    
                    # 5. 获取每个交易日的数据
                    total_saved = 0
                    processed_dates = []
                    
                    for fetch_date in dates_to_fetch:
                        try:
                            # 获取单日数据
                            tushare_date = fetch_date.strftime('%Y%m%d')
                            df = self.fetch_and_filter_daily_data(trade_date=tushare_date)
                            
                            if df is not None and not df.empty:
                                total_records = len(df)
                                daily_saved = 0
                                
                                try:
                                    with transaction.atomic():
                                        for start_idx in range(0, total_records, batch_size):
                                            end_idx = min(start_idx + batch_size, total_records)
                                            batch_df = df.iloc[start_idx:end_idx]
                                            
                                            bulk_data = [
                                                StockDailyData(
                                                    stock=row['stock'],
                                                    trade_date=row['trade_date'],
                                                    open=row['open'],
                                                    high=row['high'],
                                                    low=row['low'],
                                                    close=row['close'],
                                                    volume=row['vol'],
                                                    amount=row['amount'],
                                                    up_limit=row['up_limit'],
                                                    down_limit=row['down_limit']
                                                )
                                                for _, row in batch_df.iterrows()
                                            ]
                                            
                                            try:
                                                StockDailyData.objects.bulk_create(bulk_data)
                                                daily_saved += len(bulk_data)
                                                total_saved += len(bulk_data)
                                            except OSError as ose:
                                                if "Broken pipe" in str(ose) or "write error" in str(ose):
                                                    continue  # 忽略管道错误，继续处理
                                                raise
                                            
                                    processed_dates.append(fetch_date)
                                    
                                except Exception as tx_error:
                                    if "Broken pipe" not in str(tx_error) and "write error" not in str(tx_error):
                                        raise
                                    
                        except Exception as date_error:
                            if "Broken pipe" not in str(date_error) and "write error" not in str(date_error):
                                continue
                    
                    # 6. 清理旧数据
                    cleanup_result = self.cleanup_old_data()
                    
                    if total_saved > 0:
                        return {
                            'status': 'success',
                            'message': (
                                f'数据更新完成，共更新 {total_saved} 条记录，'
                                f'处理了 {len(processed_dates)} 个交易日。'
                                f'{cleanup_result["message"] if "message" in cleanup_result else ""}'
                            )
                        }
                    else:
                        return {
                            'status': 'failed',
                            'message': '没有获取到任何有效数据'
                        }
                    
                except Exception as query_error:
                    if "Broken pipe" in str(query_error) or "write error" in str(query_error):
                        return {
                            'status': 'interrupted',
                            'message': '数据更新被中断，但已保存部分数据'
                        }
                    raise
                
        except Exception as e:
            if "Broken pipe" in str(e) or "write error" in str(e):
                return {
                    'status': 'interrupted',
                    'message': '连接中断，但已保存部分数据'
                }
            raise

    def analyze_stock_pattern(self, trade_date):
        """分析特定日期的股票涨停回落模式并保存策略"""
        try:
            logger.info(f"开始分析日期 {trade_date} 的股票模式")
            
            # 直接获取交易日历数据
            try:
                check_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
                logger.debug(f"解析输入日期成功: {check_date}")
                
                trading_days = list(TradingCalendar.objects
                    .filter(date__lte=check_date, is_trading_day=True)
                    .order_by('-date')
                    .values_list('date', flat=True)[:4])
                
                logger.debug(f"获取到的交易日数据: {trading_days}")
                
                if len(trading_days) < 4:
                    logger.warning(f"交易日数据不足，仅获取到 {len(trading_days)} 天")
                    return {'status': 'failed', 'message': '没有足够的交易日数据进行分析'}
                
                # 格式化日期
                analysis_dates = []
                for d in trading_days:
                    try:
                        if d is None:
                            logger.error(f"遇到空日期值")
                            continue
                        formatted_date = d.strftime('%Y-%m-%d')
                        analysis_dates.append(formatted_date)
                        logger.debug(f"成功格式化日期: {formatted_date}")
                    except Exception as e:
                        logger.error(f"日期格式化错误: {str(e)}, 日期值: {d}, 类型: {type(d)}")
                        continue
                
                if len(analysis_dates) < 4:
                    logger.error(f"格式化后的日期数量不足: {len(analysis_dates)}")
                    return {'status': 'failed', 'message': '日期格式化后数据不足'}
                
                logger.info(f"分析日期列表: {analysis_dates}")
                
                # 执行 SQL 查询
                try:
                    with connection.cursor() as cursor:
                        logger.debug("开始执行 SQL 查询")
                        cursor.execute("""
                            WITH consecutive_ups AS (
                                SELECT s.STOCK_ID as stock_code, COUNT(*) as up_days
                                FROM BASIC_STOCKDAILYDATA s
                                WHERE s.TRADE_DATE IN (
                                    TO_DATE(:1, 'YYYY-MM-DD'),
                                    TO_DATE(:2, 'YYYY-MM-DD')
                                )
                                AND s.CLOSE = s.UP_LIMIT
                                GROUP BY s.STOCK_ID
                                HAVING COUNT(*) = 2
                            )
                            SELECT DISTINCT s.STOCK_ID
                            FROM consecutive_ups c
                            JOIN BASIC_STOCKDAILYDATA s ON c.stock_code = s.STOCK_ID
                            WHERE s.TRADE_DATE IN (
                                TO_DATE(:3, 'YYYY-MM-DD'),
                                TO_DATE(:4, 'YYYY-MM-DD')
                            )
                            AND s.CLOSE < s.OPEN
                            GROUP BY s.STOCK_ID
                            HAVING COUNT(*) = 2
                        """, analysis_dates)
                        
                        down_stocks = [row[0] for row in cursor.fetchall()]
                        logger.info(f"SQL 查询完成，找到 {len(down_stocks)} 只股票")
                        
                except Exception as e:
                    logger.error(f"SQL 查询出错: {str(e)}")
                    logger.error(f"SQL 参数: {analysis_dates}")
                    raise
                
                # 修改后续查询代码
                result_stocks = []
                stock_chunks = [down_stocks[i:i+100] for i in range(0, len(down_stocks), 100)]
                
                for stock_chunk in stock_chunks:
                    history_data = (StockDailyData.objects
                        .filter(stock_id__in=stock_chunk)
                        .filter(trade_date__lt=datetime.strptime(analysis_dates[0], '%Y-%m-%d').date())
                        .exclude(close=F('up_limit'))
                        .order_by('-trade_date')
                        .select_related('stock'))
                    
                    for stock_id in stock_chunk:
                        stock_history = history_data.filter(stock_id=stock_id)[:3]
                        if len(stock_history) == 3:
                            # 计算关键价格点位
                            max_high = max(d.high for d in stock_history)
                            min_low = min(d.low for d in stock_history)
                            avg_price = (max_high + min_low) / 2
                            take_profit = max_high * Decimal('1.075')
                            
                            # 获取股票对象
                            try:
                                stock_obj = stock_history[0].stock
                                
                                # 保存到 PolicyDetails 模型
                                try:
                                    with transaction.atomic():
                                        PolicyDetails.objects.create(
                                            stock=stock_obj,
                                            date=datetime.strptime(trade_date, '%Y-%m-%d').date(),
                                            first_buy_point=max_high,
                                            second_buy_point=avg_price,
                                            stop_loss_point=min_low,
                                            take_profit_point=take_profit,
                                            strategy_type='龙回头',
                                            signal_strength=Decimal('0.85'),
                                            current_status='L'
                                        )
                                        
                                        # 添加到结果列表
                                        result_stocks.append({
                                            'stock': stock_obj.ts_code,
                                            'pattern_dates': analysis_dates,
                                            'history_dates': [d.trade_date for d in stock_history],
                                            'max_high': float(max_high),
                                            'min_low': float(min_low),
                                            'avg_price': float(avg_price),
                                            'take_profit': float(take_profit)
                                        })
                                except IntegrityError:
                                    logger.warning(f"股票 {stock_obj.ts_code} 在 {trade_date} 的策略记录已存在")
                                    continue
                                except Exception as e:
                                    logger.error(f"保存策略记录时出错: {str(e)}")
                                    continue
                                
                            except Exception as e:
                                logger.error(f"获取股票信息时出错: {str(e)}")
                                continue
                
                saved_count = len(result_stocks)
                logger.info(f"分析完成: 找到并保存了 {saved_count} 只符合条件的股票策略")
                
                return {
                    'status': 'success',
                    'message': f'找到并保存了 {saved_count} 只符合条件的股票策略',
                    'data': result_stocks
                }
                
            except ValueError as e:
                logger.error(f"日期解析错误: {str(e)}")
                return {'status': 'error', 'message': f'日期格式错误: {str(e)}'}
            
        except Exception as e:
            logger.error(f"分析过程出错: {str(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
            return {'status': 'error', 'message': f'分析过程出错: {str(e)}'}

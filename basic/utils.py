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
            batch_size = 500
            total_saved = 0
            
            if trade_date:
                check_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
                
                is_trading = TradingCalendar.objects.filter(
                    date=check_date,
                    is_trading_day=True
                ).exists()
                
                if not is_trading:
                    return {
                        'status': 'skipped',
                        'message': f'{trade_date} 不是交易日'
                    }
                
                existing_data = StockDailyData.objects.filter(
                    trade_date=check_date
                ).exists()
                
                if existing_data:
                    return {
                        'status': 'skipped',
                        'message': f'{trade_date} 的数据已存在'
                    }
                
                tushare_date = check_date.strftime('%Y%m%d')
                df = self.fetch_and_filter_daily_data(trade_date=tushare_date)
                
                if df is not None and not df.empty:
                    try:
                        total_records = len(df)
                        
                        with transaction.atomic():
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
                                    total_saved += len(bulk_data)
                                    
                                except Exception as batch_error:
                                    logger.error(f"{trade_date} 批量错误: {str(batch_error)}")
                                    raise
                        
                        cleanup_result = self.cleanup_old_data()
                        
                        if total_saved > 0:
                            return {
                                'status': 'success',
                                'message': f'更新完成: {total_saved}/{total_records} 条记录',
                                'total_saved': total_saved
                            }
                        else:
                            return {
                                'status': 'failed',
                                'message': f'没有获取到 {trade_date} 的数据'
                            }
                    
                    except Exception as save_error:
                        logger.error(f"保存数据错误: {str(save_error)}")
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
                    
                    # 修改多日期处理的返回逻辑
                    if total_saved > 0:
                        return {
                            'status': 'success',
                            'message': (
                                f'数据更新完成，共更新 {total_saved} 条记录，'
                                f'处理了 {len(processed_dates)} 个交易日。'
                                f'{cleanup_result["message"] if "message" in cleanup_result else ""}'
                            ),
                            'total_saved': total_saved  # 直接返回 total_saved
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
        """分析股票模式"""
        try:
            # 获取分析日期
            analysis_dates = self.get_analysis_dates(trade_date)
            
            with connection.cursor() as cursor:
                try:
                    sql = """
                        WITH consecutive_ups AS (
                            SELECT s.STOCK_ID as stock_code
                            FROM BASIC_STOCKDAILYDATA s
                            WHERE s.TRADE_DATE IN (
                                TO_DATE('{date1}', 'YYYY-MM-DD'),
                                TO_DATE('{date2}', 'YYYY-MM-DD')
                            )
                            AND s.CLOSE = s.UP_LIMIT
                            GROUP BY s.STOCK_ID
                            HAVING COUNT(*) = 2
                        ),
                        down_days AS (
                            SELECT s.STOCK_ID
                            FROM BASIC_STOCKDAILYDATA s
                            WHERE s.TRADE_DATE IN (
                                TO_DATE('{date3}', 'YYYY-MM-DD'),
                                TO_DATE('{date4}', 'YYYY-MM-DD')
                            )
                            AND s.CLOSE < s.OPEN
                            GROUP BY s.STOCK_ID
                            HAVING COUNT(*) = 2
                        )
                        SELECT DISTINCT c.stock_code
                        FROM consecutive_ups c
                        JOIN down_days d ON c.stock_code = d.STOCK_ID
                        JOIN BASIC_CODE bc ON c.stock_code = bc.TS_CODE
                        WHERE LOWER(bc.NAME) NOT LIKE '%st%'
                    """.format(
                        date1=analysis_dates[3],
                        date2=analysis_dates[2],
                        date3=analysis_dates[1],
                        date4=analysis_dates[0]
                    )
                    
                    cursor.execute(sql)
                    down_stocks = [row[0] for row in cursor.fetchall()]
                    
                    result_stocks = []
                    for stock_id in down_stocks:
                        try:
                            history_data = self.get_stock_history(stock_id, analysis_dates[3], num_days=15)
                            if history_data:
                                price_points = self.calculate_price_points(history_data)
                                self.save_strategy_details(stock_id, trade_date, price_points)
                                result_stocks.append({
                                    'stock': stock_id,
                                    'pattern': '龙回头',
                                    'signal': 'buy',
                                    **price_points
                                })
                        except Exception as e:
                            logger.error(f"处理股票 {stock_id} 时出错: {str(e)}")
                            continue
                    
                    return {'status': 'success', 'data': result_stocks}
                    
                except Exception as e:
                    logger.error(f"数据库错误: {str(e)}")
                    return {'status': 'error', 'message': str(e)}
        except Exception as e:
            logger.error(f"分析错误: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def get_analysis_dates(self, trade_date, num_days=4, is_begin=True):
        """
        获取分析所需的日期列表
        
        Args:
            trade_date (str): 交易日期，格式为 'YYYY-MM-DD'
            num_days (int): 需要获取的交易日天数，默认为4天
            is_begin (bool): 是否获取当前日期之前的交易日，默认为True
                - True: 获取当前日期之前的交易日
                - False: 获取当前日期之后的交易日
            
        Returns:
            list: 包含指定天数的日期列表，按时间倒序排列（最近的日期在前）
        """
        try:
            # 将输入日期转换为日期对象
            current_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
            
            # 根据is_begin参数决定查询条件
            if is_begin:
                # 获取当前日期之前的交易日
                trading_days = list(TradingCalendar.objects.filter(
                    date__lte=current_date,
                    is_trading_day=True
                ).order_by('-date')[:num_days + 6].values_list('date', flat=True))
            else:
                # 获取当前日期之后的交易日
                trading_days = list(TradingCalendar.objects.filter(
                    date__gte=current_date,
                    is_trading_day=True
                ).order_by('date')[:num_days + 6].values_list('date', flat=True))
            
            # 确保有足够的交易日
            if len(trading_days) < num_days:
                logger.warning(f"找不到足够的交易日，仅找到 {len(trading_days)} 天，需要 {num_days} 天")
                return None
            
            # 返回指定数量的交易日
            analysis_dates = [d.strftime('%Y-%m-%d') for d in trading_days[:num_days]]
            logger.info(f"分析日期: {analysis_dates}")
            return analysis_dates
            
        except Exception as e:
            logger.error(f"获取分析日期出错: {str(e)}")
            logger.error(traceback.format_exc())
            return None

    def get_stock_history(self, stock_id, date, num_days=3, is_begin=True):
        """获取股票历史数据
        
        Args:
            stock_id (str): 股票代码
            date (str): 日期，格式为 'YYYY-MM-DD'
            num_days (int): 需要获取的历史数据天数，默认为3天
            is_begin (bool): 是否获取当前日期之前的数据，默认为True
                - True: 获取当前日期之前的数据
                - False: 获取当前日期之后的数据
            
        Returns:
            list: 包含指定天数历史数据的列表，按时间倒序排列
            None: 如果获取数据失败或数据不足
        """
        try:
            # 将输入日期转换为日期对象
            current_date = datetime.strptime(date, '%Y-%m-%d').date()
            
            # 根据is_begin参数决定查询条件
            if is_begin:
                # 获取当前日期之前的数据
                history_data = list(StockDailyData.objects.filter(
                    stock_id=stock_id,
                    trade_date__lt=current_date  # 获取当前日期之前的数据
                ).order_by('-trade_date')[:num_days])  # 获取指定天数的数据
            else:
                # 获取当前日期之后的数据
                history_data = list(StockDailyData.objects.filter(
                    stock_id=stock_id,
                    trade_date__gt=current_date  # 获取当前日期之后的数据
                ).order_by('trade_date')[:num_days])  # 获取指定天数的数据
            
            if len(history_data) == num_days:  # 确保有足够的数据
                return history_data
            logger.warning(f"股票 {stock_id} 的历史数据不足 {num_days} 天")
            return None
            
        except Exception as e:
            logger.error(f"获取股票 {stock_id} 的历史数据时出错: {str(e)}")
            return None

    def calculate_price_points(self, history_data):
        """计算关键价格点位
        
        Args:
            history_data (list): 股票历史数据列表
            
        Returns:
            dict: 包含计算出的价格点位的字典
        """
        try:
            # 获取最近15天的数据
            recent_data = history_data[:15]  # 已经是按时间倒序排列的列表
            
            # 检查最近10天是否有涨停
            has_limit_up = False
            limit_up_date = None
            
            # 只检查最近10天的数据
            for data in recent_data[:10]:
                if data.close == data.up_limit:
                    has_limit_up = True
                    limit_up_date = data.trade_date
                    break
            
            if has_limit_up:
                # 如果有涨停，获取涨停日前三天的数据
                pre_limit_data = list(StockDailyData.objects.filter(
                    stock_id=history_data[0].stock_id,  # 使用列表的第一个元素
                    trade_date__lt=limit_up_date
                ).order_by('-trade_date')[:3])
                
                if len(pre_limit_data) == 3:
                    # 使用涨停前三天的最高价
                    max_high = Decimal(str(max(d.high for d in pre_limit_data)))
                    logger.info(f"使用涨停 {limit_up_date} 前三天的最高价: {max_high}")
                else:
                    # 如果数据不足，使用传入的历史数据
                    max_high = Decimal(str(max(d.high for d in history_data)))
                    logger.info("涨停前数据不足，使用历史数据最高价")
            else:
                # 如果没有涨停，使用传入的历史数据
                max_high = Decimal(str(max(d.high for d in history_data)))
                logger.info("最近10天无涨停，使用历史数据最高价")
            
            # 使用Decimal进行所有计算
            min_low = max_high * Decimal('0.8')
            avg_price = max_high * Decimal('0.9')
            take_profit = max_high * Decimal('1.075')
            
            return {
                'max_high': float(max_high),
                'min_low': float(min_low),
                'avg_price': float(avg_price),
                'take_profit': float(take_profit)
            }
        except Exception as e:
            logger.error(f"计算价格点位时出错: {str(e)}")
            raise

    def save_strategy_details(self, stock_id, trade_date, price_points):
        """保存策略详情"""
        try:
            with transaction.atomic():
                stock = Code.objects.get(ts_code=stock_id)
                current_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
                
                # 检查是否已存在相同的策略记录
                existing = PolicyDetails.objects.filter(
                    stock=stock,
                    date=current_date,
                    strategy_type='龙回头'
                ).exists()
                
                if not existing:
                    PolicyDetails.objects.create(
                        stock=stock,
                        date=current_date,
                        first_buy_point=price_points['max_high'],
                        second_buy_point=price_points['avg_price'],
                        stop_loss_point=price_points['min_low'],
                        take_profit_point=price_points['take_profit'],
                        strategy_type='龙回头',
                        signal_strength=Decimal('0.85'),
                        current_status='L'
                    )
                    logger.info(f"已为股票 {stock_id} 创建策略详情")
                else:
                    logger.info(f"股票 {stock_id} 的策略详情已存在")
        except Exception as e:
            logger.error(f"保存策略详情失败，股票 {stock_id}: {str(e)}")
            raise

    def analyze_trading_signals(self, start_date=None, end_date=None):
        """分析交易信号并更新状态
        
        Args:
            start_date (str, optional): 开始日期，格式：YYYY-MM-DD
            end_date (str, optional): 结束日期，格式：YYYY-MM-DD
            
        Returns:
            dict: 分析结果统计
        """
        logger.info("开始分析交易信号")
        
        try:
            # 获取活跃信号
            signals_query = PolicyDetails.objects.filter(current_status='L')
            if start_date:
                signals_query = signals_query.filter(date__gte=start_date)
            if end_date:
                signals_query = signals_query.filter(date__lte=end_date)
                
            stats = {
                'total': 0,
                'first_buy': 0,
                'second_buy': 0,
                'take_profit': 0,
                'stop_loss': 0,
                'errors': 0
            }
            
            # 批量获取所有需要的数据
            signal_ids = list(signals_query.values_list('id', flat=True))
            signals = PolicyDetails.objects.filter(id__in=signal_ids).select_related('stock')
            
            for signal in signals:
                try:
                    # 获取后续日线数据
                    daily_data = StockDailyData.objects.filter(
                        stock=signal.stock,
                        trade_date__gt=signal.date
                    ).order_by('trade_date')
                    
                    if not daily_data.exists():
                        continue
                        
                    stats['total'] += 1
                    
                    # 处理第一买点
                    first_buy_hit = False
                    for data in daily_data:
                        if data.low <= signal.first_buy_point:
                            first_buy_hit = True
                            signal.first_buy_time = data.trade_date
                            
                            # 计算实际买入价格
                            if data.open <= signal.first_buy_point:
                                signal.holding_price = round(float(data.open), 2)
                            else:
                                signal.holding_price = round(float(signal.first_buy_point), 2)
                                
                            stats['first_buy'] += 1
                            break
                    
                    if not first_buy_hit:
                        continue
                    
                    # 处理第二买点和止盈
                    for data in daily_data.filter(trade_date__gt=signal.first_buy_time):
                        # 检查止损
                        if data.low <= signal.stop_loss_point:
                            signal.stop_loss_time = data.trade_date
                            signal.current_status = 'F'
                            stats['stop_loss'] += 1
                            break
                            
                        # 检查第二买点
                        if data.low <= signal.second_buy_point:
                            signal.second_buy_time = data.trade_date
                            # 更新持仓价格和止盈点
                            signal.holding_price = round((float(data.close) + float(signal.holding_price)) / 2, 2)
                            signal.take_profit_point = round(float(signal.holding_price) * 1.075, 2)
                            stats['second_buy'] += 1
                            continue
                        
                        # 检查止盈
                        if data.high >= signal.take_profit_point:
                            signal.take_profit_time = data.trade_date
                            signal.current_status = 'S'
                            stats['take_profit'] += 1
                            break
                    
                    # 保存更新
                    signal.save()
                    
                except Exception as e:
                    logger.error(f"处理信号 {signal.id} 时出错: {str(e)}")
                    stats['errors'] += 1
                    continue
            
            # 记录分析结果
            logger.info(f"分析完成: 共处理 {stats['total']} 条信号")
            logger.info(f"第一买点: {stats['first_buy']}")
            logger.info(f"第二买点: {stats['second_buy']}")
            logger.info(f"止盈: {stats['take_profit']}")
            logger.info(f"止损: {stats['stop_loss']}")
            logger.info(f"错误: {stats['errors']}")
            
            return {
                'status': 'success',
                'stats': stats,
                'message': f"分析完成: 共处理 {stats['total']} 条信号"
            }
            
        except Exception as e:
            logger.error(f"分析过程出错: {str(e)}")
            return {'status': 'error', 'message': str(e)}

    def validate_price_points(self, price_points):
        """验证价格点位的合理性
        
        Args:
            price_points (dict): 包含价格点位的字典
            
        Returns:
            bool: 价格点位是否合理
        """
        try:
            # 检查价格是否为正数
            if any(price <= 0 for price in price_points.values()):
                return False
                
            # 检查价格顺序
            if not (price_points['stop_loss_point'] < price_points['second_buy_point'] < 
                   price_points['first_buy_point'] < price_points['take_profit_point']):
                return False
                
            return True
        except Exception as e:
            logger.error(f"验证价格点位出错: {str(e)}")
            return False

    def calculate_trading_stats(self, signal):
        """计算交易统计指标
        
        Args:
            signal (PolicyDetails): 策略信号对象
            
        Returns:
            dict: 统计指标
        """
        try:
            stats = {
                'holding_days': 0,
                'max_profit': 0,
                'max_drawdown': 0,
                'final_profit': 0
            }
            
            if not signal.first_buy_time:
                return stats
                
            # 获取持仓期间的数据
            daily_data = StockDailyData.objects.filter(
                stock=signal.stock,
                trade_date__gte=signal.first_buy_time
            ).order_by('trade_date')
            
            if not daily_data.exists():
                return stats
                
            # 计算持仓天数
            if signal.current_status in ['S', 'F']:
                end_date = signal.take_profit_time or signal.stop_loss_time
                stats['holding_days'] = (end_date - signal.first_buy_time).days
            else:
                stats['holding_days'] = (daily_data.last().trade_date - signal.first_buy_time).days
                
            # 计算最大收益和最大回撤
            max_price = float(signal.holding_price)
            min_price = float(signal.holding_price)
            
            for data in daily_data:
                current_price = float(data.high)
                if current_price > max_price:
                    max_price = current_price
                if float(data.low) < min_price:
                    min_price = float(data.low)
                    
            stats['max_profit'] = round((max_price - float(signal.holding_price)) / float(signal.holding_price) * 100, 2)
            stats['max_drawdown'] = round((float(signal.holding_price) - min_price) / float(signal.holding_price) * 100, 2)
            
            # 计算最终收益
            if signal.current_status == 'S':
                stats['final_profit'] = round((float(signal.take_profit_point) - float(signal.holding_price)) / 
                                            float(signal.holding_price) * 100, 2)
            elif signal.current_status == 'F':
                stats['final_profit'] = round((float(signal.stop_loss_point) - float(signal.holding_price)) / 
                                            float(signal.holding_price) * 100, 2)
            else:
                last_price = float(daily_data.last().close)
                stats['final_profit'] = round((last_price - float(signal.holding_price)) / 
                                            float(signal.holding_price) * 100, 2)
                                            
            return stats
            
        except Exception as e:
            logger.error(f"计算交易统计指标出错: {str(e)}")
            return stats

    def test_date_functions(self):
        """测试日期相关函数
        
        测试 get_analysis_dates 和 get_stock_history 函数的功能
        """
        try:
            # 测试用例1：获取当前日期之前的交易日
            test_date = '2024-03-15'  # 使用一个已知的交易日
            print("\n测试用例1: 获取当前日期之前的交易日")
            print("测试 get_analysis_dates (is_begin=True):")
            dates_before = self.get_analysis_dates(test_date, num_days=4, is_begin=True)
            print(f"获取到的日期: {dates_before}")
            
            # 测试用例2：获取当前日期之后的交易日
            print("\n测试用例2: 获取当前日期之后的交易日")
            print("测试 get_analysis_dates (is_begin=False):")
            dates_after = self.get_analysis_dates(test_date, num_days=4, is_begin=False)
            print(f"获取到的日期: {dates_after}")
            
            # 测试用例3：获取股票历史数据（之前）
            print("\n测试用例3: 获取股票历史数据（之前）")
            test_stock = '000001.SZ'  # 使用一个已知的股票代码
            print("测试 get_stock_history (is_begin=True):")
            history_before = self.get_stock_history(test_stock, test_date, num_days=3, is_begin=True)
            if history_before:
                print(f"获取到的历史数据数量: {len(history_before)}")
                print(f"第一条数据日期: {history_before[0].trade_date}")
                print(f"最后一条数据日期: {history_before[-1].trade_date}")
            
            # 测试用例4：获取股票历史数据（之后）
            print("\n测试用例4: 获取股票历史数据（之后）")
            print("测试 get_stock_history (is_begin=False):")
            history_after = self.get_stock_history(test_stock, test_date, num_days=3, is_begin=False)
            if history_after:
                print(f"获取到的历史数据数量: {len(history_after)}")
                print(f"第一条数据日期: {history_after[0].trade_date}")
                print(f"最后一条数据日期: {history_after[-1].trade_date}")
            
            # 验证结果
            print("\n验证结果:")
            
            # 验证日期顺序
            if dates_before:
                print("1. 验证之前的日期顺序:")
                for i in range(len(dates_before)-1):
                    date1 = datetime.strptime(dates_before[i], '%Y-%m-%d')
                    date2 = datetime.strptime(dates_before[i+1], '%Y-%m-%d')
                    print(f"   {dates_before[i]} 应该大于 {dates_before[i+1]}: {date1 > date2}")
            
            if dates_after:
                print("\n2. 验证之后的日期顺序:")
                for i in range(len(dates_after)-1):
                    date1 = datetime.strptime(dates_after[i], '%Y-%m-%d')
                    date2 = datetime.strptime(dates_after[i+1], '%Y-%m-%d')
                    print(f"   {dates_after[i]} 应该小于 {dates_after[i+1]}: {date1 < date2}")
            
            # 验证历史数据
            if history_before:
                print("\n3. 验证之前的历史数据:")
                for i in range(len(history_before)-1):
                    print(f"   {history_before[i].trade_date} 应该大于 {history_before[i+1].trade_date}: "
                          f"{history_before[i].trade_date > history_before[i+1].trade_date}")
            
            if history_after:
                print("\n4. 验证之后的历史数据:")
                for i in range(len(history_after)-1):
                    print(f"   {history_after[i].trade_date} 应该小于 {history_after[i+1].trade_date}: "
                          f"{history_after[i].trade_date < history_after[i+1].trade_date}")
            
            return {
                'status': 'success',
                'message': '测试完成',
                'dates_before': dates_before,
                'dates_after': dates_after,
                'history_before': history_before,
                'history_after': history_after
            }
            
        except Exception as e:
            logger.error(f"测试过程出错: {str(e)}")
            return {
                'status': 'error',
                'message': str(e)
            }







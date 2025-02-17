import tushare as ts
from .models import Code, StockDailyData, TradingCalendar
from decouple import config
from django.db import transaction, connection
import pandas as pd
from datetime import datetime, timedelta


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

    def update_all_stocks_daily_data(self, trade_date=None, start_date=None, end_date=None):
        """更新所有股票的日线数据"""
        try:
            with transaction.atomic():
                # 转换日期格式
                if trade_date:
                    check_date = datetime.strptime(trade_date, '%Y-%m-%d').date()
                    # 检查是否已有数据
                    existing_data = StockDailyData.objects.filter(
                        trade_date=check_date
                    ).exists()
                    
                    if existing_data:
                        return {'status': 'skipped', 'message': f'{trade_date} 的数据已存在'}
                    
                    tushare_date = check_date.strftime('%Y%m%d')
                    df = self.fetch_all_stocks_daily_data(trade_date=tushare_date)
                else:
                    check_start = datetime.strptime(start_date, '%Y-%m-%d').date()
                    check_end = datetime.strptime(end_date, '%Y-%m-%d').date()
                    
                    # 检查日期范围内是否已有数据
                    existing_dates = StockDailyData.objects.filter(
                        trade_date__range=[check_start, check_end]
                    ).values_list('trade_date', flat=True).distinct()
                    
                    if existing_dates:
                        existing_dates_str = [d.strftime('%Y-%m-%d') for d in existing_dates]
                        return {
                            'status': 'skipped',
                            'message': f'以下日期的数据已存在: {", ".join(existing_dates_str)}'
                        }
                    
                    tushare_start = check_start.strftime('%Y%m%d')
                    tushare_end = check_end.strftime('%Y%m%d')
                    df = self.fetch_all_stocks_daily_data(
                        start_date=tushare_start,
                        end_date=tushare_end
                    )
                
                if df is not None and not df.empty:
                    # 转换数据类型
                    df['trade_date'] = pd.to_datetime(df['trade_date'])
                    
                    # 获取所有有效的股票代码
                    valid_codes = set(Code.objects.values_list('ts_code', flat=True))
                    
                    # 批量创建数据
                    bulk_data = []
                    skipped_codes = set()
                    
                    for _, row in df.iterrows():
                        if row['ts_code'] not in valid_codes:
                            skipped_codes.add(row['ts_code'])
                            continue
                        
                        try:
                            stock = Code.objects.get(ts_code=row['ts_code'])
                            bulk_data.append(
                                StockDailyData(
                                    stock=stock,
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
                            )
                        except Code.DoesNotExist:
                            skipped_codes.add(row['ts_code'])
                            continue
                    
                    # 批量保存数据
                    if bulk_data:
                        StockDailyData.objects.bulk_create(bulk_data)
                    
                    # 清理旧数据
                    cleanup_result = self.cleanup_old_data()
                    
                    message = f'数据更新完成，共更新 {len(bulk_data)} 条记录。'
                    if skipped_codes:
                        message += f'\n跳过的股票代码: {", ".join(skipped_codes)}'
                    if cleanup_result:
                        message += f'\n{cleanup_result["message"]}'
                    
                    return {
                        'status': 'success',
                        'message': message,
                        'skipped_codes': list(skipped_codes)
                    }
                else:
                    return {
                        'status': 'failed',
                        'message': '没有新数据需要更新'
                    }
                
        except Exception as e:
            print(f"更新数据失败：{str(e)}")
            raise

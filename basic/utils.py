import tushare as ts
from .models import Code, StockDailyData
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
        """获取指定股票的日线数据
        
        Args:
            ts_code (str): Tushare股票代码
            start_date (str): 开始日期（YYYYMMDD）
            end_date (str): 结束日期（YYYYMMDD）
            
        Returns:
            DataFrame: 包含股票日线数据的DataFrame
            None: 如果获取失败
        """
        try:
            df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            return df
        except Exception as e:
            print(f"获取{ts_code}日线数据失败：{str(e)}")
            return None

    def update_stock_daily_data(self):
        """更新所有股票的日线数据
        
        功能说明：
        1. 获取数据库中的最新数据日期
        2. 增量获取新数据
        3. 批量保存到数据库
        """
        with transaction.atomic():
            codes = Code.objects.all()
            for code in codes:
                # 获取最新的数据日期
                latest_data = StockDailyData.objects.filter(stock=code).order_by('-trade_date').first()
                start_date = (latest_data.trade_date + timedelta(days=1)).strftime('%Y%m%d') if latest_data else '20200101'
                end_date = datetime.now().strftime('%Y%m%d')
                
                df = self.fetch_daily_data(code.ts_code, start_date, end_date)
                if df is not None:
                    for _, row in df.iterrows():
                        StockDailyData.objects.create(
                            stock=code,
                            trade_date=row['trade_date'],
                            open=row['open'],
                            high=row['high'],
                            low=row['low'],
                            close=row['close'],
                            volume=row['vol'],
                            amount=row['amount']
                        )

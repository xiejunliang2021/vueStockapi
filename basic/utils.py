import tushare as ts
from .models import Code
from decouple import config
from django.db import transaction, connection
import pandas as pd


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

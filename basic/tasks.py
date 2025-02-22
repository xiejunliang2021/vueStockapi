from celery import shared_task
from .models import Code, StockDailyData
from .utils import StockDataFetcher
from .analysis import ContinuousLimitStrategy
from datetime import datetime, timedelta

@shared_task
def update_daily_data_and_signals():
    """每日更新数据和策略信号的定时任务
    
    功能说明：
    1. 从Tushare获取最新的股票日线数据
    2. 对所有股票进行策略分析
    3. 生成新的交易信号
    4. 更新已有信号的状态
    
    执行时机：
    - 每个交易日下午5点自动执行
    
    异常处理：
    - 捕获并记录单个股票处理失败的异常
    - 记录整体任务失败的异常
    """
    try:
        # 更新日线数据
        fetcher = StockDataFetcher()
        fetcher.update_stock_daily_data()

        # 分析新信号
        strategy = ContinuousLimitStrategy()
        today = datetime.now().date()
        
        # 获取所有股票代码并生成新信号
        codes = Code.objects.all()
        for code in codes:
            try:
                signals = strategy.analyze_stock(
                    code.ts_code,
                    (today - timedelta(days=1)).strftime('%Y%m%d'),
                    today.strftime('%Y%m%d')
                )
                strategy.save_signals(signals)
            except Exception as e:
                print(f"处理股票 {code.ts_code} 时出错: {str(e)}")
                continue

        # 更新历史信号状态
        strategy.update_historical_signals()
        
    except Exception as e:
        print(f"更新任务执行失败: {str(e)}")
        raise 
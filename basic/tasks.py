from celery import shared_task, chain
from .models import Code, StockDailyData, PolicyDetails, StrategyStats, TradingCalendar
from .utils import StockDataFetcher
from .analysis import ContinuousLimitStrategy
from .views import ManualStrategyAnalysisView
from datetime import datetime, timedelta
import logging
from celery.exceptions import MaxRetriesExceededError
from django_celery_results.models import TaskResult
from django.core.cache import cache
from contextlib import contextmanager
import time

logger = logging.getLogger(__name__)

@contextmanager
def task_lock(lock_id, timeout=3600):
    """使用 Redis 实现的分布式锁"""
    lock_id = f'lock_{lock_id}'
    timeout_at = time.monotonic() + timeout
    try:
        while time.monotonic() < timeout_at:
            if cache.add(lock_id, 'lock', timeout):
                yield True
                break
            time.sleep(0.1)
        else:
            yield False
    finally:
        cache.delete(lock_id)

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

@shared_task(bind=True, max_retries=3)
def daily_data_update(self):
    """每日更新股票数据"""
    logger.info("开始执行每日数据更新任务")
    try:
        with task_lock('daily_data_update', timeout=3600) as acquired:
            if not acquired:
                logger.warning('Another daily_data_update task is already running')
                return
            
            # 获取当前日期
            today = datetime.now().date()
            
            # 检查是否为交易日
            trading_day = TradingCalendar.objects.filter(
                date=today,
                is_trading_day=True
            ).exists()
            
            if not trading_day:
                print(f"{today} 不是交易日，跳过更新")
                return
            
            # 更新日线数据
            fetcher = StockDataFetcher()
            result = fetcher.update_all_stocks_daily_data(trade_date=today.strftime('%Y-%m-%d'))
            
            if result.get('status') == 'success':
                print(f"成功更新 {result.get('total_saved', 0)} 条日线数据")
                logger.info("每日数据更新任务完成")
                return True
            else:
                print(f"更新日线数据失败: {result.get('message')}")
                return False
            
    except Exception as e:
        try:
            self.retry(countdown=300)  # 5分钟后重试
        except MaxRetriesExceededError:
            logger.error(f"每日数据更新任务重试次数超限: {str(e)}")
            raise

@shared_task
def analyze_stock_patterns():
    """分析股票模式并生成策略结果"""
    logger.info("开始分析股票模式并生成策略结果")
    try:
        # 获取当前日期
        today = datetime.now().date()
        
        # 检查是否为交易日
        trading_day = TradingCalendar.objects.filter(
            date=today,
            is_trading_day=True
        ).exists()
        
        if not trading_day:
            logger.info(f"{today} 不是交易日，跳过分析")
            return
        
        # 获取所有股票
        stocks = Code.objects.filter(list_status='L')  # 只分析上市状态的股票
        
        success_count = 0
        for stock in stocks:
            try:
                # 获取该股票最近的日线数据
                daily_data = StockDailyData.objects.filter(
                    stock=stock,
                    trade_date__lte=today
                ).order_by('-trade_date')[:20]  # 获取最近20个交易日数据
                
                if daily_data.count() < 20:
                    logger.warning(f"股票 {stock.ts_code} 数据不足，跳过分析")
                    continue
                
                # 分析连续涨停模式
                latest_data = daily_data[0]  # 最新一天的数据
                if latest_data.close >= latest_data.up_limit:  # 当日涨停
                    # 检查前期走势
                    prev_highs = []
                    prev_lows = []
                    for data in daily_data[1:]:  # 不包括最新一天
                        prev_highs.append(float(data.high))
                        prev_lows.append(float(data.low))
                    
                    # 计算买点
                    max_high = max(prev_highs[:3])  # 前3天最高价
                    min_low = min(prev_lows[:3])    # 前3天最低价
                    
                    # 创建策略记录
                    PolicyDetails.objects.create(
                        stock=stock,
                        date=today,
                        first_buy_point=max_high,
                        second_buy_point=round(max_high * 0.9, 2),
                        stop_loss_point=min_low,
                        take_profit_point=round(max_high * 1.075, 2),
                        strategy_type='CONTINUOUS_LIMIT_UP',
                        signal_strength=0.8,
                        current_status='L'  # 初始状态为进行中
                    )
                    success_count += 1
                    
            except Exception as e:
                logger.error(f"处理股票 {stock.ts_code} 时出错: {str(e)}")
                continue
        
        logger.info(f"成功生成 {success_count} 条策略记录")
        return True
        
    except Exception as e:
        logger.error(f"分析股票模式任务失败: {str(e)}")
        return False

@shared_task
def daily_strategy_analysis():
    """每日策略分析"""
    try:
        # 获取当前日期
        today = datetime.now().date()
        
        # 检查是否为交易日
        trading_day = TradingCalendar.objects.filter(
            date=today,
            is_trading_day=True
        ).exists()
        
        if not trading_day:
            logger.info(f"{today} 不是交易日，跳过分析")
            return
        
        # 获取需要分析的策略记录
        signals = PolicyDetails.objects.filter(
            current_status='L'  # 只分析进行中的信号
        ).select_related('stock')
        
        updated_count = 0
        for signal in signals:
            try:
                # 获取该股票在策略生成日期之后的日线数据
                daily_data = StockDailyData.objects.filter(
                    stock=signal.stock,
                    trade_date__gt=signal.date,
                    trade_date__lte=today
                ).order_by('trade_date')
                
                if daily_data.exists():
                    # 分析策略结果
                    first_buy_point = float(signal.first_buy_point)
                    second_buy_point = float(signal.second_buy_point)
                    stop_loss_point = float(signal.stop_loss_point)
                    take_profit_point = float(signal.take_profit_point)
                    
                    # ... 策略分析逻辑 ...
                    # (这里使用你之前实现的策略分析逻辑)
                    
                    updated_count += 1
            
            except Exception as e:
                logger.error(f"分析策略 {signal.id} 时出错: {str(e)}")
                continue
        
        logger.info(f"成功更新 {updated_count} 条策略记录")
        return True
        
    except Exception as e:
        logger.error(f"策略分析任务失败: {str(e)}")
        return False

@shared_task
def daily_stats_analysis():
    """每日统计分析"""
    try:
        # 获取当前日期
        today = datetime.now().date()
        yesterday = today - timedelta(days=1)
        
        # 检查是否为交易日
        trading_day = TradingCalendar.objects.filter(
            date=today,
            is_trading_day=True
        ).exists()
        
        if not trading_day:
            print(f"{today} 不是交易日，跳过统计")
            return
        
        # 执行统计分析
        analysis_view = ManualStrategyAnalysisView()
        stats = analysis_view.analyze_signals(yesterday, today)
        
        # 保存统计结果
        if stats['total'] > 0:
            StrategyStats.objects.create(
                date=today,
                total_signals=stats['total'],
                first_buy_success=stats['first_buy_success'],
                second_buy_success=stats['second_buy_success'],
                failed_signals=stats['failed'],
                success_rate=round((stats['first_buy_success'] + stats['second_buy_success']) / stats['total'] * 100, 2),
                avg_hold_days=stats['avg_hold_days'],
                max_drawdown=stats['max_drawdown'],
                profit_0_3=stats['profit_distribution']['0-3%'],
                profit_3_5=stats['profit_distribution']['3-5%'],
                profit_5_7=stats['profit_distribution']['5-7%'],
                profit_7_10=stats['profit_distribution']['7-10%'],
                profit_above_10=stats['profit_distribution']['>10%']
            )
            print(f"成功保存统计数据")
            return True
        else:
            print("没有需要统计的数据")
            return False
            
    except Exception as e:
        print(f"统计分析任务失败: {str(e)}")
        return False

@shared_task
def run_daily_analysis_chain():
    """运行每日分析任务链"""
    chain(
        daily_data_update.s(),
        analyze_stock_patterns.s(),
        daily_strategy_analysis.s(),
        daily_stats_analysis.s()
    ).apply_async()

@shared_task
def monitor_task_status():
    """监控任务执行状态"""
    # 检查最近的任务执行情况
    recent_tasks = TaskResult.objects.filter(
        date_done__date=datetime.now().date()
    )
    
    # 发送通知或警报
    if recent_tasks.filter(status='FAILURE').exists():
        # 发送警报
        pass 
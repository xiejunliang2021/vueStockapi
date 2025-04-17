from celery import Celery
from celery.schedules import crontab

app = Celery('basic')

# 配置定时任务
app.conf.beat_schedule = {
    'analyze-trading-signals-daily': {
        'task': 'basic.tasks.analyze_trading_signals_daily',
        'schedule': crontab(hour=16, minute=30),  # 每天15:30执行
    },
    'analyze-trading-signals-weekly': {
        'task': 'basic.tasks.analyze_trading_signals_weekly',
        'schedule': crontab(day_of_week='fri', hour=16, minute=30),  # 每周五15:30执行
    },
} 
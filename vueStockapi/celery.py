from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings
import logging
from celery.schedules import crontab
from celery.signals import task_failure, worker_ready
from celery.exceptions import MaxRetriesExceededError
from django.utils import timezone

# 设置默认Django settings模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')

app = Celery('vueStockapi')

# 使用CELERY_作为配置前缀
app.config_from_object('django.conf:settings', namespace='CELERY')

# 设置时区
app.conf.timezone = settings.TIME_ZONE
app.conf.enable_utc = False

# 自动发现任务
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# 配置日志
logger = logging.getLogger('celery')

# 重新配置定时任务
app.conf.beat_schedule = {
    'update-daily-data': {
        'task': 'basic.tasks.daily_data_update',
        'schedule': crontab(hour=17, minute=0, timezone=settings.TIME_ZONE),
        'options': {'expires': 3600}  # 任务过期时间
    },
    'analyze-stock-patterns': {
        'task': 'basic.tasks.analyze_stock_patterns',
        'schedule': crontab(hour=17, minute=5, timezone=settings.TIME_ZONE),  # 每天下午5点05分执行
    },
    'analyze-daily-strategy': {
        'task': 'basic.tasks.daily_strategy_analysis',
        'schedule': crontab(hour=17, minute=10, timezone=settings.TIME_ZONE),  # 每天下午5点10分执行
    },
    'analyze-daily-stats': {
        'task': 'basic.tasks.daily_stats_analysis',
        'schedule': crontab(hour=17, minute=20, timezone=settings.TIME_ZONE),  # 每天下午5点20分执行
    },
    'analyze-trading-signals-daily': {
        'task': 'basic.tasks.analyze_trading_signals_daily',
        'schedule': crontab(hour=15, minute=30, timezone=settings.TIME_ZONE),  # 每天15:30执行
        'options': {'expires': 3600}  # 任务过期时间
    },
    'analyze-trading-signals-weekly': {
        'task': 'basic.tasks.analyze_trading_signals_weekly',
        'schedule': crontab(day_of_week='fri', hour=15, minute=30, timezone=settings.TIME_ZONE),  # 每周五15:30执行
        'options': {'expires': 3600}  # 任务过期时间
    },
}

@app.task(bind=True)
def debug_task(self):
    logger.info('Request: {0!r}'.format(self.request))

@task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, **kwargs):
    """处理任务失败的回调"""
    logger.error(f'Task {task_id} failed: {exception}')

# 修改 app 配置
app.conf.update(
    task_default_retry_delay=60,    # 1分钟后重试
    task_max_retries=3,            # 最大重试次数
    task_soft_time_limit=3540,     # 软超时时间（秒）
    task_time_limit=3600,          # 任务超时时间（秒）
    worker_max_tasks_per_child=50, # 限制子进程处理的最大任务数
    worker_prefetch_multiplier=1,   # 限制预取任务数
    task_acks_late=True,           # 任务完成后再确认
    task_reject_on_worker_lost=True, # 在worker丢失时拒绝任务
    broker_transport_options={
        'visibility_timeout': 3600,  # 消息可见性超时
    },
    beat_max_loop_interval=5,       # beat 循环间隔（秒）
    beat_sync_every=1,              # 每次循环都同步
)

@worker_ready.connect
def at_start(sender, **kwargs):
    """当 worker 启动时执行的操作"""
    print("Celery worker is ready!")

if __name__ == '__main__':
    app.start() 
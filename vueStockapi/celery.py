from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings
import logging
from celery.schedules import crontab
from celery.signals import task_failure
from celery.exceptions import MaxRetriesExceededError

# 设置默认Django settings模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')

app = Celery('vueStockapi')

# 使用CELERY_作为配置前缀
app.config_from_object('django.conf:settings', namespace='CELERY')

# 设置时区
app.conf.timezone = 'Asia/Shanghai'

# 自动发现任务
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

# 配置日志
logger = logging.getLogger('celery')

# 重新配置定时任务
app.conf.beat_schedule = {
    'update-daily-data': {
        'task': 'basic.tasks.daily_data_update',
        'schedule': crontab(hour=17, minute=0),
        'options': {'expires': 3600}  # 任务过期时间
    },
    'analyze-stock-patterns': {
        'task': 'basic.tasks.analyze_stock_patterns',
        'schedule': crontab(hour=17, minute=5),  # 每天下午5点05分执行
    },
    'analyze-daily-strategy': {
        'task': 'basic.tasks.daily_strategy_analysis',
        'schedule': crontab(hour=17, minute=10),  # 每天下午5点10分执行
    },
    'analyze-daily-stats': {
        'task': 'basic.tasks.daily_stats_analysis',
        'schedule': crontab(hour=17, minute=20),  # 每天下午5点20分执行
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
    task_default_retry_delay=300,  # 5分钟后重试
    task_max_retries=3,           # 最大重试次数
    task_soft_time_limit=3600,    # 软时间限制（1小时）
    task_time_limit=3600,         # 硬时间限制（1小时）
    worker_max_tasks_per_child=200,  # 工作进程最大任务数
    worker_prefetch_multiplier=1,    # 限制预取任务数
) 
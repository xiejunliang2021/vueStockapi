from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings
import logging
from celery.schedules import crontab

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

# 配置定时任务
app.conf.beat_schedule = {
    'update-daily-data': {
        'task': 'basic.tasks.daily_data_update',
        'schedule': crontab(hour=17, minute=0),  # 每天下午5点执行
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
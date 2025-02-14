from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings
import logging

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

@app.task(bind=True)
def debug_task(self):
    logger.info('Request: {0!r}'.format(self.request)) 
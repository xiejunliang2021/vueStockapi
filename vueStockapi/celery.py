from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings

# 设置默认Django settings模块
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')

app = Celery('vueStockapi')

# 使用CELERY_作为配置前缀
app.config_from_object('django.conf:settings', namespace='CELERY')

# 自动发现任务
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS) 
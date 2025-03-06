from __future__ import absolute_import, unicode_literals

# 确保在 Django 启动时导入 celery app
from .celery import app as celery_app

import pymysql
pymysql.install_as_MySQLdb()

__all__ = ('celery_app',)

from __future__ import absolute_import, unicode_literals

# 确保在 Django 启动时导入 celery app
from .celery import app as celery_app

import pymysql
pymysql.install_as_MySQLdb()

# Configure oracledb to work as cx_Oracle
try:
    import oracledb
    import sys
    sys.modules['cx_Oracle'] = oracledb
except ImportError:
    pass

__all__ = ('celery_app',)

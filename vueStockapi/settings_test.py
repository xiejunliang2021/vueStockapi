"""
专门用于测试的配置
在测试时覆盖数据库设置，避免Oracle权限问题
"""
from .settings import *

# 测试时使用MySQL数据库，避免Oracle权限问题
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'test_backtest',
        'USER': config('USER_MYSQL'),
        'PASSWORD': config('PASSWORD_MYSQL'),
        'HOST': config('HOST'),
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
        'TEST': {
            'NAME': 'test_backtest_db',
        }
    },
    'mysql': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'quant',
        'USER': config('USER_MYSQL'),
        'PASSWORD': config('PASSWORD_MYSQL'),
        'HOST': config('HOST'),
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        }
    }
}

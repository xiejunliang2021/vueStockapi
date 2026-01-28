from decouple import config
from pathlib import Path
import oracledb
import os
from celery.schedules import crontab
import logging

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize Oracle client
# Initialize Oracle client
# try:
#     wallet_location = config('WALLET_LOCATION')
#     if wallet_location and os.path.exists(wallet_location):
#         oracledb.init_oracle_client(config_dir=wallet_location)
#         logging.info(f"Oracle client initialized with wallet location: {wallet_location}")
#     else:
#         logging.warning(f"Oracle wallet location not found or not configured: {wallet_location}")
# except Exception as e:
#     logging.error(f"Error initializing Oracle client: {e}")


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-yz1)2zwsqijy!e+$^2_ix&#0zic3@0&!!y@3t0@g$=lxo&s^x%'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*' ]

# 定义钱包相关路径和密码
WALLET_DIRECTORY = config('WALLET_DIRECTORY')
WALLET_PEM_PASS_PHRASE = config('WALLET_PEM_PASS_PHRASE')


# Application definition

INSTALLED_APPS = [
    'drf_spectacular',
    'drf_spectacular_sidecar',
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'basic',
    'weighing',
    'backtest',
    'rest_framework',
    'rest_framework_simplejwt',  # JWT 认证
    'django_filters',
    'django_celery_beat',
    'django_celery_results',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'vueStockapi.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'vueStockapi.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

# DATABASES = {
#

    # 'default': {
    #     'ENGINE': 'django.db.backends.oracle',
    #     'NAME': config('NAME_ORACLE',),
    #     'USER': config('USER_ORACLE',),
    #     'PASSWORD': config('PASSWORD_ORACLE',),
    #     'HOST': '',
    #     'PORT': '',
    #     'CONN_MAX_AGE': 0,  # 禁用连接持久化
    #     'OPTIONS': {
    #         'retry_count': 3,
    #         'retry_delay': 1,
    #         'ssl_server_dn_match': True,
    #     },
    #     'TEST': {
    #         'NAME': 'test_' + config('NAME_ORACLE',),
    #     },
    # },
# }
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.oracle',
        'NAME': config('NAME_ORACLE', ),
        'USER': config('USER_ORACLE', ),
        'PASSWORD': config('PASSWORD_ORACLE', ),
        'HOST': '',
        'PORT': '',
        'CONN_MAX_AGE': 0,  # 禁用连接持久化
        'OPTIONS': {
            'retry_count': 3,
            'retry_delay': 1,
            'ssl_server_dn_match': True,
            # 这些选项会传递给 python-oracledb 驱动
            'config_dir': WALLET_DIRECTORY,
            'wallet_location': WALLET_DIRECTORY,  # 通常与 config_dir 相同
            'wallet_password': WALLET_PEM_PASS_PHRASE,  # 钱包的密码 (PEM pass phrase)

        }

    },
    'mysql': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'quant',
        'USER': config('USER_MYSQL'),
        'PASSWORD': config('PASSWORD_MYSQL'),
        'HOST': config('HOST'),
        'PORT': '3306',
        'CONN_MAX_AGE': 60,
        'OPTIONS': {
            'charset': 'utf8mb4',
        }
    }
}

DATABASE_ROUTERS = ['weighing.db_router.WeighingRouter']

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = 'zh-hans'

TIME_ZONE = 'Asia/Shanghai'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# DRF配置鉴权方式
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend',),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
}

# 添加文档相关配置
DOCS_ROOT = os.path.join(BASE_DIR, 'docs')
DOCS_ACCESS = 'public'

# Celery Configuration
CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'
CELERY_RESULT_BACKEND = 'redis://127.0.0.1:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Shanghai'
CELERY_ENABLE_UTC = False
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Celery Beat 配置
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BEAT_SCHEDULE = {
    'update-daily-data-and-signals': {
        'task': 'basic.tasks.update_daily_data_and_signals',
        'schedule': crontab(
            hour=17,
            minute=0,
            day_of_week='mon-fri'
        ),
        'options': {'queue': 'default'}
    },
}

# 日志配置
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'WARNING',  # 只记录警告及以上级别的日志
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': 'logs/db_debug.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,  # 保留5个备份文件
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'basic': {
            'handlers': ['file', 'console'],
            'level': 'WARNING',
            'propagate': True,
        },
        'backtest': {
            'handlers': ['console'],  # 只输出到控制台,方便实时查看
            'level': 'INFO',  # 设置为 INFO 级别,显示详细的回测过程
            'propagate': False,  # 不传播到父logger
        },
    },
}

# 确保日志目录存在
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

SPECTACULAR_SETTINGS = {
    'TITLE': '股票回测分析平台 API',  # 这里填写你想要的标题
    'DESCRIPTION': '基于 Django 和 Vue3 的股票分析与回测系统接口文档',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    # 解决国内网络导致页面空白的关键配置
    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
    'REDOC_DIST': 'SIDECAR',
}

# CORS 配置
# 开发环境：允许所有源访问（生产环境应该设置为 False）
CORS_ALLOW_ALL_ORIGINS = False

# 允许访问的源列表
CORS_ALLOWED_ORIGINS = [
    "https://www.huabenwuxin.com",  # 生产环境域名
    "http://localhost:5173",        # 开发环境域名
    "http://127.0.0.1:5173",        # 同样添加 127.0.0.1
]

# 是否允许携带认证信息（cookies, HTTP authentication）
CORS_ALLOW_CREDENTIALS = True

# 允许的 HTTP 方法列表
CORS_ALLOW_METHODS = [
    'GET',
    'POST',
    'PUT',
    'PATCH',
    'DELETE',
    'OPTIONS'
]

# 允许的请求头列表
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# 预检请求（OPTIONS）的缓存时间（秒）
CORS_PREFLIGHT_MAX_AGE = 86400  # 24小时

# 是否允许特定的 HTTP 头暴露给 JavaScript
CORS_EXPOSE_HEADERS = [
    'content-disposition',  # 允许前端访问下载文件名
]

# 添加 Celery 配置
CELERY_BROKER_POOL_LIMIT = 10  # 限制连接池大小
CELERY_TASK_ACKS_LATE = True   # 任务完成后再确认
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # 限制预取任务数

# 添加 Celery Beat 特定配置
DJANGO_CELERY_BEAT_TZ_AWARE = False
CELERY_BEAT_MAX_LOOP_INTERVAL = 5  # 降低循环间隔
CELERY_BEAT_SYNC_EVERY = 1  # 每次循环都同步数据库
# REST Framework 配置
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',  # 默认需要认证
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
}

# JWT 配置
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': False,  # 暂时不启用黑名单
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

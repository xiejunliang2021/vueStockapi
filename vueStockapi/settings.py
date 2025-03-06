from decouple import config
from pathlib import Path
import oracledb
import os
from celery.schedules import crontab
import logging

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-yz1)2zwsqijy!e+$^2_ix&#0zic3@0&!!y@3t0@g$=lxo&s^x%'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['*' ]


# Application definition

INSTALLED_APPS = [
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'basic',
    'weighing',
    'rest_framework',
    'coreapi',
    'django_filters',
    'django_celery_beat',
    'django_celery_results'
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

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.oracle',
        'NAME': config('NAME_ORACLE',),
        'USER': config('USER_ORACLE',),
        'PASSWORD': config('PASSWORD_ORACLE',),
        'HOST': '',
        'PORT': '',
        'CONN_MAX_AGE': 0,  # 禁用连接持久化
        'OPTIONS': {
            'retry_count': 3,
            'retry_delay': 1,
            'ssl_server_dn_match': True,
        },
        'TEST': {
            'NAME': 'test_' + config('NAME_ORACLE',),
        },
    },
        'mysql_db': {
        'ENGINE': 'django.db.backends.mysql',  # 使用 MySQL 数据库
        'NAME': 'weighing',
        'USER': config('USER_MYSQL',),
        'PASSWORD': config('PASSWORD_MYSQL',),
        'HOST': 'localhost',
        'PORT': '3306',  # MySQL 的默认端口
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

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# DRF配置鉴权方式
REST_FRAMEWORK = {
    'DEFAULT_SCHEMA_CLASS': 'rest_framework.schemas.coreapi.AutoSchema',
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
CELERY_BROKER_URL = 'redis://localhost:6379/0'  # 使用Redis作为消息代理
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Asia/Shanghai'  # 设置时区
CELERY_ENABLE_UTC = False
# Celery Configuration
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Celery Beat 配置
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BEAT_SYNC_EVERY = 1  # 每次循环都同步数据库
CELERY_BEAT_MAX_LOOP_INTERVAL = 5  # 降低循环间隔

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
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'logs/debug.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        'basic': {
            'handlers': ['file', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# 确保日志目录存在
if not os.path.exists('logs'):
    os.makedirs('logs')

# CORS 配置
# 是否允许所有源访问，生产环境建议设置为 False
CORS_ALLOW_ALL_ORIGINS = False

CORS_ALLOW_CREDENTIALS = True

# 添加更多的 CORS 配置
# 允许访问的源列表，当 CORS_ALLOW_ALL_ORIGINS 为 False 时生效
CORS_ALLOWED_ORIGINS = [
    "https://www.huabenwuxin.com",  # 生产环境域名
    "http://localhost:5173",        # 开发环境域名
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

# 是否允许处理非标准的 Content-Type 头
CORS_ALLOW_NON_STANDARD_CONTENT_TYPE = False

# 是否在响应中添加 Vary: Origin 头
CORS_VARY_HEADER = True

# 是否允许特定的 HTTP 头暴露给 JavaScript
CORS_EXPOSE_HEADERS = [
    'content-disposition',  # 允许前端访问下载文件名
]

# URL 正则表达式，只对匹配的 URL 启用 CORS
CORS_URLS_REGEX = r'^/api/.*$'  # 只对 /api/ 开头的 URL 启用 CORS

# 是否检查请求头中的 Host 是否与 Django 的 ALLOWED_HOSTS 匹配
CORS_ORIGIN_ALLOW_ALL = False

# 是否允许请求中包含通配符
CORS_ALLOW_WILDCARDS = False

# 添加 Celery 配置
CELERY_BROKER_POOL_LIMIT = 10  # 限制连接池大小
CELERY_TASK_ACKS_LATE = True   # 任务完成后再确认
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # 限制预取任务数

# 添加 Celery Beat 特定配置
DJANGO_CELERY_BEAT_TZ_AWARE = False
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'
CELERY_BEAT_MAX_LOOP_INTERVAL = 5  # 降低循环间隔
CELERY_BEAT_SYNC_EVERY = 1  # 每次循环都同步数据库

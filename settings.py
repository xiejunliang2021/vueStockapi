from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'update-daily-data-and-signals': {
        'task': 'basic.tasks.update_daily_data_and_signals',
        'schedule': crontab(hour=17, minute=0),  # 每天下午5点执行
    },
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.oracle',
        'NAME': 'your_oracle_sid',  # Oracle SID
        'USER': 'your_oracle_user',
        'PASSWORD': 'your_oracle_password',
        'HOST': 'your_oracle_host',
        'PORT': '1521',  # Oracle默认端口
    },
    'mysql_db': {  # weighing应用专用的MySQL数据库
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'weighing_db',
        'USER': 'your_mysql_user',
        'PASSWORD': 'your_mysql_password',
        'HOST': 'localhost',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        }
    }
}

DATABASE_ROUTERS = ['db_router.WeighingRouter'] 
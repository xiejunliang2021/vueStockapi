from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'update-daily-data-and-signals': {
        'task': 'basic.tasks.update_daily_data_and_signals',
        'schedule': crontab(hour=17, minute=0),  # 每天下午5点执行
    },
}


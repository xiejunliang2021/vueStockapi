from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, CrontabSchedule
from django.db import transaction
import json

class Command(BaseCommand):
    help = 'Setup Celery Beat schedules safely'

    def handle(self, *args, **kwargs):
        try:
            with transaction.atomic():
                # 清理现有的调度
                self.stdout.write('Cleaning existing schedules...')
                PeriodicTask.objects.all().delete()
                CrontabSchedule.objects.all().delete()

                # 创建定时调度
                schedules = {
                    'daily_data_update': CrontabSchedule.objects.create(
                        hour=17, 
                        minute=0,
                        timezone='Asia/Shanghai'
                    ),
                    'analyze_stock_patterns': CrontabSchedule.objects.create(
                        hour=17,
                        minute=5,
                        timezone='Asia/Shanghai'
                    ),
                    'analyze_daily_strategy': CrontabSchedule.objects.create(
                        hour=17,
                        minute=10,
                        timezone='Asia/Shanghai'
                    ),
                    'analyze_daily_stats': CrontabSchedule.objects.create(
                        hour=17,
                        minute=20,
                        timezone='Asia/Shanghai'
                    ),
                }

                # 创建任务
                tasks = [
                    {
                        'name': 'daily_data_update',
                        'task': 'basic.tasks.daily_data_update',
                        'schedule': schedules['daily_data_update'],
                    },
                    {
                        'name': 'analyze_stock_patterns',
                        'task': 'basic.tasks.analyze_stock_patterns',
                        'schedule': schedules['analyze_stock_patterns'],
                    },
                    {
                        'name': 'analyze_daily_strategy',
                        'task': 'basic.tasks.daily_strategy_analysis',
                        'schedule': schedules['analyze_daily_strategy'],
                    },
                    {
                        'name': 'analyze_daily_stats',
                        'task': 'basic.tasks.daily_stats_analysis',
                        'schedule': schedules['analyze_daily_stats'],
                    },
                ]

                for task in tasks:
                    PeriodicTask.objects.create(
                        name=task['name'],
                        task=task['task'],
                        crontab=task['schedule'],
                        enabled=True
                    )

                self.stdout.write(self.style.SUCCESS('Successfully set up Celery Beat schedules'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to set up schedules: {str(e)}'))
            raise 
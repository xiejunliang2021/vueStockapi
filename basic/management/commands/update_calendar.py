from django.core.management.base import BaseCommand
from basic.utils import StockDataFetcher
from datetime import datetime

class Command(BaseCommand):
    help = '更新交易日历数据，可指定年份或更新当前年份。'

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            help='指定要更新的年份 (例如: 2023)。如果不指定，则更新当前年份。',
            required=False
        )

    def handle(self, *args, **options):
        year = options['year']
        fetcher = StockDataFetcher()

        if year:
            # 构建一个该年份的日期字符串，例如 '2023-01-01'
            date_str = f'{year}-01-01'
            self.stdout.write(self.style.SUCCESS(f'正在更新 {year} 年的交易日历...'))
            success = fetcher.update_trading_calendar(date_str=date_str)
        else:
            self.stdout.write(self.style.SUCCESS('正在更新当前年份的交易日历...'))
            success = fetcher.update_trading_calendar()

        if success:
            self.stdout.write(self.style.SUCCESS('交易日历更新成功！'))
        else:
            self.stdout.write(self.style.ERROR('交易日历更新失败。'))

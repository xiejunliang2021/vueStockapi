from django.core.management.base import BaseCommand
from django.db import connections

class Command(BaseCommand):
    help = '清理数据库表'

    def handle(self, *args, **options):
        with connections['default'].cursor() as cursor:
            try:
                # 先删除可能存在的表
                tables_to_drop = [
                    'BASIC_STOCKDAILYDATA',
                    'BASIC_POLICYDETAILS',
                    'BASIC_CODE',
                    'DJANGO_MIGRATIONS'
                ]
                
                for table in tables_to_drop:
                    try:
                        cursor.execute(f"DROP TABLE {table} CASCADE CONSTRAINTS")
                        self.stdout.write(self.style.SUCCESS(f'成功删除表 {table}'))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'删除表 {table} 时出错: {str(e)}'))

                self.stdout.write(self.style.SUCCESS('数据库清理完成'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'清理过程出错: {str(e)}')) 
from django.core.management.base import BaseCommand
from django.db import connections

class Command(BaseCommand):
    help = '测试表创建'

    def handle(self, *args, **options):
        with connections['default'].cursor() as cursor:
            try:
                # 尝试创建一个测试表
                cursor.execute("""
                    CREATE TABLE test_table (
                        id NUMBER PRIMARY KEY,
                        name VARCHAR2(100)
                    )
                """)
                self.stdout.write(self.style.SUCCESS('测试表创建成功'))
                
                # 验证表是否存在
                cursor.execute("""
                    SELECT table_name 
                    FROM user_tables 
                    WHERE table_name = 'TEST_TABLE'
                """)
                if cursor.fetchone():
                    self.stdout.write(self.style.SUCCESS('可以在数据库中找到测试表'))
                
                # 清理
                cursor.execute("DROP TABLE test_table")
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'错误: {str(e)}')) 
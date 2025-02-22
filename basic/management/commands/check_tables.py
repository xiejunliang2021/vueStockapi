from django.core.management.base import BaseCommand
from django.db import connections

class Command(BaseCommand):
    help = '检查数据库表结构'

    def handle(self, *args, **options):
        with connections['default'].cursor() as cursor:
            # 检查当前用户
            cursor.execute("SELECT USER FROM DUAL")
            current_user = cursor.fetchone()[0]
            self.stdout.write(f"当前用户: {current_user}")

            # 检查所有表
            cursor.execute("""
                SELECT table_name 
                FROM user_tables 
                ORDER BY table_name
            """)
            tables = cursor.fetchall()
            
            self.stdout.write("发现的表:")
            for table in tables:
                self.stdout.write(f"- {table[0]}")

            # 检查用户权限
            cursor.execute("""
                SELECT privilege 
                FROM user_sys_privs
            """)
            privileges = cursor.fetchall()
            
            self.stdout.write("\n用户权限:")
            for priv in privileges:
                self.stdout.write(f"- {priv[0]}") 
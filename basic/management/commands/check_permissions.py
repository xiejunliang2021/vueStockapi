from django.core.management.base import BaseCommand
from django.db import connections

class Command(BaseCommand):
    help = '检查数据库用户权限'

    def handle(self, *args, **options):
        with connections['default'].cursor() as cursor:
            # 检查当前用户
            cursor.execute("SELECT sys_context('USERENV', 'CURRENT_SCHEMA') FROM DUAL")
            current_schema = cursor.fetchone()[0]
            self.stdout.write(f"当前 Schema: {current_schema}")

            # 检查用户权限
            cursor.execute("""
                SELECT privilege 
                FROM user_sys_privs 
                UNION 
                SELECT privilege 
                FROM user_tab_privs
            """)
            privileges = cursor.fetchall()
            
            self.stdout.write("\n用户权限:")
            for priv in privileges:
                self.stdout.write(f"- {priv[0]}")

            # 检查表空间权限
            cursor.execute("""
                SELECT tablespace_name, max_bytes
                FROM user_ts_quotas
            """)
            quotas = cursor.fetchall()
            
            self.stdout.write("\n表空间配额:")
            for quota in quotas:
                self.stdout.write(f"- {quota[0]}: {quota[1]}") 
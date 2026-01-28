from django.core.management.base import BaseCommand
from django.db import connections, OperationalError
import traceback

class Command(BaseCommand):
    help = '测试表创建'

    def handle(self, *args, **options):
        db_name = 'default'
        try:
            with connections[db_name].cursor() as cursor:
                self.stdout.write(self.style.SUCCESS(f"成功连接到数据库 '{db_name}'。"))
                
                # 尝试创建一个测试表
                cursor.execute("""
                    CREATE TABLE test_table (
                        id NUMBER PRIMARY KEY,
                        name VARCHAR2(100)
                    )
                """)
                self.stdout.write(self.style.SUCCESS('测试表创建成功'))
                
                # 验证表是否存在
                cursor.execute("SELECT table_name FROM user_tables WHERE table_name = 'TEST_TABLE'")
                if cursor.fetchone():
                    self.stdout.write(self.style.SUCCESS('可以在数据库中找到测试表'))
                else:
                    self.stderr.write(self.style.ERROR('无法在数据库中找到测试表'))

                # 清理
                cursor.execute("DROP TABLE test_table")
                self.stdout.write(self.style.SUCCESS('测试表已删除'))

        except OperationalError as e:
            self.stderr.write(self.style.ERROR(f"连接到数据库 '{db_name}' 失败: {e}"))
            self.stderr.write(self.style.ERROR("这是一个数据库连接错误。请检查您的数据库设置、网络连接和防火墙规则。"))
            self.stderr.write(self.style.ERROR("根本原因很可能是 'ORA-12506: TNS:listener rejected connection based on service ACL filtering'。"))
            self.stderr.write(self.style.ERROR("这通常是由于数据库服务器端的安全设置（ACL）阻止了来自此应用程序的连接。"))
            self.stderr.write(self.style.ERROR("请联系您的数据库管理员（DBA），并向他们提供此错误消息以及应用服务器的IP地址。"))
            self.stderr.write(self.style.ERROR("详细的追溯信息如下:"))
            traceback.print_exc()
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'在数据库操作期间发生意外错误: {e}'))
            self.stderr.write(self.style.ERROR("详细的追溯信息如下:"))
            traceback.print_exc() 
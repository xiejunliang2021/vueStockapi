# your_app/management/commands/test_db.py
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError
import time

class Command(BaseCommand):
    help = '测试Oracle数据库连接'

    def handle(self, *args, **options):
        # 获取默认数据库连接
        db_conn = connections['default']
        start_time = time.time()
        
        self.stdout.write('开始测试数据库连接...')
        
        try:
            # 测试数据库连接
            db_conn.cursor()
            
            # 执行简单查询
            with db_conn.cursor() as cursor:
                # 测试1：使用DUAL表进行简单测试
                cursor.execute("SELECT 'Connected' FROM DUAL")
                result = cursor.fetchone()
                self.stdout.write(self.style.SUCCESS(f'基础连接测试: {result[0]}'))
                
                # 测试2：检查数据库版本
                cursor.execute("SELECT BANNER FROM v$version WHERE banner LIKE 'Oracle%'")
                version = cursor.fetchone()
                self.stdout.write(self.style.SUCCESS(f'数据库版本: {version[0]}'))
                
                # 测试3：检查当前会话信息
                cursor.execute("""
                    SELECT 
                        SYS_CONTEXT('USERENV','SERVER_HOST'),
                        SYS_CONTEXT('USERENV','DB_NAME'),
                        SYS_CONTEXT('USERENV','CURRENT_SCHEMA')
                    FROM DUAL
                """)
                host, db_name, schema = cursor.fetchone()
                self.stdout.write(self.style.SUCCESS(f'数据库主机: {host}'))
                self.stdout.write(self.style.SUCCESS(f'数据库名称: {db_name}'))
                self.stdout.write(self.style.SUCCESS(f'当前Schema: {schema}'))
                
                # 测试4：检查数据库时间
                cursor.execute("SELECT SYSDATE FROM DUAL")
                db_time = cursor.fetchone()[0]
                self.stdout.write(self.style.SUCCESS(f'数据库时间: {db_time}'))
                
            elapsed_time = time.time() - start_time
            self.stdout.write(self.style.SUCCESS(
                f'✓ 数据库连接测试成功! 耗时: {elapsed_time:.2f}秒'
            ))
            
        except OperationalError as e:
            self.stdout.write(self.style.ERROR(f'连接失败: {str(e)}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'测试过程中出错: {str(e)}'))
        finally:
            db_conn.close()

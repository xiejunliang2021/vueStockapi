from django.core.management.base import BaseCommand
from django.db import connections

class Command(BaseCommand):
    help = '完全清理数据库中的所有表'

    def handle(self, *args, **options):
        with connections['default'].cursor() as cursor:
            try:
                # 获取所有表名
                cursor.execute("""
                    SELECT table_name 
                    FROM user_tables 
                    ORDER BY table_name
                """)
                tables = cursor.fetchall()
                
                self.stdout.write("开始清理数据库...")
                
                # 先禁用所有外键约束
                for table in tables:
                    try:
                        cursor.execute(f"""
                            BEGIN
                                FOR c IN (
                                    SELECT constraint_name, table_name
                                    FROM user_constraints
                                    WHERE constraint_type = 'R'
                                    AND table_name = '{table[0]}'
                                ) LOOP
                                    EXECUTE IMMEDIATE 'ALTER TABLE '|| c.table_name ||
                                        ' DISABLE CONSTRAINT '|| c.constraint_name;
                                END LOOP;
                            END;
                        """)
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'禁用约束时出错: {str(e)}'))

                # 删除所有表
                for table in tables:
                    try:
                        cursor.execute(f"DROP TABLE {table[0]} CASCADE CONSTRAINTS PURGE")
                        self.stdout.write(self.style.SUCCESS(f'成功删除表 {table[0]}'))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'删除表 {table[0]} 时出错: {str(e)}'))

                # 删除所有序列
                cursor.execute("SELECT sequence_name FROM user_sequences")
                sequences = cursor.fetchall()
                for seq in sequences:
                    try:
                        cursor.execute(f"DROP SEQUENCE {seq[0]}")
                        self.stdout.write(self.style.SUCCESS(f'成功删除序列 {seq[0]}'))
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'删除序列 {seq[0]} 时出错: {str(e)}'))

                self.stdout.write(self.style.SUCCESS('数据库清理完成！'))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'清理过程出错: {str(e)}')) 
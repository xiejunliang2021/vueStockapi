from django.core.management.base import BaseCommand
from django.db import connections

class Command(BaseCommand):
    help = '重建迁移记录'

    def handle(self, *args, **options):
        with connections['default'].cursor() as cursor:
            try:
                # 检查 django_migrations 表是否存在
                cursor.execute("""
                    SELECT table_name 
                    FROM user_tables 
                    WHERE table_name = 'DJANGO_MIGRATIONS'
                """)
                
                if not cursor.fetchone():
                    # 创建 django_migrations 表
                    cursor.execute("""
                        CREATE TABLE django_migrations (
                            id NUMBER(11) PRIMARY KEY,
                            app VARCHAR2(255) NOT NULL,
                            name VARCHAR2(255) NOT NULL,
                            applied TIMESTAMP(6) NOT NULL
                        )
                    """)
                    
                    # 创建序列
                    cursor.execute("""
                        CREATE SEQUENCE django_migrations_id_seq
                        START WITH 1
                        INCREMENT BY 1
                        NOCACHE
                        NOCYCLE
                    """)
                
                # 插入基本应用的迁移记录
                cursor.execute("""
                    INSERT INTO django_migrations (
                        id, app, name, applied
                    ) VALUES (
                        django_migrations_id_seq.NEXTVAL,
                        'basic',
                        '0001_initial',
                        SYSTIMESTAMP
                    )
                """)
                
                self.stdout.write(self.style.SUCCESS('迁移记录重建完成'))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'重建过程出错: {str(e)}')) 
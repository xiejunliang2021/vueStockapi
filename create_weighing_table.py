#!/usr/bin/env python
"""手动创建 weighing 表"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')
django.setup()

from django.db import connections

def create_weighing_table():
    print("=" * 60)
    print("手动创建 weighing_weighingrecord 表")
    print("=" * 60)
    
    try:
        conn = connections['mysql']
        with conn.cursor() as cursor:
            # 创建 weighing_weighingrecord 表
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS `weighing_weighingrecord` (
                `id` bigint NOT NULL AUTO_INCREMENT,
                `license_plate` varchar(20) NOT NULL,
                `tare_weight` int NOT NULL,
                `gross_weight` int NOT NULL,
                `net_weight` int NOT NULL,
                `cargo_spec` varchar(100) NOT NULL,
                `receiving_unit` varchar(255) NOT NULL,
                `updated_at` datetime(6) NOT NULL,
                PRIMARY KEY (`id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
            
            cursor.execute(create_table_sql)
            print("✅ 表创建成功！")
            
            # 验证表是否创建
            cursor.execute("SHOW TABLES LIKE 'weighing%'")
            tables = cursor.fetchall()
            
            if tables:
                print(f"\n找到 weighing 表:")
                for table in tables:
                    print(f"   - {table[0]}")
            else:
                print("❌ 表创建失败")
                
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    create_weighing_table()

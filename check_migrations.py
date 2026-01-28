#!/usr/bin/env python
"""检查迁移记录"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')
django.setup()

from django.db import connections

def check_migration_records():
    print("=" * 60)
    print("检查 MySQL 数据库中的迁移记录")
    print("=" * 60)
    
    try:
        conn = connections['mysql']
        with conn.cursor() as cursor:
            # 查询 weighing 和 backtest 的迁移记录
            cursor.execute("""
                SELECT app, name, applied 
                FROM django_migrations 
                WHERE app IN ('weighing', 'backtest')
                ORDER BY app, id
            """)
            migrations = cursor.fetchall()
            
            if migrations:
                print("\n找到以下迁移记录:")
                for app, name, applied in migrations:
                    print(f"   {app}: {name} (应用时间: {applied})")
            else:
                print("\n❌ 没有找到 weighing 或 backtest 的迁移记录")
            
            # 检查所有应用的迁移记录
            print("\n" + "=" * 60)
            cursor.execute("""
                SELECT app, COUNT(*) as count 
                FROM django_migrations 
                GROUP BY app
                ORDER BY app
            """)
            stats = cursor.fetchall()
            
            print("所有应用的迁移记录统计:")
            for app, count in stats:
                print(f"   {app}: {count} 个迁移")
                
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    check_migration_records()

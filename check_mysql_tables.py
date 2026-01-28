#!/usr/bin/env python
"""检查 MySQL 数据库中的表"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')
django.setup()

from django.db import connections

def check_mysql_tables():
    print("=" * 60)
    print("检查 MySQL 数据库中的表")
    print("=" * 60)
    
    try:
        conn = connections['mysql']
        with conn.cursor() as cursor:
            # 获取所有表
            cursor.execute(f"SHOW TABLES FROM {conn.settings_dict['NAME']}")
            tables = cursor.fetchall()
            
            print(f"\n📋 总共有 {len(tables)} 个表\n")
            
            # 分类显示
            backtest_tables = []
            weighing_tables = []
            other_tables = []
            
            for table in tables:
                table_name = table[0]
                if table_name.startswith('backtest_'):
                    backtest_tables.append(table_name)
                elif table_name.startswith('weighing_'):
                    weighing_tables.append(table_name)
                else:
                    other_tables.append(table_name)
            
            print("🎯 Backtest 应用的表:")
            if backtest_tables:
                for table in backtest_tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"   ✅ {table} (记录数: {count})")
            else:
                print("   ❌ 没有 backtest_ 开头的表")
            
            print("\n⚖️  Weighing 应用的表:")
            if weighing_tables:
                for table in weighing_tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"   ✅ {table} (记录数: {count})")
            else:
                print("   ❌ 没有 weighing_ 开头的表")
            
            print("\n🔧 其他表:")
            for table in sorted(other_tables):
                print(f"   - {table}")
                
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)

if __name__ == '__main__':
    check_mysql_tables()

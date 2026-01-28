#!/usr/bin/env python
"""测试数据库连接"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')
django.setup()

from django.db import connections

def test_databases():
    print("=" * 60)
    print("测试数据库连接")
    print("=" * 60)
    
    # 测试 MySQL 连接
    print("\n1. 测试 MySQL 数据库连接...")
    try:
        conn = connections['mysql']
        with conn.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
            print(f"   ✅ MySQL 连接成功！")
            print(f"   📊 数据库名称: {conn.settings_dict['NAME']}")
            print(f"   🌐 主机地址: {conn.settings_dict['HOST']}")
            print(f"   🔢 端口: {conn.settings_dict['PORT']}")
            print(f"   👤 用户名: {conn.settings_dict['USER']}")
            print(f"   📦 MySQL 版本: {version[0]}")
            
            # 列出所有表
            cursor.execute(f"SHOW TABLES FROM {conn.settings_dict['NAME']}")
            tables = cursor.fetchall()
            print(f"   📋 现有表数量: {len(tables)}")
            if tables:
                print("   现有表:")
                for table in tables[:10]:  # 只显示前10个
                    print(f"      - {table[0]}")
                if len(tables) > 10:
                    print(f"      ... 还有 {len(tables) - 10} 个表")
    except Exception as e:
        print(f"   ❌ MySQL 连接失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试 Oracle 连接
    print("\n2. 测试 Oracle 数据库连接...")
    try:
        conn = connections['default']
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM v$version WHERE rownum = 1")
            version = cursor.fetchone()
            print(f"   ✅ Oracle 连接成功！")
            print(f"   📊 数据库名称: {conn.settings_dict['NAME']}")
            print(f"   👤 用户名: {conn.settings_dict['USER']}")
            if version:
                print(f"   📦 Oracle 版本: {version[0][:50]}...")
    except Exception as e:
        print(f"   ❌ Oracle 连接失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("数据库连接测试完成")
    print("=" * 60)
    return True

if __name__ == '__main__':
    test_databases()

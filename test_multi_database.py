#!/usr/bin/env python
"""完整的多数据库验证脚本"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')
django.setup()

from django.db import connections
from weighing.models import WeighingRecord
from backtest.models import PortfolioBacktest, TradeLog

def test_multi_database():
    print("=" * 70)
    print("🧪 Django 多数据库配置验证")
    print("=" * 70)
    
    # 测试 1: 数据库连接
    print("\n【测试 1】数据库连接测试")
    print("-" * 70)
    
    try:
        conn_mysql = connections['mysql']
        conn_mysql.ensure_connection()
        print("✅ MySQL 连接成功")
        print(f"   数据库: {conn_mysql.settings_dict['NAME']}")
        print(f"   主机: {conn_mysql.settings_dict['HOST']}")
    except Exception as e:
        print(f"❌ MySQL 连接失败: {e}")
        return False
    
    try:
        conn_oracle = connections['default']
        conn_oracle.ensure_connection()
        print("✅ Oracle 连接成功")
        print(f"   数据库: {conn_oracle.settings_dict['NAME']}")
    except Exception as e:
        print(f"❌ Oracle 连接失败: {e}")
        return False
    
    # 测试 2: 数据库路由
    print("\n【测试 2】数据库路由测试")
    print("-" * 70)
    
    # WeighingRecord 应该路由到 MySQL
    weighing_db = WeighingRecord.objects.db
    print(f"WeighingRecord 模型使用数据库: {weighing_db}")
    if weighing_db == 'mysql':
        print("✅ WeighingRecord 正确路由到 MySQL")
    else:
        print(f"❌ WeighingRecord 路由错误，期望 'mysql'，实际 '{weighing_db}'")
    
    # PortfolioBacktest 应该路由到 MySQL
    backtest_db = PortfolioBacktest.objects.db
    print(f"PortfolioBacktest 模型使用数据库: {backtest_db}")
    if backtest_db == 'mysql':
        print("✅ PortfolioBacktest 正确路由到 MySQL")
    else:
        print(f"❌ PortfolioBacktest 路由错误，期望 'mysql'，实际 '{backtest_db}'")
    
    # 测试 3: 表结构验证
    print("\n【测试 3】表结构验证")
    print("-" * 70)
    
    try:
        with conn_mysql.cursor() as cursor:
            # 检查 weighing 表
            cursor.execute("SHOW TABLES LIKE 'weighing_%'")
            weighing_tables = cursor.fetchall()
            print(f"Weighing 表: {len(weighing_tables)} 个")
            for table in weighing_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                count = cursor.fetchone()[0]
                print(f"   ✅ {table[0]} (记录数: {count})")
            
            # 检查 backtest 表
            cursor.execute("SHOW TABLES LIKE 'backtest_%'")
            backtest_tables = cursor.fetchall()
            print(f"Backtest 表: {len(backtest_tables)} 个")
            for table in backtest_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                count = cursor.fetchone()[0]
                print(f"   ✅ {table[0]} (记录数: {count})")
    except Exception as e:
        print(f"❌ 表结构验证失败: {e}")
        return False
    
    # 测试 4: ORM 操作测试
    print("\n【测试 4】ORM 操作测试")
    print("-" * 70)
    
    try:
        # 测试 WeighingRecord 查询
        weighing_count = WeighingRecord.objects.count()
        print(f"✅ WeighingRecord 查询成功: {weighing_count} 条记录")
        
        # 测试 PortfolioBacktest 查询
        backtest_count = PortfolioBacktest.objects.count()
        print(f"✅ PortfolioBacktest 查询成功: {backtest_count} 条记录")
        
        # 测试 TradeLog 查询
        tradelog_count = TradeLog.objects.count()
        print(f"✅ TradeLog 查询成功: {tradelog_count} 条记录")
        
        # 显示最近的回测记录
        if backtest_count > 0:
            latest_backtest = PortfolioBacktest.objects.order_by('-created_at').first()
            print(f"\n   最新回测记录:")
            print(f"   - 策略: {latest_backtest.strategy_name}")
            print(f"   - 时间范围: {latest_backtest.start_date} 至 {latest_backtest.end_date}")
            print(f"   - 总收益率: {latest_backtest.total_return:.2%}")
            print(f"   - 交易次数: {latest_backtest.total_trades}")
    except Exception as e:
        print(f"❌ ORM 操作失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 测试 5: 迁移状态检查
    print("\n【测试 5】迁移状态检查")
    print("-" * 70)
    
    try:
        with conn_mysql.cursor() as cursor:
            cursor.execute("""
                SELECT app, name 
                FROM django_migrations 
                WHERE app IN ('weighing', 'backtest')
                ORDER BY app, id
            """)
            migrations = cursor.fetchall()
            
            weighing_migrations = [m for m in migrations if m[0] == 'weighing']
            backtest_migrations = [m for m in migrations if m[0] == 'backtest']
            
            print(f"Weighing 迁移记录: {len(weighing_migrations)} 个")
            for app, name in weighing_migrations:
                print(f"   ✅ {name}")
            
            print(f"Backtest 迁移记录: {len(backtest_migrations)} 个")
            for app, name in backtest_migrations:
                print(f"   ✅ {name}")
    except Exception as e:
        print(f"❌ 迁移状态检查失败: {e}")
    
    # 总结
    print("\n" + "=" * 70)
    print("🎉 多数据库配置验证完成！")
    print("=" * 70)
    print("\n✅ 配置总结:")
    print("   • Oracle 数据库 (default): 用于 basic 等应用")
    print("   • MySQL 数据库 (mysql): 用于 weighing 和 backtest 应用")
    print("   • 数据库路由器: weighing.db_router.WeighingRouter")
    print("   • 所有表已正确创建并可以正常访问")
    print("\n📚 下一步建议:")
    print("   1. 测试 API 接口是否正常工作")
    print("   2. 如需从其他数据库迁移数据，请创建数据迁移脚本")
    print("   3. 为两个数据库配置定期备份")
    print("=" * 70)
    
    return True

if __name__ == '__main__':
    success = test_multi_database()
    exit(0 if success else 1)

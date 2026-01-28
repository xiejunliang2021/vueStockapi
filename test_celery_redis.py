#!/usr/bin/env python
"""测试 Celery 和 Redis 连接"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')
django.setup()

from celery import Celery
from django.conf import settings

def test_celery_redis():
    print("=" * 70)
    print("🧪 Celery 和 Redis 连接测试")
    print("=" * 70)
    
    # 测试 1: Redis 连接
    print("\n【测试 1】Redis 连接测试")
    print("-" * 70)
    
    try:
        import redis
        r = redis.Redis(host='127.0.0.1', port=6379, db=0)
        pong = r.ping()
        print(f"✅ Redis 连接成功！Response: {pong}")
        
        # 设置和获取测试值
        r.set('test_key', 'Hello from Redis!')
        value = r.get('test_key')
        print(f"✅ Redis 读写测试成功！值: {value.decode('utf-8')}")
        
        # 清理测试键
        r.delete('test_key')
        
    except Exception as e:
        print(f"❌ Redis 连接失败: {e}")
        return False
    
    # 测试 2: Celery 配置
    print("\n【测试 2】Celery 配置检查")
    print("-" * 70)
    
    try:
        print(f"Broker URL: {settings.CELERY_BROKER_URL}")
        print(f"Result Backend: {settings.CELERY_RESULT_BACKEND}")
        print(f"Timezone: {settings.CELERY_TIMEZONE}")
        print("✅ Celery 配置正确")
    except Exception as e:
        print(f"❌ Celery 配置错误: {e}")
        return False
    
    # 测试 3: Celery App
    print("\n【测试 3】Celery Application 测试")
    print("-" * 70)
    
    try:
        from vueStockapi.celery import app
        
        # 检查 Celery 是否能连接到 Redis
        inspect = app.control.inspect()
        print("✅ Celery App 创建成功")
        
        # 尝试获取注册的任务
        try:
            registered_tasks = inspect.registered()
            if registered_tasks:
                print(f"✅ 找到 {len(registered_tasks)} 个 Worker（如果有的话）")
            else:
                print("ℹ️  当前没有运行的 Worker（这是正常的）")
        except Exception as e:
            print(f"ℹ️  无法连接到 Worker: {e}")
            print("   （这是正常的，因为 Worker 可能还没启动）")
        
    except Exception as e:
        print(f"❌ Celery App 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # 总结
    print("\n" + "=" * 70)
    print("🎉 测试完成！")
    print("=" * 70)
    print("\n✅ Redis 和 Celery 配置正常")
    print("\n📚 下一步：")
    print("   1. 启动 Celery Worker:")
    print("      uv run celery -A vueStockapi worker -l info -P solo")
    print("\n   2. 启动 Celery Beat (定时任务):")
    print("      uv run celery -A vueStockapi beat -l info")
    print("\n   3. 或者同时启动 Worker 和 Beat:")
    print("      uv run celery -A vueStockapi worker -l info -P solo --beat")
    print("=" * 70)
    
    return True

if __name__ == '__main__':
    success = test_celery_redis()
    exit(0 if success else 1)

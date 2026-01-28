"""
Redis 环境诊断脚本
用于检查服务器上的 Redis 配置和连接问题
"""

import sys
import os

print("=" * 60)
print("Redis 环境诊断")
print("=" * 60)

# 1. 检查 Python 环境
print("\n1. Python 环境信息:")
print(f"   Python 可执行文件: {sys.executable}")
print(f"   Python 版本: {sys.version}")
print(f"   Python 路径: {sys.path[:3]}...")

# 2. 检查 redis 模块
print("\n2. Redis 模块检查:")
try:
    import redis
    print(f"   ✓ redis 模块已安装")
    print(f"   版本: {redis.__version__}")
    print(f"   路径: {redis.__file__}")
except ImportError as e:
    print(f"   ✗ redis 模块未安装: {e}")
    print("\n   修复方法:")
    print(f"   在当前 conda 环境中运行: pip install redis")
    sys.exit(1)

# 3. 检查 Django 配置
print("\n3. Django 配置检查:")
try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')
    import django
    django.setup()
    
    from django.conf import settings
    print(f"   ✓ Django 配置加载成功")
    print(f"   CELERY_BROKER_URL: {settings.CELERY_BROKER_URL}")
    print(f"   CELERY_RESULT_BACKEND: {settings.CELERY_RESULT_BACKEND}")
except Exception as e:
    print(f"   ✗ Django 配置加载失败: {e}")
    import traceback
    traceback.print_exc()

# 4. 测试 Redis 连接
print("\n4. Redis 连接测试:")
try:
    from django.conf import settings
    
    # 解析 Redis URL
    broker_url = settings.CELERY_BROKER_URL
    print(f"   连接地址: {broker_url}")
    
    # 创建 Redis 客户端
    r = redis.Redis.from_url(broker_url)
    
    # 测试连接
    r.ping()
    print(f"   ✓ Redis 连接成功")
    
    # 测试读写
    r.set('test_key', 'test_value')
    value = r.get('test_key')
    r.delete('test_key')
    print(f"   ✓ Redis 读写测试通过")
    
except Exception as e:
    print(f"   ✗ Redis 连接失败: {e}")
    import traceback
    traceback.print_exc()
    print("\n   可能的原因:")
    print("   1. Redis 服务未启动")
    print("   2. Redis 连接地址错误")
    print("   3. 防火墙阻止连接")
    print("   4. Redis 密码配置错误")

# 5. 检查 Celery 配置
print("\n5. Celery 配置检查:")
try:
    from vueStockapi.celery import app as celery_app
    print(f"   ✓ Celery 应用加载成功")
    print(f"   Broker: {celery_app.conf.broker_url}")
    print(f"   Backend: {celery_app.conf.result_backend}")
except Exception as e:
    print(f"   ✗ Celery 配置加载失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("诊断完成")
print("=" * 60)

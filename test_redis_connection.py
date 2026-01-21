"""
快速 Redis 连接测试
在服务器上运行此脚本以快速验证 Redis 配置
"""

def test_redis_connection():
    """测试 Redis 连接的最小化脚本"""
    
    print("开始测试 Redis 连接...")
    
    # 测试 1: 导入 redis 模块
    try:
        import redis
        print("✓ redis 模块导入成功")
        print(f"  版本: {redis.__version__}")
    except ImportError as e:
        print(f"✗ redis 模块导入失败: {e}")
        print("\n修复命令: pip install redis")
        return False
    
    # 测试 2: 连接 Redis
    try:
        r = redis.Redis(host='127.0.0.1', port=6379, db=0, socket_timeout=5)
        r.ping()
        print("✓ Redis 服务连接成功")
    except redis.exceptions.ConnectionError as e:
        print(f"✗ Redis 连接失败: {e}")
        print("\n可能原因:")
        print("  1. Redis 服务未启动")
        print("  2. Redis 监听地址/端口错误")
        print("  3. 防火墙阻止连接")
        return False
    except Exception as e:
        print(f"✗ 未知错误: {e}")
        return False
    
    # 测试 3: 读写测试
    try:
        r.set('test_connection', 'ok')
        value = r.get('test_connection')
        r.delete('test_connection')
        print("✓ Redis 读写测试通过")
    except Exception as e:
        print(f"✗ Redis 读写失败: {e}")
        return False
    
    # 测试 4: 测试 Celery broker URL 格式
    try:
        broker_url = 'redis://127.0.0.1:6379/0'
        r = redis.Redis.from_url(broker_url)
        r.ping()
        print(f"✓ Celery broker URL 连接成功: {broker_url}")
    except Exception as e:
        print(f"✗ Broker URL 连接失败: {e}")
        return False
    
    print("\n" + "="*50)
    print("所有测试通过! Redis 配置正确")
    print("="*50)
    return True

if __name__ == '__main__':
    import sys
    print(f"Python 环境: {sys.executable}")
    print("="*50 + "\n")
    
    success = test_redis_connection()
    
    if not success:
        print("\n请按照上述提示修复问题后重试")
        sys.exit(1)
    else:
        print("\n可以继续运行 Django 应用")
        sys.exit(0)

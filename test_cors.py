#!/usr/bin/env python
"""测试 CORS 配置"""
import requests

def test_cors():
    print("=" * 70)
    print("🧪 测试 CORS 配置")
    print("=" * 70)
    
    # 测试 API 端点
    url = "http://127.0.0.1:8000/api/backtest/portfolio/results/"
    
    # 模拟前端请求（带 Origin 头）
    headers = {
        'Origin': 'http://localhost:5173',
    }
    
    print(f"\n发送请求到: {url}")
    print(f"Origin: {headers['Origin']}")
    print("-" * 70)
    
    try:
        response = requests.get(url, headers=headers)
        
        print(f"\n状态码: {response.status_code}")
        print(f"\n响应头:")
        for key, value in response.headers.items():
            if 'access-control' in key.lower() or key.lower() == 'vary':
                print(f"  {key}: {value}")
        
        if 'Access-Control-Allow-Origin' in response.headers:
            print(f"\n✅ CORS 配置正确！")
            print(f"   允许的源: {response.headers['Access-Control-Allow-Origin']}")
        else:
            print(f"\n❌ 缺少 Access-Control-Allow-Origin 头")
            
        if response.status_code == 200:
            print(f"\n✅ API 请求成功")
            data = response.json()
            print(f"   返回数据数量: {len(data.get('results', []))} 条")
        else:
            print(f"\n⚠️  API 返回状态码: {response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print(f"\n❌ 无法连接到服务器")
        print(f"   请确保 Django 服务器正在运行")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)

if __name__ == '__main__':
    test_cors()

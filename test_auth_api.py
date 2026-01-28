#!/usr/bin/env python
"""测试后端认证 API"""
import requests
import json

BASE_URL = "http://127.0.0.1:8000"

def test_login():
    """测试登录 API"""
    print("=" * 70)
    print("🧪 测试登录 API")
    print("=" * 70)
    
    url = f"{BASE_URL}/api/auth/login/"
    data = {
        "username": "admin",
        "password": "admin123456"
    }
    
    print(f"\n发送请求到: {url}")
    print(f"请求数据: {json.dumps(data, indent=2)}")
    print("-" * 70)
    
    try:
        response = requests.post(url, json=data)
        print(f"\n状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ 登录成功！")
            print(f"\nAccess Token: {result['access'][:50]}...")
            print(f"Refresh Token: {result['refresh'][:50]}...")
            print(f"\n用户信息:")
            print(json.dumps(result['user'], indent=2, ensure_ascii=False))
            
            # 测试获取用户信息
            test_get_user_info(result['access'])
        else:
            print(f"\n❌ 登录失败")
            print(f"响应: {response.text}")
    except requests.exceptions.ConnectionError:
        print("\n❌ 无法连接到服务器")
        print("请确保 Django 服务器正在运行: uv run python manage.py runserver")
    except Exception as e:
        print(f"\n❌ 错误: {e}")

def test_get_user_info(access_token):
    """测试获取用户信息 API"""
    print("\n" + "=" * 70)
    print("🧪 测试获取用户信息 API")
    print("=" * 70)
    
    url = f"{BASE_URL}/api/auth/user/"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    print(f"\n发送请求到: {url}")
    print(f"Authorization Header: Bearer {access_token[:30]}...")
    print("-" * 70)
    
    try:
        response = requests.get(url, headers=headers)
        print(f"\n状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print("\n✅ 获取用户信息成功！")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"\n❌ 获取用户信息失败")
            print(f"响应: {response.text}")
    except Exception as e:
        print(f"\n❌ 错误: {e}")

if __name__ == "__main__":
    test_login()
    print("\n" + "=" * 70)
    print("✅ 测试完成")
    print("=" * 70)

#!/usr/bin/env python
"""
vueStockapi 项目 API 全面测试脚本
测试范围：
1. 认证模块（登录、获取用户信息、修改密码、更新资料、登出）
2. 基础数据模块（股票代码、交易日历、日线数据、策略分析）
3. 回测模块
4. 权重分析模块
5. 数据库连接（Oracle + MySQL）
"""
import requests
import json
import sys
import os
import django
from datetime import datetime

# ===================== 配置 =====================
BASE_URL = "http://127.0.0.1:8000"
# 请将下面的账号密码替换成项目中实际存在的超级管理员账号
TEST_USER = "admin"
TEST_PASS = "TestPass2026!"

# ===================== 测试工具类 =====================
class TestRunner:
    def __init__(self):
        self.results = []
        self.token = None
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.pass_count = 0
        self.fail_count = 0
        self.warn_count = 0

    def log(self, name, status, detail="", response=None):
        """记录测试结果"""
        icon = {"PASS": "✅", "FAIL": "❌", "WARN": "⚠️", "INFO": "ℹ️"}.get(status, "?")
        resp_code = f"[HTTP {response.status_code}]" if response else ""
        print(f"  {icon} {name} {resp_code}")
        if detail:
            print(f"     └─ {detail}")
        self.results.append({
            "name": name,
            "status": status,
            "detail": detail,
            "http_code": response.status_code if response else None
        })
        if status == "PASS":
            self.pass_count += 1
        elif status == "FAIL":
            self.fail_count += 1
        elif status == "WARN":
            self.warn_count += 1

    def set_auth(self, token):
        """设置 Authorization 请求头"""
        self.token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def get(self, path, **kwargs):
        return self.session.get(f"{BASE_URL}{path}", timeout=15, **kwargs)

    def post(self, path, data=None, **kwargs):
        return self.session.post(f"{BASE_URL}{path}", json=data, timeout=15, **kwargs)

    def put(self, path, data=None, **kwargs):
        return self.session.put(f"{BASE_URL}{path}", json=data, timeout=15, **kwargs)

    def summary(self):
        print(f"\n{'='*60}")
        print(f"  测试汇总")
        print(f"{'='*60}")
        print(f"  ✅ 通过: {self.pass_count}")
        print(f"  ❌ 失败: {self.fail_count}")
        print(f"  ⚠️  警告: {self.warn_count}")
        print(f"  📊 总计: {self.pass_count + self.fail_count + self.warn_count}")
        return self.results

# ===================== 测试模块 =====================
runner = TestRunner()

def test_server_alive():
    """测试服务器是否可访问"""
    print("\n📡 [1] 服务器连通性测试")
    try:
        r = requests.get(f"{BASE_URL}/api/schema/", timeout=5)
        runner.log("服务器连通性", "PASS", f"服务器正常运行中", r)
    except requests.ConnectionError:
        runner.log("服务器连通性", "FAIL", "❌ 无法连接到 http://127.0.0.1:8000，请先启动 Django 服务器！")
        print("\n⛔ 服务器未启动，终止测试！")
        runner.summary()
        sys.exit(1)

def test_auth():
    """测试认证模块"""
    print("\n🔑 [2] 认证模块测试")

    # 2.1 未认证访问受保护接口
    try:
        r = requests.get(f"{BASE_URL}/api/basics/code/", timeout=5)
        if r.status_code == 401:
            runner.log("未认证返回 401", "PASS", "权限保护正常", r)
        else:
            runner.log("未认证返回 401", "WARN", f"期望 401，实际返回 {r.status_code}", r)
    except Exception as e:
        runner.log("未认证返回 401", "FAIL", str(e))

    # 2.2 错误密码登录
    try:
        r = runner.post("/api/auth/login/", {"username": TEST_USER, "password": "wrong_password_xyz"})
        if r.status_code in (400, 401):
            runner.log("错误密码拒绝登录", "PASS", "错误凭证被正确拒绝", r)
        else:
            runner.log("错误密码拒绝登录", "WARN", f"期望 400/401，实际 {r.status_code}", r)
    except Exception as e:
        runner.log("错误密码拒绝登录", "FAIL", str(e))

    # 2.3 正确登录
    try:
        r = runner.post("/api/auth/login/", {"username": TEST_USER, "password": TEST_PASS})
        if r.status_code == 200 and "access" in r.json():
            token = r.json()["access"]
            runner.set_auth(token)
            runner.log("正确账号登录", "PASS", f"获取 JWT Token 成功", r)
        else:
            runner.log("正确账号登录", "FAIL", f"登录失败: {r.text[:200]}", r)
            print("\n⚠️  登录失败，后续认证测试将跳过。请检查 TEST_USER 和 TEST_PASS 配置。")
    except Exception as e:
        runner.log("正确账号登录", "FAIL", str(e))

    # 2.4 获取用户信息
    try:
        r = runner.get("/api/auth/user/")
        if r.status_code == 200 and "username" in r.json():
            runner.log("获取用户信息", "PASS", f"用户名: {r.json().get('username')}", r)
        else:
            runner.log("获取用户信息", "FAIL", f"响应: {r.text[:200]}", r)
    except Exception as e:
        runner.log("获取用户信息", "FAIL", str(e))

    # 2.5 更新用户邮箱
    try:
        r = runner.put("/api/auth/profile/update/", {"email": "test_update@example.com"})
        if r.status_code == 200:
            runner.log("更新用户邮箱", "PASS", f"邮箱更新成功: {r.json().get('email')}", r)
        else:
            runner.log("更新用户邮箱", "FAIL", f"响应: {r.text[:200]}", r)
    except Exception as e:
        runner.log("更新用户邮箱", "FAIL", str(e))

    # 2.6 修改密码（改回来）
    try:
        r = runner.post("/api/auth/password/change/", {
            "old_password": TEST_PASS,
            "new_password": TEST_PASS  # 改回原密码
        })
        if r.status_code == 200:
            runner.log("修改密码接口", "PASS", "密码修改接口正常", r)
        else:
            runner.log("修改密码接口", "FAIL", f"响应: {r.text[:200]}", r)
    except Exception as e:
        runner.log("修改密码接口", "FAIL", str(e))

    # 2.7 Token 刷新
    try:
        r = runner.post("/api/auth/login/", {"username": TEST_USER, "password": TEST_PASS})
        if r.status_code == 200 and "refresh" in r.json():
            refresh = r.json()["refresh"]
            r2 = runner.post("/api/auth/refresh/", {"refresh": refresh})
            if r2.status_code == 200 and "access" in r2.json():
                runner.log("Token 刷新接口", "PASS", "Refresh Token 正常工作", r2)
            else:
                runner.log("Token 刷新接口", "FAIL", f"响应: {r2.text[:200]}", r2)
    except Exception as e:
        runner.log("Token 刷新接口", "FAIL", str(e))


def test_stock_codes():
    """测试股票代码接口"""
    print("\n📈 [3] 股票代码接口测试")

    # 3.1 获取股票列表
    try:
        r = runner.get("/api/basics/code/")
        if r.status_code == 200:
            data = r.json()
            count = data.get("count", len(data.get("results", [])))
            runner.log("获取股票列表", "PASS", f"共 {count} 条记录，返回分页正常", r)
        else:
            runner.log("获取股票列表", "FAIL", f"响应: {r.text[:200]}", r)
    except Exception as e:
        runner.log("获取股票列表", "FAIL", str(e))

    # 3.2 获取单只股票详情
    try:
        r = runner.get("/api/basics/code/000001.SZ/")
        if r.status_code == 200:
            data = r.json()
            runner.log("获取单股详情", "PASS", f"股票名称: {data.get('name')}", r)
        elif r.status_code == 404:
            runner.log("获取单股详情", "WARN", "000001.SZ 不在数据库中，可忽略", r)
        else:
            runner.log("获取单股详情", "FAIL", f"响应: {r.text[:200]}", r)
    except Exception as e:
        runner.log("获取单股详情", "FAIL", str(e))


def test_trading_calendar():
    """测试交易日历接口"""
    print("\n📅 [4] 交易日历接口测试")

    # 4.1 获取交易日历列表
    try:
        r = runner.get("/api/basics/trading-calendar/")
        if r.status_code == 200:
            count = r.json().get("count", 0)
            runner.log("交易日历列表", "PASS", f"共 {count} 条记录", r)
        else:
            runner.log("交易日历列表", "FAIL", f"响应: {r.text[:200]}", r)
    except Exception as e:
        runner.log("交易日历列表", "FAIL", str(e))

    # 4.2 检查某天是否为交易日
    try:
        r = runner.get("/api/basics/check-trading-day/?date=2026-03-31")
        if r.status_code == 200:
            is_trading = r.json().get("is_trading_day")
            runner.log("检查交易日 (2026-03-31)", "PASS", f"是否交易日: {is_trading}", r)
        else:
            runner.log("检查交易日", "FAIL", f"响应: {r.text[:200]}", r)
    except Exception as e:
        runner.log("检查交易日", "FAIL", str(e))


def test_policy_details():
    """测试策略详情接口"""
    print("\n🎯 [5] 策略详情接口测试")

    try:
        r = runner.get("/api/basics/policy-details/")
        if r.status_code == 200:
            count = r.json().get("count", 0)
            runner.log("策略详情列表", "PASS", f"共 {count} 条策略记录", r)
        else:
            runner.log("策略详情列表", "FAIL", f"响应: {r.text[:200]}", r)
    except Exception as e:
        runner.log("策略详情列表", "FAIL", str(e))


def test_strategy_stats():
    """测试策略统计接口"""
    print("\n📊 [6] 策略统计接口测试")

    try:
        r = runner.get("/api/basics/strategy-stats/")
        if r.status_code == 200:
            count = r.json().get("count", 0)
            runner.log("策略统计列表", "PASS", f"共 {count} 条统计记录", r)
        else:
            runner.log("策略统计列表", "FAIL", f"响应: {r.text[:200]}", r)
    except Exception as e:
        runner.log("策略统计列表", "FAIL", str(e))


def test_backtest():
    """测试回测模块接口"""
    print("\n🔬 [7] 回测模块接口测试")

    try:
        from backtest.urls import urlpatterns as bt_urls
        bt_paths = [str(u.pattern) for u in bt_urls]
        runner.log("回测路由加载", "PASS", f"共 {len(bt_paths)} 条路由: {bt_paths[:3]}...")
    except Exception as e:
        runner.log("回测路由加载", "FAIL", str(e))

    # 测试回测列表接口（不同项目路径可能不同）
    for path in ["/api/backtest/portfolios/", "/api/backtest/results/", "/api/backtest/"]:
        try:
            r = runner.get(path)
            if r.status_code in (200, 404):
                if r.status_code == 200:
                    runner.log(f"回测接口 {path}", "PASS", "接口正常响应", r)
                    break
        except Exception:
            pass


def test_api_docs():
    """测试 API 文档接口"""
    print("\n📚 [8] API 文档接口测试")

    for name, path in [("Swagger UI", "/api/docs/"), ("ReDoc", "/api/redoc/"), ("Schema", "/api/schema/")]:
        try:
            r = runner.get(path)
            if r.status_code == 200:
                runner.log(f"{name}", "PASS", f"文档页面正常加载", r)
            else:
                runner.log(f"{name}", "FAIL", f"状态码: {r.status_code}", r)
        except Exception as e:
            runner.log(f"{name}", "FAIL", str(e))


def test_database():
    """测试数据库连接"""
    print("\n🗄️  [9] 数据库连接测试")

    # 通过 Django ORM 测试 Oracle 连接
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vueStockapi.settings')
    try:
        django.setup()
        from django.db import connections, connection

        # Oracle
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM DUAL")
                result = cursor.fetchone()
                if result and result[0] == 1:
                    runner.log("Oracle 数据库连接", "PASS", "SELECT 1 FROM DUAL 查询成功")
        except Exception as e:
            runner.log("Oracle 数据库连接", "FAIL", str(e))

        # MySQL
        try:
            with connections['mysql'].cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                if result and result[0] == 1:
                    runner.log("MySQL 数据库连接", "PASS", "SELECT 1 查询成功")
        except Exception as e:
            runner.log("MySQL 数据库连接", "FAIL", str(e))

    except Exception as e:
        runner.log("Django ORM 初始化", "FAIL", str(e))


def test_security():
    """测试安全相关设置"""
    print("\n🔒 [10] 安全配置检查")

    # 检查管理员界面是否有保护
    try:
        r = requests.get(f"{BASE_URL}/admin/", timeout=5, allow_redirects=False)
        if r.status_code in (200, 302):
            runner.log("Admin 界面可访问", "WARN", "Admin 界面对外暴露，生产环境请限制访问", r)
        else:
            runner.log("Admin 界面访问", "PASS", f"状态码: {r.status_code}", r)
    except Exception as e:
        runner.log("Admin 界面安全检查", "FAIL", str(e))

    # 检查 CORS 配置（跨域请求）
    try:
        headers = {"Origin": "http://evil.com", "Content-Type": "application/json"}
        r = requests.options(f"{BASE_URL}/api/basics/code/", headers=headers, timeout=5)
        acao = r.headers.get("Access-Control-Allow-Origin", "")
        if acao == "*":
            runner.log("CORS 跨域限制", "FAIL", "⚠️ CORS 允许所有来源 (*)，存在安全风险！", r)
        elif acao == "http://evil.com":
            runner.log("CORS 跨域限制", "FAIL", "恶意来源被允许，CORS 配置有误！", r)
        else:
            runner.log("CORS 跨域限制", "PASS", f"恶意来源被拒绝，Access-Control-Allow-Origin: '{acao}'", r)
    except Exception as e:
        runner.log("CORS 安全检查", "FAIL", str(e))


# ===================== 执行所有测试 =====================
if __name__ == "__main__":
    print("=" * 60)
    print(f"  vueStockapi 项目 API 全面测试")
    print(f"  测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  目标地址: {BASE_URL}")
    print("=" * 60)

    # 先测试 Django ORM（不依赖 HTTP 服务）
    test_database()

    # 再测试 HTTP API
    test_server_alive()
    test_auth()
    test_stock_codes()
    test_trading_calendar()
    test_policy_details()
    test_strategy_stats()
    test_backtest()
    test_api_docs()
    test_security()

    results = runner.summary()
    print()

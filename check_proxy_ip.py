# -*- coding: UTF-8 -*-
'''
@Project ：vueStockapi 
@File ：check_proxy_ip.py
@Author ：Anita_熙烨（路虽远，行则降至！事虽难，做则必成！）
@Date ：2025/11/19 10:49 
@JianShu : 
'''
import urllib.request
import os

# 如果你需要显式设置代理（例如你的代理软件没有开启系统全局代理）
# 请取消下面两行的注释，并修改为你的代理地址
# os.environ["http_proxy"] = "http://127.0.0.1:7890"
# os.environ["https_proxy"] = "http://127.0.0.1:7890"

print("正在检测 Python 环境下的出口 IP...")

try:
    # 访问一个查看 IP 的服务
    with urllib.request.urlopen('https://ifconfig.me/ip', timeout=10) as response:
        ip = response.read().decode('utf-8').strip()
        print(f"✅ Oracle 看到的真实 IP 是: {ip}")
        print("请将此 IP 添加到 Oracle 数据库的访问控制列表(ACL)中。")
except Exception as e:
    print(f"❌ 检测失败: {e}")
    print("请检查你的代理配置是否允许 Python 访问外网。")
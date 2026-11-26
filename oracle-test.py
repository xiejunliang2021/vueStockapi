"""Oracle 直连测试（独立脚本，不走 Django）：.venv/bin/python oracle-test.py

原来这里复制了一份建池逻辑；现在只是 vueStockapi/oracle_config.py
的薄包装，连接参数只从 .env 读。Django ORM 那条路用 manage.py test_db。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vueStockapi.oracle_config import test_connection


def run_app():
    result = test_connection()
    if not result["ok"]:
        print("❌ --- Database connection failed! ---")
        print(f"Oracle error: {result['error']}")
        print("💡 检查 .env 里的 USER_ORACLE / PASSWORD_ORACLE / NAME_ORACLE / "
              "WALLET_DIRECTORY，以及钱包目录下的 tnsnames.ora。")
        return
    print("✅ --- Database connection successful! ---")
    print(f"Version: {result['version']}")
    print(f"Database: {result['db_name']}, Schema: {result['schema']}, "
          f"DB time: {result['db_time']}, took {result['elapsed']}s")


if __name__ == "__main__":
    run_app()

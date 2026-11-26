"""Oracle Autonomous DB 连接的唯一事实源头。

原来 Oracle 连接散在多处：vueStockapi/settings.py 里两份 DATABASES
（一份生效、一份注释掉的旧版）、manage.py / vueStockapi/__init__.py
里重复的 cx_Oracle 兼容垫片、根目录 oracle-test.py、两个管理命令
test_oracle.py / test_odb_tls.py（都把数据库密码硬编码在文件里，
且 DSN 一个写 medium、一个写 high，端口一个 1522、一个 1521）、
根目录 db_router.py（已删除：指向不存在的 mysql_db）、oracle/
tnsnames.ora 副本（与钱包里的不一致）。

现在统一规则：
- 连接参数只从服务器 .env 读，不在任何 .py 里写密码、写 DSN：
  USER_ORACLE / PASSWORD_ORACLE / NAME_ORACLE（TNS 别名，如 stockapi_high）
  / WALLET_DIRECTORY（钱包目录，含 tnsnames.ora；兼容旧名 WALLET_LOCATION）
  / WALLET_PEM_PASS_PHRASE。
- Django ORM 走 vueStockapi/settings.py 的 DATABASES['default']，
  其 OPTIONS 就是这里的 ORACLE_DJANGO_OPTIONS。
- 不走 Django 的直连（脚本、排障）走这里的 test_connection() /
  create_pool()，用 python-oracledb Thin 模式，不需要 Oracle Instant Client。
- 钱包：在用的是 /home/opc/oracle_wallet（stockapi_*）；
  vueStockapi/Wallet_Mhuabenwuxin 是旧库 mhuabenwuxin 的钱包，已不用，
  留在磁盘上不动。
- cx_Oracle 垫片仍留在 manage.py 和 vueStockapi/__init__.py（两个入口
  各需一份，Django 启动前就要生效，不宜再抽一层）。
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import oracledb

# 延迟优化（vue-notes → Oracle 迁移）：LOB 随行取数 + 客户端预取。
# 只推代码不设此默认值，ORDER BY + FETCH FIRST 优化无效（列表仍 10 秒级）。
# 作用于同一进程内所有 Oracle 连接（含 stockapi 'default' 库），预期无害或有益。
oracledb.defaults.fetch_lobs = False
oracledb.defaults.prefetchrows = 100

from decouple import config


def ensure_cx_oracle_alias() -> None:
    """让 Django 的 Oracle 后端（找 cx_Oracle）用上 oracledb。"""
    sys.modules.setdefault("cx_Oracle", oracledb)


def load_oracle_config() -> dict:
    """从 .env 读 Oracle 配置并校验，缺项 / 钱包不对时直接报清楚原因。"""
    user = config("USER_ORACLE", default="")
    password = config("PASSWORD_ORACLE", default="")
    tns_name = config("NAME_ORACLE", default="")
    wallet = config("WALLET_DIRECTORY", default="") or config(
        "WALLET_LOCATION", default=""
    )
    wallet_password = config("WALLET_PEM_PASS_PHRASE", default="")

    missing = [
        name
        for name, value in [
            ("USER_ORACLE", user),
            ("PASSWORD_ORACLE", password),
            ("NAME_ORACLE", tns_name),
            ("WALLET_DIRECTORY", wallet),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(f"Oracle 连接配置缺失，请检查 .env：{', '.join(missing)}")

    wallet_path = Path(wallet).expanduser()
    if not wallet_path.is_dir():
        raise RuntimeError(f"Oracle 钱包目录不存在：{wallet}")
    tns_file = wallet_path / "tnsnames.ora"
    if tns_file.is_file():
        aliases = re.findall(
            r"(?m)^\s*([A-Za-z0-9_]+)\s*=",
            tns_file.read_text(errors="ignore"),
        )
        if tns_name not in aliases:
            raise RuntimeError(
                f"TNS 别名 {tns_name} 不在 {tns_file} 里，现有别名："
                f"{', '.join(aliases)}"
            )

    return {
        "user": user,
        "password": password,
        "tns_name": tns_name,
        "wallet_directory": str(wallet_path),
        "wallet_password": wallet_password,
    }


# settings.py 在 import 时就会读一次，配置有问题启动即报错，别等到第一次查库。
ORACLE_CONFIG = load_oracle_config()

# 传给 Django Oracle 后端（进而传给 python-oracledb）的连接选项。
ORACLE_DJANGO_OPTIONS = {
    "retry_count": 3,
    "retry_delay": 1,
    "ssl_server_dn_match": True,
    "config_dir": ORACLE_CONFIG["wallet_directory"],
    "wallet_location": ORACLE_CONFIG["wallet_directory"],
    "wallet_password": ORACLE_CONFIG["wallet_password"],
}


def create_pool():
    """按 .env 建一个 oracledb 连接池（Thin 模式）。调用方负责 pool.close()。"""
    cfg = load_oracle_config()
    kwargs = {
        "user": cfg["user"],
        "password": cfg["password"],
        "dsn": cfg["tns_name"],
        "config_dir": cfg["wallet_directory"],
        "wallet_location": cfg["wallet_directory"],
        "min": 1,
        "max": 2,
    }
    if cfg["wallet_password"]:
        kwargs["wallet_password"] = cfg["wallet_password"]
    return oracledb.create_pool(**kwargs)


def test_connection() -> dict:
    """直连 Oracle 跑 SELECT 1 FROM DUAL + 版本 / 库名 / Schema，不走 Django。

    返回 dict：ok 时含 version / db_name / schema / elapsed；
    失败时 ok=False，error 里是 Oracle 报错原文。
    """
    cfg = load_oracle_config()
    started = time.time()
    try:
        pool = create_pool()
        try:
            with pool.acquire() as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1 FROM DUAL")
                    cursor.fetchone()
                    cursor.execute(
                        "SELECT BANNER FROM v$version WHERE banner LIKE 'Oracle%'"
                    )
                    version = cursor.fetchone()[0]
                    cursor.execute(
                        "SELECT SYS_CONTEXT('USERENV','DB_NAME'), "
                        "SYS_CONTEXT('USERENV','CURRENT_SCHEMA'), SYSDATE FROM DUAL"
                    )
                    db_name, schema, db_time = cursor.fetchone()
        finally:
            pool.close()
    except oracledb.Error as e:
        return {
            "ok": False,
            "tns_name": cfg["tns_name"],
            "user": cfg["user"],
            "wallet_directory": cfg["wallet_directory"],
            "elapsed": round(time.time() - started, 2),
            "error": str(e),
        }
    return {
        "ok": True,
        "tns_name": cfg["tns_name"],
        "user": cfg["user"],
        "wallet_directory": cfg["wallet_directory"],
        "version": version,
        "db_name": db_name,
        "schema": schema,
        "db_time": str(db_time),
        "elapsed": round(time.time() - started, 2),
    }

# ---------------------------------------------------------------------------
# xiansanzhenren（新库，Phoenix，vue-notes 迁移目标库）
# 与上面 stockapi 的 Oracle 配置完全同款模式：只读 .env 的 XSZR_*，
# 校验钱包目录与 TNS 别名在钱包 tnsnames.ora 里，Thin 模式。
# 凭据不进代码。settings.py 的 DATABASES['notes_oracle'] 用这里的
# XSZR_ORACLE_CONFIG / XSZR_ORACLE_DJANGO_OPTIONS。
# ---------------------------------------------------------------------------


def load_xszr_config() -> dict:
    """从 .env 读 xiansanzhenren 配置并校验，缺项 / 钱包不对时直接报清楚原因。"""
    user = config("XSZR_USER", default="")
    password = config("XSZR_PASSWORD", default="")
    tns_name = config("XSZR_TNS_NAME", default="")
    wallet = config("XSZR_WALLET_DIRECTORY", default="")
    wallet_password = config("XSZR_WALLET_PASSWORD", default="")

    missing = [
        name
        for name, value in [
            ("XSZR_USER", user),
            ("XSZR_PASSWORD", password),
            ("XSZR_TNS_NAME", tns_name),
            ("XSZR_WALLET_DIRECTORY", wallet),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(f"xiansanzhenren 连接配置缺失，请检查 .env：{', '.join(missing)}")

    wallet_path = Path(wallet).expanduser()
    if not wallet_path.is_dir():
        raise RuntimeError(f"xiansanzhenren 钱包目录不存在：{wallet}")
    tns_file = wallet_path / "tnsnames.ora"
    if tns_file.is_file():
        aliases = re.findall(
            r"(?m)^\s*([A-Za-z0-9_]+)\s*=",
            tns_file.read_text(errors="ignore"),
        )
        if tns_name not in aliases:
            raise RuntimeError(
                f"TNS 别名 {tns_name} 不在 {tns_file} 里，现有别名："
                f"{', '.join(aliases)}"
            )

    return {
        "user": user,
        "password": password,
        "tns_name": tns_name,
        "wallet_directory": str(wallet_path),
        "wallet_password": wallet_password,
    }


# settings.py 在 import 时就会读一次，配置有问题启动即报错，别等到第一次查库。
XSZR_ORACLE_CONFIG = load_xszr_config()

# 传给 Django Oracle 后端（进而传给 python-oracledb）的连接选项。
XSZR_ORACLE_DJANGO_OPTIONS = {
    "retry_count": 3,
    "retry_delay": 1,
    "ssl_server_dn_match": True,
    "config_dir": XSZR_ORACLE_CONFIG["wallet_directory"],
    "wallet_location": XSZR_ORACLE_CONFIG["wallet_directory"],
    "wallet_password": XSZR_ORACLE_CONFIG["wallet_password"],
}

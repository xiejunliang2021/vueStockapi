"""直连 Oracle 测试（不走 Django ORM）：python manage.py test_oracle

原来这个文件是 Oracle 官网示例的复制，把数据库密码硬编码在文件里，
DSN 也是写死的 medium；test_odb_tls.py 则是它的重复版（密码同样硬编码，
DSN 写 high、端口却写 1521）。两个都已按统一规则重写 / 删除：
现在只读 .env，连接逻辑只在 vueStockapi/oracle_config.py 里。

Django ORM 那条路用 test_db.py（SELECT BANNER / 会话信息）。
"""
from django.core.management.base import BaseCommand

from vueStockapi.oracle_config import test_connection


class Command(BaseCommand):
    help = "直连 Oracle 测试（python-oracledb Thin 模式，不走 Django ORM）"

    def handle(self, *args, **options):
        result = test_connection()
        if not result["ok"]:
            self.stderr.write(
                self.style.ERROR(
                    f"Oracle 直连失败（{result['tns_name']}，"
                    f"钱包：{result['wallet_directory']}）：{result['error']}"
                )
            )
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"Oracle 直连成功：{result['version']}，"
                f"库 {result['db_name']}，Schema {result['schema']}，"
                f"库时间 {result['db_time']}，耗时 {result['elapsed']} 秒"
            )
        )

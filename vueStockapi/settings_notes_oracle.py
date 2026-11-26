"""测试 / 迁移专用 settings：把 notes 应用路由到新 Oracle 库 notes_oracle。

用途：
- 第 3 步建表：``manage.py migrate --database=notes_oracle --settings=vueStockapi.settings_notes_oracle``
- 第 6 步跑测试服务器验证 notes 功能（同一模块）。

规则：
- DATABASES 与线上 ``vueStockapi/settings.py`` 完全一致（不改 'default' /
  'mysql'，只复用已注册的 'notes_oracle'）。
- 只覆盖 DATABASE_ROUTERS：notes 应用读写走 notes_oracle；其他应用保持
  线上路由（weighing / backtest / subscription 走 mysql，其余走 default）。
- 绝对不要把这个模块当线上 settings 用；绝对不要用它对 mysql 跑 migrate；
  迁移只允许 ``--database=notes_oracle``。
"""

from .settings import *  # noqa: F401,F403

from weighing.db_router import WeighingRouter

_PROD_ROUTER = WeighingRouter()


class NotesOracleRouter:
    """测试路由：notes -> notes_oracle，其余委托给线上 WeighingRouter。"""

    def db_for_read(self, model, **hints):
        if model._meta.app_label == "notes":
            return "notes_oracle"
        return _PROD_ROUTER.db_for_read(model, **hints)

    def db_for_write(self, model, **hints):
        if model._meta.app_label == "notes":
            return "notes_oracle"
        return _PROD_ROUTER.db_for_write(model, **hints)

    def allow_relation(self, obj1, obj2, **hints):
        if obj1._meta.app_label == "notes" or obj2._meta.app_label == "notes":
            # notes 的外键只指向 notes 自身，且都在 notes_oracle 内
            return obj1._meta.app_label == obj2._meta.app_label == "notes"
        return _PROD_ROUTER.allow_relation(obj1, obj2, **hints)

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == "notes":
            # notes 的迁移只在 notes_oracle 上执行，绝不在 mysql / default 上跑
            return db == "notes_oracle"
        return _PROD_ROUTER.allow_migrate(db, app_label, model_name=model_name, **hints)


DATABASE_ROUTERS = ["vueStockapi.settings_notes_oracle.NotesOracleRouter"]

# ---- 延迟优化试验 ①（仅测试配置，2026-11-26）----
# 驱动层参数：fetch_lobs=False（LOB 以 str/bytes 而非 LOB 对象返回）、
# prefetchrows=100（每批预取 100 行）、arraysize=100（与 Django 默认一致）。
import oracledb as _oracledb  # noqa: E402

_oracledb.defaults.fetch_lobs = False
_oracledb.defaults.prefetchrows = 100
_oracledb.defaults.arraysize = 100

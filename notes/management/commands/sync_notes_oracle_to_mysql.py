"""定时同步：notes 应用 Oracle notes_oracle -> MySQL(quant)，增量为主。

用法：
    .venv/bin/python manage.py sync_notes_oracle_to_mysql [--full] [--batch 200]

迁移第 8 步：Oracle 为主库，MySQL 长期保留作热备份。本命令每小时跑一次
（cron，正式切换时再启用），只做 Oracle -> MySQL 的单向同步。
- 方向固定 Oracle -> MySQL；读 .using('notes_oracle')，写 .using('mysql')，
  不依赖路由器，不改路由、不重载服务。
- 增量：只同步 Oracle 侧自上次同步以来新增/修改的行（用 updated_at 判断；
  上次同步时间存在状态文件里）。FieldOption 没有 updated_at，每次全量比对
  （只有几十行，便宜）。
- 删除：MySQL 里有、Oracle 里没有的行按主键删除（只删 notes 四张表）。
  安全阀：某表 Oracle 侧读到 0 行而 MySQL 侧有行时，整轮中止、不删不写，
  防止源库读取异常时误删热备份。
- 按主键幂等 upsert，重复跑不产生重复行；顺序与搬运一致：
  NoteType -> FieldOption -> FieldDefinition -> Note。已存在的行先逐字段比对
  （'' 与 NULL 视为等价，因 Oracle 把 '' 存为 NULL），值相同则跳过不写，
  只有真正变化的行才 UPDATE，因此重复跑的“更新”计数为 0，幂等可验证。
- 时间戳：created_at/updated_at 写回源值（update() 路径本身不触发 auto_now；
  INSERT 后立即用 QuerySet.update() 写回，与搬运命令同款做法）。
- 每次同步后核对四张表行数，不一致打印告警并以非零退出码退出；状态文件只在
  成功跑完后更新。
- --full：忽略状态文件，全表按主键 upsert + 删除多余行。
"""
import json
import os
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from notes.models import FieldDefinition, FieldOption, Note, NoteType

SOURCE_DB = "notes_oracle"
TARGET_DB = "mysql"
STATE_FILE = "/home/opc/vueStockapi/notes_sync_state.json"
MODELS_IN_ORDER = (NoteType, FieldOption, FieldDefinition, Note)
TIMESTAMP_FIELDS = ("created_at", "updated_at")
# 增量读取的重叠窗口：防时钟偏差/边界行漏读，upsert 幂等所以重读无害。
OVERLAP = timedelta(minutes=5)


def _row_values(obj):
    """取出一行全部具体字段（除主键外），外键用 attname（如 note_type_id）。"""
    values = {}
    for field in obj._meta.concrete_fields:
        if field.primary_key:
            continue
        values[field.get_attname()] = getattr(obj, field.get_attname())
    return values


def _has_updated_at(model):
    return any(f.name == "updated_at" for f in model._meta.concrete_fields)


def _load_state():
    if not os.path.exists(STATE_FILE):
        return None
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_state(last_sync, counts):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(
            {"last_sync": last_sync.isoformat(), "counts": counts},
            f,
            ensure_ascii=False,
            indent=2,
        )
        f.write("\n")
    os.replace(tmp, STATE_FILE)


def _values_equal(src_values, tgt_values):
    """逐字段比对：'' 与 None 视为等价（Oracle 把 '' 存为 NULL）。"""
    for key, src_v in src_values.items():
        tgt_v = tgt_values.get(key)
        if src_v == tgt_v:
            continue
        if src_v in (None, "") and tgt_v in (None, ""):
            continue
        return False
    return True


class Command(BaseCommand):
    help = "定时同步 notes 数据：Oracle notes_oracle -> MySQL(quant)（增量 + 删除，幂等）"

    def add_arguments(self, parser):
        parser.add_argument("--full", action="store_true", help="强制全量同步（忽略状态文件）")
        parser.add_argument("--batch", type=int, default=200, help="每批处理行数（默认 200）")

    def _upsert_batch(self, model, batch, target_ids, counts):
        """一批源行按主键 upsert 到 MySQL；counts 为 [created, updated]。

        已存在的行先比对值，相同则跳过（不写），只有真正变化的行才 UPDATE，
        因此重复跑时 updated 计数为 0。
        """
        if not batch:
            return
        created, updated = counts
        with transaction.atomic(using=TARGET_DB):
            for src in batch:
                defaults = _row_values(src)
                if src.pk in target_ids:
                    existing = (
                        model.objects.using(TARGET_DB)
                        .filter(pk=src.pk)
                        .values(*defaults.keys())
                        .first()
                    )
                    if existing is not None and _values_equal(defaults, existing):
                        continue
                    model.objects.using(TARGET_DB).filter(pk=src.pk).update(**defaults)
                    updated += 1
                else:
                    obj = model(id=src.pk, **defaults)
                    obj.save(force_insert=True, using=TARGET_DB)
                    # save() 会把 auto_now_add/auto_now 写成当前时间，写回源值
                    ts = {k: defaults[k] for k in TIMESTAMP_FIELDS if k in defaults}
                    if ts:
                        model.objects.using(TARGET_DB).filter(pk=src.pk).update(**ts)
                    target_ids.add(src.pk)
                    created += 1
        counts[0], counts[1] = created, updated

    def handle(self, *args, **options):
        full = options["full"]
        batch_size = options["batch"]
        run_start = timezone.now()

        if full:
            self.stdout.write("全量模式：忽略状态文件")
            last_sync = None
        else:
            state = _load_state()
            if state and state.get("last_sync"):
                last_sync = parse_datetime(state["last_sync"])
                self.stdout.write(f"增量模式：上次同步 {state['last_sync']}")
            else:
                self.stdout.write("无状态文件：首次运行，本次做全量核对")
                last_sync = None

        summary = {}
        for model in MODELS_IN_ORDER:
            name = model._meta.model_name
            source_qs = model.objects.using(SOURCE_DB).order_by("id")
            if last_sync is not None and _has_updated_at(model):
                # 增量：只读上次同步以来改动过的行（留 5 分钟重叠防漏读）
                source_qs = source_qs.filter(updated_at__gt=last_sync - OVERLAP)
            oracle_total = model.objects.using(SOURCE_DB).count()
            mysql_total_before = model.objects.using(TARGET_DB).count()

            # 安全阀：源库读到 0 行而目标有行，说明源库读取异常，整轮中止
            if oracle_total == 0 and mysql_total_before > 0:
                raise CommandError(
                    f"{name}: Oracle 侧 0 行但 MySQL 侧 {mysql_total_before} 行，"
                    "疑似源库读取异常，已中止同步（未删未写）"
                )

            target_ids = set(model.objects.using(TARGET_DB).values_list("id", flat=True))
            counts = [0, 0]  # created, updated
            batch = []
            for src in source_qs.iterator(chunk_size=batch_size):
                batch.append(src)
                if len(batch) >= batch_size:
                    self._upsert_batch(model, batch, target_ids, counts)
                    batch = []
            self._upsert_batch(model, batch, target_ids, counts)

            # 删除：MySQL 里有、Oracle 里没有的行（按主键比对）
            # 核对用的 Oracle id 集在这里重新取（新鲜值），不用本轮开始时
            # 的 oracle_total：并发写入时旧快照会让行数核对误报。
            oracle_ids = set(model.objects.using(SOURCE_DB).values_list("id", flat=True))
            stale_ids = sorted(target_ids - oracle_ids)
            deleted = 0
            if stale_ids:
                with transaction.atomic(using=TARGET_DB):
                    deleted, _ = (
                        model.objects.using(TARGET_DB).filter(pk__in=stale_ids).delete()
                    )
            mysql_ids = set(model.objects.using(TARGET_DB).values_list("id", flat=True))
            summary[name] = {
                "created": counts[0],
                "updated": counts[1],
                "deleted": deleted,
                "oracle": len(oracle_ids),
                "mysql": len(mysql_ids),
                "oracle_ids": oracle_ids,
                "mysql_ids": mysql_ids,
            }
            self.stdout.write(
                f"{name}: 新增 {counts[0]}，更新 {counts[1]}，删除 {deleted}；"
                f"Oracle {oracle_total} 行，MySQL {summary[name]['mysql']} 行"
            )

        # 行数核对（按主键 id 集比对，比单纯计数更严：能发现多行少行之外的错位）
        mismatches = []
        for k, v in summary.items():
            if v["oracle_ids"] != v["mysql_ids"]:
                only_o = sorted(v["oracle_ids"] - v["mysql_ids"])
                only_m = sorted(v["mysql_ids"] - v["oracle_ids"])
                mismatches.append(
                    f"{k} Oracle {v['oracle']} != MySQL {v['mysql']}"
                    f"（仅 Oracle 有：{only_o}；仅 MySQL 有：{only_m}）"
                )
        if mismatches:
            self.stderr.write(self.style.ERROR("行数核对不一致：" + "；".join(mismatches)))
            self.stderr.write(self.style.ERROR("状态文件未更新，请检查后重跑"))
            raise SystemExit(1)

        # 成功才更新状态文件：记本次开始时间（下次增量用重叠窗口兜底）
        counts_only = {
            k: {"created": v["created"], "updated": v["updated"], "deleted": v["deleted"]}
            for k, v in summary.items()
        }
        _save_state(run_start, counts_only)
        self.stdout.write(
            self.style.SUCCESS(
                "同步完成，行数核对一致："
                + "；".join(f"{k} {v['oracle']} 行" for k, v in summary.items())
                + f"；状态文件已更新（last_sync={run_start.isoformat()}）"
            )
        )

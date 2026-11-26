"""一次性搬运：notes 应用 MySQL(quant) -> Oracle notes_oracle。

用法：
    .venv/bin/python manage.py copy_notes_to_oracle [--batch 200]

只做迁移第 5 步：搬数据，不改路由、不重载服务、不写 MySQL。
- 顺序：NoteType -> FieldOption -> FieldDefinition（外键 NoteType）
  -> Note（外键 NoteType）。
- 显式保留原主键；可重复执行：已存在按主键 UPDATE，不存在 INSERT，
  不产生重复行。
- 读 .using('mysql')，写 .using('notes_oracle')，不依赖路由器。
- 时间戳注意：created_at(auto_now_add) / updated_at(auto_now) 会被
  save() 改写为当前时间，因此 INSERT 后立即用 QuerySet.update()
  把两列写回源值；UPDATE 路径本身不触发 auto_now，直接写源值。
- Oracle 把 '' 存为 NULL：CharField/TextField 的 '' 与 NULL 在核对时
  视为等价，这里不做特殊转换，按 Django 惯例写入即可。
- JSON 字段直接写 Python 值（标量与容器都不包装），由 JSONField 序列化。
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from notes.models import FieldDefinition, FieldOption, Note, NoteType

SOURCE_DB = "mysql"
TARGET_DB = "notes_oracle"

MODELS_IN_ORDER = (NoteType, FieldOption, FieldDefinition, Note)
TIMESTAMP_FIELDS = ("created_at", "updated_at")


def _row_values(obj):
    """取出一行全部具体字段（除主键外），外键用 attname（如 note_type_id）。"""
    values = {}
    for field in obj._meta.concrete_fields:
        if field.primary_key:
            continue
        values[field.get_attname()] = getattr(obj, field.get_attname())
    return values


class Command(BaseCommand):
    help = "一次性搬运 notes 数据：MySQL(quant) -> Oracle notes_oracle（按主键 upsert，可重复执行）"

    def add_arguments(self, parser):
        parser.add_argument("--batch", type=int, default=200, help="每批处理行数（默认 200）")

    def _flush(self, model, batch, target_ids, counts):
        if not batch:
            return
        created, updated = counts
        with transaction.atomic(using=TARGET_DB):
            for src in batch:
                defaults = _row_values(src)
                if src.pk in target_ids:
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
        batch_size = options["batch"]
        summary = {}
        for model in MODELS_IN_ORDER:
            name = model._meta.model_name
            source_qs = model.objects.using(SOURCE_DB).order_by("id")
            source_count = source_qs.count()
            target_ids = set(model.objects.using(TARGET_DB).values_list("id", flat=True))
            counts = [0, 0]  # created, updated
            batch = []
            done = 0
            for src in source_qs.iterator(chunk_size=batch_size):
                batch.append(src)
                if len(batch) >= batch_size:
                    self._flush(model, batch, target_ids, counts)
                    batch = []
                    done = counts[0] + counts[1]
                    self.stdout.write(f"  {name}: 已处理 {done}/{source_count}（新增 {counts[0]}，更新 {counts[1]}）")
            self._flush(model, batch, target_ids, counts)
            done = counts[0] + counts[1]
            summary[name] = (counts[0], counts[1], source_count)
            self.stdout.write(
                self.style.SUCCESS(f"{name}: 完成，源 {source_count} 行，新增 {counts[0]}，更新 {counts[1]}")
            )
        self.stdout.write(
            self.style.SUCCESS(
                "搬运完成：" + "；".join(
                    f"{k} 新增 {v[0]} 更新 {v[1]} / 源 {v[2]}" for k, v in summary.items()
                )
            )
        )

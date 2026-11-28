from django.db import models


class OracleTolerantJSONField(models.JSONField):
    """JSONField：兼容 Oracle 读路径（只改读，不改写、不改列类型、不产生迁移）。

    实测（Oracle 26ai + python-oracledb 2.5.1，NCLOB + IS JSON 列）：
    - 写入没问题：顶层原始值（字符串 'Google'、布尔 True）与对象/数组都能存。
    - 读出时驱动层已经把对象/数组解成了 dict/list，顶层原始值仍是 str。
      Django 4.2 的 JSONField.from_db_value() 假定读到的总是 str，直接
      json.loads(value)，只捕 JSONDecodeError；值已是 dict/list 时就抛
      TypeError: the JSON object must be str, bytes or bytearray, not list
      ——于是 Oracle 上任何含 JSON 对象/数组的行都读不出来。
    这里只放宽读路径：非 str（已解码好的 dict/list/bool/数字）原样返回，
    str 才走父类的 json.loads。写路径（get_db_prep_value）与列类型完全
    继承内置 JSONField；deconstruct() 也返回内置 JSONField 路径，因此
    makemigrations 无变化、不产生新迁移，MySQL 侧零影响（旧形状裸原始值
    与新数据在 MySQL 上的读写与改动前完全一致）。
    """

    def from_db_value(self, value, expression, connection):
        if value is None or not isinstance(value, str):
            # 驱动已解码好的 dict/list/bool/数字：原样返回，不再 json.loads。
            return value
        return super().from_db_value(value, expression, connection)

    def deconstruct(self):
        # 与内置 JSONField 同构：不产生迁移，迁移状态仍与 0001/0003/0005 一致。
        name, path, args, kwargs = super().deconstruct()
        return name, "django.db.models.JSONField", args, kwargs


class NoteType(models.Model):
    """笔记类型，如：网站注册。字段模板挂在类型下，新增类型不用改代码。"""

    name = models.CharField(max_length=50, unique=True, verbose_name="类型名称")
    slug = models.SlugField(max_length=50, unique=True, verbose_name="标识")
    description = models.CharField(max_length=200, blank=True, verbose_name="说明")
    icon = models.CharField(max_length=10, blank=True, verbose_name="图标")
    order = models.PositiveIntegerField(default=0, verbose_name="排序")
    is_active = models.BooleanField(default=True, verbose_name="是否启用")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "笔记类型"
        verbose_name_plural = "笔记类型"
        ordering = ["order", "id"]

    def __str__(self):
        return self.name


class FieldDefinition(models.Model):
    """字段定义：挂在笔记类型下的结构化字段模板。"""

    FIELD_TYPES = [
        ("text", "单行文本"),
        ("textarea", "多行文本"),
        ("email", "邮箱"),
        ("datetime", "日期时间"),
        ("boolean", "是/否"),
        ("select", "下拉选择"),
        ("multiselect", "多选下拉"),
        ("steps", "步骤列表"),
    ]

    note_type = models.ForeignKey(
        NoteType, on_delete=models.CASCADE, related_name="fields", verbose_name="所属类型"
    )
    key = models.SlugField(max_length=50, verbose_name="字段标识")
    label = models.CharField(max_length=50, verbose_name="字段名称")
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, verbose_name="字段类型")
    required = models.BooleanField(default=False, verbose_name="是否必填")
    # 默认值按字段类型解释：boolean 用 "true"/"false"；datetime 用 "__now__" 表示当前时间
    default_value = models.TextField(blank=True, null=True, verbose_name="默认值")
    options = OracleTolerantJSONField(default=list, blank=True, verbose_name="下拉选项")
    # 选项组：设置后，下拉选项从 FieldOption 表（key=option_group）实时取，不用内联 options
    option_group = models.CharField(max_length=50, blank=True, null=True, verbose_name="选项组")
    # 排除的选项值：下拉候选里去掉这些值（比如关联平台不列出 Google 自身）
    exclude_option_values = OracleTolerantJSONField(default=list, blank=True, verbose_name="排除的选项值")
    # 条件显示：仅当 show_when_key 对应字段的值等于 show_when_value 时才显示本字段
    show_when_key = models.CharField(max_length=50, blank=True, null=True, verbose_name="条件字段标识")
    show_when_value = OracleTolerantJSONField(blank=True, null=True, verbose_name="条件字段取值")
    # 条件取反：为 True 时，条件字段值不等于 show_when_value 才显示（比如配置只在平台≠Google 时显示）
    show_when_negate = models.BooleanField(default=False, verbose_name="条件取反")
    help_text = models.CharField(max_length=200, blank=True, verbose_name="帮助提示")
    order = models.PositiveIntegerField(default=0, verbose_name="排序")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "字段定义"
        verbose_name_plural = "字段定义"
        unique_together = [("note_type", "key")]
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.note_type.name} - {self.label}"

    def is_visible(self, field_values):
        """按条件显示：无条件则始终显示；否则按条件字段值与设定值是否相等决定，取反时反过来。"""
        if not self.show_when_key:
            return True
        matches = field_values.get(self.show_when_key) == self.show_when_value
        return (not matches) if self.show_when_negate else matches

    def resolved_options(self):
        """下拉候选：配了 option_group 就从 FieldOption 表实时取；否则用内联 options。

        统一返回 [{"value": ..., "label": ...}]，内联选项可能是字符串或 {value, label}。
        exclude_option_values 里列出的值会被去掉（比如关联平台不列出 Google 自身）。
        """
        if self.option_group:
            out = [
                {"value": o.value, "label": o.label or o.value}
                for o in FieldOption.objects.filter(key=self.option_group)
            ]
        else:
            out = []
            for item in self.options or []:
                if isinstance(item, dict):
                    out.append({"value": item.get("value"), "label": item.get("label") or item.get("value")})
                else:
                    out.append({"value": item, "label": item})
        excluded = set(self.exclude_option_values or [])
        if excluded:
            out = [o for o in out if o["value"] not in excluded]
        return out

    def allowed_values(self):
        """下拉合法取值（校验用）。"""
        return [o["value"] for o in self.resolved_options()]


class FieldOption(models.Model):
    """下拉选项：按 key 分组（如 platform / email / 2fa_method），用户在页面上自行增删。"""

    key = models.CharField(max_length=50, db_index=True, verbose_name="选项组键")
    value = models.CharField(max_length=100, verbose_name="选项值")
    label = models.CharField(max_length=100, blank=True, verbose_name="显示名称")
    sort_order = models.PositiveIntegerField(default=0, verbose_name="排序")

    class Meta:
        verbose_name = "下拉选项"
        verbose_name_plural = "下拉选项"
        unique_together = [("key", "value")]
        ordering = ["sort_order", "id"]

    def save(self, *args, **kwargs):
        if not self.label:
            self.label = self.value
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.key}: {self.label or self.value}"


class Note(models.Model):
    """一篇笔记：结构化字段值（JSON）+ Markdown 正文。"""

    note_type = models.ForeignKey(
        NoteType, on_delete=models.PROTECT, related_name="notes", verbose_name="笔记类型"
    )
    field_values = OracleTolerantJSONField(default=dict, blank=True, verbose_name="结构化字段值")
    # 自定义字段：{key: {"label": 名称, "type": 类型, "value": 值}}，用户在页面上自行添加
    custom_fields = OracleTolerantJSONField(default=dict, blank=True, verbose_name="自定义字段")
    content = models.TextField(blank=True, verbose_name="Markdown 正文")
    folder = models.CharField(max_length=100, blank=True, db_index=True, verbose_name="文件夹")
    tags = OracleTolerantJSONField(default=list, blank=True, verbose_name="标签")
    is_pinned = models.BooleanField(default=False, verbose_name="是否置顶")
    is_archived = models.BooleanField(default=False, verbose_name="是否归档")
    created_by = models.CharField(max_length=150, blank=True, verbose_name="创建人")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        verbose_name = "笔记"
        verbose_name_plural = "笔记"
        ordering = ["-is_pinned", "-updated_at"]
        indexes = [
            models.Index(fields=["note_type", "-updated_at"], name="notes_type_updated_idx"),
        ]

    def __str__(self):
        # 无标题字段：用类型名 + 主键标识
        return f"{self.note_type.name} #{self.pk}"


# ---------------------------------------------------------------------------
# note-types 元数据缓存失效信号
# 覆盖 Admin 与 API 所有写路径（NoteType / FieldDefinition / FieldOption
# 的新增、修改、删除均通过 post_save / post_delete 失效缓存）。
# 注意：QuerySet.update() / bulk_create 不触发信号，如有此类写入路径
# 需手动调用 cache.delete(NOTE_TYPES_LIST_CACHE_KEY)。
# ---------------------------------------------------------------------------
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save

NOTE_TYPES_LIST_CACHE_KEY = "notes:note_types_list"


def invalidate_note_types_cache(sender, **kwargs):
    cache.delete(NOTE_TYPES_LIST_CACHE_KEY)


post_save.connect(invalidate_note_types_cache, sender=NoteType)
post_delete.connect(invalidate_note_types_cache, sender=NoteType)
post_save.connect(invalidate_note_types_cache, sender=FieldDefinition)
post_delete.connect(invalidate_note_types_cache, sender=FieldDefinition)
post_save.connect(invalidate_note_types_cache, sender=FieldOption)
post_delete.connect(invalidate_note_types_cache, sender=FieldOption)

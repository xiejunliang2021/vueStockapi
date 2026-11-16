from django.db import models


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
    options = models.JSONField(default=list, blank=True, verbose_name="下拉选项")
    # 选项组：设置后，下拉选项从 FieldOption 表（key=option_group）实时取，不用内联 options
    option_group = models.CharField(max_length=50, blank=True, null=True, verbose_name="选项组")
    # 条件显示：仅当 show_when_key 对应字段的值等于 show_when_value 时才显示本字段
    show_when_key = models.CharField(max_length=50, blank=True, null=True, verbose_name="条件字段标识")
    show_when_value = models.JSONField(blank=True, null=True, verbose_name="条件字段取值")
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
        """按条件显示：无条件则始终显示；否则当条件字段值等于设定值时显示。"""
        if not self.show_when_key:
            return True
        return field_values.get(self.show_when_key) == self.show_when_value

    def resolved_options(self):
        """下拉候选：配了 option_group 就从 FieldOption 表实时取；否则用内联 options。

        统一返回 [{"value": ..., "label": ...}]，内联选项可能是字符串或 {value, label}。
        """
        if self.option_group:
            return [
                {"value": o.value, "label": o.label or o.value}
                for o in FieldOption.objects.filter(key=self.option_group)
            ]
        out = []
        for item in self.options or []:
            if isinstance(item, dict):
                out.append({"value": item.get("value"), "label": item.get("label") or item.get("value")})
            else:
                out.append({"value": item, "label": item})
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
    field_values = models.JSONField(default=dict, blank=True, verbose_name="结构化字段值")
    # 自定义字段：{key: {"label": 名称, "type": 类型, "value": 值}}，用户在页面上自行添加
    custom_fields = models.JSONField(default=dict, blank=True, verbose_name="自定义字段")
    content = models.TextField(blank=True, verbose_name="Markdown 正文")
    folder = models.CharField(max_length=100, blank=True, db_index=True, verbose_name="文件夹")
    tags = models.JSONField(default=list, blank=True, verbose_name="标签")
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

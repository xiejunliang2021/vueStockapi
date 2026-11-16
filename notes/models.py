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


class Note(models.Model):
    """一篇笔记：结构化字段值（JSON）+ Markdown 正文。"""

    note_type = models.ForeignKey(
        NoteType, on_delete=models.PROTECT, related_name="notes", verbose_name="笔记类型"
    )
    title = models.CharField(max_length=200, verbose_name="标题", db_index=True)
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
        return self.title

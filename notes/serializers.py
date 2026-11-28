from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.utils import timezone
from rest_framework import serializers

from .models import FieldDefinition, FieldOption, Note, NoteType


class FieldOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FieldOption
        fields = "__all__"
        read_only_fields = ["id"]


class FieldDefinitionSerializer(serializers.ModelSerializer):
    resolved_options = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = FieldDefinition
        fields = [
            "id",
            "note_type",
            "key",
            "label",
            "field_type",
            "required",
            "default_value",
            "options",
            "option_group",
            "exclude_option_values",
            "show_when_key",
            "show_when_value",
            "show_when_negate",
            "help_text",
            "order",
            "resolved_options",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        # 嵌套路由创建时 note_type 由 URL 提供，不用前端传
        extra_kwargs = {"note_type": {"required": False}}

    def get_resolved_options(self, obj):
        # 修复 ③：上下文里有一次取全的选项表时直接用它，不再逐字段定义查库；
        # 上下文缺失时回退到逐条查询，行为与之前完全一致（含排除项过滤与排序）。
        options_map = self.context.get("field_options_map")
        if options_map is not None and obj.option_group:
            out = list(options_map.get(obj.option_group, []))
            excluded = set(obj.exclude_option_values or [])
            if excluded:
                out = [o for o in out if o["value"] not in excluded]
            return out
        return obj.resolved_options()

    def validate(self, attrs):
        field_type = attrs.get("field_type", getattr(self.instance, "field_type", None))
        options = attrs.get("options", getattr(self.instance, "options", []))
        option_group = attrs.get("option_group", getattr(self.instance, "option_group", None))
        if field_type in ("select", "multiselect") and not options and not option_group:
            raise serializers.ValidationError({"options": "下拉类型必须提供候选选项或选项组"})
        show_when_key = attrs.get("show_when_key", getattr(self.instance, "show_when_key", None))
        note_type = self.context.get("note_type") or attrs.get("note_type")
        if not note_type and self.instance:
            note_type = self.instance.note_type
        if show_when_key and note_type:
            exists = (
                FieldDefinition.objects.filter(note_type=note_type, key=show_when_key)
                .exclude(pk=getattr(self.instance, "pk", None))
                .exists()
            )
            if not exists:
                raise serializers.ValidationError(
                    {"show_when_key": f"同类型下没有标识为 {show_when_key} 的字段"}
                )
        return attrs


class NoteTypeSerializer(serializers.ModelSerializer):
    fields = FieldDefinitionSerializer(many=True, read_only=True)
    notes_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = NoteType
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "icon",
            "order",
            "is_active",
            "fields",
            "notes_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


def _coerce_default(field_def):
    """把字段定义的默认值转成对应类型的值；无默认值返回 None。"""
    raw = field_def.default_value
    if raw is None or raw == "":
        return None
    if field_def.field_type == "boolean":
        return str(raw).strip().lower() in ("true", "1", "yes", "是")
    if field_def.field_type == "datetime" and raw == "__now__":
        return timezone.now()
    return raw


def _ensure_options(field_def, values, options_cache=None):
    """下拉新值自动建选项：提交的值不在选项组里时，把它加进 FieldOption 表。

    这样表单上下拉框可以直接输入新值（比如新建 Google 账号时输入新邮箱），
    下次下拉里就有它了。只对配了 option_group 的字段生效。
    如果提供了 options_cache，优先使用并在新建后同步更新，避免重复查库。
    """
    grp = field_def.option_group
    if not grp:
        return
    if options_cache is not None and grp in options_cache:
        existing = {opt.value for opt in options_cache[grp]}
    else:
        existing = set(
            FieldOption.objects.filter(key=grp).values_list("value", flat=True)
        )
    for v in values:
        if not isinstance(v, str) or not v.strip() or v in existing:
            continue
        if options_cache is not None and grp in options_cache and options_cache[grp]:
            last_order = max(opt.sort_order for opt in options_cache[grp])
            new_order = last_order + 1
        else:
            last = (
                FieldOption.objects.filter(key=grp)
                .order_by("-sort_order")
                .first()
            )
            new_order = (last.sort_order + 1) if last else 0
        new_opt = FieldOption.objects.create(
            key=grp,
            value=v,
            label=v,
            sort_order=new_order,
        )
        existing.add(v)
        if options_cache is not None and grp in options_cache:
            options_cache[grp].append(new_opt)


def _get_allowed_values(field_def, options_cache=None):
    """获取下拉字段的合法候选值。

    若提供了 options_cache 且字段配了 option_group，直接基于内存列表计算，
    不再查库；同样正确应用 exclude_option_values 排除。
    """
    grp = field_def.option_group
    if grp and options_cache is not None and grp in options_cache:
        out = [opt.value for opt in options_cache[grp]]
        excluded = set(field_def.exclude_option_values or [])
        if excluded:
            out = [v for v in out if v not in excluded]
        return out
    return field_def.allowed_values()


def validate_field_values(note_type, field_values):
    """按类型模板校验结构化字段值，返回清洗后的 dict；不合法抛 ValidationError。

    规则：必填不能为空；邮箱要合格式；下拉要在候选值内（新值先自动建进选项组）；
    条件隐藏的字段值直接丢弃；模板之外的 key 直接丢弃（防脏数据）。
    """
    if not isinstance(field_values, dict):
        raise serializers.ValidationError({"field_values": "结构化字段值必须是对象"})
    # Oracle 上 JSON/LOB 列的取回需要 ORDER BY + FETCH FIRST（Top-N 查询随行预取
    # LOB）：不带 limit 的查询每个 JSON 值多一次 Phoenix 往返，16 个字段定义约 7.3 秒。
    # limit 1000 远大于实际字段数，不会截断；顺序与模型 Meta ordering 一致，返回结构不变。
    defs = {f.key: f for f in note_type.fields.all().order_by("order", "id")[:1000]}

    # 优化 ①：一次性拉取该类型下所有 select/multiselect 字段涉及的选项组，
    # 避免每个字段在 _ensure_options 和 allowed_values 两个阶段反复查库。
    # 节省的查询数 = 下拉字段数 × 2 次往返（原 _ensure_options 一次、allowed_values 一次）。
    needed_groups = {
        f.option_group
        for f in defs.values()
        if f.field_type in ("select", "multiselect") and f.option_group
    }
    options_cache: dict = {}
    if needed_groups:
        for opt in FieldOption.objects.filter(key__in=needed_groups).order_by("sort_order", "id"):
            options_cache.setdefault(opt.key, []).append(opt)
        # 确保每个组的 key 都存在（即使该组当前没有选项也要有空列表）
        for grp in needed_groups:
            options_cache.setdefault(grp, [])

    errors = {}
    cleaned = {}
    for key, f in defs.items():
        value = field_values.get(key)
        # 未提供时填默认值
        if value is None or value == "":
            default = _coerce_default(f)
            if default is not None:
                value = default
        # 条件隐藏的字段：值直接丢弃
        if not f.is_visible({**field_values, **cleaned}):
            continue
        if f.required and (value is None or value == "" or value == []):
            errors[key] = f"{f.label}是必填项"
            continue
        if value is None or value == "":
            continue
        if f.field_type == "email":
            try:
                validate_email(value)
            except DjangoValidationError:
                errors[key] = f"{f.label}邮箱格式不正确"
                continue
        elif f.field_type == "boolean":
            if not isinstance(value, bool):
                errors[key] = f"{f.label}必须是是/否"
                continue
        elif f.field_type == "select":
            _ensure_options(f, [value], options_cache=options_cache)
            if value not in _get_allowed_values(f, options_cache=options_cache):
                errors[key] = f"{f.label}必须是候选选项之一"
                continue
        elif f.field_type == "multiselect":
            if not isinstance(value, list):
                errors[key] = f"{f.label}必须是选项数组"
                continue
            _ensure_options(f, value, options_cache=options_cache)
            allowed = _get_allowed_values(f, options_cache=options_cache)
            if any(item not in allowed for item in value):
                errors[key] = f"{f.label}只能选候选选项里的值"
                continue
        elif f.field_type == "steps":
            # 步骤列表：[{text: 字符串, image: 图片 URL 或 null}]，空列表合法
            if not isinstance(value, list):
                errors[key] = f"{f.label}必须是步骤数组"
                continue
            steps_ok = True
            for item in value:
                if not isinstance(item, dict):
                    errors[key] = f"{f.label}每一步都必须是对象"
                    steps_ok = False
                    break
                if not isinstance(item.get("text", ""), str):
                    errors[key] = f"{f.label}每一步的文字必须是字符串"
                    steps_ok = False
                    break
                image = item.get("image")
                if image is not None and not isinstance(image, str):
                    errors[key] = f"{f.label}每一步的图片必须是 URL 字符串"
                    steps_ok = False
                    break
            if not steps_ok:
                continue
        elif f.field_type == "datetime":
            try:
                value = serializers.DateTimeField().to_internal_value(value)
            except serializers.ValidationError:
                errors[key] = f"{f.label}日期时间格式不正确"
                continue
            # JSON 字段存不进 datetime 对象，统一转 ISO 字符串
            value = value.isoformat()
        elif f.field_type in ("text", "textarea"):
            if not isinstance(value, str):
                errors[key] = f"{f.label}必须是文本"
                continue
        cleaned[key] = value
    if errors:
        raise serializers.ValidationError({"field_values": errors})
    return cleaned


class NoteSerializer(serializers.ModelSerializer):
    note_type_name = serializers.CharField(source="note_type.name", read_only=True)

    class Meta:
        model = Note
        fields = [
            "id",
            "note_type",
            "note_type_name",
            "field_values",
            "custom_fields",
            "content",
            "folder",
            "tags",
            "is_pinned",
            "is_archived",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_by", "created_at", "updated_at"]

    def validate_tags(self, value):
        if not isinstance(value, list) or not all(isinstance(t, str) for t in value):
            raise serializers.ValidationError("标签必须是字符串数组")
        return [t.strip() for t in value if t.strip()]

    def validate_custom_fields(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError("自定义字段必须是对象")
        for key, item in value.items():
            if not isinstance(item, dict) or "label" not in item or "value" not in item:
                raise serializers.ValidationError(f"自定义字段 {key} 必须包含 label 和 value")
        return value

    def validate(self, attrs):
        note_type = attrs.get("note_type") or getattr(self.instance, "note_type", None)
        if note_type is None:
            raise serializers.ValidationError({"note_type": "必须选择笔记类型"})
        field_values = attrs.get("field_values")
        if field_values is None and self.instance is not None:
            field_values = self.instance.field_values
        if field_values is None:
            field_values = {}
        attrs["field_values"] = validate_field_values(note_type, field_values)
        return attrs

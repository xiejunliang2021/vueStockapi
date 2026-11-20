"""种子数据：创建笔记类型「网站注册」「记录生活」及字段定义，并种子化下拉选项。

用法：.venv/bin/python manage.py seed_note_types
可重复执行：按 slug/key 更新，不会重复创建。
"""

from django.core.management.base import BaseCommand

from notes.models import FieldDefinition, FieldOption, NoteType

WEBSITE_FIELDS = [
    # key, label, field_type, required, default_value, options, show_when_key, show_when_value, help_text, option_group
    ("platform", "平台", "select", True, None, [], None, None, "", "platform"),
    ("platform_intro", "平台介绍", "textarea", False, None, [], None, None, "", None),
    ("email", "邮箱", "select", True, None, [], None, None, "", "email"),
    ("registered_at", "注册时间", "datetime", False, "__now__", [], None, None, "默认当前时间", None),
    ("password_hint", "密码提示", "text", False, None, [], None, None, "只存提示，不存真实密码", None),
    ("has_2fa", "是否二次验证", "boolean", False, "false", [], None, None, "", None),
    ("two_fa_methods", "二次验证方式", "multiselect", False, None, [], "has_2fa", True, "仅当二次验证=是时显示", "2fa_method"),
    ("has_password_manager", "是否密码管理器", "boolean", False, "false", [], None, None, "", None),
    ("has_other_auth", "是否其他验证", "boolean", False, "false", [], None, None, "", None),
    ("other_auth_desc", "其他验证说明", "text", False, None, [], "has_other_auth", True, "仅当其他验证=是时显示", None),
    ("config", "配置", "textarea", False, None, [], None, None, "", None),
    ("remark", "备注", "textarea", False, None, [], None, None, "支持 Markdown", None),
]

LIFE_FIELDS = [
    # key, label, field_type, required, default_value, options, show_when_key, show_when_value, help_text, option_group
    ("title", "标题", "text", True, None, [], None, None, "", None),
    ("scope", "范围", "select", False, None, [], None, None, "", "scope"),
    ("created_time", "创建时间", "datetime", False, "__now__", [], None, None, "默认当前时间", None),
    ("steps", "正文", "steps", False, None, [], None, None, "", None),
]

# 下拉选项种子：二次验证方式初始三项，范围初始六项；
# platform / email 两组初始为空，用户在页面上自行添加
FIELD_OPTIONS = [
    ("2fa_method", "邮箱验证"),
    ("2fa_method", "谷歌验证器验证"),
    ("2fa_method", "其他"),
    ("scope", "生活常识"),
    ("scope", "健康医疗"),
    ("scope", "工作经验"),
    ("scope", "量化"),
    ("scope", "炒菜"),
    ("scope", "其他"),
]

NOTE_TYPES = [
    (
        "website-registration",
        {
            "name": "网站注册",
            "description": "记录各网站的注册信息：平台、邮箱、验证方式等",
            "icon": "🌐",
            "order": 0,
            "is_active": True,
        },
        WEBSITE_FIELDS,
    ),
    (
        "life-record",
        {
            "name": "记录生活",
            "description": "按步骤记录生活中的做法与经验：每步文字加图片",
            "icon": "📝",
            "order": 1,
            "is_active": True,
        },
        LIFE_FIELDS,
    ),
]


class Command(BaseCommand):
    help = "创建笔记类型及字段定义（可重复执行）"

    def handle(self, *args, **options):
        for slug, type_defaults, field_defs in NOTE_TYPES:
            note_type, created = NoteType.objects.update_or_create(
                slug=slug, defaults=type_defaults
            )
            self.stdout.write(f"笔记类型「{note_type.name}」{'已创建' if created else '已更新'}")

            for order, (key, label, field_type, required, default, opts, sw_key, sw_value, help_text, option_group) in enumerate(
                field_defs, start=1
            ):
                _, f_created = FieldDefinition.objects.update_or_create(
                    note_type=note_type,
                    key=key,
                    defaults={
                        "label": label,
                        "field_type": field_type,
                        "required": required,
                        "default_value": default,
                        "options": opts,
                        "option_group": option_group,
                        "show_when_key": sw_key,
                        "show_when_value": sw_value,
                        "help_text": help_text,
                        "order": order,
                    },
                )
                self.stdout.write(f"  字段 {label}（{key}）{'已创建' if f_created else '已更新'}")

        for sort_order, (key, value) in enumerate(FIELD_OPTIONS):
            _, o_created = FieldOption.objects.update_or_create(
                key=key,
                value=value,
                defaults={"label": value, "sort_order": sort_order},
            )
            self.stdout.write(f"  选项 {key}={value} {'已创建' if o_created else '已更新'}")

        self.stdout.write(self.style.SUCCESS("种子数据完成"))

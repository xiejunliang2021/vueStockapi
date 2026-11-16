"""种子数据：创建首个笔记类型「网站注册」及 11 个字段定义。

用法：.venv/bin/python manage.py seed_note_types
可重复执行：按 slug/key 更新，不会重复创建。
"""

from django.core.management.base import BaseCommand

from notes.models import FieldDefinition, NoteType

WEBSITE_FIELDS = [
    # key, label, field_type, required, default_value, options, show_when_key, show_when_value, help_text
    ("platform", "平台", "text", True, None, [], None, None, ""),
    ("platform_intro", "平台介绍", "textarea", False, None, [], None, None, ""),
    ("email", "邮箱", "email", True, None, [], None, None, ""),
    ("registered_at", "注册时间", "datetime", False, "__now__", [], None, None, "默认当前时间"),
    ("password_hint", "密码提示", "text", False, None, [], None, None, "只存提示，不存真实密码"),
    ("has_2fa", "是否二次验证", "boolean", False, "false", [], None, None, ""),
    ("has_password_manager", "是否密码管理器", "boolean", False, "false", [], None, None, ""),
    ("has_other_auth", "是否其他验证", "boolean", False, "false", [], None, None, ""),
    ("other_auth_desc", "其他验证说明", "text", False, None, [], "has_other_auth", True, "仅当其他验证=是时显示"),
    ("config", "配置", "textarea", False, None, [], None, None, ""),
    ("remark", "备注", "textarea", False, None, [], None, None, "支持 Markdown"),
]


class Command(BaseCommand):
    help = "创建笔记类型「网站注册」及字段定义（可重复执行）"

    def handle(self, *args, **options):
        note_type, created = NoteType.objects.update_or_create(
            slug="website-registration",
            defaults={
                "name": "网站注册",
                "description": "记录各网站的注册信息：平台、邮箱、验证方式等",
                "icon": "🌐",
                "order": 0,
                "is_active": True,
            },
        )
        self.stdout.write(f"笔记类型「{note_type.name}」{'已创建' if created else '已更新'}")

        for order, (key, label, field_type, required, default, opts, sw_key, sw_value, help_text) in enumerate(
            WEBSITE_FIELDS, start=1
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
                    "show_when_key": sw_key,
                    "show_when_value": sw_value,
                    "help_text": help_text,
                    "order": order,
                },
            )
            self.stdout.write(f"  字段 {label}（{key}）{'已创建' if f_created else '已更新'}")

        self.stdout.write(self.style.SUCCESS("种子数据完成"))

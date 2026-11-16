from django.contrib import admin
from .models import FieldDefinition, FieldOption, Note, NoteType


@admin.register(NoteType)
class NoteTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "order", "updated_at"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(FieldDefinition)
class FieldDefinitionAdmin(admin.ModelAdmin):
    list_display = ["note_type", "label", "key", "field_type", "required", "order"]
    list_filter = ["note_type", "field_type", "required"]


@admin.register(Note)
class NoteAdmin(admin.ModelAdmin):
    list_display = ["id", "note_type", "folder", "is_pinned", "is_archived", "updated_at"]
    list_filter = ["note_type", "is_pinned", "is_archived"]
    search_fields = ["content"]


@admin.register(FieldOption)
class FieldOptionAdmin(admin.ModelAdmin):
    list_display = ["key", "value", "label", "sort_order"]
    list_filter = ["key"]
    search_fields = ["value", "label"]

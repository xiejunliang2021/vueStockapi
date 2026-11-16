from django.contrib import admin
from .models import Note, NoteType, FieldDefinition


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
    list_display = ["title", "note_type", "folder", "is_pinned", "is_archived", "updated_at"]
    list_filter = ["note_type", "is_pinned", "is_archived"]
    search_fields = ["title"]

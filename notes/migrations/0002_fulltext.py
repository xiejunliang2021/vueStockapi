from django.db import migrations


def create_fulltext_index(apps, schema_editor):
    # MySQL 专属：全文索引 DDL，只在 MySQL 上执行；Oracle 上跳过
    #（Oracle 侧搜索方案另定，见迁移设计文档）。
    if schema_editor.connection.vendor != "mysql":
        return
    schema_editor.execute(
        "CREATE FULLTEXT INDEX notes_note_search_idx "
        "ON notes_note (title, content) WITH PARSER ngram;"
    )


def drop_fulltext_index(apps, schema_editor):
    if schema_editor.connection.vendor != "mysql":
        return
    schema_editor.execute("DROP INDEX notes_note_search_idx ON notes_note;")


class Migration(migrations.Migration):
    """标题+正文的 MySQL 全文索引（ngram 分词，支持中文搜索）。"""

    dependencies = [
        ("notes", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_fulltext_index, drop_fulltext_index),
    ]

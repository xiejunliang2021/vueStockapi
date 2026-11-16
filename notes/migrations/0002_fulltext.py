from django.db import migrations


class Migration(migrations.Migration):
    """标题+正文的 MySQL 全文索引（ngram 分词，支持中文搜索）。"""

    dependencies = [
        ("notes", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            "CREATE FULLTEXT INDEX notes_note_search_idx "
            "ON notes_note (title, content) WITH PARSER ngram;",
            reverse_sql="DROP INDEX notes_note_search_idx ON notes_note;",
        ),
    ]

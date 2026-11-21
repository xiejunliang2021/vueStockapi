# 手写迁移：字段定义加条件取反与排除选项（Google 关联平台功能）

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notes', '0004_alter_fielddefinition_field_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='fielddefinition',
            name='exclude_option_values',
            field=models.JSONField(blank=True, default=list, verbose_name='排除的选项值'),
        ),
        migrations.AddField(
            model_name='fielddefinition',
            name='show_when_negate',
            field=models.BooleanField(default=False, verbose_name='条件取反'),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('_1nbox_ai', '0005_add_briefed_products_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='topic',
            name='current_clusters',
            field=models.JSONField(blank=True, default=dict, null=True),
        ),
    ]


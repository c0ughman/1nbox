from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('_1nbox_ai', '0006_add_current_clusters_to_topic'),
    ]

    operations = [
        migrations.AddField(
            model_name='genieanalysis',
            name='research_type',
            field=models.CharField(
                choices=[
                    ('quick', 'Quick'),
                    ('comprehensive', 'Comprehensive'),
                    ('deep', 'Deep Research'),
                ],
                default='quick',
                max_length=20
            ),
        ),
        migrations.AddField(
            model_name='genieanalysis',
            name='deep_research_id',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='genieanalysis',
            name='deep_research_results',
            field=models.TextField(blank=True, null=True),
        ),
    ]


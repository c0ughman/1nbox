from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('_1nbox_ai', '0003_create_comment_model'), 
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='send_email',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='organization',
            name='summary_time',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='summary_timezone',
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
    ]

from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('_1nbox_ai', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='name',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='state',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]

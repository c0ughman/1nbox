# Generated by Django 5.0.1 on 2024-05-23 06:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('_1nbox_ai', '0004_user_provider_refresh_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='phone_number',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]

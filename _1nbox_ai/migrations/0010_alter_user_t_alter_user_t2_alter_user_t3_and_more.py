# Generated by Django 5.0.1 on 2024-07-07 17:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('_1nbox_ai', '0009_user_t2_user_t3_user_t4_user_t5_user_weekday_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='t',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='t2',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='t3',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='t4',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='t5',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='weekday',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]

# Generated by Django 5.0.1 on 2024-07-07 17:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('_1nbox_ai', '0008_remove_user_t2_remove_user_t3_remove_user_t4_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='t2',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='t3',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='t4',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='t5',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='user',
            name='weekday',
            field=models.CharField(max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name='user',
            name='t',
            field=models.CharField(max_length=255, null=True),
        ),
    ]

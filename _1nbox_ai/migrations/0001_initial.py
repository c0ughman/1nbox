import django.contrib.postgres.fields
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Organization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('plan', models.CharField(max_length=255)),
                ('status', models.CharField(choices=[('active', 'Active'), ('past_due', 'Past Due'), ('canceled', 'Canceled')], default='active', max_length=50)),
                ('stripe_customer_id', models.CharField(blank=True, max_length=255, null=True)),
                ('stripe_subscription_id', models.CharField(blank=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Topic',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('sources', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=255), blank=True, default=list, size=None)),
                ('prompt', models.TextField(blank=True, null=True)),
                ('negative_keywords', models.TextField(blank=True, null=True)),
                ('positive_keywords', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='topics', to='_1nbox_ai.organization')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Summary',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('clusters', models.JSONField(blank=True, default=dict, null=True)),
                ('cluster_summaries', models.JSONField(blank=True, default=dict, null=True)),
                ('final_summary', models.JSONField(blank=True, default=dict, null=True)),
                ('questions', models.TextField(blank=True, null=True)),
                ('number_of_articles', models.IntegerField(blank=True, default=0, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('topic', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='summaries', to='_1nbox_ai.topic')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('email', models.CharField(max_length=255, unique=True)),
                ('joined_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('role', models.CharField(choices=[('admin', 'Admin'), ('member', 'Member')], default='member', max_length=50)),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='users', to='_1nbox_ai.organization')),
            ],
            options={
                'ordering': ['-joined_at'],
            },
        ),
    ]



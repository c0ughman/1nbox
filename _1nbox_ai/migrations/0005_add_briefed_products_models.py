from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('_1nbox_ai', '0004_add_send_email_summary_time_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='industry',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='headquarters',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='employee_count',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='annual_revenue',
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='key_products',
            field=models.JSONField(blank=True, default=list, null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='competitors',
            field=models.JSONField(blank=True, default=list, null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='target_markets',
            field=models.JSONField(blank=True, default=list, null=True),
        ),
        migrations.AddField(
            model_name='organization',
            name='strategic_priorities',
            field=models.JSONField(blank=True, default=list, null=True),
        ),
        migrations.CreateModel(
            name='ChatConversation',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='chat_conversations', to='_1nbox_ai.user')),
                ('topic', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='chat_conversations', to='_1nbox_ai.topic')),
            ],
            options={
                'ordering': ['-updated_at'],
            },
        ),
        migrations.CreateModel(
            name='ChatMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('role', models.CharField(choices=[('user', 'User'), ('assistant', 'Assistant')], max_length=20)),
                ('content', models.TextField()),
                ('document_type', models.CharField(blank=True, choices=[('executive_brief', 'Executive Brief'), ('swot_analysis', 'SWOT Analysis'), ('risk_assessment', 'Risk Assessment'), ('competitive_intel', 'Competitive Intel'), ('trend_report', 'Trend Report'), ('stakeholder_brief', 'Stakeholder Brief'), ('action_items', 'Action Items'), ('market_snapshot', 'Market Snapshot')], max_length=50, null=True)),
                ('metadata', models.JSONField(blank=True, default=dict, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='_1nbox_ai.chatconversation')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='GenieAnalysis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('query', models.TextField()),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')], default='pending', max_length=20)),
                ('results', models.JSONField(blank=True, default=dict, null=True)),
                ('sources', models.JSONField(blank=True, default=list, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='genie_analyses', to='_1nbox_ai.user')),
                ('organization', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='genie_analyses', to='_1nbox_ai.organization')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='BitesSubscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('frequency', models.CharField(choices=[('daily', 'Daily'), ('weekly', 'Weekly')], max_length=20)),
                ('delivery_time', models.TimeField(default=django.utils.timezone.now)),
                ('timezone', models.CharField(default='UTC', max_length=50)),
                ('is_active', models.BooleanField(default=True)),
                ('last_sent_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bites_subscriptions', to='_1nbox_ai.user')),
                ('topic', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bites_subscriptions', to='_1nbox_ai.topic')),
            ],
            options={
                'ordering': ['-created_at'],
                'unique_together': {('user', 'topic')},
            },
        ),
        migrations.CreateModel(
            name='BitesDigest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('digest_type', models.CharField(choices=[('daily', 'Daily'), ('weekly', 'Weekly')], max_length=20)),
                ('digest_date', models.DateField()),
                ('content', models.JSONField()),
                ('article_count', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('topic', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bites_digests', to='_1nbox_ai.topic')),
            ],
            options={
                'ordering': ['-digest_date'],
                'unique_together': {('topic', 'digest_type', 'digest_date')},
            },
        ),
    ]

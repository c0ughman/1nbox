from django.db import migrations, models
import django.db.models.deletion
from django.utils import timezone

class Migration(migrations.Migration):
    dependencies = [
        ('_1nbox_ai', '0002_add_description_name_state_fields.py'),  # Adjust this to match your previous migration
    ]

    operations = [
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('comment', models.TextField()),
                ('position', models.IntegerField()),
                ('created_at', models.DateTimeField(default=timezone.now)),
                ('writer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='comments', to='_1nbox_ai.user')),
            ],
            options={
                'ordering': ['position'],
            },
        ),
    ]

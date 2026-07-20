from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('content', '0009_category_priority_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CaptionModerationEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('caption_fingerprint', models.CharField(db_index=True, max_length=64)),
                ('model_version', models.CharField(max_length=80)),
                ('decision', models.CharField(choices=[('allow', 'Allow'), ('warn', 'Warn'), ('review', 'Review'), ('block', 'Block'), ('error', 'Error')], db_index=True, max_length=20)),
                ('scores', models.JSONField(default=dict)),
                ('reasons', models.JSONField(default=list)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('post', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='caption_moderation_events', to='content.post')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='caption_moderation_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]

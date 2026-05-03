from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0003_post_status_subpost'),
    ]

    operations = [
        migrations.AddField(
            model_name='subpost',
            name='is_media_deleted',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='subpost',
            name='media_file',
            field=models.FileField(blank=True, null=True, upload_to='subposts/'),
        ),
    ]

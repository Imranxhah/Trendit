from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('social', '0013_community_is_private_community_latitude_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='community',
            name='city_name',
            field=models.CharField(blank=True, default='', max_length=120),
        ),
    ]

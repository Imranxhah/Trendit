# Generated to align Post migrations with the current many-to-many category model.

from django.db import migrations, models


def copy_category_to_categories(apps, schema_editor):
    Post = apps.get_model('content', 'Post')
    through = Post.categories.through

    rows = [
        through(post_id=post.id, category_id=post.category_id)
        for post in Post.objects.exclude(category_id__isnull=True).only('id', 'category_id')
    ]
    through.objects.bulk_create(rows, ignore_conflicts=True)


class Migration(migrations.Migration):

    dependencies = [
        ('content', '0007_alter_post_media_file_alter_subpost_media_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='categories',
            field=models.ManyToManyField(blank=True, related_name='posts', to='content.category'),
        ),
        migrations.RunPython(copy_category_to_categories, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='post',
            name='category',
        ),
    ]

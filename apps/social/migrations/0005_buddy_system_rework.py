import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('social', '0004_alter_buddyrequest_receiver_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Drop the old BuddyRequest table (was mutual friend-request)
        migrations.DeleteModel(
            name='BuddyRequest',
        ),

        # 2. Create new Buddy table (simple follow, no permission)
        migrations.CreateModel(
            name='Buddy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('follower', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='following',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('following', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='followers',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'unique_together': {('follower', 'following')},
            },
        ),

        # 3. Re-create CloseBuddyRequest (permission-based inner circle invite)
        migrations.CreateModel(
            name='CloseBuddyRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    choices=[('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')],
                    default='pending',
                    max_length=10,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sender', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='close_buddy_requests_sent',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('receiver', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='close_buddy_requests_received',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'unique_together': {('sender', 'receiver')},
            },
        ),
    ]

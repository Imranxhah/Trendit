from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.content.models import Post
import os

class Command(BaseCommand):
    help = 'Delete media files of posts older than 7 days but keep the database records'

    def handle(self, *args, **options):
        expiry_date = timezone.now() - timedelta(days=7)
        expired_posts = Post.objects.filter(
            created_at__lt=expiry_date,
            media_file__isnull=False,
            is_media_deleted=False
        )

        count = 0
        for post in expired_posts:
            if post.media_file:
                # Delete the actual file from storage
                if os.path.isfile(post.media_file.path):
                    os.remove(post.media_file.path)
                
                # Update database record
                post.media_file = None
                post.is_media_deleted = True
                post.save()
                count += 1

        self.stdout.write(self.style.SUCCESS(f'Successfully deleted media for {count} expired posts.'))

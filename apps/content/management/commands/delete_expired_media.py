import cloudinary
import cloudinary.uploader
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from apps.content.models import Post, SubPost


class Command(BaseCommand):
    help = 'Delete Cloudinary media files for posts/subposts older than 7 days, keeping DB records'

    def _delete_cloudinary_file(self, file_field):
        """
        Given a FileField whose name contains the Cloudinary public_id,
        delete the resource from Cloudinary. Returns True on success.
        """
        if not file_field:
            return False

        # django-cloudinary-storage stores the public_id as the file name
        public_id = file_field.name

        # Strip known extensions so Cloudinary matches the resource correctly
        for ext in ['.mp4', '.mov', '.avi', '.jpg', '.jpeg', '.png', '.gif', '.webp']:
            if public_id.lower().endswith(ext):
                public_id = public_id[:-(len(ext))]
                break

        # Determine resource type
        video_exts = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
        original_name = file_field.name.lower()
        resource_type = 'video' if any(original_name.endswith(e) for e in video_exts) else 'image'

        try:
            result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            return result.get('result') == 'ok'
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Could not delete {public_id}: {e}'))
            return False

    def handle(self, *args, **options):
        expiry_date = timezone.now() - timedelta(days=7)

        # ── Posts ────────────────────────────────────────────────────────────
        expired_posts = Post.objects.filter(
            created_at__lt=expiry_date,
            media_file__isnull=False,
            is_media_deleted=False
        ).exclude(media_file='')

        post_count = 0
        for post in expired_posts:
            deleted = self._delete_cloudinary_file(post.media_file)
            if deleted:
                post.media_file = None
                post.is_media_deleted = True
                post.save(update_fields=['media_file', 'is_media_deleted'])
                post_count += 1
                self.stdout.write(f'  Deleted media for Post #{post.id}')

        # ── SubPosts ─────────────────────────────────────────────────────────
        expired_subposts = SubPost.objects.filter(
            created_at__lt=expiry_date,
            media_file__isnull=False,
        ).exclude(media_file='')

        subpost_count = 0
        for subpost in expired_subposts:
            deleted = self._delete_cloudinary_file(subpost.media_file)
            if deleted:
                subpost.media_file = None
                subpost.save(update_fields=['media_file'])
                subpost_count += 1
                self.stdout.write(f'  Deleted media for SubPost #{subpost.id}')

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Deleted Cloudinary media for {post_count} post(s) and {subpost_count} subpost(s).'
        ))

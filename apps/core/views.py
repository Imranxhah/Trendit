from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings
from django.shortcuts import redirect, render
from django.utils import timezone
from datetime import timedelta
from .models import Notification, Report
from .serializers import NotificationSerializer, ReportSerializer
import cloudinary
import cloudinary.uploader


def landing_page(request):
    return render(request, 'core/landing_page.html', {
        'apk_download_url': settings.TRENDIT_APK_DOWNLOAD_URL,
        'app_version': settings.TRENDIT_APP_VERSION,
    })


def post_share_landing(request, post_id):
    # Verified Android App Links open the installed app before this view runs.
    # Browser visitors reach the download landing page instead.
    return redirect('landing-page')


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

class NotificationReadView(generics.UpdateAPIView):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Notification.objects.all()

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.recipient != request.user:
            return Response(status=status.HTTP_403_FORBIDDEN)
        instance.read_status = True
        instance.save()
        return Response({"status": "notification marked as read"})

class ReportCreateView(generics.CreateAPIView):
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(reporter=self.request.user)


class CleanupExpiredMediaView(APIView):
    """
    POST /api/core/cleanup-media/
    Protected by a secret token passed in the Authorization header:
        Authorization: Bearer <CLEANUP_SECRET_TOKEN>
    Called daily by an external cron service (e.g. cron-job.org).
    Deletes Cloudinary media files for posts/subposts older than 7 days.
    """
    permission_classes = [permissions.AllowAny]
    authentication_classes = []  # Bypass global JWT authentication


    def _delete_cloudinary_file(self, file_field):
        if not file_field:
            return False
        
        # CloudinaryField returns a CloudinaryResource.
        # It might not have a .name attribute like a standard Django FileField.
        # We use getattr to safely get public_id, or fall back to str() representation.
        public_id = getattr(file_field, 'public_id', None)
        if not public_id:
            try:
                public_id = str(file_field)
            except Exception:
                return False
        
        if not public_id:
            return False

        video_exts = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
        original_name = public_id.lower()
        for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.jpg', '.jpeg', '.png', '.gif', '.webp']:
            if original_name.endswith(ext):
                public_id = public_id[:-(len(ext))]
                break
        resource_type = 'video' if any(original_name.endswith(e) for e in video_exts) else 'image'
        try:
            result = cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            return result.get('result') == 'ok'
        except Exception:
            return False

    def post(self, request):
        # Verify secret token
        auth_header = request.headers.get('Authorization', '')
        expected = f"Bearer {settings.CLEANUP_SECRET_TOKEN}"
        if auth_header != expected:
            return Response({'error': 'Forbidden'}, status=status.HTTP_403_FORBIDDEN)

        from apps.content.models import Post, SubPost
        expiry_date = timezone.now() - timedelta(days=7)

        # Delete expired Post media
        expired_posts = Post.objects.filter(
            created_at__lt=expiry_date,
            is_media_deleted=False
        ).exclude(media_file='')
        post_count = 0
        for post in expired_posts:
            if self._delete_cloudinary_file(post.media_file):
                post.media_file = None
                post.is_media_deleted = True
                post.save(update_fields=['media_file', 'is_media_deleted'])
                post_count += 1

        # Delete expired SubPost media
        expired_subposts = SubPost.objects.filter(
            created_at__lt=expiry_date,
            is_media_deleted=False
        ).exclude(media_file='')
        subpost_count = 0
        for subpost in expired_subposts:
            if self._delete_cloudinary_file(subpost.media_file):
                subpost.media_file = None
                subpost.is_media_deleted = True
                subpost.save(update_fields=['media_file', 'is_media_deleted'])
                subpost_count += 1

        return Response({
            'message': 'Cleanup complete',
            'posts_cleaned': post_count,
            'subposts_cleaned': subpost_count,
        }, status=status.HTTP_200_OK)

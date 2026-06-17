from rest_framework import generics, permissions, status
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from .models import Post, Category
from .serializers import PostSerializer, CategorySerializer
from apps.users.permissions import IsProfileComplete

class PostCreateView(generics.CreateAPIView):
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

from django.db.models import Avg, Count, OuterRef, Subquery, Exists, Value
from django.db.models.functions import Coalesce
from .models import Post, Category, SubPost
from .serializers import PostSerializer, CategorySerializer, SubPostSerializer
from apps.social.models import Vote, Favorite

class FeedCursorPagination(CursorPagination):
    """
    Cursor-based pagination for the main feed.
    Prevents duplicate posts appearing when new content is uploaded while
    a user is mid-scroll. Flutter's Dio client simply follows the `next`
    URL string — no client-side cursor math needed.
    """
    page_size = 15
    ordering = '-created_at'
    cursor_query_param = 'cursor'


class TrendingFeedView(generics.ListAPIView):
    serializer_class = PostSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        user = self.request.user
        return Post.objects.filter(
            status__in=['active', 'trending'],
            is_media_deleted=False
        ).with_annotations(user).order_by('-avg_rating', '-vote_count', '-created_at')[:10]

class SubPostCreateView(generics.CreateAPIView):
    serializer_class = SubPostSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

class SubPostDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SubPostSerializer
    permission_classes = [permissions.IsAuthenticated, IsAuthorOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        return SubPost.objects.with_annotations(user)

class PostFeedView(generics.ListAPIView):
    serializer_class = PostSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = FeedCursorPagination

    def get_queryset(self):
        user = self.request.user
        return Post.objects.filter(is_media_deleted=False).with_annotations(user).order_by('-created_at')

class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

class UserPostListView(generics.ListAPIView):
    """
    GET /api/content/posts/user/<user_id>/
    Returns all posts for a specific user.
    If the requester is the author, they see all statuses (pending, active, etc.).
    Otherwise, they only see 'active' or 'trending' posts.
    Includes posts even if media is deleted.
    """
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        user_id = self.kwargs.get('user_id')
        user = self.request.user
        queryset = Post.objects.filter(author_id=user_id).with_annotations(user)

        # If not the author, only show active/trending posts
        if not user.is_authenticated or user.id != int(user_id):
            queryset = queryset.filter(status__in=['active', 'trending'])
            
        return queryset.order_by('-created_at')



import cloudinary.uploader
import time
import threading
from django.conf import settings
from rest_framework.views import APIView


def _delete_cloudinary_async(public_id: str, resource_type: str = 'image') -> None:
    """
    Fires a Cloudinary delete in a background daemon thread so that
    PostDetailView.perform_destroy() can return a 204 to Flutter immediately
    without blocking on the Cloudinary API round-trip.
    Mirrors the EmailThread pattern in apps/users/utils.py.
    """
    def _task():
        try:
            cloudinary.uploader.destroy(public_id, resource_type=resource_type)
        except Exception as e:
            # Log but never crash the request cycle.
            print(f"[Cloudinary async delete] Failed for {public_id!r}: {e}")

    t = threading.Thread(target=_task, daemon=True)
    t.start()

class CloudinarySignatureView(APIView):
    """
    POST /api/content/upload-signature/
    Generates a signed upload request for direct client-to-Cloudinary uploads.
    """
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def post(self, request, *args, **kwargs):
        timestamp = int(time.time())
        # Parameters to include in the signature
        params = {
            'timestamp': timestamp,
            'folder': 'posts', # You can adjust this based on request data if needed
            'eager': 'sp_auto',
            'eager_async': True,
        }
        
        # Generate signature using the Cloudinary SDK
        signature = cloudinary.utils.api_sign_request(
            params, 
            settings.CLOUDINARY_STORAGE['API_SECRET']
        )
        
        return Response({
            'signature': signature,
            'timestamp': timestamp,
            'api_key': settings.CLOUDINARY_STORAGE['API_KEY'],
            'cloud_name': settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
            'folder': params['folder'],
            'eager': params['eager'],
            'eager_async': params['eager_async'],
        })

class PostDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/content/posts/<id>/  -> Retrieve post details
    PATCH  /api/content/posts/<id>/  -> Update caption/category (Author only)
    DELETE /api/content/posts/<id>/  -> Delete post and its Cloudinary media (Author only)
    """
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        return Post.objects.all().with_annotations(user)

    def perform_destroy(self, instance):
        # Capture media metadata BEFORE deleting the DB row so we still
        # have the data needed for the Cloudinary call.
        public_id = None
        resource_type = 'image'

        if instance.media_file and not instance.is_media_deleted:
            public_id = getattr(instance.media_file, 'public_id', None)
            if not public_id:
                try:
                    public_id = str(instance.media_file)
                except Exception:
                    public_id = None

            if public_id:
                # Strip file extension from public_id if present.
                for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm',
                            '.jpg', '.jpeg', '.png', '.gif', '.webp']:
                    if public_id.lower().endswith(ext):
                        public_id = public_id[: -(len(ext))]
                        break

                # Determine resource type from the stored media name.
                video_exts = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
                media_name = getattr(instance.media_file, 'name',
                                     str(instance.media_file) or '')
                resource_type = 'video' if any(
                    media_name.lower().endswith(e) for e in video_exts
                ) else 'image'

        # Delete the DB row first — Flutter gets an instant 204.
        instance.delete()

        # Fire Cloudinary deletion in background — non-blocking.
        if public_id:
            _delete_cloudinary_async(public_id, resource_type)

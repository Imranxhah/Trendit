from datetime import datetime, time as datetime_time, timedelta

from django.utils import timezone
from rest_framework import generics, permissions, status
from rest_framework.pagination import CursorPagination
from rest_framework.response import Response
from .models import Post, Category, calculate_trending_score
from .serializers import PostSerializer, CategorySerializer
from apps.users.permissions import IsProfileComplete
from .moderation import ModerationUnavailable, analyze_caption, record_moderation_event

class PostCreateView(generics.CreateAPIView):
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]


class CaptionModerationView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def post(self, request, *args, **kwargs):
        caption = str(request.data.get('caption', '')).strip()
        if not caption:
            return Response({'caption': ['This field is required.']}, status=status.HTTP_400_BAD_REQUEST)
        try:
            result = analyze_caption(caption)
        except ModerationUnavailable as error:
            return Response(
                {'status': 'error', 'code': 503, 'message': str(error), 'errors': None},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if result.decision == 'block':
            record_moderation_event(request.user, result)
        return Response({
            'decision': result.decision,
            'reasons': result.reasons,
            'scores': result.scores,
            'model_version': result.model_version,
        })

from django.db.models import Avg, Count, OuterRef, Subquery, Exists, Value
from django.db.models.functions import Coalesce
from .models import Post, Category, SubPost
from .serializers import PostSerializer, CategorySerializer, SubPostSerializer
from apps.social.models import (
    CloseBuddy,
    CommunityMembership,
    Favorite,
    Vote,
)

class IsAuthorOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Allow safe methods (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True
        if (
            request.method == 'DELETE'
            and getattr(obj, 'status', None) == 'pending'
        ):
            is_close_buddy_moderator = CloseBuddy.objects.filter(
                user=obj.author,
                buddy=request.user,
            ).exists()
            if is_close_buddy_moderator:
                return True
        # PATCH/PUT and non-pending deletion remain restricted to the author.
        return obj.author == request.user

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


def _rank_trending_queryset(queryset, user, *, candidate_limit, result_limit, score_now=None):
    candidates = list(queryset.with_trending_base_score(user).order_by(
        '-trending_base_score',
        '-created_at',
    )[:candidate_limit])

    for post in candidates:
        post.trending_score = calculate_trending_score(post, now=score_now)

    return sorted(
        candidates,
        key=lambda post: (
            post.trending_score,
            post.vote_count or 0,
            post.avg_rating or 0,
            post.created_at,
        ),
        reverse=True,
    )[:result_limit]


class TrendingFeedView(generics.ListAPIView):
    serializer_class = PostSerializer
    permission_classes = [permissions.AllowAny]
    candidate_limit = 250
    result_limit = 10

    def _query_int(self, *names):
        for name in names:
            raw_value = self.request.query_params.get(name)
            if raw_value in (None, ''):
                continue
            try:
                value = int(raw_value)
            except (TypeError, ValueError):
                return None
            return value if value > 0 else None
        return None

    def get_queryset(self):
        user = self.request.user
        queryset = Post.objects.filter(
            status__in=['active', 'trending'],
            is_media_deleted=False
        )

        category_id = self._query_int('category', 'category_id')
        if category_id is not None:
            post_category = Post.categories.through.objects.filter(
                post_id=OuterRef('pk'),
                category_id=category_id,
            )
            queryset = queryset.filter(Exists(post_category))

        community_id = self._query_int('community', 'community_id')
        if community_id is not None:
            community_member = CommunityMembership.objects.filter(
                community_id=community_id,
                user_id=OuterRef('author_id'),
            )
            queryset = queryset.filter(Exists(community_member))

        return _rank_trending_queryset(
            queryset,
            user,
            candidate_limit=self.candidate_limit,
            result_limit=self.result_limit,
        )


class PreviousTrendsView(generics.GenericAPIView):
    serializer_class = PostSerializer
    permission_classes = [permissions.AllowAny]
    days = 7
    result_limit = 3
    candidate_limit = 100

    def get(self, request, *args, **kwargs):
        user = request.user
        current_day = timezone.localdate()
        tz = timezone.get_current_timezone()
        payload = []

        for offset in range(self.days):
            day = current_day - timedelta(days=offset)
            day_start = timezone.make_aware(
                datetime.combine(day, datetime_time.min),
                tz,
            )
            day_end = day_start + timedelta(days=1)
            queryset = Post.objects.filter(
                status__in=['active', 'trending'],
                is_media_deleted=False,
                created_at__gte=day_start,
                created_at__lt=day_end,
            )

            posts = _rank_trending_queryset(
                queryset,
                user,
                candidate_limit=self.candidate_limit,
                result_limit=self.result_limit,
                score_now=day_end,
            )
            serializer = self.get_serializer(posts, many=True)
            payload.append({
                'date': day.isoformat(),
                'posts': serializer.data,
            })

        return Response(payload)

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
        requested_folder = str(request.data.get('folder', 'posts')).strip()
        folder = requested_folder if requested_folder in {'posts', 'chat_media'} else 'posts'
        # Parameters to include in the signature
        params = {
            'timestamp': timestamp,
            'folder': folder,
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

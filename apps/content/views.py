from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Post, Category
from .serializers import PostSerializer, CategorySerializer

class PostCreateView(generics.CreateAPIView):
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]

from django.db.models import Avg, Count, OuterRef, Subquery, Exists, Value
from django.db.models.functions import Coalesce
from .models import Post, Category, SubPost
from .serializers import PostSerializer, CategorySerializer, SubPostSerializer
from apps.social.models import Vote, Favorite

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
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

class PostFeedView(generics.ListAPIView):
    serializer_class = PostSerializer
    permission_classes = [permissions.AllowAny] # Feed is public or restricted? Let's assume public for now

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

class IsAuthorOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Allow safe methods (GET, HEAD, OPTIONS)
        if request.method in permissions.SAFE_METHODS:
            return True
        # Restricted to author for PATCH, PUT, DELETE
        return obj.author == request.user

import cloudinary.uploader

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
        # Delete from Cloudinary before deleting from DB
        if instance.media_file and not instance.is_media_deleted:
            public_id = instance.media_file.name
            # Basic cleanup logic for Cloudinary public_id
            for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.jpg', '.jpeg', '.png', '.gif', '.webp']:
                if public_id.lower().endswith(ext):
                    public_id = public_id[:-(len(ext))]
                    break
            
            # Determine resource type
            video_exts = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
            resource_type = 'video' if any(instance.media_file.name.lower().endswith(e) for e in video_exts) else 'image'
            
            try:
                cloudinary.uploader.destroy(public_id, resource_type=resource_type)
            except Exception:
                pass # Silently fail if Cloudinary deletion fails
        
        instance.delete()

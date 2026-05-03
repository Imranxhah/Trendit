from rest_framework import generics, permissions, status
from rest_framework.response import Response
from .models import Post, Category
from .serializers import PostSerializer, CategorySerializer

class PostCreateView(generics.CreateAPIView):
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]

from django.db.models import Avg, Count
from .models import Post, Category, SubPost
from .serializers import PostSerializer, CategorySerializer, SubPostSerializer

class TrendingFeedView(generics.ListAPIView):
    serializer_class = PostSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        # Trending logic: Active posts ordered by average rating and vote count
        # In a real app, this would be a more complex formula (e.g., Wilson Score or Hacker News algorithm)
        return Post.objects.filter(
            status__in=['active', 'trending'],
            is_media_deleted=False
        ).annotate(
            avg_rating=Avg('votes__value'),
            vote_count=Count('votes')
        ).order_by('-avg_rating', '-vote_count', '-created_at')[:10]

class SubPostCreateView(generics.CreateAPIView):
    serializer_class = SubPostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

class PostFeedView(generics.ListAPIView):
    serializer_class = PostSerializer
    permission_classes = [permissions.AllowAny] # Feed is public or restricted? Let's assume public for now

    def get_queryset(self):
        # Returns posts where is_media_deleted=False
        return Post.objects.filter(is_media_deleted=False).order_by('-created_at')

class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]

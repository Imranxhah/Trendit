from django.urls import path
from .views import (
    PostCreateView, PostFeedView, CategoryListView, 
    TrendingFeedView, SubPostCreateView, SubPostDetailView, UserPostListView, PostDetailView,
    CloudinarySignatureView
)

urlpatterns = [
    path('posts/', PostCreateView.as_view(), name='post-create'),
    path('posts/<int:pk>/', PostDetailView.as_view(), name='post-detail'),
    path('posts/user/<int:user_id>/', UserPostListView.as_view(), name='user-posts'),
    path('feed/', PostFeedView.as_view(), name='post-feed'),
    path('trending/', TrendingFeedView.as_view(), name='post-trending'),
    path('subposts/', SubPostCreateView.as_view(), name='subpost-create'),
    path('subposts/<int:pk>/', SubPostDetailView.as_view(), name='subpost-detail'),
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('upload-signature/', CloudinarySignatureView.as_view(), name='upload-signature'),
]

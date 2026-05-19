from rest_framework import serializers
from .models import Category, Post, SubPost
from django.core.exceptions import ValidationError as DjangoValidationError

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

class SubPostSerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')
    author_profile_picture = serializers.ImageField(source='author.profile_picture', read_only=True)
    media_file = serializers.SerializerMethodField()

    class Meta:
        model = SubPost
        fields = [
            'id', 'parent_post', 'author', 'author_username', 'author_profile_picture', 
            'media_file', 'caption', 'aspect_ratio', 'duration', 'size', 'created_at'
        ]
        read_only_fields = ['author', 'created_at']

    def get_media_file(self, obj):
        if not obj.media_file:
            return None
        # CloudinaryField returns a CloudinaryResource.
        # We try to get its string representation safely.
        try:
            val = str(obj.media_file)
            if val is None:
                return getattr(obj.media_file, 'public_id', None)
            return val
        except Exception:
            return getattr(obj.media_file, 'public_id', None)

class PostSerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')
    author_profile_picture = serializers.ImageField(source='author.profile_picture', read_only=True)
    category_name = serializers.ReadOnlyField(source='category.name')
    avg_rating = serializers.FloatField(read_only=True)
    vote_count = serializers.IntegerField(read_only=True)
    user_rating = serializers.IntegerField(read_only=True)
    favorite_count = serializers.IntegerField(read_only=True)
    is_favorited = serializers.BooleanField(read_only=True)
    sub_posts = SubPostSerializer(many=True, read_only=True)
    media_file = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'author', 'author_username', 'author_profile_picture', 
            'category', 'category_name', 'media_file', 'caption', 'aspect_ratio', 
            'duration', 'size', 'status', 'created_at', 'is_media_deleted', 
            'avg_rating', 'vote_count', 'user_rating', 'favorite_count', 
            'is_favorited', 'sub_posts'
        ]
        read_only_fields = ['author', 'created_at', 'status']

    def get_media_file(self, obj):
        if not obj.media_file:
            return None
        try:
            val = str(obj.media_file)
            if val is None:
                return getattr(obj.media_file, 'public_id', None)
            return val
        except Exception:
            return getattr(obj.media_file, 'public_id', None)

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        try:
            return super().create(validated_data)
        except DjangoValidationError as e:
            if hasattr(e, 'message_dict') and e.message_dict:
                raise serializers.ValidationError(e.message_dict)
            raise serializers.ValidationError({'detail': e.messages})

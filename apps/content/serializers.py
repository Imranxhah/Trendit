from rest_framework import serializers
from .models import Category, Post, SubPost
from django.core.exceptions import ValidationError as DjangoValidationError

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug']

class SubPostSerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')

    class Meta:
        model = SubPost
        fields = ['id', 'parent_post', 'author', 'author_username', 'media_file', 'caption', 'aspect_ratio', 'created_at']
        read_only_fields = ['author', 'created_at']

class PostSerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')
    category_name = serializers.ReadOnlyField(source='category.name')
    avg_rating = serializers.FloatField(read_only=True)
    vote_count = serializers.IntegerField(read_only=True)
    sub_posts = SubPostSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'author', 'author_username', 'category', 'category_name', 
            'media_file', 'caption', 'aspect_ratio', 'status', 'created_at', 
            'avg_rating', 'vote_count', 'sub_posts'
        ]
        read_only_fields = ['author', 'created_at', 'status']

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        try:
            return super().create(validated_data)
        except DjangoValidationError as e:
            if hasattr(e, 'message_dict') and e.message_dict:
                raise serializers.ValidationError(e.message_dict)
            raise serializers.ValidationError({'detail': e.messages})

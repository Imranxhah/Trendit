from rest_framework import serializers
from .models import Category, Post, SubPost
from django.core.exceptions import ValidationError as DjangoValidationError
from django.conf import settings
import cloudinary
import logging

from .moderation import ModerationUnavailable, analyze_caption, record_moderation_event
from .media_moderation import MediaModerationUnavailable, check_media_url

logger = logging.getLogger(__name__)


def _generate_media_url(media_file):
    if not media_file:
        return None
    try:
        public_id = getattr(media_file, 'public_id', None)
        if not public_id:
            val = str(media_file)
            if val:
                public_id = val
            else:
                return None

        video_exts = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
        is_video = any(public_id.lower().endswith(ext) for ext in video_exts)

        if is_video:
            base_public_id = public_id
            for ext in video_exts:
                if base_public_id.lower().endswith(ext):
                    base_public_id = base_public_id[:-len(ext)]
                    break
            
            return cloudinary.CloudinaryVideo(base_public_id).build_url(
                secure=True, 
                format='m3u8', 
                streaming_profile='auto'
            )
        else:
            return cloudinary.CloudinaryImage(public_id).build_url(secure=True)
    except Exception:
        return getattr(media_file, 'public_id', str(media_file))


class CategorySerializer(serializers.ModelSerializer):
    priority_multiplier = serializers.FloatField(read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'priority_status', 'priority_multiplier']

class SubPostSerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')
    author_profile_picture = serializers.ImageField(source='author.profile_picture', read_only=True)
    media_file = serializers.SerializerMethodField()
    avg_rating = serializers.FloatField(read_only=True)
    vote_count = serializers.IntegerField(read_only=True)
    user_rating = serializers.IntegerField(read_only=True)

    class Meta:
        model = SubPost
        fields = [
            'id', 'parent_post', 'author', 'author_username', 'author_profile_picture', 
            'media_file', 'caption', 'aspect_ratio', 'duration', 'size', 'created_at',
            'avg_rating', 'vote_count', 'user_rating'
        ]
        read_only_fields = ['author', 'created_at']

    def get_media_file(self, obj):
        return _generate_media_url(obj.media_file)

    def create(self, validated_data):
        moderation = self._moderate_caption(validated_data.get('caption', ''))
        media_file = self.initial_data.get('media_file')
        if media_file:
            validated_data['media_file'] = media_file
        sub_post = super().create(validated_data)
        if moderation is not None:
            record_moderation_event(self.context['request'].user, moderation)
        return sub_post

    def _moderate_caption(self, caption):
        if not settings.CAPTION_MODERATION_ENABLED:
            return None
        try:
            result = analyze_caption(caption)
        except ModerationUnavailable as error:
            raise serializers.ValidationError({'caption': {'code': 'moderation_unavailable', 'message': str(error)}})
        if result.decision == 'block':
            record_moderation_event(self.context['request'].user, result)
            raise serializers.ValidationError({'caption': {'code': 'caption_blocked', 'message': 'This caption contains content that cannot be published.', 'reasons': result.reasons}})
        return result

    def update(self, instance, validated_data):
        media_file = self.initial_data.get('media_file')
        if media_file is not None:
            instance.media_file = media_file
        return super().update(instance, validated_data)

class PostSerializer(serializers.ModelSerializer):
    author_username = serializers.ReadOnlyField(source='author.username')
    author_profile_picture = serializers.ImageField(source='author.profile_picture', read_only=True)
    categories = CategorySerializer(many=True, read_only=True)
    category_ids = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        many=True,
        write_only=True,
        source='categories',
        required=False,
    )
    category_names = serializers.SerializerMethodField()
    avg_rating = serializers.FloatField(read_only=True)
    vote_count = serializers.IntegerField(read_only=True)
    user_rating = serializers.IntegerField(read_only=True)
    favorite_count = serializers.IntegerField(read_only=True)
    is_favorited = serializers.BooleanField(read_only=True)
    trending_score = serializers.FloatField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True, default=0)
    media_file = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'author', 'author_username', 'author_profile_picture', 
            'categories', 'category_ids', 'category_names',
            'media_file', 'caption', 'aspect_ratio', 
            'duration', 'size', 'status', 'created_at', 'is_media_deleted', 
            'avg_rating', 'vote_count', 'user_rating', 'favorite_count', 
            'is_favorited', 'trending_score', 'comments_count'
        ]
        read_only_fields = ['author', 'created_at', 'status']

    def get_media_file(self, obj):
        return _generate_media_url(obj.media_file)

    def get_category_names(self, obj):
        return [cat.name for cat in obj.categories.all()]

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        moderation = self._moderate_caption(validated_data.get('caption', ''))
        categories = validated_data.pop('categories', [])

        if len(categories) > 1:
            categories = [categories[0]]

        media_file = self.initial_data.get('media_file')
        if media_file:
            validated_data['media_file'] = media_file

        # ── Sightengine media moderation (images only; videos are skipped) ──
        # We build the Cloudinary URL from the raw media_file before creating
        # the DB record. If the image is NSFW we reject here — nothing is saved.
        if settings.MEDIA_MODERATION_ENABLED and media_file:
            # Determine whether this is a video by extension.
            filename = getattr(media_file, 'name', '') or ''
            video_exts = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
            is_video = any(filename.lower().endswith(ext) for ext in video_exts)

            if not is_video:
                # Build the provisional Cloudinary URL so Sightengine can fetch it.
                media_url = _generate_media_url(media_file)
                if media_url:
                    try:
                        media_result = check_media_url(media_url)
                        if media_result.decision == 'block':
                            raise serializers.ValidationError({
                                'media_file': {
                                    'code': 'media_blocked',
                                    'message': (
                                        'This media contains content that cannot be '
                                        'published. Please upload appropriate content.'
                                    ),
                                    'raw_score': round(media_result.raw_score, 3),
                                },
                            })
                        elif media_result.decision == 'review':
                            # Flag the post for human review after creation.
                            validated_data['status'] = 'pending'
                    except MediaModerationUnavailable as exc:
                        # Fail-safe: Sightengine is down or quota exceeded.
                        # Allow the post through and log so ops can investigate.
                        logger.warning(
                            'Media moderation unavailable — post allowed through: %s', exc
                        )

        try:
            post = super().create(validated_data)
            if categories:
                post.categories.set(categories)
            if moderation is not None:
                record_moderation_event(self.context['request'].user, moderation, post)
            return post
        except DjangoValidationError as e:
            if hasattr(e, 'message_dict') and e.message_dict:
                raise serializers.ValidationError(e.message_dict)
            raise serializers.ValidationError({'detail': e.messages})

    def update(self, instance, validated_data):
        moderation = None
        if 'caption' in validated_data:
            moderation = self._moderate_caption(validated_data['caption'])
            if moderation is not None and moderation.decision == 'review':
                validated_data['status'] = 'pending'
        categories = validated_data.pop('categories', None)
        media_file = self.initial_data.get('media_file')
        if media_file is not None:
            instance.media_file = media_file
        instance = super().update(instance, validated_data)
        if categories is not None:
            instance.categories.set(categories)
        if moderation is not None:
            record_moderation_event(self.context['request'].user, moderation, instance)
        return instance

    def _moderate_caption(self, caption):
        if not settings.CAPTION_MODERATION_ENABLED:
            return None
        try:
            result = analyze_caption(caption)
        except ModerationUnavailable as error:
            raise serializers.ValidationError({'caption': {'code': 'moderation_unavailable', 'message': str(error)}})
        if result.decision == 'block':
            record_moderation_event(self.context['request'].user, result)
            raise serializers.ValidationError({'caption': {'code': 'caption_blocked', 'message': 'This caption contains content that cannot be published.', 'reasons': result.reasons}})
        return result

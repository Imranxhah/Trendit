from rest_framework import serializers
from .models import Notification, Report
from django.contrib.contenttypes.models import ContentType

class NotificationSerializer(serializers.ModelSerializer):
    actor_username = serializers.ReadOnlyField(source='actor.username')
    actor_profile_picture = serializers.SerializerMethodField()
    target = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'recipient', 'actor', 'actor_username',
            'actor_profile_picture', 'verb', 'target',
            'read_status', 'created_at',
        ]
        read_only_fields = ['recipient', 'actor', 'created_at']

    def get_actor_profile_picture(self, obj):
        picture = getattr(obj.actor, 'profile_picture', None)
        if not picture:
            return None
        url = getattr(picture, 'url', None)
        if not url:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(url) if request else url

    def get_target(self, obj):
        if obj.content_type and obj.object_id:
            return {
                'type': obj.content_type.model,
                'id': obj.object_id
            }
        return None

class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ['id', 'reporter', 'content_type', 'object_id', 'reason', 'status', 'created_at']
        read_only_fields = ['reporter', 'status', 'created_at']

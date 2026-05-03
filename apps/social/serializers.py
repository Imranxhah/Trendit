from rest_framework import serializers
from .models import CloseBuddy, PostApproval, Vote, BuddyRequest
from django.contrib.auth import get_user_model

User = get_user_model()

class UserMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email']

class BuddyRequestSerializer(serializers.ModelSerializer):
    sender = UserMinimalSerializer(read_only=True)
    
    class Meta:
        model = BuddyRequest
        fields = ['id', 'sender', 'receiver', 'status', 'created_at']
        read_only_fields = ['sender', 'status', 'created_at']

class BuddyRespondSerializer(serializers.Serializer):
    request_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=['accepted', 'rejected'])

class CloseBuddySerializer(serializers.ModelSerializer):
    buddy_details = UserMinimalSerializer(source='buddy', read_only=True)

    class Meta:
        model = CloseBuddy
        fields = ['id', 'buddy', 'buddy_details']

    def validate(self, data):
        user = self.context['request'].user
        buddy = data['buddy']
        
        if user == buddy:
            raise serializers.ValidationError("You cannot add yourself as a close buddy.")
            
        # Check if already a Close Buddy
        if CloseBuddy.objects.filter(user=user, buddy=buddy).exists():
            raise serializers.ValidationError("This user is already in your inner circle.")

        return data

class PostApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostApproval
        fields = ['id', 'post', 'buddy', 'approved_at']
        read_only_fields = ['buddy', 'approved_at']

class VoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = ['id', 'post', 'user', 'value']
        read_only_fields = ['user']

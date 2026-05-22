from rest_framework import serializers
from .models import Follow, Buddy, CloseBuddy, CloseBuddyRequest, PostApproval, Vote, Favorite
from django.contrib.auth import get_user_model

User = get_user_model()


class UserMinimalSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile_picture']


# ─── Follow (One-way) ────────────────────────────────────────────────────────

class FollowSerializer(serializers.ModelSerializer):
    """Used to display who you follow or who follows you."""
    following_details = UserMinimalSerializer(source='following', read_only=True)
    follower_details = UserMinimalSerializer(source='follower', read_only=True)

    class Meta:
        model = Follow
        fields = ['id', 'follower', 'following', 'follower_details', 'following_details', 'created_at']
        read_only_fields = ['follower', 'created_at']


# ─── Buddy (Mutual Follows) ──────────────────────────────────────────────────

class BuddySerializer(serializers.ModelSerializer):
    user1_details = UserMinimalSerializer(source='user1', read_only=True)
    user2_details = UserMinimalSerializer(source='user2', read_only=True)

    class Meta:
        model = Buddy
        fields = ['id', 'user1', 'user2', 'user1_details', 'user2_details', 'created_at']


# ─── Close Buddy Request (Permission-based) ───────────────────────────────────

class CloseBuddyRequestSerializer(serializers.ModelSerializer):
    sender_details = UserMinimalSerializer(source='sender', read_only=True)
    receiver_details = UserMinimalSerializer(source='receiver', read_only=True)

    class Meta:
        model = CloseBuddyRequest
        fields = ['id', 'sender', 'receiver', 'sender_details', 'receiver_details', 'status', 'created_at']
        read_only_fields = ['sender', 'status', 'created_at']

    def validate(self, data):
        user = self.context['request'].user
        receiver = data['receiver']

        if user == receiver:
            raise serializers.ValidationError("You cannot send a close buddy request to yourself.")

        # Prerequisite: Must be mutual Buddies
        u1, u2 = sorted([user.id, receiver.id])
        if not Buddy.objects.filter(user1_id=u1, user2_id=u2).exists():
            raise serializers.ValidationError("You can only send close buddy requests to mutual buddies.")

        # Check existing requests (regardless of status) to avoid database IntegrityError due to UNIQUE constraint
        existing_request = CloseBuddyRequest.objects.filter(sender=user, receiver=receiver).first()
        if existing_request:
            if existing_request.status == 'pending':
                raise serializers.ValidationError("You already have a pending request to this user.")
            elif existing_request.status == 'accepted':
                raise serializers.ValidationError("This user is already in your inner circle.")
            else:
                raise serializers.ValidationError("A close buddy request has already been sent to this user.")

        # Check for reverse pending request (receiver has already requested sender)
        reverse_request = CloseBuddyRequest.objects.filter(sender=receiver, receiver=user, status='pending').exists()
        if reverse_request:
            raise serializers.ValidationError("This user has already sent you a close buddy request.")

        if CloseBuddy.objects.filter(user=user, buddy=receiver).exists():
            raise serializers.ValidationError("This user is already in your inner circle.")

        if CloseBuddy.objects.filter(user=user).count() >= 5:
            raise serializers.ValidationError("Your inner circle is full (max 5 close buddies).")

        return data


class CloseBuddyRespondSerializer(serializers.Serializer):
    request_id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=['accepted', 'rejected'])


# ─── Close Buddy (Inner Circle) ───────────────────────────────────────────────

class CloseBuddySerializer(serializers.ModelSerializer):
    buddy_details = UserMinimalSerializer(source='buddy', read_only=True)

    class Meta:
        model = CloseBuddy
        fields = ['id', 'buddy', 'buddy_details']


# ─── Post Approval ────────────────────────────────────────────────────────────

class PostApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = PostApproval
        fields = ['id', 'post', 'buddy', 'approved_at']
        read_only_fields = ['buddy', 'approved_at']


# ─── Vote ─────────────────────────────────────────────────────────────────────

class VoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vote
        fields = ['id', 'post', 'user', 'value']
        read_only_fields = ['user']


class FavoriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Favorite
        fields = ['id', 'post', 'user', 'created_at']
        read_only_fields = ['user', 'created_at']

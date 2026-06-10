from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Q
from .models import Follow, Buddy, CloseBuddy, CloseBuddyRequest, PostApproval, Vote, Favorite
from .serializers import (
    FollowSerializer, BuddySerializer,
    CloseBuddyRequestSerializer, CloseBuddyRespondSerializer,
    CloseBuddySerializer, ReverseCloseBuddySerializer,
    PostApprovalSerializer, VoteSerializer,
    FavoriteSerializer, UserMinimalSerializer, UserSearchSerializer
)
from django.contrib.auth import get_user_model
from apps.content.models import Post
from apps.content.serializers import PostSerializer
from apps.users.permissions import IsProfileComplete

User = get_user_model()


# ─── Follow (One-way) ────────────────────────────────────────────────────────

class FollowView(APIView):
    """
    POST   /api/social/follow/         → follow a user  { "user_id": <id> }
    DELETE /api/social/follow/         → unfollow a user  { "user_id": <id> }
    No permission from the target is needed.
    """
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def post(self, request):
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({"error": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        target = get_object_or_404(User, id=user_id)

        if target == request.user:
            return Response({"error": "You cannot follow yourself."}, status=status.HTTP_400_BAD_REQUEST)

        _, created = Follow.objects.get_or_create(follower=request.user, following=target)
        if not created:
            return Response({"message": f"You are already following {target.username}."}, status=status.HTTP_200_OK)

        return Response({"message": f"You are now following {target.username}."}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({"error": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        target = get_object_or_404(User, id=user_id)
        deleted, _ = Follow.objects.filter(follower=request.user, following=target).delete()
        if deleted:
            return Response({"message": f"You have unfollowed {target.username}."}, status=status.HTTP_200_OK)
        return Response({"error": "You are not following this user."}, status=status.HTTP_404_NOT_FOUND)


class FollowingListView(generics.ListAPIView):
    """
    GET /api/social/following/          → list of users YOU are following
    GET /api/social/following/<user_id>/ → list of users target user is following
    """
    serializer_class = UserMinimalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user_id = self.kwargs.get('user_id')
        target_user = self.request.user if user_id is None else get_object_or_404(User, id=user_id)
        return User.objects.filter(
            followers__follower=target_user
        ).order_by('username')


class FollowersListView(generics.ListAPIView):
    """
    GET /api/social/followers/        → list of users who are following YOU
    GET /api/social/followers/<user_id>/ → list of users who are following target user
    """
    serializer_class = UserMinimalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user_id = self.kwargs.get('user_id')
        target_user = self.request.user if user_id is None else get_object_or_404(User, id=user_id)
        return User.objects.filter(
            following__following=target_user
        ).order_by('username')


# ─── Buddy (Mutual) ──────────────────────────────────────────────────────────

class BuddyListView(generics.ListAPIView):
    """
    GET /api/social/buddies/          → list of users who are your mutual buddies
    """
    serializer_class = UserMinimalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Get users who are buddies with current user
        # user1_id or user2_id matches current user
        return User.objects.filter(
            Q(buddies_as_user1__user2=user) | 
            Q(buddies_as_user2__user1=user)
        ).order_by('username')


# ─── Close Buddy Request (Permission required) ────────────────────────────────

class SendCloseBuddyRequestView(generics.CreateAPIView):
    """
    POST /api/social/close-buddies/request/
    Body: { "receiver": <user_id> }
    Sends a request to add someone to your inner circle. They must accept.
    Only mutual buddies can send requests.
    """
    serializer_class = CloseBuddyRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)


class RespondCloseBuddyRequestView(APIView):
    """
    POST /api/social/close-buddies/respond/
    Body: { "request_id": <id>, "action": "accepted" | "rejected" }
    The RECEIVER accepts or rejects a close buddy request.
    On acceptance, a CloseBuddy entry is automatically created.
    """
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def post(self, request):
        serializer = CloseBuddyRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request_id = serializer.validated_data['request_id']
        action = serializer.validated_data['action']

        try:
            cbr = CloseBuddyRequest.objects.get(
                id=request_id, receiver=request.user, status='pending'
            )
        except CloseBuddyRequest.DoesNotExist:
            return Response(
                {"error": "Request not found or already processed."},
                status=status.HTTP_404_NOT_FOUND)

        cbr.status = action
        cbr.save()

        if action == 'accepted':
            # Guard: max 5 close buddies for the sender
            if CloseBuddy.objects.filter(user=cbr.sender).count() >= 5:
                cbr.status = 'rejected'
                cbr.save()
                return Response(
                    {"error": "Sender's inner circle is already full (max 5)."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            CloseBuddy.objects.get_or_create(user=cbr.sender, buddy=request.user)

        return Response({"message": f"Close buddy request {action}."}, status=status.HTTP_200_OK)


class IncomingCloseBuddyRequestsView(generics.ListAPIView):
    """
    GET /api/social/close-buddies/requests/
    Returns all pending close buddy requests sent TO the current user.
    """
    serializer_class = CloseBuddyRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def get_queryset(self):
        return CloseBuddyRequest.objects.filter(
            receiver=self.request.user, status='pending'
        ).order_by('-created_at')


class PendingSentCloseBuddyRequestsView(generics.ListAPIView):
    """
    GET /api/social/close-buddies/pending-sent/
    Returns all close buddy requests the current user sent that are still pending.
    """
    serializer_class = CloseBuddyRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def get_queryset(self):
        return CloseBuddyRequest.objects.filter(
            sender=self.request.user, status='pending'
        ).order_by('-created_at')


# ─── Close Buddy (Inner Circle) ───────────────────────────────────────────────

class CloseBuddyListView(generics.ListAPIView):
    """
    GET /api/social/close-buddies/
    Returns the current user's inner circle (up to 5 close buddies).
    """
    serializer_class = CloseBuddySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CloseBuddy.objects.filter(user=self.request.user)


class ReverseCloseBuddyListView(generics.ListAPIView):
    """
    GET /api/social/close-buddies/added-by/
    Returns users who have added the current user to their inner circle.
    """
    serializer_class = ReverseCloseBuddySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CloseBuddy.objects.filter(buddy=self.request.user)


class CloseBuddySuggestionsView(generics.ListAPIView):
    """
    GET /api/social/close-buddies/suggestions/
    Returns mutual buddies who are not yet close buddies and don't have pending requests.
    """
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def get_queryset(self):
        user = self.request.user
        # Mutual buddies
        buddies = User.objects.filter(
            Q(buddies_as_user1__user2=user) | 
            Q(buddies_as_user2__user1=user)
        )
        
        # Already close buddies
        already_close = CloseBuddy.objects.filter(user=user).values_list('buddy_id', flat=True)
        
        # Pending sent requests
        pending_sent = CloseBuddyRequest.objects.filter(sender=user, status='pending').values_list('receiver_id', flat=True)
        
        # Pending received requests
        pending_received = CloseBuddyRequest.objects.filter(receiver=user, status='pending').values_list('sender_id', flat=True)

        return buddies.exclude(
            id__in=already_close
        ).exclude(
            id__in=pending_sent
        ).exclude(
            id__in=pending_received
        ).order_by('username')


class RemoveCloseBuddyView(APIView):
    """
    DELETE /api/social/close-buddies/remove/
    Body: { "user_id": <id> }
    Removes a user from your inner circle.
    """
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def delete(self, request):
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({"error": "user_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        deleted, _ = CloseBuddy.objects.filter(user=request.user, buddy_id=user_id).delete()
        if deleted:
            return Response({"message": "User removed from your inner circle."}, status=status.HTTP_200_OK)
        return Response({"error": "This user is not in your inner circle."}, status=status.HTTP_404_NOT_FOUND)


# ─── Post Approval ────────────────────────────────────────────────────────────

class PostApprovalCreateView(generics.CreateAPIView):
    """
    POST /api/social/approve-post/
    Body: { "post": <post_id> }
    Allows a close buddy of the post's author to approve the post.
    Auto-activates the post when all close buddies have approved.
    """
    serializer_class = PostApprovalSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def perform_create(self, serializer):
        post = serializer.validated_data['post']
        user = self.request.user

        if not CloseBuddy.objects.filter(user=post.author, buddy=user).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Only close buddies of the author can approve this post.")

        if post.status != 'pending':
            from rest_framework.exceptions import ValidationError
            raise ValidationError("This post is not pending approval.")

        serializer.save(buddy=user)

        # Auto-activate when all close buddies have approved
        total_buddies = CloseBuddy.objects.filter(user=post.author).count()
        total_approvals = PostApproval.objects.filter(post=post).count() + 1
        if total_buddies > 0 and total_approvals >= total_buddies:
            post.status = 'active'
            post.save(update_fields=['status'])


# ─── Vote ─────────────────────────────────────────────────────────────────────

from django.db import transaction

class VoteCreateView(generics.CreateAPIView):
    """
    POST /api/social/vote/
    Body: { "post": <post_id>, "value": <1-5> }
    Records a rating for a post. If the user has already rated this post,
    the existing rating is updated to the new value.
    Returns the full updated post object.
    """
    serializer_class = VoteSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        post_obj = serializer.validated_data['post']
        value = serializer.validated_data['value']
        user = request.user

        with transaction.atomic():
            Vote.objects.update_or_create(
                user=user,
                post=post_obj,
                defaults={'value': value}
            )

        # Return full updated post data to help frontend sync state (avg_rating, etc.)
        updated_post = Post.objects.with_annotations(user).get(id=post_obj.id)
        post_serializer = PostSerializer(updated_post, context={'request': request})
        
        data = post_serializer.data
        data['message'] = "Vote recorded successfully."
        
        return Response(data, status=status.HTTP_201_CREATED)


class FavoriteToggleView(APIView):
    """
    POST /api/social/favorite/
    Body: { "post": <post_id> }
    Toggles a post as favorite for the current user.
    Returns whether the post is now favorited or not.
    """
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def post(self, request):
        post_id = request.data.get('post')
        if not post_id:
            return Response({"error": "post ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        post = get_object_or_404(Post, id=post_id)
        favorite, created = Favorite.objects.get_or_create(user=request.user, post=post)

        if not created:
            favorite.delete()
            msg = "Removed from favorites."
            status_code = status.HTTP_200_OK
        else:
            msg = "Added to favorites."
            status_code = status.HTTP_201_CREATED

        # Return full updated post data to help frontend sync state
        updated_post = Post.objects.with_annotations(request.user).get(id=post.id)
        serializer = PostSerializer(updated_post, context={'request': request})
        
        data = serializer.data
        data['message'] = msg # For StandardizedJSONRenderer
        
        return Response(data, status=status_code)


# ─── Unapproved Posts from Close Buddies ──────────────────────────────────────

class UnapprovedBuddyPostsView(generics.ListAPIView):
    """
    GET /api/social/close-buddies/unapproved-posts/
    Returns posts from close buddies that are pending and not yet approved by the current user.
    """
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def get_queryset(self):
        user = self.request.user
        # Find users who have added ME to their inner circle
        authors_who_added_me = CloseBuddy.objects.filter(buddy=user).values_list('user_id', flat=True)
        already_approved_post_ids = PostApproval.objects.filter(buddy=user).values_list('post_id', flat=True)

        return Post.objects.filter(
            author__in=authors_who_added_me,
            status='pending',
            is_media_deleted=False
        ).exclude(
            id__in=already_approved_post_ids
        ).order_by('-created_at')


# ─── User Search ──────────────────────────────────────────────────────────────

class UserSearchView(generics.ListAPIView):
    """
    GET /api/users/search/?q=<query>
    Search users by username, first_name, or last_name.
    """
    serializer_class = UserSearchSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        query = self.request.query_params.get('q', '').strip()
        if not query:
            return User.objects.none()
        return User.objects.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query),
            is_active=True
        ).exclude(id=self.request.user.id).order_by('username')[:30]


class RejectedCloseBuddyRequestsView(generics.ListAPIView):
    """
    GET /api/social/close-buddies/requests/rejected/
    Returns all rejected close buddy requests sent TO the current user.
    """
    serializer_class = CloseBuddyRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def get_queryset(self):
        return CloseBuddyRequest.objects.filter(
            receiver=self.request.user, status='rejected'
        ).order_by('-created_at')


class IgnoredCloseBuddyRequestsView(generics.ListAPIView):
    """
    GET /api/social/close-buddies/requests/ignored/
    Returns all ignored close buddy requests sent TO the current user.
    """
    serializer_class = CloseBuddyRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def get_queryset(self):
        return CloseBuddyRequest.objects.filter(
            receiver=self.request.user, status='ignored'
        ).order_by('-created_at')

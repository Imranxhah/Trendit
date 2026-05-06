from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from .models import CloseBuddy, PostApproval, Vote, BuddyRequest
from .serializers import (
    BuddyRequestSerializer, BuddyRespondSerializer, 
    CloseBuddySerializer, PostApprovalSerializer, VoteSerializer,
    UserMinimalSerializer
)
from django.contrib.auth import get_user_model
from apps.content.models import Post
from apps.content.serializers import PostSerializer

User = get_user_model()

class SendBuddyRequestView(generics.CreateAPIView):
    serializer_class = BuddyRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)

class RespondBuddyRequestView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BuddyRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        request_id = serializer.validated_data['request_id']
        action = serializer.validated_data['action']
        
        try:
            buddy_req = BuddyRequest.objects.get(id=request_id, receiver=request.user, status='pending')
            buddy_req.status = action
            buddy_req.save()
            return Response({"message": f"Request {action}."}, status=status.HTTP_200_OK)
        except BuddyRequest.DoesNotExist:
            return Response({"error": "Request not found or already processed."}, status=status.HTTP_404_NOT_FOUND)

class IncomingRequestsView(generics.ListAPIView):
    serializer_class = BuddyRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return BuddyRequest.objects.filter(receiver=self.request.user, status='pending')

class BuddyListView(generics.ListAPIView):
    serializer_class = UserMinimalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Mutual buddies are those where a request was accepted (either sent or received by user)
        accepted_requests = BuddyRequest.objects.filter(
            (Q(sender=user) | Q(receiver=user)),
            status='accepted'
        )
        buddy_ids = []
        for req in accepted_requests:
            if req.sender == user:
                buddy_ids.append(req.receiver.id)
            else:
                buddy_ids.append(req.sender.id)
        return User.objects.filter(id__in=buddy_ids)

class CloseBuddyListCreateView(generics.ListCreateAPIView):
    serializer_class = CloseBuddySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return CloseBuddy.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        buddy = serializer.validated_data['buddy']
        user = self.request.user
        
        # Logic: Auto-create Buddy connection if adding to Close Buddy
        # We ensure a 'BuddyRequest' exists and is 'accepted'
        BuddyRequest.objects.update_or_create(
            sender=user, receiver=buddy,
            defaults={'status': 'accepted'}
        )
        # Also ensure the reverse if we want mutual (though the above covers the connection)
        
        serializer.save(user=user)

class PostApprovalCreateView(generics.CreateAPIView):
    """
    POST /api/social/approve-post/
    Body: { "post": <post_id> }
    Allows a close buddy of the post's author to approve (vote the post into Active).
    Only close buddies of the author can call this. Each buddy can approve once per post.
    """
    serializer_class = PostApprovalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        post = serializer.validated_data['post']
        user = self.request.user

        # Guard: caller must be a close buddy of the post author
        if not CloseBuddy.objects.filter(user=post.author, buddy=user).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError("Only close buddies of the author can approve this post.")

        # Guard: post must be in pending state
        if post.status != 'pending':
            from rest_framework.exceptions import ValidationError
            raise ValidationError("This post is not pending approval.")

        serializer.save(buddy=user)

        # Auto-activate: if all 5 close buddies (or however many exist) have approved, mark as active
        total_buddies = CloseBuddy.objects.filter(user=post.author).count()
        total_approvals = PostApproval.objects.filter(post=post).count() + 1  # +1 for current
        if total_buddies > 0 and total_approvals >= total_buddies:
            post.status = 'active'
            post.save(update_fields=['status'])


class VoteCreateView(generics.CreateAPIView):
    serializer_class = VoteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


# ─── New Endpoints ────────────────────────────────────────────────────────────

class UnapprovedBuddyPostsView(generics.ListAPIView):
    """
    GET /api/social/close-buddies/unapproved-posts/
    Returns all posts authored by the current user's close buddies
    that are still in 'pending' status AND have NOT yet been approved by the current user.
    Auth required.
    """
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # IDs of users who are in this user's close buddy list
        close_buddy_ids = CloseBuddy.objects.filter(
            user=user
        ).values_list('buddy_id', flat=True)

        # IDs of posts the current user has already approved
        already_approved_post_ids = PostApproval.objects.filter(
            buddy=user
        ).values_list('post_id', flat=True)

        # Pending posts by close buddies that this user hasn't approved yet
        return Post.objects.filter(
            author__in=close_buddy_ids,
            status='pending',
            is_media_deleted=False
        ).exclude(
            id__in=already_approved_post_ids
        ).order_by('-created_at')


class UserSearchView(generics.ListAPIView):
    """
    GET /api/users/search/?q=<query>
    Smart search: matches users whose username, first_name, or last_name
    contains the query string (case-insensitive). Returns minimal user info.
    Auth required.
    """
    serializer_class = UserMinimalSerializer
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


class PendingSentRequestsView(generics.ListAPIView):
    """
    GET /api/social/buddies/pending-sent/
    Returns all buddy requests that the current user has SENT
    and are still in 'pending' status (not accepted or rejected yet).
    Auth required.
    """
    serializer_class = BuddyRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return BuddyRequest.objects.filter(
            sender=self.request.user,
            status='pending'
        ).order_by('-created_at')

import hashlib
import math
import secrets
from datetime import timedelta
from html import escape
from urllib.parse import quote

from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from .models import (
    Follow, Buddy, CloseBuddy, CloseBuddyRequest, PostApproval, Vote, Favorite,
    SubPostVote, Community, CommunityMembership, CommunityInvite
)
from .serializers import (
    FollowSerializer, BuddySerializer,
    CloseBuddyRequestSerializer, CloseBuddyRespondSerializer,
    CloseBuddySerializer, ReverseCloseBuddySerializer,
    PostApprovalSerializer, VoteSerializer,
    FavoriteSerializer, UserMinimalSerializer, UserSearchSerializer,
    SubPostVoteSerializer, CommunitySerializer
)
from django.contrib.auth import get_user_model
from apps.content.models import Post, SubPost
from apps.content.serializers import PostSerializer, SubPostSerializer
from apps.users.permissions import IsProfileComplete
from apps.core.fcm_utils import send_push_notification
from apps.core.models import Notification
from django.contrib.contenttypes.models import ContentType

User = get_user_model()


def _community_queryset_for(user):
    membership = CommunityMembership.objects.filter(
        community_id=OuterRef('pk'),
        user=user,
    )
    return (
        Community.objects.select_related('creator')
        .annotate(
            user_is_member=Exists(membership),
            members_count=Count('memberships', distinct=True),
        )
        .filter(
            Q(is_private=False) | Q(creator=user) | Q(user_is_member=True)
        )
    )


def _request_coordinates(request):
    raw_latitude = request.query_params.get('latitude')
    raw_longitude = request.query_params.get('longitude')
    if raw_latitude is None and raw_longitude is None:
        return None
    if raw_latitude is None or raw_longitude is None:
        raise ValidationError("Latitude and longitude must be provided together.")
    try:
        latitude = float(raw_latitude)
        longitude = float(raw_longitude)
    except (TypeError, ValueError):
        raise ValidationError("Latitude and longitude must be valid numbers.")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValidationError("Latitude or longitude is outside the valid range.")
    return latitude, longitude


def _distance_km(origin_latitude, origin_longitude, community):
    if community.latitude is None or community.longitude is None:
        return None
    latitude = math.radians(float(community.latitude))
    longitude = math.radians(float(community.longitude))
    origin_latitude = math.radians(origin_latitude)
    origin_longitude = math.radians(origin_longitude)
    delta_latitude = latitude - origin_latitude
    delta_longitude = longitude - origin_longitude
    haversine = (
        math.sin(delta_latitude / 2) ** 2
        + math.cos(origin_latitude)
        * math.cos(latitude)
        * math.sin(delta_longitude / 2) ** 2
    )
    return round(6371.0088 * 2 * math.asin(math.sqrt(haversine)), 1)


def _rank_communities(queryset, request):
    communities = list(queryset)
    coordinates = _request_coordinates(request)
    if coordinates is None:
        communities.sort(
            key=lambda community: (
                -community.members_count,
                community.name.casefold(),
            )
        )
        return communities

    for community in communities:
        community.distance_km = _distance_km(*coordinates, community)
    communities.sort(
        key=lambda community: (
            community.distance_km is None,
            community.distance_km if community.distance_km is not None else math.inf,
            -community.members_count,
            community.name.casefold(),
        )
    )
    return communities


def _invite_hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


class IsCommunityCreator(permissions.BasePermission):
    message = "Only the community creator can manage this community."

    def has_object_permission(self, request, view, obj):
        return obj.creator_id == request.user.id


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

        # Trigger notification
        Notification.objects.create(
            recipient=target,
            actor=request.user,
            verb='started following you',
            content_type=ContentType.objects.get_for_model(User),
            object_id=request.user.id
        )
        send_push_notification(
            user=target,
            title="New Follower",
            body=f"{request.user.username} started following you.",
            data={"type": "follow", "target_id": str(request.user.id)},
            trigger_user=request.user
        )

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
        cbr = serializer.save(sender=self.request.user)
        
        # Trigger notification
        Notification.objects.create(
            recipient=cbr.receiver,
            actor=self.request.user,
            verb='sent you a close buddy request',
            content_type=ContentType.objects.get_for_model(User),
            object_id=self.request.user.id
        )
        send_push_notification(
            user=cbr.receiver,
            title="Close Buddy Request",
            body=f"{self.request.user.username} sent you a close buddy request.",
            data={"type": "close_buddy_request", "target_id": str(self.request.user.id), "request_id": str(cbr.id)},
            trigger_user=self.request.user
        )

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
            
            # Trigger notification to the sender that their request was accepted
            Notification.objects.create(
                recipient=cbr.sender,
                actor=request.user,
                verb='accepted your close buddy request',
                content_type=ContentType.objects.get_for_model(User),
                object_id=request.user.id
            )
            send_push_notification(
                user=cbr.sender,
                title="Request Accepted",
                body=f"{request.user.username} accepted your close buddy request.",
                data={"type": "close_buddy_accepted", "target_id": str(request.user.id)},
                trigger_user=request.user
            )

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
            
        # Trigger notification to the author that someone approved it
        Notification.objects.create(
            recipient=post.author,
            actor=user,
            verb='approved your post',
            content_type=ContentType.objects.get_for_model(Post),
            object_id=post.id
        )
        post_thumbnail = getattr(post, 'thumbnail', None)
        data_payload = {"type": "post_approval", "target_id": str(post.id)}
        if post_thumbnail and hasattr(post_thumbnail, 'url'):
            data_payload['post_image'] = post_thumbnail.url

        send_push_notification(
            user=post.author,
            title="Post Approved",
            body=f"{user.username} approved your recent post.",
            data=data_payload,
            trigger_user=user
        )


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

        if post_obj.author != user:
            # Trigger notification
            Notification.objects.get_or_create(
                recipient=post_obj.author,
                actor=user,
                verb='rated your post',
                content_type=ContentType.objects.get_for_model(Post),
                object_id=post_obj.id
            )
            send_push_notification(
                user=post_obj.author,
                title="New Rating",
                body=f"{user.username} rated your post.",
                data={"type": "like", "target_id": str(post_obj.id)},
                trigger_user=user
            )

        # Return full updated post data to help frontend sync state (avg_rating, etc.)
        updated_post = Post.objects.with_annotations(user).get(id=post_obj.id)
        post_serializer = PostSerializer(updated_post, context={'request': request})
        
        data = post_serializer.data
        data['message'] = "Vote recorded successfully."
        
        return Response(data, status=status.HTTP_201_CREATED)


class SubPostVoteCreateView(generics.CreateAPIView):
    """
    POST /api/social/vote-subpost/
    Body: { "sub_post": <sub_post_id>, "value": <1-5> }
    """
    serializer_class = SubPostVoteSerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        sub_post_obj = serializer.validated_data['sub_post']
        value = serializer.validated_data['value']
        user = request.user

        with transaction.atomic():
            SubPostVote.objects.update_or_create(
                user=user,
                sub_post=sub_post_obj,
                defaults={'value': value}
            )

        if sub_post_obj.author != user:
            Notification.objects.get_or_create(
                recipient=sub_post_obj.author,
                actor=user,
                verb='rated your comment',
                content_type=ContentType.objects.get_for_model(SubPost),
                object_id=sub_post_obj.id
            )
            send_push_notification(
                user=sub_post_obj.author,
                title="New Rating",
                body=f"{user.username} rated your comment.",
                data={"type": "like", "target_id": str(sub_post_obj.parent_post.id)},
                trigger_user=user
            )

        updated_sub_post = SubPost.objects.with_annotations(user).get(id=sub_post_obj.id)
        sub_post_serializer = SubPostSerializer(updated_sub_post, context={'request': request})
        
        data = sub_post_serializer.data
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


# Community

class CommunityListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/social/communities/
    POST /api/social/communities/  Body: { "name": "Community name" }
    Creates a community and automatically joins the creator as the first member.
    """
    serializer_class = CommunitySerializer
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        return _rank_communities(
            _community_queryset_for(self.request.user),
            self.request,
        )

    def perform_create(self, serializer):
        community = serializer.save(creator=self.request.user)
        CommunityMembership.objects.get_or_create(
            community=community,
            user=self.request.user
        )


class CommunitySearchView(generics.ListAPIView):
    """
    GET /api/social/communities/search/?q=<query>
    Search communities by community name.
    """
    serializer_class = CommunitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        query = self.request.query_params.get('q', '').strip()
        if not query:
            return Community.objects.none()
        return _rank_communities(
            _community_queryset_for(self.request.user).filter(
                name__icontains=query
            ),
            self.request,
        )[:30]


class CommunityDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/social/communities/<community_id>/
    PATCH  /api/social/communities/<community_id>/  Body: name/profile_picture
    DELETE /api/social/communities/<community_id>/
    Any visible community can be read. Only the creator can edit or delete it.
    """
    serializer_class = CommunitySerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    lookup_field = 'id'
    lookup_url_kwarg = 'community_id'

    def get_permissions(self):
        permission_classes = [permissions.IsAuthenticated, IsProfileComplete]
        if self.request.method not in permissions.SAFE_METHODS:
            permission_classes.append(IsCommunityCreator)
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        return _community_queryset_for(self.request.user)


class CommunityJoinView(APIView):
    """
    POST   /api/social/communities/<community_id>/join/  joins a community.
    DELETE /api/social/communities/<community_id>/join/  leaves a community.
    """
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def post(self, request, community_id):
        community = get_object_or_404(Community, id=community_id)
        if community.is_private and not CommunityMembership.objects.filter(
            community=community,
            user=request.user,
        ).exists():
            raise PermissionDenied(
                "This community is private. Join it using a valid invite link."
            )
        _, created = CommunityMembership.objects.get_or_create(
            community=community,
            user=request.user
        )
        serializer = CommunitySerializer(
            Community.objects.select_related('creator').annotate(
                members_count=Count('memberships')
            ).get(id=community.id),
            context={'request': request}
        )
        message = "Joined community successfully." if created else "You are already a member of this community."
        data = serializer.data
        data['message'] = message
        return Response(data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request, community_id):
        community = get_object_or_404(Community, id=community_id)
        deleted, _ = CommunityMembership.objects.filter(
            community=community,
            user=request.user
        ).delete()
        if not deleted:
            return Response(
                {"error": "You are not a member of this community."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = CommunitySerializer(
            Community.objects.select_related('creator').annotate(
                members_count=Count('memberships')
            ).get(id=community.id),
            context={'request': request}
        )
        data = serializer.data
        data['message'] = "Left community successfully."
        return Response(data, status=status.HTTP_200_OK)


class CommunityLocationContextView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def get(self, request):
        phone = request.user.phone_number
        country_code = None
        if phone:
            try:
                from phonenumbers import parse as parse_phone_number
                from phonenumbers import region_code_for_number

                country_code = region_code_for_number(
                    parse_phone_number(str(phone))
                )
            except Exception:
                country_code = None
        if not country_code:
            raise ValidationError(
                "A valid international phone number is required."
            )
        return Response({'country_code': country_code})


class CommunityInviteCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def post(self, request, community_id):
        community = get_object_or_404(Community, id=community_id)
        if community.creator_id != request.user.id:
            raise PermissionDenied(
                "Only the community creator can create invite links."
            )

        token = secrets.token_urlsafe(32)
        ttl_hours = getattr(settings, 'COMMUNITY_INVITE_TTL_HOURS', 168)
        CommunityInvite.objects.create(
            community=community,
            token_hash=_invite_hash(token),
            created_by=request.user,
            expires_at=timezone.now() + timedelta(hours=ttl_hours),
        )
        invite_url = request.build_absolute_uri(
            f'/community-invite/{token}'
        )
        return Response(
            {
                'invite_url': invite_url,
                'expires_in_hours': ttl_hours,
                'single_use': True,
            },
            status=status.HTTP_201_CREATED,
        )


class CommunityInviteView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsProfileComplete]

    def _get_valid_invite(self, token, for_update=False):
        queryset = CommunityInvite.objects.select_related(
            'community', 'community__creator'
        )
        if for_update:
            queryset = queryset.select_for_update()
        invite = get_object_or_404(queryset, token_hash=_invite_hash(token))
        if invite.consumed_at is not None:
            raise ValidationError("This invite link has already been used.")
        if invite.expires_at <= timezone.now():
            raise ValidationError("This invite link has expired.")
        return invite

    def get(self, request, token):
        invite = self._get_valid_invite(token)
        community = _community_queryset_for(request.user).filter(
            id=invite.community_id
        ).first()
        if community is None:
            community = (
                Community.objects.select_related('creator')
                .annotate(members_count=Count('memberships', distinct=True))
                .get(id=invite.community_id)
            )
            community.user_is_member = False
        serializer = CommunitySerializer(
            community,
            context={'request': request},
        )
        return Response(serializer.data)

    @transaction.atomic
    def post(self, request, token):
        invite = self._get_valid_invite(token, for_update=True)
        CommunityMembership.objects.get_or_create(
            community=invite.community,
            user=request.user,
        )
        invite.consumed_at = timezone.now()
        invite.consumed_by = request.user
        invite.save(update_fields=['consumed_at', 'consumed_by'])

        community = _community_queryset_for(request.user).get(
            id=invite.community_id
        )
        data = CommunitySerializer(
            community,
            context={'request': request},
        ).data
        data['message'] = f"Joined {community.name}."
        return Response(data, status=status.HTTP_201_CREATED)


def community_invite_landing(request, token):
    safe_token = quote(token, safe='')
    app_uri = escape(
        f'trendit://skorpion.pythonanywhere.com/community-invite/{safe_token}',
        quote=True,
    )
    return HttpResponse(
        '<!doctype html><html><head>'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<meta http-equiv="refresh" content="0;url={app_uri}">'
        '<title>Open Trendit</title></head>'
        '<body style="font-family:sans-serif;text-align:center;padding:48px">'
        '<h1>Open Trendit</h1><p>This invite opens in the Trendit app.</p>'
        f'<p><a href="{app_uri}">Continue to Trendit</a></p>'
        '</body></html>'
    )


def android_asset_links(request):
    fingerprints = getattr(
        settings,
        'ANDROID_APP_SHA256_CERT_FINGERPRINTS',
        [],
    )
    return JsonResponse(
        [
            {
                'relation': ['delegate_permission/common.handle_all_urls'],
                'target': {
                    'namespace': 'android_app',
                    'package_name': 'com.imranshah.trendit',
                    'sha256_cert_fingerprints': fingerprints,
                },
            }
        ],
        safe=False,
    )


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

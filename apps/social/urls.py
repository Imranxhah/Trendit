from django.urls import path
from .views import (
    # Follow (One-way)
    FollowView, FollowingListView, FollowersListView,
    
    # Buddy (Mutual)
    BuddyListView,

    # Close Buddy Requests (permission-based)
    SendCloseBuddyRequestView, RespondCloseBuddyRequestView,
    IncomingCloseBuddyRequestsView, PendingSentCloseBuddyRequestsView,
    RejectedCloseBuddyRequestsView, IgnoredCloseBuddyRequestsView,

    # Close Buddy (Inner Circle)
    CloseBuddyListView, ReverseCloseBuddyListView, CloseBuddySuggestionsView,
    RemoveCloseBuddyView,

    # Interactions
    PostApprovalCreateView, VoteCreateView, FavoriteToggleView, SubPostVoteCreateView,

    # Extra
    UnapprovedBuddyPostsView, UserSearchView,
    CommunityListCreateView, CommunitySearchView, CommunityDetailView,
    CommunityJoinView, CommunityLocationContextView,
    CommunityInviteCreateView, CommunityInviteView,
)

urlpatterns = [
    # ── Follow (no permission needed) ────────────────────────────────────────
    path('follow/', FollowView.as_view(), name='follow'),
    path('following/', FollowingListView.as_view(), name='following-list'),
    path('following/<int:user_id>/', FollowingListView.as_view(), name='user-following-list'),
    path('followers/', FollowersListView.as_view(), name='follower-list'),
    path('followers/<int:user_id>/', FollowersListView.as_view(), name='user-follower-list'),

    # ── Buddy (Mutual Follows) ───────────────────────────────────────────────
    path('buddies/', BuddyListView.as_view(), name='buddy-list'),

    # ── Close Buddy Requests (permission required) ────────────────────────────
    path('close-buddies/request/', SendCloseBuddyRequestView.as_view(), name='close-buddy-request-send'),
    path('close-buddies/respond/', RespondCloseBuddyRequestView.as_view(), name='close-buddy-request-respond'),
    path('close-buddies/requests/', IncomingCloseBuddyRequestsView.as_view(), name='close-buddy-request-list'),
    path('close-buddies/requests/rejected/', RejectedCloseBuddyRequestsView.as_view(), name='close-buddy-requests-rejected'),
    path('close-buddies/requests/ignored/', IgnoredCloseBuddyRequestsView.as_view(), name='close-buddy-requests-ignored'),
    path('close-buddies/pending-sent/', PendingSentCloseBuddyRequestsView.as_view(), name='close-buddy-pending-sent'),

    # ── Close Buddy (Inner Circle) ────────────────────────────────────────────
    path('close-buddies/', CloseBuddyListView.as_view(), name='close-buddy-list'),
    path('close-buddies/added-by/', ReverseCloseBuddyListView.as_view(), name='close-buddy-added-by'),
    path('close-buddies/suggestions/', CloseBuddySuggestionsView.as_view(), name='close-buddy-suggestions'),
    path('close-buddies/remove/', RemoveCloseBuddyView.as_view(), name='close-buddy-remove'),
    path('close-buddies/unapproved-posts/', UnapprovedBuddyPostsView.as_view(), name='close-buddy-unapproved-posts'),

    # ── Interactions ─────────────────────────────────────────────────────────
    path('approve-post/', PostApprovalCreateView.as_view(), name='post-approval'),
    path('vote/', VoteCreateView.as_view(), name='vote'),
    path('vote-subpost/', SubPostVoteCreateView.as_view(), name='vote-subpost'),
    path('favorite/', FavoriteToggleView.as_view(), name='favorite-toggle'),

    # ── Search (social context) ───────────────────────────────────────────────
    path('users/search/', UserSearchView.as_view(), name='user-search'),
    path('communities/', CommunityListCreateView.as_view(), name='community-list-create'),
    path('communities/search/', CommunitySearchView.as_view(), name='community-search'),
    path('communities/location-context/', CommunityLocationContextView.as_view(), name='community-location-context'),
    path('communities/<int:community_id>/', CommunityDetailView.as_view(), name='community-detail'),
    path('communities/<int:community_id>/join/', CommunityJoinView.as_view(), name='community-join'),
    path('communities/<int:community_id>/invites/', CommunityInviteCreateView.as_view(), name='community-invite-create'),
    path('community-invites/<str:token>/', CommunityInviteView.as_view(), name='community-invite'),
]

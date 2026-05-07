from django.urls import path
from .views import (
    # Follow (One-way)
    FollowView, FollowingListView, FollowersListView,
    
    # Buddy (Mutual)
    BuddyListView,

    # Close Buddy Requests (permission-based)
    SendCloseBuddyRequestView, RespondCloseBuddyRequestView,
    IncomingCloseBuddyRequestsView, PendingSentCloseBuddyRequestsView,

    # Close Buddy (Inner Circle)
    CloseBuddyListView, RemoveCloseBuddyView,

    # Interactions
    PostApprovalCreateView, VoteCreateView,

    # Extra
    UnapprovedBuddyPostsView, UserSearchView,
)

urlpatterns = [
    # ── Follow (no permission needed) ────────────────────────────────────────
    path('follow/', FollowView.as_view(), name='follow'),
    path('following/', FollowingListView.as_view(), name='following-list'),
    path('followers/', FollowersListView.as_view(), name='follower-list'),

    # ── Buddy (Mutual Follows) ───────────────────────────────────────────────
    path('buddies/', BuddyListView.as_view(), name='buddy-list'),

    # ── Close Buddy Requests (permission required) ────────────────────────────
    path('close-buddies/request/', SendCloseBuddyRequestView.as_view(), name='close-buddy-request-send'),
    path('close-buddies/respond/', RespondCloseBuddyRequestView.as_view(), name='close-buddy-request-respond'),
    path('close-buddies/requests/', IncomingCloseBuddyRequestsView.as_view(), name='close-buddy-request-list'),
    path('close-buddies/pending-sent/', PendingSentCloseBuddyRequestsView.as_view(), name='close-buddy-pending-sent'),

    # ── Close Buddy (Inner Circle) ────────────────────────────────────────────
    path('close-buddies/', CloseBuddyListView.as_view(), name='close-buddy-list'),
    path('close-buddies/remove/', RemoveCloseBuddyView.as_view(), name='close-buddy-remove'),
    path('close-buddies/unapproved-posts/', UnapprovedBuddyPostsView.as_view(), name='close-buddy-unapproved-posts'),

    # ── Interactions ─────────────────────────────────────────────────────────
    path('approve-post/', PostApprovalCreateView.as_view(), name='post-approval'),
    path('vote/', VoteCreateView.as_view(), name='vote'),

    # ── Search (social context) ───────────────────────────────────────────────
    path('users/search/', UserSearchView.as_view(), name='user-search'),
]

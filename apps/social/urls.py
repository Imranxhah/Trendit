from django.urls import path
from .views import (
    SendBuddyRequestView, RespondBuddyRequestView, IncomingRequestsView,
    BuddyListView, CloseBuddyListCreateView, PostApprovalCreateView, VoteCreateView
)

urlpatterns = [
    # General Buddies
    path('buddies/request/', SendBuddyRequestView.as_view(), name='buddy-request-send'),
    path('buddies/respond/', RespondBuddyRequestView.as_view(), name='buddy-request-respond'),
    path('buddies/requests/', IncomingRequestsView.as_view(), name='buddy-request-list'),
    path('buddies/list/', BuddyListView.as_view(), name='buddy-list'),
    
    # Close Buddies
    path('close-buddies/', CloseBuddyListCreateView.as_view(), name='close-buddy-list'),
    
    # Interactions
    path('approve-post/', PostApprovalCreateView.as_view(), name='post-approval'),
    path('vote/', VoteCreateView.as_view(), name='vote'),
]

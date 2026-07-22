from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import (
    Follow, Buddy, CloseBuddy, CloseBuddyRequest, PostApproval, Vote,
    Community, CommunityMembership, CommunityInvite
)

@admin.register(Follow)
class FollowAdmin(ModelAdmin):
    list_display = ('follower', 'following', 'created_at')
    search_fields = ('follower__username', 'following__username')

@admin.register(Buddy)
class BuddyAdmin(ModelAdmin):
    list_display = ('user1', 'user2', 'created_at')
    search_fields = ('user1__username', 'user2__username')

@admin.register(CloseBuddyRequest)
class CloseBuddyRequestAdmin(ModelAdmin):
    list_display = ('sender', 'receiver', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('sender__username', 'receiver__username')

@admin.register(CloseBuddy)
class CloseBuddyAdmin(ModelAdmin):
    list_display = ('user', 'buddy')
    search_fields = ('user__username', 'buddy__username')

@admin.register(PostApproval)
class PostApprovalAdmin(ModelAdmin):
    list_display = ('post', 'buddy', 'approved_at')

@admin.register(Vote)
class VoteAdmin(ModelAdmin):
    list_display = ('post', 'user', 'value')


@admin.register(Community)
class CommunityAdmin(ModelAdmin):
    list_display = (
        'name', 'creator', 'is_private', 'latitude', 'longitude', 'created_at'
    )
    list_filter = ('is_private',)
    search_fields = ('name', 'creator__username')


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(ModelAdmin):
    list_display = ('community', 'user', 'joined_at')
    search_fields = ('community__name', 'user__username')


@admin.register(CommunityInvite)
class CommunityInviteAdmin(ModelAdmin):
    list_display = (
        'community', 'created_by', 'created_at', 'expires_at', 'consumed_at'
    )
    search_fields = ('community__name', 'created_by__username')
    readonly_fields = ('token_hash', 'created_at', 'consumed_at', 'consumed_by')

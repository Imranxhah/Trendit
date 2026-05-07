from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Follow, Buddy, CloseBuddy, CloseBuddyRequest, PostApproval, Vote

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

from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import CloseBuddy, PostApproval, Vote, BuddyRequest

@admin.register(CloseBuddy)
class CloseBuddyAdmin(ModelAdmin):
    list_display = ('user', 'buddy')

@admin.register(PostApproval)
class PostApprovalAdmin(ModelAdmin):
    list_display = ('post', 'buddy', 'approved_at')

@admin.register(Vote)
class VoteAdmin(ModelAdmin):
    list_display = ('post', 'user', 'value')

@admin.register(BuddyRequest)
class BuddyRequestAdmin(ModelAdmin):
    list_display = ('sender', 'receiver', 'status', 'created_at')

from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import CaptionModerationEvent, Category, Post, SubPost

@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ('name', 'slug', 'priority_status', 'priority_multiplier')
    list_filter = ('priority_status',)
    search_fields = ('name',)

@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ('author', 'status', 'created_at', 'is_media_deleted')
    list_filter = ('status', 'is_media_deleted', 'categories')
    search_fields = ('author__username', 'caption')
    filter_horizontal = ('categories',)

@admin.register(SubPost)
class SubPostAdmin(ModelAdmin):
    list_display = ('author', 'parent_post', 'created_at')
    search_fields = ('author__username', 'caption')


@admin.register(CaptionModerationEvent)
class CaptionModerationEventAdmin(ModelAdmin):
    list_display = ('user', 'decision', 'model_version', 'created_at')
    list_filter = ('decision', 'model_version', 'created_at')
    search_fields = ('user__username', 'caption_fingerprint')
    readonly_fields = (
        'user', 'post', 'caption_fingerprint', 'model_version',
        'decision', 'scores', 'reasons', 'created_at',
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

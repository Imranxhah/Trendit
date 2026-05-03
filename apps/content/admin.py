from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import Category, Post, SubPost

@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name',)

@admin.register(Post)
class PostAdmin(ModelAdmin):
    list_display = ('author', 'category', 'status', 'created_at', 'is_media_deleted')
    list_filter = ('status', 'is_media_deleted', 'category')
    search_fields = ('author__username', 'caption')

@admin.register(SubPost)
class SubPostAdmin(ModelAdmin):
    list_display = ('author', 'parent_post', 'created_at')
    search_fields = ('author__username', 'caption')

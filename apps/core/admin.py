from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import AppSettings, Notification, Report

@admin.register(AppSettings)
class AppSettingsAdmin(ModelAdmin):
    list_display = ('upload_start_time', 'upload_end_time')

@admin.register(Notification)
class NotificationAdmin(ModelAdmin):
    list_display = ('recipient', 'actor', 'verb', 'created_at', 'read_status')
    list_filter = ('read_status',)

@admin.register(Report)
class ReportAdmin(ModelAdmin):
    list_display = ('reporter', 'status', 'created_at')
    list_filter = ('status',)

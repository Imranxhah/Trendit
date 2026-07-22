from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import messages
from unfold.admin import ModelAdmin
from .models import ChatReport, User, Profile, UserDevice, OTPVerification, UserViolation


# --- Custom Admin Actions ---

@admin.action(description="🚫 Ban selected users")
def ban_users(modeladmin, request, queryset):
    updated = queryset.filter(is_banned=False).update(is_banned=True)
    modeladmin.message_user(request, f"{updated} user(s) have been banned.", messages.WARNING)


@admin.action(description="✅ Unban selected users")
def unban_users(modeladmin, request, queryset):
    updated = queryset.filter(is_banned=True).update(is_banned=False, ban_reason=None)
    modeladmin.message_user(request, f"{updated} user(s) have been unbanned.", messages.SUCCESS)


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):
    list_display = ('username', 'email', 'phone_number', 'is_verified', 'is_banned', 'is_staff', 'date_joined')
    list_filter = ('is_verified', 'is_banned', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email', 'phone_number')
    actions = [ban_users, unban_users]

    # Add extra fields to the user detail/edit form
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Extra Profile Data', {
            'fields': ('phone_number', 'profile_picture'),
        }),
        ('Account Status', {
            'fields': ('is_verified', 'is_banned', 'ban_reason'),
        }),
    )
    readonly_fields = ('date_joined', 'last_login')


@admin.register(Profile)
class ProfileAdmin(ModelAdmin):
    list_display = ('user', 'total_posts', 'total_ratings_received')
    search_fields = ('user__username', 'user__email')


@admin.register(UserDevice)
class UserDeviceAdmin(ModelAdmin):
    list_display = ('user', 'device_id', 'is_active', 'created_at')


@admin.register(OTPVerification)
class OTPVerificationAdmin(ModelAdmin):
    list_display = ('user', 'otp_code', 'expires_at', 'created_at')


@admin.register(UserViolation)
class UserViolationAdmin(ModelAdmin):
    list_display = ('user', 'rule_broken', 'created_at')
    list_filter = ('rule_broken', 'created_at')
    search_fields = ('user__username', 'user__email', 'rule_broken', 'description')


@admin.register(ChatReport)
class ChatReportAdmin(ModelAdmin):
    list_display = ('reporter', 'reported_user', 'reason', 'room_id', 'created_at')
    list_filter = ('reason', 'created_at')
    search_fields = (
        'reporter__username',
        'reported_user__username',
        'room_id',
        'message_id',
        'details',
    )


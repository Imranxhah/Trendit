from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import datetime
from django.conf import settings
from phonenumber_field.modelfields import PhoneNumberField

class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone_number = PhoneNumberField(unique=True, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    username = models.CharField(max_length=150, unique=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', null=True, blank=True)
    has_completed_profile = models.BooleanField(default=False)

    # Ban fields — only admins should toggle these
    is_banned = models.BooleanField(default=False)
    ban_reason = models.TextField(blank=True, null=True)

    REQUIRED_FIELDS = ['email']
    
    def __str__(self):
        return self.username

class OTPVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otps')
    otp_code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.user.email} - {self.otp_code}"

class Profile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    
    # Buddies: Many-to-Many with Profile.
    buddies = models.ManyToManyField('self', blank=True, symmetrical=True)
    
    # Close buddies: "List of up to 5 special buddies". 
    close_buddies = models.ManyToManyField('self', related_name='close_friends', blank=True, symmetrical=False)
    
    blocked_users = models.ManyToManyField('self', related_name='blocked_by', blank=True, symmetrical=False)
    
    total_posts = models.PositiveIntegerField(default=0)
    total_ratings_received = models.PositiveIntegerField(default=0)
    top_10_achievements = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return f"Profile of {self.user.username}"

class UserDevice(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='devices')
    device_id = models.CharField(max_length=255, unique=True)
    fcm_token = models.CharField(max_length=255, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.device_id}"


class UserViolation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='violations')
    rule_broken = models.CharField(max_length=255, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.rule_broken or 'Violation'} - {self.created_at}"


from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class AppSettings(models.Model):
    """
    Singleton model to control app-wide settings dynamically.
    """
    upload_start_time = models.TimeField(help_text="Time upload portal opens (e.g., 18:00)")
    upload_end_time = models.TimeField(help_text="Time upload portal closes (e.g., 20:00)")

    def save(self, *args, **kwargs):
        if not self.pk and AppSettings.objects.exists():
            # If you want to prevent creating multiple instances:
            raise ValueError('There can be only one AppSettings instance')
        return super(AppSettings, self).save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "App Settings"

    def __str__(self):
        return "Global App Settings"


class ApkDownloadCounter(models.Model):
    count = models.PositiveBigIntegerField(default=3017)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.count:,} APK downloads"


class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='actions_performed')
    verb = models.CharField(max_length=255, help_text="Short text describing action (e.g., 'rated your post')")
    
    # Generic relation to link to any object (Post, SubPost, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey('content_type', 'object_id')
    
    read_status = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.recipient}: {self.actor} {self.verb}"

class Report(models.Model):
    STATUS_CHOICES = (
        ('submitted', 'Submitted'),
        ('in_review', 'In Review'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    )
    
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reports_filed')
    # We will link to Post specifically as per requirements, but generic is also an option. 
    # For now, adhering to 'Link to Post being reported' from PDF.
    # To avoid circular imports, we use a string reference or generic FK. 
    # Since Post is in 'content', and core might be imported there, let's use string if possible or Generic.
    # Given the requirement "Link to Post", I'll use Generic to avoid hard dependency on 'content' app in 'core' models 
    # if 'content' imports 'core'. But 'content' usually imports 'core'. 
    # Actually, let's use GenericForeignKey to be safe and flexible.
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='submitted')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Report by {self.reporter} - {self.status}"

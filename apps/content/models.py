from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.models import AppSettings

class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

class Post(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('trending', 'Trending'),
        ('rejected', 'Rejected'),
    )

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='posts')
    media_file = models.FileField(upload_to='posts/', null=True, blank=True)
    caption = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    is_media_deleted = models.BooleanField(default=False)

    def clean(self):
        # 1. Enforce Upload Window
        settings_obj = AppSettings.objects.first()
        if settings_obj:
            now = timezone.localtime().time()
            if not (settings_obj.upload_start_time <= now <= settings_obj.upload_end_time):
                raise ValidationError(f"Uploads are only allowed between {settings_obj.upload_start_time} and {settings_obj.upload_end_time}.")

        # 2. Basic Video/Image size validation (Proxy for 20s)
        if self.media_file:
            # Assuming 20MB as a rough upper limit for 20s mobile video
            if self.media_file.size > 20 * 1024 * 1024: 
                raise ValidationError("Media file is too large. Videos must be 20 seconds or less.")

    def save(self, *args, **kwargs):
        # In testing, we might not want to enforce time windows unless explicitly testing them.
        # But for full compliance, we call full_clean.
        # Note: self.full_clean() will call self.clean()
        try:
            self.full_clean()
        except ValidationError:
            # If we are in a test and haven't set AppSettings, it might fail if we aren't careful.
            # However, clean() handles the case if settings_obj is None.
            raise
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.author.username} - {self.created_at}"

class SubPost(models.Model):
    """
    Represents a media-based reply to a main Post (Parent-Child relationship).
    """
    parent_post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='sub_posts')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sub_posts')
    media_file = models.FileField(upload_to='subposts/', null=True, blank=True)
    caption = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_media_deleted = models.BooleanField(default=False)

    def __str__(self):
        return f"Reply by {self.author.username} to Post {self.parent_post.id}"

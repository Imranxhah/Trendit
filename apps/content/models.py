from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.models import AppSettings
from django.db.models import Avg, Count, OuterRef, Subquery, Exists, Value
from django.db.models.functions import Coalesce
from cloudinary.models import CloudinaryField

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

class PostQuerySet(models.QuerySet):
    def with_annotations(self, user=None):
        from apps.social.models import Vote, Favorite
        
        votes_sq = Vote.objects.filter(post=OuterRef('pk'))
        avg_rating_sq = votes_sq.values('post').annotate(a=Avg('value')).values('a')
        vote_count_sq = votes_sq.values('post').annotate(c=Count('*')).values('c')
        favorite_count_sq = Favorite.objects.filter(post=OuterRef('pk')).values('post').annotate(c=Count('*')).values('c')

        queryset = self
        if user and user.is_authenticated:
            user_vote = Vote.objects.filter(post=OuterRef('pk'), user=user).values('value')
            queryset = queryset.annotate(
                user_rating=Subquery(user_vote[:1]),
                is_favorited=Exists(Favorite.objects.filter(post=OuterRef('pk'), user=user))
            )
        else:
            queryset = queryset.annotate(
                user_rating=Value(None, output_field=models.IntegerField()),
                is_favorited=Value(False, output_field=models.BooleanField())
            )

        return queryset.annotate(
            avg_rating=Subquery(avg_rating_sq),
            vote_count=Coalesce(Subquery(vote_count_sq), Value(0)),
            favorite_count=Coalesce(Subquery(favorite_count_sq), Value(0))
        )

class PostManager(models.Manager):
    def get_queryset(self):
        return PostQuerySet(self.model, using=self._db)

    def with_annotations(self, user=None):
        return self.get_queryset().with_annotations(user)

class Post(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('trending', 'Trending'),
        ('rejected', 'Rejected'),
    )

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='posts')
    media_file = CloudinaryField('media', null=True, blank=True)
    caption = models.TextField()
    aspect_ratio = models.FloatField(null=True, blank=True)
    duration = models.FloatField(null=True, blank=True, help_text="Duration in seconds")
    size = models.PositiveBigIntegerField(null=True, blank=True, help_text="Size in bytes")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    is_media_deleted = models.BooleanField(default=False)

    objects = PostManager()

    def clean(self):
        # 1. Enforce Upload Window
        settings_obj = AppSettings.objects.first()
        if settings_obj:
            now = timezone.localtime().time()
            if not (settings_obj.upload_start_time <= now <= settings_obj.upload_end_time):
                raise ValidationError(f"Uploads are only allowed between {settings_obj.upload_start_time} and {settings_obj.upload_end_time}.")

        # 2. Metadata Validation (Client-provided)
        if self.size:
            if self.size > 60 * 1024 * 1024: 
                raise ValidationError("Media file is too large. Videos must be 60MB or less.")
        
        if self.duration:
            if self.duration > 60:
                raise ValidationError("Video duration must be 60 seconds or less.")

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
    media_file = CloudinaryField('media', null=True, blank=True)
    caption = models.TextField(blank=True)
    aspect_ratio = models.FloatField(null=True, blank=True)
    duration = models.FloatField(null=True, blank=True, help_text="Duration in seconds")
    size = models.PositiveBigIntegerField(null=True, blank=True, help_text="Size in bytes")
    created_at = models.DateTimeField(auto_now_add=True)
    is_media_deleted = models.BooleanField(default=False)

    def clean(self):
        # 1. Enforce Upload Window
        settings_obj = AppSettings.objects.first()
        if settings_obj:
            now = timezone.localtime().time()
            if not (settings_obj.upload_start_time <= now <= settings_obj.upload_end_time):
                raise ValidationError(f"Uploads are only allowed between {settings_obj.upload_start_time} and {settings_obj.upload_end_time}.")

        # 2. Metadata Validation (Client-provided)
        if self.size:
            if self.size > 60 * 1024 * 1024: 
                raise ValidationError("Media file is too large. Videos must be 60MB or less.")
        
        if self.duration:
            if self.duration > 60:
                raise ValidationError("Video duration must be 60 seconds or less.")

    def save(self, *args, **kwargs):
        try:
            self.full_clean()
        except ValidationError:
            raise
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Reply by {self.author.username} to Post {self.parent_post.id}"

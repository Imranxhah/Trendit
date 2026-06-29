from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.models import AppSettings
from django.db.models import Avg, Case, Count, ExpressionWrapper, F, FloatField, OuterRef, Subquery, Exists, Value, When
from django.db.models.functions import Coalesce
from cloudinary.models import CloudinaryField


TRENDING_CONFIDENCE_VOTES = 12.0
TRENDING_VOLUME_VOTES = 25.0
TRENDING_FAVORITE_SATURATION = 10.0
CATEGORY_PRIORITY_MULTIPLIERS = {
    'punished': 0.5,
    'normal': 1.0,
    'trending': 2.0,
}


def calculate_trending_score(post, now=None):
    """
    Product ranking score for trending posts.

    The score intentionally rewards rating quality only after enough users have
    voted. This prevents a tiny perfect sample from beating a broadly validated
    post, while still allowing excellent new content to rise as votes arrive.
    """
    if now is None:
        now = timezone.now()

    vote_count = int(getattr(post, 'vote_count', 0) or 0)
    favorite_count = int(getattr(post, 'favorite_count', 0) or 0)
    avg_rating = getattr(post, 'avg_rating', None)
    category_multiplier = float(getattr(post, 'category_priority_multiplier', 1.0) or 1.0)

    if vote_count <= 0 or avg_rating is None:
        rating_quality = 0.0
    else:
        rating_quality = max(0.0, min(1.0, (float(avg_rating) - 1.0) / 4.0))

    rating_confidence = vote_count / (vote_count + TRENDING_CONFIDENCE_VOTES)
    rating_component = rating_quality * rating_confidence
    vote_momentum = vote_count / (vote_count + TRENDING_VOLUME_VOTES)
    favorite_momentum = favorite_count / (favorite_count + TRENDING_FAVORITE_SATURATION)

    created_at = getattr(post, 'created_at', None)
    if created_at:
        age_hours = max((now - created_at).total_seconds() / 3600.0, 0.0)
        recency = 1.0 / (1.0 + (age_hours / 72.0) ** 1.35)
    else:
        recency = 0.0

    status_boost = 0.02 if getattr(post, 'status', None) == 'trending' else 0.0
    score = (
        0.58 * rating_component
        + 0.22 * vote_momentum
        + 0.10 * favorite_momentum
        + 0.10 * recency
        + status_boost
    )
    return round(score * 100.0 * category_multiplier, 6)

class Category(models.Model):
    PRIORITY_STATUS_CHOICES = (
        ('punished', 'Punished'),
        ('normal', 'Normal'),
        ('trending', 'Trending'),
    )

    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    priority_status = models.CharField(
        max_length=20,
        choices=PRIORITY_STATUS_CHOICES,
        default='normal',
        help_text="Editorial weight used by the trending algorithm.",
    )

    @property
    def priority_multiplier(self):
        return CATEGORY_PRIORITY_MULTIPLIERS.get(self.priority_status, 1.0)

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

        from django.db.models import Prefetch

        return queryset.annotate(
            avg_rating=Subquery(avg_rating_sq),
            vote_count=Coalesce(Subquery(vote_count_sq), Value(0)),
            favorite_count=Coalesce(Subquery(favorite_count_sq), Value(0))
        ).select_related(
            # Eliminates per-row FK lookups for author.username
            # and author.profile_picture in PostSerializer.
            'author',
        ).prefetch_related(
            # Eliminates the N+1 on the nested SubPostSerializer list field.
            # Also pre-fetches sub_post authors so SubPostSerializer's
            # author_username / author_profile_picture fields don't hit the DB per row.
            Prefetch('sub_posts', queryset=SubPost.objects.with_annotations(user)),
            'sub_posts__author',
            'categories',
        )

    def with_trending_base_score(self, user=None):
        queryset = self.with_annotations(user).annotate(
            avg_rating_safe=Coalesce('avg_rating', Value(0.0), output_field=FloatField()),
            category_priority_multiplier=Coalesce(
                Avg(
                    Case(
                        When(categories__priority_status='punished', then=Value(CATEGORY_PRIORITY_MULTIPLIERS['punished'])),
                        When(categories__priority_status='trending', then=Value(CATEGORY_PRIORITY_MULTIPLIERS['trending'])),
                        default=Value(CATEGORY_PRIORITY_MULTIPLIERS['normal']),
                        output_field=FloatField(),
                    )
                ),
                Value(CATEGORY_PRIORITY_MULTIPLIERS['normal']),
                output_field=FloatField(),
            ),
        )
        queryset = queryset.annotate(
            normalized_rating=Case(
                When(
                    vote_count__gt=0,
                    then=ExpressionWrapper(
                        (F('avg_rating_safe') - Value(1.0)) / Value(4.0),
                        output_field=FloatField(),
                    ),
                ),
                default=Value(0.0),
                output_field=FloatField(),
            ),
            rating_confidence=ExpressionWrapper(
                F('vote_count') * Value(1.0) / (F('vote_count') + Value(TRENDING_CONFIDENCE_VOTES)),
                output_field=FloatField(),
            ),
            vote_momentum=ExpressionWrapper(
                F('vote_count') * Value(1.0) / (F('vote_count') + Value(TRENDING_VOLUME_VOTES)),
                output_field=FloatField(),
            ),
            favorite_momentum=ExpressionWrapper(
                F('favorite_count') * Value(1.0) / (F('favorite_count') + Value(TRENDING_FAVORITE_SATURATION)),
                output_field=FloatField(),
            ),
            manual_trending_boost=Case(
                When(status='trending', then=Value(0.02)),
                default=Value(0.0),
                output_field=FloatField(),
            ),
        )
        return queryset.annotate(
            trending_base_score=ExpressionWrapper(
                (
                    Value(0.58) * F('normalized_rating') * F('rating_confidence')
                    + Value(0.22) * F('vote_momentum')
                    + Value(0.10) * F('favorite_momentum')
                    + F('manual_trending_boost')
                ) * Value(100.0) * F('category_priority_multiplier'),
                output_field=FloatField(),
            )
        )

class PostManager(models.Manager):
    def get_queryset(self):
        return PostQuerySet(self.model, using=self._db)

    def with_annotations(self, user=None):
        return self.get_queryset().with_annotations(user)

    def with_trending_base_score(self, user=None):
        return self.get_queryset().with_trending_base_score(user)

class Post(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('active', 'Active'),
        ('trending', 'Trending'),
        ('rejected', 'Rejected'),
    )

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='posts')
    categories = models.ManyToManyField(Category, blank=True, related_name='posts')
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

class SubPostQuerySet(models.QuerySet):
    def with_annotations(self, user=None):
        from apps.social.models import SubPostVote
        
        votes_sq = SubPostVote.objects.filter(sub_post=OuterRef('pk'))
        avg_rating_sq = votes_sq.values('sub_post').annotate(a=Avg('value')).values('a')
        vote_count_sq = votes_sq.values('sub_post').annotate(c=Count('*')).values('c')

        queryset = self
        if user and user.is_authenticated:
            user_vote = SubPostVote.objects.filter(sub_post=OuterRef('pk'), user=user).values('value')
            queryset = queryset.annotate(
                user_rating=Subquery(user_vote[:1])
            )
        else:
            queryset = queryset.annotate(
                user_rating=Value(None, output_field=models.IntegerField())
            )

        return queryset.annotate(
            avg_rating=Subquery(avg_rating_sq),
            vote_count=Coalesce(Subquery(vote_count_sq), Value(0))
        )

class SubPostManager(models.Manager):
    def get_queryset(self):
        return SubPostQuerySet(self.model, using=self._db)

    def with_annotations(self, user=None):
        return self.get_queryset().with_annotations(user)

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

    objects = SubPostManager()

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

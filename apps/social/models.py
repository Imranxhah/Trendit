from django.db import models
from django.conf import settings
from apps.content.models import Post, SubPost
from django.core.exceptions import ValidationError

User = settings.AUTH_USER_MODEL


class Follow(models.Model):
    """
    One-way follow relationship.
    'follower' follows 'following'.
    """
    follower = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='following'
    )
    following = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='followers'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')

    def __str__(self):
        return f"{self.follower} → {self.following}"


class Buddy(models.Model):
    """
    Mutual follow relationship.
    Automatically created when two users follow each other.
    """
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buddies_as_user1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buddies_as_user2')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user1', 'user2')
        verbose_name_plural = "Buddies"

    def __str__(self):
        return f"Mutual Buddies: {self.user1} ↔ {self.user2}"


class CloseBuddyRequest(models.Model):
    """
    Permission-based request to add someone to your Inner Circle.
    Sender asks receiver to become their Close Buddy.
    Receiver must accept.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('ignored', 'Ignored'),
    )

    sender = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='close_buddy_requests_sent'
    )
    receiver = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='close_buddy_requests_received'
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f"{self.sender} → {self.receiver} ({self.status})"


class CloseBuddy(models.Model):
    """
    The 'Inner Circle' (Max 5).
    Created when a CloseBuddyRequest is accepted.
    These users have the power to vote your posts into 'Trending'.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='my_close_buddies')
    buddy = models.ForeignKey(User, on_delete=models.CASCADE, related_name='close_buddy_of')

    class Meta:
        unique_together = ('user', 'buddy')

    def clean(self):
        if self.user == self.buddy:
            raise ValidationError("You cannot be your own close buddy.")
        if not self.pk and CloseBuddy.objects.filter(user=self.user).count() >= 5:
            raise ValidationError("You can only have 5 Close Buddies.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user}'s Inner Circle: {self.buddy}"


class PostApproval(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='approvals')
    buddy = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_approvals')
    approved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'buddy')


class Vote(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_votes')
    value = models.IntegerField(choices=[(i, i) for i in range(1, 6)])

    class Meta:
        unique_together = ('post', 'user')


class SubPostVote(models.Model):
    sub_post = models.ForeignKey(SubPost, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_subpost_votes')
    value = models.IntegerField(choices=[(i, i) for i in range(1, 6)])

    class Meta:
        unique_together = ('sub_post', 'user')


class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')

    def __str__(self):
        return f"{self.user.username} favorited post {self.post.id}"


class Community(models.Model):
    name = models.CharField(max_length=100, unique=True)
    profile_picture = models.ImageField(
        upload_to='community_pics/',
        null=True,
        blank=True
    )
    creator = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='created_communities'
    )
    members = models.ManyToManyField(
        User,
        through='CommunityMembership',
        related_name='communities'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Communities'

    def __str__(self):
        return self.name


class CommunityMembership(models.Model):
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='community_memberships'
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('community', 'user')
        ordering = ['-joined_at']

    def __str__(self):
        return f"{self.user} joined {self.community}"

from django.db import models
from django.conf import settings
from apps.content.models import Post
from django.core.exceptions import ValidationError

User = settings.AUTH_USER_MODEL

class BuddyRequest(models.Model):
    """
    Manages the 'Friend Request' logic.
    User A sends a request to User B. B must accept.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
    )

    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_requests')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_requests')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('sender', 'receiver')

    def __str__(self):
        return f"{self.sender} -> {self.receiver} ({self.status})"

class CloseBuddy(models.Model):
    """
    The 'Inner Circle' (Max 5).
    These users have the power to vote your posts into 'Trending'.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='my_close_buddies')
    buddy = models.ForeignKey(User, on_delete=models.CASCADE, related_name='close_buddy_of')

    class Meta:
        unique_together = ('user', 'buddy')

    def clean(self):
        if self.user == self.buddy:
            raise ValidationError("You cannot be your own close buddy.")
        # Only check count on creation
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

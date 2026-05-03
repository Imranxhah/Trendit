from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from apps.content.models import Post
from apps.social.models import Vote
from .models import Profile, User

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(user=instance)

@receiver(post_save, sender=Post)
def update_profile_post_count(sender, instance, created, **kwargs):
    if created:
        profile, _ = Profile.objects.get_or_create(user=instance.author)
        profile.total_posts = instance.author.posts.count()
        profile.save()

@receiver(post_save, sender=Vote)
def update_profile_rating_stats(sender, instance, created, **kwargs):
    # Update the total ratings received by the post author
    author = instance.post.author
    profile, _ = Profile.objects.get_or_create(user=author)
    # Sum of all votes across all posts by this author
    total_ratings = Vote.objects.filter(post__author=author).count()
    profile.total_ratings_received = total_ratings
    profile.save()

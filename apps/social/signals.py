from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import PostApproval, Follow, Buddy, CloseBuddy, CloseBuddyRequest
from apps.content.models import Post

@receiver(post_save, sender=PostApproval)
def check_post_approval_count(sender, instance, created, **kwargs):
    if created:
        post = instance.post
        approval_count = PostApproval.objects.filter(post=post).count()
        
        # Requirement: 3 approvals needed to publish (as per Database Schema PDF)
        if approval_count >= 3 and post.status == 'pending':
            post.status = 'active'
            post.save()


@receiver(post_save, sender=Follow)
def manage_buddy_on_follow(sender, instance, created, **kwargs):
    if created:
        follower = instance.follower
        following = instance.following
        
        # Check if the reciprocal follow exists
        if Follow.objects.filter(follower=following, following=follower).exists():
            u1, u2 = sorted([follower.id, following.id])
            user1 = follower if follower.id == u1 else following
            user2 = following if following.id == u2 else follower
            Buddy.objects.get_or_create(user1=user1, user2=user2)


@receiver(post_delete, sender=Follow)
def manage_buddy_on_unfollow(sender, instance, **kwargs):
    follower = instance.follower
    following = instance.following
    
    # If either user unfollows the other, they are no longer mutual buddies
    u1, u2 = sorted([follower.id, following.id])
    Buddy.objects.filter(user1_id=u1, user2_id=u2).delete()


@receiver(post_delete, sender=CloseBuddy)
def manage_close_buddy_request_on_remove(sender, instance, **kwargs):
    # When a user is removed from the Inner Circle, delete the accepted request 
    # so they can be invited again in the future if needed.
    CloseBuddyRequest.objects.filter(
        sender=instance.user,
        receiver=instance.buddy,
        status='accepted'
    ).delete()

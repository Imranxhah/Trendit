from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import PostApproval
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

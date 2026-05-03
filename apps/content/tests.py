from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from .models import Category, Post
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta
from django.core.management import call_command
import os

User = get_user_model()

class ContentTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@ex.com", password="pass", is_verified=True)
        self.client.force_authenticate(user=self.user)
        self.category = Category.objects.create(name="Health")
        self.create_post_url = reverse('post-create')
        self.feed_url = reverse('post-feed')

    def test_create_post(self):
        image = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")
        data = {
            "category": self.category.id,
            "caption": "Feeling good!",
            "media_file": image
        }
        response = self.client.post(self.create_post_url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Post.objects.count(), 1)

    def test_feed_filters_deleted_media(self):
        # Post with media
        Post.objects.create(author=self.user, category=self.category, caption="Visible", is_media_deleted=False)
        # Post with deleted media
        Post.objects.create(author=self.user, category=self.category, caption="Hidden", is_media_deleted=True)
        
        response = self.client.get(self.feed_url)
        self.assertEqual(len(response.data['results'] if 'results' in response.data else response.data), 1)

    def test_delete_expired_media_command(self):
        # Create an old post
        old_post = Post.objects.create(
            author=self.user, 
            category=self.category, 
            caption="Old Post",
            media_file=SimpleUploadedFile("old.jpg", b"old_content", content_type="image/jpeg")
        )
        # Manually set created_at back in time
        Post.objects.filter(id=old_post.id).update(created_at=timezone.now() - timedelta(days=8))
        
        # Run command
        call_command('delete_expired_media')
        
        old_post.refresh_from_db()
        self.assertTrue(old_post.is_media_deleted)
        self.assertFalse(bool(old_post.media_file)) # Check if it's empty/None
        # Note: In tests, the physical file might not be created depending on storage settings, 
        # but the DB state change is the primary logic to verify.
        # Check that we didn't delete a recent post
        recent_post = Post.objects.create(
            author=self.user, 
            category=self.category, 
            caption="New Post",
            media_file=SimpleUploadedFile("new.jpg", b"new_content", content_type="image/jpeg")
        )
        call_command('delete_expired_media')
        recent_post.refresh_from_db()
        self.assertFalse(recent_post.is_media_deleted)
        self.assertIsNotNone(recent_post.media_file.name)

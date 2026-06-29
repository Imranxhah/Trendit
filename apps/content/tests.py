from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from .models import Category, Post
from apps.social.models import Favorite, Vote
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta
from django.core.management import call_command
from unittest.mock import patch
import os

User = get_user_model()

class ContentTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@ex.com", password="pass", 
            is_verified=True, phone_number="+2347000000000", has_completed_profile=True
        )
        self.client.force_authenticate(user=self.user)
        self.category = Category.objects.create(name="Health")
        self.create_post_url = reverse('post-create')
        self.feed_url = reverse('post-feed')
        self.trending_url = reverse('post-trending')

    def _response_items(self, response):
        body = response.data.get('data', response.data) if isinstance(response.data, dict) else response.data
        return body.get('results', body) if isinstance(body, dict) else body

    @patch('cloudinary.uploader.upload')
    def test_create_post(self, mock_upload):
        mock_upload.return_value = {
            'public_id': 'test_id',
            'secure_url': 'http://example.com/test.jpg',
            'format': 'jpg',
            'version': 1,
            'type': 'upload',
            'resource_type': 'image',
        }
        image = SimpleUploadedFile("test.jpg", b"file_content", content_type="image/jpeg")
        data = {
            "category_ids": [self.category.id],
            "caption": "Feeling good!",
            "media_file": image
        }
        response = self.client.post(self.create_post_url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Post.objects.count(), 1)

    def test_feed_filters_deleted_media(self):
        # Post with media
        visible_post = Post.objects.create(author=self.user, caption="Visible", is_media_deleted=False)
        visible_post.categories.set([self.category])
        # Post with deleted media
        hidden_post = Post.objects.create(author=self.user, caption="Hidden", is_media_deleted=True)
        hidden_post.categories.set([self.category])
        
        response = self.client.get(self.feed_url)
        # StandardizedJSONRenderer wraps the response body in 'data'.
        # Cursor pagination then wraps the list in 'results'.
        # Unwrap both layers to get the actual post list.
        body = response.data.get('data', response.data) if isinstance(response.data, dict) else response.data
        data_list = body.get('results', body) if isinstance(body, dict) else body
        self.assertEqual(len(data_list), 1)

    def test_trending_prefers_confident_rating_over_tiny_perfect_sample(self):
        high_confidence_post = Post.objects.create(
            author=self.user,
            caption="Twenty voters gave this a strong rating",
            status="active",
        )
        tiny_perfect_post = Post.objects.create(
            author=self.user,
            caption="Five voters gave this a perfect rating",
            status="active",
        )

        created_at = timezone.now() - timedelta(hours=2)
        Post.objects.filter(id__in=[high_confidence_post.id, tiny_perfect_post.id]).update(created_at=created_at)

        voters = [
            User.objects.create_user(
                username=f"voter{i}",
                email=f"voter{i}@ex.com",
                password="pass",
                is_verified=True,
                phone_number=f"+2348000{i:06d}",
            )
            for i in range(25)
        ]

        Vote.objects.bulk_create([
            Vote(post=high_confidence_post, user=voter, value=4)
            for voter in voters[:20]
        ])
        Vote.objects.bulk_create([
            Vote(post=tiny_perfect_post, user=voter, value=5)
            for voter in voters[20:]
        ])

        response = self.client.get(self.trending_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        items = self._response_items(response)
        self.assertEqual(items[0]['id'], high_confidence_post.id)
        self.assertGreater(items[0]['trending_score'], items[1]['trending_score'])

    def test_trending_uses_favorites_as_secondary_engagement_signal(self):
        favorited_post = Post.objects.create(
            author=self.user,
            caption="Same rating, stronger save signal",
            status="active",
        )
        plain_post = Post.objects.create(
            author=self.user,
            caption="Same rating, no favorites",
            status="active",
        )

        voters = [
            User.objects.create_user(
                username=f"favvoter{i}",
                email=f"favvoter{i}@ex.com",
                password="pass",
                is_verified=True,
                phone_number=f"+2348010{i:06d}",
            )
            for i in range(12)
        ]

        Vote.objects.bulk_create([
            Vote(post=favorited_post, user=voter, value=4)
            for voter in voters[:6]
        ])
        Vote.objects.bulk_create([
            Vote(post=plain_post, user=voter, value=4)
            for voter in voters[6:]
        ])
        Favorite.objects.bulk_create([
            Favorite(post=favorited_post, user=voter)
            for voter in voters[6:10]
        ])

        response = self.client.get(self.trending_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        items = self._response_items(response)
        self.assertEqual(items[0]['id'], favorited_post.id)

    def test_trending_applies_category_priority_multiplier(self):
        trending_category = Category.objects.create(name="Editorial Push", priority_status="trending")
        normal_category = Category.objects.create(name="Normal Priority", priority_status="normal")

        boosted_post = Post.objects.create(
            author=self.user,
            caption="Good post in boosted category",
            status="active",
        )
        boosted_post.categories.set([trending_category])

        normal_post = Post.objects.create(
            author=self.user,
            caption="Same quality post in normal category",
            status="active",
        )
        normal_post.categories.set([normal_category])
        Post.objects.filter(id__in=[boosted_post.id, normal_post.id]).update(created_at=timezone.now() - timedelta(hours=2))

        voters = [
            User.objects.create_user(
                username=f"catvoter{i}",
                email=f"catvoter{i}@ex.com",
                password="pass",
                is_verified=True,
                phone_number=f"+2348020{i:06d}",
            )
            for i in range(10)
        ]

        Vote.objects.bulk_create([
            Vote(post=boosted_post, user=voter, value=4)
            for voter in voters[:5]
        ])
        Vote.objects.bulk_create([
            Vote(post=normal_post, user=voter, value=4)
            for voter in voters[5:]
        ])

        response = self.client.get(self.trending_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        items = self._response_items(response)
        self.assertEqual(items[0]['id'], boosted_post.id)
        self.assertAlmostEqual(items[0]['trending_score'], items[1]['trending_score'] * 2, delta=0.01)

    def test_trending_penalizes_punished_category(self):
        punished_category = Category.objects.create(name="Editorial Penalty", priority_status="punished")
        normal_category = Category.objects.create(name="Regular Priority", priority_status="normal")

        punished_post = Post.objects.create(
            author=self.user,
            caption="Same quality post in punished category",
            status="active",
        )
        punished_post.categories.set([punished_category])

        normal_post = Post.objects.create(
            author=self.user,
            caption="Same quality post in normal category",
            status="active",
        )
        normal_post.categories.set([normal_category])
        Post.objects.filter(id__in=[punished_post.id, normal_post.id]).update(created_at=timezone.now() - timedelta(hours=2))

        voters = [
            User.objects.create_user(
                username=f"punishvoter{i}",
                email=f"punishvoter{i}@ex.com",
                password="pass",
                is_verified=True,
                phone_number=f"+2348030{i:06d}",
            )
            for i in range(10)
        ]

        Vote.objects.bulk_create([
            Vote(post=punished_post, user=voter, value=4)
            for voter in voters[:5]
        ])
        Vote.objects.bulk_create([
            Vote(post=normal_post, user=voter, value=4)
            for voter in voters[5:]
        ])

        response = self.client.get(self.trending_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        items = self._response_items(response)
        self.assertEqual(items[0]['id'], normal_post.id)
        self.assertAlmostEqual(items[1]['trending_score'], items[0]['trending_score'] * 0.5, delta=0.01)

    @patch('cloudinary.uploader.upload')
    @patch('cloudinary.uploader.destroy')
    def test_delete_expired_media_command(self, mock_destroy, mock_upload):
        mock_upload.return_value = {
            'public_id': 'old',
            'secure_url': 'http://ex.com/old.jpg',
            'version': 1,
            'type': 'upload',
            'resource_type': 'image',
        }
        mock_destroy.return_value = {'result': 'ok'}
        # Create an old post
        old_post = Post.objects.create(
            author=self.user, 
            caption="Old Post",
            media_file=SimpleUploadedFile("old.jpg", b"old_content", content_type="image/jpeg")
        )
        old_post.categories.set([self.category])
        # Manually set created_at back in time
        Post.objects.filter(id=old_post.id).update(created_at=timezone.now() - timedelta(days=8))
        
        # Run command
        call_command('delete_expired_media')
        
        old_post.refresh_from_db()
        self.assertTrue(old_post.is_media_deleted)
        self.assertFalse(bool(old_post.media_file)) # Check if it's empty/None
        
        # Check that we didn't delete a recent post
        mock_upload.return_value = {
            'public_id': 'new',
            'secure_url': 'http://ex.com/new.jpg',
            'version': 1,
            'type': 'upload',
            'resource_type': 'image',
        }
        recent_post = Post.objects.create(
            author=self.user, 
            caption="New Post",
            media_file=SimpleUploadedFile("new.jpg", b"new_content", content_type="image/jpeg")
        )
        recent_post.categories.set([self.category])
        call_command('delete_expired_media')
        recent_post.refresh_from_db()
        self.assertFalse(recent_post.is_media_deleted)
        self.assertTrue(bool(recent_post.media_file))


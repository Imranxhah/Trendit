from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from apps.social.models import Vote
from apps.content.models import Post, Category

User = get_user_model()

class VoteTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="voter", 
            email="voter@example.com", 
            password="password123", 
            is_verified=True
        )
        self.author = User.objects.create_user(
            username="author", 
            email="author@example.com", 
            password="password123"
        )
        self.category = Category.objects.create(name="Test Category")
        self.post = Post.objects.create(
            author=self.author, 
            category=self.category, 
            caption="Test Post"
        )
        self.client.force_authenticate(user=self.user)
        self.vote_url = reverse('vote')

    def test_favorite_toggle(self):
        favorite_url = reverse('favorite-toggle')
        
        # 1. Add to favorites
        response = self.client.post(favorite_url, {"post": self.post.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_favorited'])
        
        # Verify in post detail
        detail_url = reverse('post-detail', kwargs={'pk': self.post.id})
        response = self.client.get(detail_url)
        self.assertEqual(response.data['favorite_count'], 1)
        self.assertTrue(response.data['is_favorited'])

        # 2. Remove from favorites (toggle)
        response = self.client.post(favorite_url, {"post": self.post.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_favorited'])

        # Verify in post detail
        response = self.client.get(detail_url)
        self.assertEqual(response.data['favorite_count'], 0)
        self.assertFalse(response.data['is_favorited'])

    def test_create_and_update_vote(self):
        # 1. Create a vote
        response = self.client.post(self.vote_url, {"post": self.post.id, "value": 3})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Vote.objects.count(), 1)
        self.assertEqual(Vote.objects.get().value, 3)

        # Verify user_rating appears in post detail
        detail_url = reverse('post-detail', kwargs={'pk': self.post.id})
        response = self.client.get(detail_url)
        self.assertEqual(response.data['user_rating'], 3)
        self.assertEqual(response.data['avg_rating'], 3.0)
        self.assertEqual(response.data['vote_count'], 1)

        # 2. Update the same vote
        response = self.client.post(self.vote_url, {"post": self.post.id, "value": 5})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Vote.objects.count(), 1) 
        self.assertEqual(Vote.objects.get().value, 5)

        # Verify updated user_rating in post detail
        response = self.client.get(detail_url)
        self.assertEqual(response.data['user_rating'], 5)
        self.assertEqual(response.data['avg_rating'], 5.0)

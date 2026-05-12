from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from apps.content.models import Post, Category
from apps.social.models import Favorite

User = get_user_model()

class FavoriteToggleTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="fav_user", 
            email="fav@example.com", 
            password="password123",
            is_verified=True
        )
        self.category = Category.objects.create(name="Test Category")
        self.post = Post.objects.create(
            author=self.user, 
            category=self.category, 
            caption="Test Post"
        )
        self.client.force_authenticate(user=self.user)
        self.favorite_url = reverse('favorite-toggle')

    def test_favorite_toggle_response_data(self):
        # 1. Add to favorites
        response = self.client.post(self.favorite_url, {"post": self.post.id})
        # print(f"DEBUG: Response data: {response.data}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_favorited'])
        self.assertEqual(response.data['favorite_count'], 1)
        self.assertEqual(response.data['id'], self.post.id)
        self.assertEqual(response.data['message'], "Added to favorites.")

        # 2. Toggle (Remove)
        response = self.client.post(self.favorite_url, {"post": self.post.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_favorited'])
        self.assertEqual(response.data['favorite_count'], 0)
        self.assertEqual(response.data['id'], self.post.id)
        self.assertEqual(response.data['message'], "Removed from favorites.")

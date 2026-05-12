from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from .models import CloseBuddy, Vote, CloseBuddyRequest, PostApproval, Follow, Buddy
from apps.content.models import Post, Category

User = get_user_model()

class SocialTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="me", email="me@ex.com", password="pass", 
            is_verified=True, phone_number="+2348000000000"
        )
        self.other_user = User.objects.create_user(
            username="friend", email="friend@ex.com", password="pass", 
            phone_number="+2348000000001"
        )
        self.client.force_authenticate(user=self.user)
        
        self.category = Category.objects.create(name="Social")
        # Post by other user
        self.other_post = Post.objects.create(author=self.other_user, category=self.category, caption="Other post")

    def make_mutual_buddies(self, user1, user2):
        # Establish mutual follows to trigger Buddy creation
        Follow.objects.create(follower=user1, following=user2)
        Follow.objects.create(follower=user2, following=user1)

    def test_close_buddy_request_flow(self):
        # 0. Setup: Must be mutual buddies first
        self.make_mutual_buddies(self.user, self.other_user)
        
        # 1. Send Request
        url = reverse('close-buddy-request-send')
        response = self.client.post(url, {"receiver": self.other_user.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(CloseBuddyRequest.objects.filter(sender=self.user, receiver=self.other_user).exists())

        # 2. List Pending Requests (as receiver)
        self.client.force_authenticate(user=self.other_user)
        url = reverse('close-buddy-request-list')
        response = self.client.get(url)
        # response.data is the raw list from the view
        self.assertEqual(len(response.data), 1)
        req_id = response.data[0]['id']

        # 3. Respond (Accept)
        url = reverse('close-buddy-request-respond')
        response = self.client.post(url, {"request_id": req_id, "action": "accepted"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 4. Check Close Buddy List (Sender should now have 'friend' in their inner circle)
        self.client.force_authenticate(user=self.user)
        url = reverse('close-buddy-list')
        response = self.client.get(url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['buddy'], self.other_user.id)

    def test_restricted_approval(self):
        # 'friend' tries to approve 'me's post without being a close buddy
        my_post = Post.objects.create(author=self.user, category=self.category, caption="My post")
        self.client.force_authenticate(user=self.other_user)
        
        url = reverse('post-approval')
        response = self.client.post(url, {"post": my_post.id})
        # Standardized renderer might not wrap 400 if it's a simple ValidationError
        # but let's check status_code first
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_close_buddy_approval(self):
        # Setup: Make them close buddies
        self.make_mutual_buddies(self.user, self.other_user)
        CloseBuddy.objects.create(user=self.user, buddy=self.other_user)
        
        my_post = Post.objects.create(author=self.user, category=self.category, caption="My post")
        
        # 'friend' approves 'me's post
        self.client.force_authenticate(user=self.other_user)
        url = reverse('post-approval')
        response = self.client.post(url, {"post": my_post.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(PostApproval.objects.filter(post=my_post, buddy=self.other_user).exists())

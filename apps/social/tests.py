from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from .models import CloseBuddy, Vote, BuddyRequest, PostApproval
from apps.content.models import Post, Category

User = get_user_model()

class SocialTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="me", email="me@ex.com", password="pass", is_verified=True, phone_number="0000")
        self.other_user = User.objects.create_user(username="friend", email="friend@ex.com", password="pass", phone_number="1111")
        self.client.force_authenticate(user=self.user)
        
        self.category = Category.objects.create(name="Social")
        # Post by other user
        self.other_post = Post.objects.create(author=self.other_user, category=self.category, caption="Other post")

    def test_buddy_request_flow(self):
        # 1. Send Request
        url = reverse('buddy-request-send')
        response = self.client.post(url, {"receiver": self.other_user.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(BuddyRequest.objects.filter(sender=self.user, receiver=self.other_user).exists())

        # 2. List Pending Requests (as receiver)
        self.client.force_authenticate(user=self.other_user)
        url = reverse('buddy-request-list')
        response = self.client.get(url)
        self.assertEqual(len(response.data), 1)
        req_id = response.data[0]['id']

        # 3. Respond (Accept)
        url = reverse('buddy-request-respond')
        response = self.client.post(url, {"request_id": req_id, "action": "accepted"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # 4. Check Buddy List
        url = reverse('buddy-list')
        response = self.client.get(url)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['username'], "me")

    def test_close_buddy_auto_buddy_and_approval(self):
        # Add other_user as Close Buddy directly
        url = reverse('close-buddy-list')
        response = self.client.post(url, {"buddy": self.other_user.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify BuddyRequest was auto-created/accepted
        self.assertTrue(BuddyRequest.objects.filter(sender=self.user, receiver=self.other_user, status='accepted').exists())

        # Verify user can approve other_user's post because user is other_user's close buddy?
        # Wait, the rule is: Only Close Buddies of the AUTHOR can approve.
        # Currently, 'me' added 'friend' as close buddy. So 'friend' can approve 'me's posts.
        
        my_post = Post.objects.create(author=self.user, category=self.category, caption="My post")
        
        # 'friend' approves 'me's post
        self.client.force_authenticate(user=self.other_user)
        url = reverse('post-approval')
        
        # If 'me' hasn't added 'friend' as close buddy, 'friend' can't approve.
        # Re-check: perform_create checks: CloseBuddy.objects.filter(user=post.author, buddy=self.request.user)
        # Author is 'me'. Request user is 'friend'. 
        # Since 'me' added 'friend' as CloseBuddy, this filter should find it.
        
        response = self.client.post(url, {"post": my_post.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_restricted_approval(self):
        # 'friend' tries to approve 'me's post without being a close buddy
        my_post = Post.objects.create(author=self.user, category=self.category, caption="My post")
        self.client.force_authenticate(user=self.other_user)
        
        url = reverse('post-approval')
        response = self.client.post(url, {"post": my_post.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Only close buddies", str(response.data))

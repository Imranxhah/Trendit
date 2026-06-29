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
            is_verified=True, phone_number="+2348000000000", has_completed_profile=True
        )
        self.other_user = User.objects.create_user(
            username="friend", email="friend@ex.com", password="pass", 
            phone_number="+2348000000001", has_completed_profile=True
        )
        self.client.force_authenticate(user=self.user)
        
        self.category = Category.objects.create(name="Social")
        # Post by other user
        self.other_post = Post.objects.create(author=self.other_user, caption="Other post")
        self.other_post.categories.set([self.category])

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
        my_post = Post.objects.create(author=self.user, caption="My post")
        my_post.categories.set([self.category])
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
        
        my_post = Post.objects.create(author=self.user, caption="My post")
        my_post.categories.set([self.category])
        
        # 'friend' approves 'me's post
        self.client.force_authenticate(user=self.other_user)
        url = reverse('post-approval')
        response = self.client.post(url, {"post": my_post.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(PostApproval.objects.filter(post=my_post, buddy=self.other_user).exists())

    def test_duplicate_close_buddy_request_pending(self):
        self.make_mutual_buddies(self.user, self.other_user)
        url = reverse('close-buddy-request-send')
        
        # Send first request
        response = self.client.post(url, {"receiver": self.other_user.id})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Send duplicate request while pending
        response = self.client.post(url, {"receiver": self.other_user.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("You already have a pending request to this user.", str(response.data))

    def test_duplicate_close_buddy_request_accepted(self):
        self.make_mutual_buddies(self.user, self.other_user)
        # Create request and set accepted
        req = CloseBuddyRequest.objects.create(sender=self.user, receiver=self.other_user, status='accepted')
        CloseBuddy.objects.create(user=self.user, buddy=self.other_user)

        url = reverse('close-buddy-request-send')
        response = self.client.post(url, {"receiver": self.other_user.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("This user is already in your inner circle.", str(response.data))

    def test_duplicate_close_buddy_request_rejected(self):
        self.make_mutual_buddies(self.user, self.other_user)
        # Create request and set rejected
        CloseBuddyRequest.objects.create(sender=self.user, receiver=self.other_user, status='rejected')

        url = reverse('close-buddy-request-send')
        response = self.client.post(url, {"receiver": self.other_user.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("A close buddy request has already been sent to this user.", str(response.data))

    def test_reverse_pending_close_buddy_request(self):
        self.make_mutual_buddies(self.user, self.other_user)
        # Create a pending request from other_user to user
        CloseBuddyRequest.objects.create(sender=self.other_user, receiver=self.user, status='pending')

        # Now current user attempts to send request to other_user
        url = reverse('close-buddy-request-send')
        response = self.client.post(url, {"receiver": self.other_user.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("This user has already sent you a close buddy request.", str(response.data))

    def test_reject_close_buddy_request(self):
        self.make_mutual_buddies(self.user, self.other_user)
        cbr = CloseBuddyRequest.objects.create(sender=self.other_user, receiver=self.user, status='pending')

        # Respond with reject
        url = reverse('close-buddy-request-respond')
        response = self.client.post(url, {"request_id": cbr.id, "action": "rejected"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cbr.refresh_from_db()
        self.assertEqual(cbr.status, 'rejected')

        # List rejected requests
        list_url = reverse('close-buddy-requests-rejected')
        list_response = self.client.get(list_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]['id'], cbr.id)

    def test_ignore_close_buddy_request(self):
        self.make_mutual_buddies(self.user, self.other_user)
        cbr = CloseBuddyRequest.objects.create(sender=self.other_user, receiver=self.user, status='pending')

        # Respond with ignore
        url = reverse('close-buddy-request-respond')
        response = self.client.post(url, {"request_id": cbr.id, "action": "ignored"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        cbr.refresh_from_db()
        self.assertEqual(cbr.status, 'ignored')

        # List ignored requests
        list_url = reverse('close-buddy-requests-ignored')
        list_response = self.client.get(list_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data), 1)
        self.assertEqual(list_response.data[0]['id'], cbr.id)


class SocialListTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="me", email="me@ex.com", password="pass", 
            is_verified=True, phone_number="+2348000000000"
        )
        self.other = User.objects.create_user(
            username="other", email="other@ex.com", password="pass", 
            is_verified=True, phone_number="+2348000000001"
        )
        self.third = User.objects.create_user(
            username="third", email="third@ex.com", password="pass", 
            is_verified=True, phone_number="+2348000000002"
        )
        self.client.force_authenticate(user=self.user)
        
        # Follow relations:
        # other follows third
        Follow.objects.create(follower=self.other, following=self.third)
        # third follows other
        Follow.objects.create(follower=self.third, following=self.other)

    def test_get_other_user_following_list(self):
        url = reverse('user-following-list', args=[self.other.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # other follows third
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.third.pk)

    def test_get_other_user_followers_list(self):
        url = reverse('user-follower-list', args=[self.other.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # third follows other
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], self.third.pk)

    def test_user_search_includes_relationships(self):
        # 1. Establish relationships
        # User 'me' follows 'other'
        Follow.objects.create(follower=self.user, following=self.other)
        # User 'me' sends a close buddy request to 'other'
        CloseBuddyRequest.objects.create(sender=self.user, receiver=self.other, status='pending')

        # User 'me' and 'third' follow each other (mutual buddies)
        Follow.objects.create(follower=self.user, following=self.third)
        Follow.objects.create(follower=self.third, following=self.user)
        # Verify Buddy record was automatically created via signal
        self.assertTrue(Buddy.objects.filter(user1_id=min(self.user.id, self.third.id), user2_id=max(self.user.id, self.third.id)).exists())
        
        # User 'me' adds 'third' as a close buddy
        CloseBuddy.objects.create(user=self.user, buddy=self.third)

        # 2. Search for 'other'
        url = reverse('user-search') + "?q=other"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        other_data = response.data[0]
        self.assertEqual(other_data['id'], self.other.id)
        self.assertTrue(other_data['is_following'])
        self.assertFalse(other_data['is_followed_by'])
        self.assertFalse(other_data['is_buddy'])
        self.assertFalse(other_data['is_close_buddy'])
        self.assertEqual(other_data['close_buddy_request_status'], 'sent_pending')

        # 3. Search for 'third'
        url = reverse('user-search') + "?q=third"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        third_data = response.data[0]
        self.assertEqual(third_data['id'], self.third.id)
        self.assertTrue(third_data['is_following'])
        self.assertTrue(third_data['is_followed_by'])
        self.assertTrue(third_data['is_buddy'])
        self.assertTrue(third_data['is_close_buddy'])
        self.assertIsNone(third_data['close_buddy_request_status'])



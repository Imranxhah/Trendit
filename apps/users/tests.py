from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth import get_user_model
from .models import ChatReport, OTPVerification, UserViolation
from apps.social.models import Buddy

from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch

User = get_user_model()


class ChatSafetyTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='chat-user', email='chat-user@example.com', password='password', is_verified=True
        )
        self.other = User.objects.create_user(
            username='chat-other', email='chat-other@example.com', password='password', is_verified=True
        )
        Buddy.objects.create(user1=self.user, user2=self.other)
        self.relationship_url = reverse('chat-relationship', args=[self.other.pk])
        self.report_url = reverse('chat-report')
        self.client.force_authenticate(user=self.user)

    def test_user_can_block_and_unblock_chat_participant(self):
        response = self.client.post(self.relationship_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.user.profile.blocked_users.filter(pk=self.other.profile.pk).exists())

        status_response = self.client.get(self.relationship_url)
        self.assertTrue(status_response.data['blocked_by_me'])

        response = self.client.delete(self.relationship_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(self.user.profile.blocked_users.filter(pk=self.other.profile.pk).exists())

    def test_user_can_report_a_valid_conversation(self):
        room_id = '_'.join(sorted([str(self.user.pk), str(self.other.pk)]))
        response = self.client.post(self.report_url, {
            'reported_user_id': self.other.pk,
            'room_id': room_id,
            'message_id': 'message-1',
            'reason': 'harassment',
            'details': 'Repeated abusive messages.',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ChatReport.objects.filter(
            reporter=self.user,
            reported_user=self.other,
            room_id=room_id,
        ).exists())

    def test_report_rejects_forged_room_id(self):
        response = self.client.post(self.report_url, {
            'reported_user_id': self.other.pk,
            'room_id': 'forged-room',
            'reason': 'spam',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.core.fcm_utils.send_push_notification')
    @patch('apps.content.moderation.analyze_caption')
    @patch('firebase_admin.firestore.client')
    def test_chat_notification_does_not_run_caption_models(
        self, firestore_client, analyze, send_push
    ):
        firestore_client.return_value.collection.return_value.document.return_value.get.return_value.exists = False
        room_id = '_'.join(sorted([str(self.user.pk), str(self.other.pk)]))
        response = self.client.post(reverse('notify-chat'), {
            'receiver_id': self.other.pk,
            'room_id': room_id,
            'message_type': 'text',
            'message_text': 'Send this directly.',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        analyze.assert_not_called()
        send_push.assert_called_once()
        self.assertTrue(send_push.call_args.kwargs['display_notification'])

    @patch('apps.core.fcm_utils.send_push_notification')
    def test_chat_notification_requires_buddies(self, send_push):
        Buddy.objects.all().delete()
        room_id = '_'.join(sorted([str(self.user.pk), str(self.other.pk)]))
        response = self.client.post(reverse('notify-chat'), {
            'receiver_id': self.other.pk,
            'room_id': room_id,
            'message_type': 'text',
            'message_text': 'This should not be delivered.',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        send_push.assert_not_called()

class UserAuthTests(APITestCase):
    def setUp(self):
        self.register_url = reverse('register')
        self.verify_url = reverse('verify-otp')
        self.login_url = reverse('token_obtain_pair')
        self.user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "phone_number": "+12125550123",
            "password": "testpassword123"
        }

    def test_registration_and_otp_generation(self):
        response = self.client.post(self.register_url, self.user_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email=self.user_data['email']).exists())
        self.assertTrue(OTPVerification.objects.filter(user__email=self.user_data['email']).exists())

    def test_registration_with_invalid_phone_number(self):
        """An invalid phone number should be rejected."""
        data = self.user_data.copy()
        data['phone_number'] = 'invalid-phone'
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_otp_verification(self):
        # Register user
        self.client.post(self.register_url, self.user_data)
        user = User.objects.get(email=self.user_data['email'])
        otp_obj = OTPVerification.objects.get(user=user)
        
        # Verify
        verify_data = {
            "email": user.email,
            "otp_code": otp_obj.otp_code
        }
        response = self.client.post(self.verify_url, verify_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        user.refresh_from_db()
        self.assertTrue(user.is_verified)

    def test_login_unverified_user_blocked(self):
        # Register but don't verify
        self.client.post(self.register_url, self.user_data)
        
        login_data = {
            "username": self.user_data['email'], # Dual login backend handles this
            "password": self.user_data['password']
        }
        response = self.client.post(self.login_url, login_data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('ACCOUNT_NOT_VERIFIED', str(response.data))

    def test_dual_login_email(self):
        # Register and verify
        self.client.post(self.register_url, self.user_data)
        user = User.objects.get(email=self.user_data['email'])
        user.is_verified = True
        user.save()

        # Login with Email
        login_data = {"username": self.user_data['email'], "password": self.user_data['password']}
        response = self.client.post(self.login_url, login_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

from .models import Profile
from apps.content.models import Category, Post
from apps.social.models import Vote

class ProfileStatsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="statuser", email="stats@t.com", password="p", phone_number="+15551234567", is_verified=True)
        self.category = Category.objects.create(name="Stats")

    def test_profile_auto_creation(self):
        self.assertTrue(Profile.objects.filter(user=self.user).exists())

    def test_post_count_update(self):
        post = Post.objects.create(author=self.user, caption="Post 1")
        post.categories.set([self.category])
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.total_posts, 1)

    def test_rating_count_update(self):
        post = Post.objects.create(author=self.user, caption="Post 1")
        post.categories.set([self.category])
        Vote.objects.create(post=post, user=self.user, value=5)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.total_ratings_received, 1)


class BanFeatureTests(APITestCase):
    def setUp(self):
        self.login_url = reverse('token_obtain_pair')
        self.ban_url = lambda uid: reverse('ban-user', args=[uid])
        self.unban_url = lambda uid: reverse('unban-user', args=[uid])

        # A regular verified user
        self.regular_user = User.objects.create_user(
            username="bantest", email="bantest@example.com",
            password="pass1234", phone_number="+19990001111",
            is_verified=True
        )

        # An admin user
        self.admin_user = User.objects.create_user(
            username="adminuser", email="admin@example.com",
            password="adminpass123", phone_number="+19990002222",
            is_verified=True, is_staff=True
        )

    def _login_data(self, user, password):
        return {"username": user.email, "password": password}

    def test_banned_user_cannot_login(self):
        """A verified but banned user should get 401 with 'account_banned' code."""
        self.regular_user.is_banned = True
        self.regular_user.ban_reason = "Violating Terms of Service"
        self.regular_user.save()

        response = self.client.post(self.login_url, self._login_data(self.regular_user, "pass1234"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('account_banned', str(response.data))

    def test_unbanned_user_can_login(self):
        """After unbanning, the user should be able to log in again."""
        self.regular_user.is_banned = True
        self.regular_user.save()

        # Unban via API
        self.client.force_authenticate(user=self.admin_user)
        self.client.post(self.unban_url(self.regular_user.pk))
        self.client.force_authenticate(user=None)

        response = self.client.post(self.login_url, self._login_data(self.regular_user, "pass1234"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_non_admin_cannot_ban(self):
        """A non-admin user should get 403 when calling the ban endpoint."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post(self.ban_url(self.admin_user.pk), {"ban_reason": "test"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_ban_user(self):
        """Admin should be able to ban a user and the ban is persisted."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            self.ban_url(self.regular_user.pk),
            {"ban_reason": "Spamming"},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.regular_user.refresh_from_db()
        self.assertTrue(self.regular_user.is_banned)
        self.assertEqual(self.regular_user.ban_reason, "Spamming")

    def test_cannot_ban_superuser(self):
        """Attempting to ban a superuser should return 403."""
        superuser = User.objects.create_superuser(
            username="superadmin", email="super@example.com",
            password="superpass", phone_number="+18880001111"
        )
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(self.ban_url(superuser.pk), {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class UserProfileDetailTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="me", email="me@example.com", password="password", is_verified=True
        )
        self.other = User.objects.create_user(
            username="other", email="other@example.com", password="password", is_verified=True
        )
        self.detail_url = lambda uid: reverse('user-profile-detail', args=[uid])

    def test_unauthenticated_blocked(self):
        response = self.client.get(self.detail_url(self.other.pk))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_view_other_user_profile_detail_basic(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.detail_url(self.other.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check standard data wrapper
        data = response.data
        self.assertEqual(data['username'], "other")
        self.assertEqual(data['followers_count'], 0)
        self.assertEqual(data['following_count'], 0)
        self.assertEqual(data['buddies_count'], 0)
        self.assertEqual(data['total_posts'], 0)
        self.assertFalse(data['is_following'])
        self.assertFalse(data['is_followed_by'])
        self.assertFalse(data['is_buddy'])
        self.assertFalse(data['is_close_buddy'])
        self.assertIsNone(data['close_buddy_request_status'])

    def test_view_other_user_profile_detail_with_relations(self):
        from apps.social.models import Follow, Buddy, CloseBuddyRequest
        
        # Establish mutual follows (Buddy)
        Follow.objects.create(follower=self.user, following=self.other)
        Follow.objects.create(follower=self.other, following=self.user)
        
        # Send Close Buddy Request
        CloseBuddyRequest.objects.create(sender=self.user, receiver=self.other, status='pending')

        self.client.force_authenticate(user=self.user)
        response = self.client.get(self.detail_url(self.other.pk))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        data = response.data
        self.assertEqual(data['followers_count'], 1)
        self.assertEqual(data['following_count'], 1)
        self.assertEqual(data['buddies_count'], 1)
        self.assertTrue(data['is_following'])
        self.assertTrue(data['is_followed_by'])
        self.assertTrue(data['is_buddy'])
        self.assertEqual(data['close_buddy_request_status'], "sent_pending")


class UserViolationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="violator",
            email="violator@example.com",
            password="password123",
            is_verified=True
        )
        self.violation_url = reverse('record-violation')

    def test_unauthenticated_blocked(self):
        response = self.client.post(self.violation_url, {})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_record_violations_up_to_ban(self):
        self.client.force_authenticate(user=self.user)

        # 1st violation
        response = self.client.post(self.violation_url, {
            "rule_broken": "No spamming",
            "description": "User spammed the chat room."
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['total_violations'], 1)
        self.assertEqual(response.data['remaining_violations'], 2)
        self.assertFalse(response.data['is_banned'])

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_banned)

        # 2nd violation
        response = self.client.post(self.violation_url, {
            "rule_broken": "Inappropriate language"
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['total_violations'], 2)
        self.assertEqual(response.data['remaining_violations'], 1)
        self.assertFalse(response.data['is_banned'])

        # 3rd violation - should trigger ban
        response = self.client.post(self.violation_url, {
            "rule_broken": "Harassment"
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['total_violations'], 3)
        self.assertEqual(response.data['remaining_violations'], 0)
        self.assertTrue(response.data['is_banned'])

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_banned)
        self.assertIn("Harassment", self.user.ban_reason)


from unittest.mock import patch
from django.test import override_settings

class GoogleLoginTests(APITestCase):
    def setUp(self):
        self.google_login_url = reverse('google_login')

    @override_settings(GOOGLE_CLIENT_ID_WEB='test-client-id')
    @patch('apps.users.serializers.id_token.verify_oauth2_token')
    def test_google_login_creates_new_user(self, mock_verify):
        mock_verify.return_value = {
            'iss': 'accounts.google.com',
            'aud': 'test-client-id',
            'email': 'newgoogleuser@example.com',
            'given_name': 'Google',
            'family_name': 'User'
        }

        response = self.client.post(self.google_login_url, {'id_token': 'fake-token'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        
        # User should be created and verified
        user = User.objects.get(email='newgoogleuser@example.com')
        self.assertTrue(user.is_verified)
        self.assertEqual(user.first_name, 'Google')

    @override_settings(GOOGLE_CLIENT_ID_WEB='test-client-id')
    @patch('apps.users.serializers.id_token.verify_oauth2_token')
    def test_google_login_existing_user(self, mock_verify):
        # Create user manually
        User.objects.create_user(
            username='existinggoogle',
            email='existinggoogle@example.com',
            is_verified=False
        )

        mock_verify.return_value = {
            'iss': 'accounts.google.com',
            'aud': 'test-client-id',
            'email': 'existinggoogle@example.com',
        }

        response = self.client.post(self.google_login_url, {'id_token': 'fake-token'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

        # User should now be verified
        user = User.objects.get(email='existinggoogle@example.com')
        self.assertTrue(user.is_verified)

    @override_settings(GOOGLE_CLIENT_ID_WEB='test-client-id')
    @patch('apps.users.serializers.id_token.verify_oauth2_token')
    def test_google_login_invalid_token(self, mock_verify):
        mock_verify.side_effect = ValueError('Invalid token')

        response = self.client.post(self.google_login_url, {'id_token': 'fake-invalid-token'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('Invalid Google token', str(response.data))

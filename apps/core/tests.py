from django.test import Client, TestCase
from django.test import override_settings
from django.urls import reverse
from .models import ApkDownloadCounter, AppSettings, Notification, Report
from django.contrib.auth import get_user_model
from apps.content.models import Post, Category
from .serializers import NotificationSerializer
from .fcm_utils import _is_invalid_fcm_token_error, _prepare_fcm_data

User = get_user_model()


class FcmPayloadTests(TestCase):
    def test_reserved_message_type_key_is_remapped(self):
        payload = _prepare_fcm_data({
            "type": "chat_message",
            "message_type": "image",
            "unread_count": 2,
        })

        self.assertEqual(payload["chat_message_type"], "image")
        self.assertEqual(payload["unread_count"], "2")
        self.assertNotIn("message_type", payload)

    def test_compact_not_registered_error_is_an_invalid_token(self):
        self.assertTrue(
            _is_invalid_fcm_token_error(Exception("NotRegistered"))
        )


class CoreModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", email="test@test.com", password="password")
        self.category = Category.objects.create(name="General")
        self.post = Post.objects.create(author=self.user, caption="Test Post")
        self.post.categories.set([self.category])

    def test_app_settings_singleton(self):
        AppSettings.objects.create(upload_start_time="08:00", upload_end_time="20:00")
        with self.assertRaises(ValueError):
            AppSettings.objects.create(upload_start_time="09:00", upload_end_time="21:00")

    def test_notification_creation(self):
        notif = Notification.objects.create(
            recipient=self.user,
            actor=self.user,
            verb="liked your post",
            target=self.post
        )
        self.assertEqual(notif.target, self.post)

    def test_notification_includes_actor_profile_picture(self):
        self.user.profile_picture = 'profile_pics/avatar.jpg'
        self.user.save(update_fields=['profile_picture'])
        notif = Notification.objects.create(
            recipient=self.user,
            actor=self.user,
            verb='followed you',
            target=self.post,
        )

        data = NotificationSerializer(notif).data

        self.assertIn('profile_pics/avatar.jpg', data['actor_profile_picture'])

    def test_report_creation(self):
        report = Report.objects.create(
            reporter=self.user,
            content_object=self.post,
            reason="Spam"
        )
        self.assertEqual(report.content_object, self.post)
        self.assertEqual(report.status, 'submitted')


class LandingPageTests(TestCase):
    def setUp(self):
        ApkDownloadCounter.objects.update_or_create(
            pk=1,
            defaults={"count": 3017},
        )

    @override_settings(
        TRENDIT_APK_DOWNLOAD_URL='https://example.com/releases/trendit.apk',
        TRENDIT_APP_VERSION='9.4.1',
    )
    def test_landing_page_uses_configured_release(self):
        response = self.client.get(reverse('landing-page'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'https://example.com/releases/trendit.apk')
        self.assertContains(response, 'Version 9.4.1')
        self.assertContains(response, '3,017')
        self.assertContains(response, 'total downloads')
        self.assertTemplateUsed(response, 'core/landing_page.html')

    def test_apk_download_click_increments_persistent_counter(self):
        response = self.client.post(reverse('apk-download-count'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"downloads": 3018})
        self.assertEqual(ApkDownloadCounter.objects.get(pk=1).count, 3018)

        landing_response = self.client.get(reverse('landing-page'))
        self.assertContains(landing_response, '3,018')

    def test_landing_page_view_does_not_increment_counter(self):
        self.client.get(reverse('landing-page'))

        self.assertEqual(ApkDownloadCounter.objects.get(pk=1).count, 3017)

    def test_browser_click_can_increment_with_csrf_protection(self):
        browser_client = Client(enforce_csrf_checks=True)
        browser_client.get(reverse('landing-page'))
        csrf_token = browser_client.cookies['csrftoken'].value

        response = browser_client.post(
            reverse('apk-download-count'),
            {'csrfmiddlewaretoken': csrf_token},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"downloads": 3018})

    def test_post_share_browser_falls_back_to_landing_page(self):
        response = self.client.get(
            reverse('post-share-landing', args=[42])
        )

        self.assertRedirects(response, reverse('landing-page'))

from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from .models import AppSettings, Notification, Report
from django.contrib.auth import get_user_model
from apps.content.models import Post, Category
from .serializers import NotificationSerializer

User = get_user_model()

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
    @override_settings(
        TRENDIT_APK_DOWNLOAD_URL='https://example.com/releases/trendit.apk',
        TRENDIT_APP_VERSION='9.4.1',
    )
    def test_landing_page_uses_configured_release(self):
        response = self.client.get(reverse('landing-page'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'https://example.com/releases/trendit.apk')
        self.assertContains(response, 'Version 9.4.1')
        self.assertTemplateUsed(response, 'core/landing_page.html')

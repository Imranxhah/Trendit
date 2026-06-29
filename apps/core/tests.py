from django.test import TestCase
from .models import AppSettings, Notification, Report
from django.contrib.auth import get_user_model
from apps.content.models import Post, Category

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

    def test_report_creation(self):
        report = Report.objects.create(
            reporter=self.user,
            content_object=self.post,
            reason="Spam"
        )
        self.assertEqual(report.content_object, self.post)
        self.assertEqual(report.status, 'submitted')

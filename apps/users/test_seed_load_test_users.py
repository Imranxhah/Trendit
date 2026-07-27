import re
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.users.models import Profile


class SeedLoadTestUsersCommandTests(TestCase):
    def test_command_requires_explicit_confirmation(self):
        with self.assertRaises(CommandError):
            call_command("seed_load_test_users", count=3)

    def test_command_creates_searchable_non_login_users_and_profiles(self):
        output = StringIO()

        call_command(
            "seed_load_test_users",
            count=12,
            prefix="loadtest_test",
            batch_size=5,
            yes=True,
            stdout=output,
        )

        User = get_user_model()
        users = User.objects.filter(username__startswith="loadtest_test_")
        self.assertEqual(users.count(), 12)
        self.assertEqual(
            Profile.objects.filter(user__in=users).count(),
            12,
        )
        self.assertTrue(all(not user.has_usable_password() for user in users))
        self.assertTrue(
            all(
                re.fullmatch(
                    r"[a-z]+\.[a-z]+\.\d{4}@example\.(com|net|org)",
                    user.email,
                )
                for user in users
            )
        )
        self.assertEqual(
            users.values("phone_number").distinct().count(),
            12,
        )
        self.assertTrue(
            all(str(user.phone_number).startswith("+9236") for user in users)
        )
        first_user = users.order_by("username").first()
        self.assertEqual(first_user.first_name, "Aariz")
        self.assertEqual(first_user.last_name, "Abbasi")
        self.assertEqual(first_user.email, "aariz.abbasi.0001@example.com")
        self.assertEqual(str(first_user.phone_number), "+923600000001")
        self.assertIn("created=12", output.getvalue())

    def test_command_is_idempotent_and_cleanup_removes_only_its_dataset(self):
        User = get_user_model()
        real_user = User.objects.create_user(
            username="real_user",
            email="real@example.com",
            password="password",
        )

        call_command(
            "seed_load_test_users",
            count=7,
            prefix="loadtest_repeat",
            yes=True,
        )
        call_command(
            "seed_load_test_users",
            count=7,
            prefix="loadtest_repeat",
            yes=True,
        )
        self.assertEqual(
            User.objects.filter(username__startswith="loadtest_repeat_").count(),
            7,
        )

        delete_output = StringIO()
        call_command(
            "seed_load_test_users",
            prefix="loadtest_repeat",
            delete=True,
            yes=True,
            stdout=delete_output,
        )
        self.assertFalse(
            User.objects.filter(username__startswith="loadtest_repeat_").exists()
        )
        self.assertTrue(User.objects.filter(pk=real_user.pk).exists())
        self.assertIn("Deleted 7 load-test users", delete_output.getvalue())

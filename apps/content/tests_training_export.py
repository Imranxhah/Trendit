import json
import tempfile
from pathlib import Path

from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from apps.content.management.commands.export_training_captions import redact_caption
from apps.content.models import Post
from apps.users.models import User


class TrainingCaptionExportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="dataset-owner",
            email="dataset-owner@example.com",
            password="test-password",
        )

    def test_redaction_masks_direct_identifiers(self):
        value = redact_caption("Email me at person@example.com or call +1 212 555 0199 @private")
        self.assertEqual(value, "Email me at [EMAIL] or call [PHONE] [USER]")

    def test_command_requires_explicit_consent(self):
        with self.assertRaises(CommandError):
            call_command("export_training_captions")

    def test_export_contains_no_account_identifiers(self):
        Post.objects.create(
            author=self.user,
            caption="Contact person@example.com about this post",
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with override_settings(BASE_DIR=root, CAPTION_EXPORT_PSEUDONYM_KEY="test-key"):
                output = root / "private_training_exports" / "captions.jsonl"
                call_command(
                    "export_training_captions",
                    acknowledge_consent=True,
                    output=str(output),
                )
                record = json.loads(output.read_text(encoding="utf-8").splitlines()[0])

        self.assertEqual(record["text_redacted"], "Contact [EMAIL] about this post")
        self.assertNotIn(self.user.username, json.dumps(record))
        self.assertNotEqual(record["author_group_id"], str(self.user.id))
        self.assertEqual(len(record["author_group_id"]), 64)

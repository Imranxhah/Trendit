import hashlib
import hmac
import json
import re
import secrets
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.content.models import Post, SubPost


EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
URL_RE = re.compile(r"(?i)\b(?:https?://|www\.)\S+|\b\S+\.(?:com|org|net|io|co)(?:/\S*)?")
MENTION_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{1,30}")
PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
SPACE_RE = re.compile(r"\s+")


def redact_caption(value):
    text = str(value or "")
    text = EMAIL_RE.sub("[EMAIL]", text)
    text = URL_RE.sub("[URL]", text)
    text = MENTION_RE.sub("[USER]", text)
    text = PHONE_RE.sub("[PHONE]", text)
    return SPACE_RE.sub(" ", text).strip()


def pseudonymize(secret, namespace, value):
    material = f"{namespace}:{value}".encode("utf-8")
    return hmac.new(secret, material, hashlib.sha256).hexdigest()


class Command(BaseCommand):
    help = "Export de-identified post captions for private moderation annotation."

    def add_arguments(self, parser):
        parser.add_argument(
            "--acknowledge-consent",
            action="store_true",
            help="Confirm that the application's privacy policy permits this training export.",
        )
        parser.add_argument(
            "--output",
            default=str(Path(settings.BASE_DIR) / "private_training_exports" / "trendit_captions.jsonl"),
        )
        parser.add_argument("--include-rejected", action="store_true")
        parser.add_argument("--limit", type=int, default=None)

    def handle(self, *args, **options):
        if not options["acknowledge_consent"]:
            raise CommandError("Pass --acknowledge-consent after confirming user consent and policy coverage.")

        output = Path(options["output"]).expanduser().resolve()
        export_root = (Path(settings.BASE_DIR) / "private_training_exports").resolve()
        if export_root != output.parent and export_root not in output.parents:
            raise CommandError(f"Output must stay inside {export_root}")
        output.parent.mkdir(parents=True, exist_ok=True)

        configured_key = getattr(settings, "CAPTION_EXPORT_PSEUDONYM_KEY", "")
        secret = configured_key.encode("utf-8") if configured_key else secrets.token_bytes(32)
        records = self._records(options["include_rejected"])
        if options["limit"] is not None:
            records = records[: max(options["limit"], 0)]

        written = 0
        with output.open("w", encoding="utf-8") as handle:
            for source_kind, source_id, author_id, caption in records:
                redacted = redact_caption(caption)
                if not redacted:
                    continue
                record = {
                    "id": pseudonymize(secret, source_kind, source_id),
                    "text_redacted": redacted,
                    "source_kind": source_kind,
                    "author_group_id": pseudonymize(secret, "author", author_id),
                    "labels": {
                        "sexual_explicit": None,
                        "profanity_obscene": None,
                        "harassment_insult": None,
                        "threat_violence": None,
                        "hate_identity_attack": None,
                    },
                    "review_status": "pending",
                    "reviewer_id": "",
                    "review_notes": "",
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1

        self.stdout.write(self.style.SUCCESS(f"Exported {written} de-identified captions to {output}"))
        if not configured_key:
            self.stdout.write(
                self.style.WARNING(
                    "CAPTION_EXPORT_PSEUDONYM_KEY is not configured; this export used a one-time key. "
                    "Set it to preserve stable author groups across future exports."
                )
            )

    @staticmethod
    def _records(include_rejected):
        post_query = Post.objects.exclude(caption="").order_by("id")
        if not include_rejected:
            post_query = post_query.exclude(status="rejected")
        posts = [
            ("post", row[0], row[1], row[2])
            for row in post_query.values_list("id", "author_id", "caption")
        ]
        sub_posts = [
            ("sub_post", row[0], row[1], row[2])
            for row in SubPost.objects.exclude(caption="").order_by("id").values_list(
                "id", "author_id", "caption"
            )
        ]
        return posts + sub_posts

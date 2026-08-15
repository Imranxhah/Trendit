from unittest.mock import patch

import numpy as np
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.content.moderation import (
    LABELS,
    CaptionModerationDecision,
    analyze_caption,
    normalize_caption,
)
from apps.content.models import CaptionModerationEvent, Post
from apps.users.models import User


import json
from unittest.mock import MagicMock

class CaptionModerationTests(SimpleTestCase):
    def setUp(self):
        from django.conf import settings
        settings.SIGHTENGINE_TEXT_API_USER = 'dummy-user'
        settings.SIGHTENGINE_TEXT_API_SECRET = 'dummy-secret'

    def _mock_response(self, moderation_classes=None, profanity_matches=None):
        base_classes = {
            "sexual": 0.01,
            "discriminatory": 0.01,
            "insulting": 0.01,
            "violent": 0.01,
            "toxic": 0.01
        }
        if moderation_classes:
            base_classes.update(moderation_classes)
            
        data = {
            "status": "success",
            "moderation_classes": base_classes,
            "profanity": {
                "matches": profanity_matches or []
            }
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(data).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    def test_normalization_masks_private_contact_data(self):
        value = normalize_caption('Call +1 212 555 0199 or email a@example.com')
        self.assertEqual(value, 'Call [PHONE] or email [EMAIL]')

    @patch('urllib.request.urlopen')
    def test_explicit_direct_threat_is_blocked_by_high_precision_safety_net(self, mock_urlopen):
        # Even if OpenAI returns low score, our regex overrides it
        mock_urlopen.return_value = self._mock_response()
        result = analyze_caption('I will fuck you up bitch')
        self.assertEqual(result.decision, 'block')
        self.assertIn('threat_violence', result.reasons)

    @patch('urllib.request.urlopen')
    def test_benign_flower_caption_is_allowed(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response()
        result = analyze_caption('A nice pink flower.')
        self.assertEqual(result.decision, 'allow')
        self.assertEqual(result.reasons, [])

    @patch('urllib.request.urlopen')
    def test_educational_sexual_health_context_is_not_blocked(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response(
            moderation_classes={"sexual": 0.99}
        )
        result = analyze_caption('An educational documentary about sexual health and consent.')
        self.assertEqual(result.decision, 'allow')

    @patch('urllib.request.urlopen')
    def test_identity_score_without_abusive_context_is_not_blocked(self, mock_urlopen):
        # We removed the old arbitrary matrix logic since OpenAI handles contextual hate well.
        # This test ensures if OpenAI says it's NOT hate, we allow it.
        mock_urlopen.return_value = self._mock_response()
        result = analyze_caption('Muslim families celebrated the holiday together.')
        self.assertEqual(result.decision, 'allow')



class CaptionModerationEndpointTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='moderation-user',
            email='moderation@example.com',
            password='test-password',
            has_completed_profile=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch('apps.content.views.analyze_caption')
    def test_blocked_preflight_is_returned_and_audited_without_raw_caption(self, analyze):
        analyze.return_value = CaptionModerationDecision(
            decision='block',
            scores={'threat_violence': 0.99},
            reasons=['threat_violence'],
            model_version='test-v1',
            caption_fingerprint='a' * 64,
        )
        response = self.client.post(
            '/api/content/moderate-caption/',
            {'caption': 'blocked text'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['decision'], 'block')
        event = CaptionModerationEvent.objects.get()
        self.assertEqual(event.decision, 'block')
        self.assertFalse(hasattr(event, 'caption'))

    @patch('apps.content.serializers.analyze_caption')
    def test_uncertain_severe_caption_edit_returns_active_post_to_pending(self, analyze):
        post = Post.objects.create(author=self.user, caption='Original caption', status='active')
        analyze.return_value = CaptionModerationDecision(
            decision='review',
            scores={'hate_identity_attack': 0.6},
            reasons=['hate_identity_attack'],
            model_version='test-v1',
            caption_fingerprint='b' * 64,
        )
        response = self.client.patch(
            f'/api/content/posts/{post.id}/',
            {'caption': 'Uncertain edited caption'},
            format='json',
        )

        self.assertEqual(response.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.status, 'pending')

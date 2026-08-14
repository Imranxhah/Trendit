"""
Media NSFW moderation via Sightengine (https://sightengine.com).

Checks a publicly accessible media URL (image or video thumbnail) against
Sightengine's nudity-2.1 model and returns a structured decision.

Design choices:
- URL-based API call: the media is already on Cloudinary, so Sightengine fetches
  it directly — we never re-upload raw bytes.
- Images only (synchronous): video NSFW scanning via Sightengine is async/webhook
  and is out of scope for this integration.
- Fail-safe: if Sightengine is unreachable or credentials are missing, a
  MediaModerationUnavailable exception is raised and the caller is responsible
  for deciding whether to block or allow (default: allow + log warning).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_SIGHTENGINE_CHECK_URL = 'https://api.sightengine.com/1.0/check.json'
_NUDITY_MODEL = 'nudity-2.1'


class MediaModerationUnavailable(Exception):
    """Raised when Sightengine cannot be reached or returns an API error."""


@dataclass(frozen=True)
class MediaModerationResult:
    """
    Structured result from Sightengine's nudity-2.1 model.

    Attributes:
        decision:      'allow' | 'review' | 'block'
        raw_score:     probability of explicit nudity (0–1)
        partial_score: probability of suggestive content, e.g. bikini (0–1)
        safe_score:    probability of safe content (0–1)
    """
    decision: str
    raw_score: float
    partial_score: float
    safe_score: float


def check_media_url(media_url: str) -> MediaModerationResult:
    """
    Call Sightengine nudity-2.1 on a public image URL and return the result.

    Raises:
        MediaModerationUnavailable: on network error, timeout, or API failure.
    """
    api_user: str = getattr(settings, 'SIGHTENGINE_API_USER', '')
    api_secret: str = getattr(settings, 'SIGHTENGINE_API_SECRET', '')
    block_threshold: float = float(getattr(settings, 'SIGHTENGINE_BLOCK_THRESHOLD', 0.6))
    review_threshold: float = float(getattr(settings, 'SIGHTENGINE_REVIEW_THRESHOLD', 0.3))

    if not api_user or not api_secret:
        raise MediaModerationUnavailable(
            'Sightengine credentials (SIGHTENGINE_API_USER / SIGHTENGINE_API_SECRET) '
            'are not configured.'
        )

    try:
        response = requests.get(
            _SIGHTENGINE_CHECK_URL,
            params={
                'url': media_url,
                'models': _NUDITY_MODEL,
                'api_user': api_user,
                'api_secret': api_secret,
            },
            timeout=12,
        )
        response.raise_for_status()
        data: dict = response.json()
    except requests.Timeout as exc:
        raise MediaModerationUnavailable('Sightengine request timed out.') from exc
    except requests.RequestException as exc:
        raise MediaModerationUnavailable(f'Sightengine request failed: {exc}') from exc

    if data.get('status') != 'success':
        error_msg = data.get('error', {}).get('message', 'Unknown Sightengine error')
        raise MediaModerationUnavailable(f'Sightengine API error: {error_msg}')

    nudity = data.get('nudity', {})
    raw = float(nudity.get('raw', 0.0))
    partial = float(nudity.get('partial', 0.0))
    safe = float(nudity.get('safe', 1.0))

    if raw >= block_threshold:
        decision = 'block'
    elif raw >= review_threshold:
        decision = 'review'
    else:
        decision = 'allow'

    logger.info(
        'Sightengine: decision=%s raw=%.3f partial=%.3f safe=%.3f url=%s',
        decision, raw, partial, safe, media_url,
    )
    return MediaModerationResult(
        decision=decision,
        raw_score=raw,
        partial_score=partial,
        safe_score=safe,
    )

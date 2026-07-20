from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

import joblib
from django.conf import settings


LABELS = (
    'sexual_explicit',
    'profanity_obscene',
    'harassment_insult',
    'threat_violence',
    'hate_identity_attack',
)
SEVERE_LABELS = {'sexual_explicit', 'threat_violence', 'hate_identity_attack'}
SPACE_RE = re.compile(r'\s+')
URL_RE = re.compile(r'(?i)\b(?:https?://|www\.)\S+|\b\S+\.(?:com|org|net|io|co)(?:/\S*)?')
EMAIL_RE = re.compile(r'(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b')
MENTION_RE = re.compile(r'(?<!\w)@[A-Za-z0-9_]{1,30}')
PHONE_RE = re.compile(r'(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)')
EXPLICIT_THREAT_RE = re.compile(
    r'(?i)\b(?:i(?:\s+will|\'ll|m\s+going\s+to)?\s+)?'
    r'(?:kill|murder|shoot|stab|rape|hurt|beat|destroy|fuck)\s+(?:you|him|her|them)\b'
)
BENIGN_SEXUAL_CONTEXT_RE = re.compile(
    r'(?i)\b(?:education|educational|health|medical|medicine|clinical|research|documentary|news|awareness|anatomy|consent|museum|history)\b'
)


class ModerationUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class CaptionModerationDecision:
    decision: str
    scores: dict[str, float]
    reasons: list[str]
    model_version: str
    caption_fingerprint: str


def normalize_caption(caption):
    value = unicodedata.normalize('NFKC', str(caption or ''))
    value = EMAIL_RE.sub('[EMAIL]', value)
    value = URL_RE.sub('[URL]', value)
    value = MENTION_RE.sub('[USER]', value)
    value = PHONE_RE.sub('[PHONE]', value)
    return SPACE_RE.sub(' ', value).strip()


@lru_cache(maxsize=1)
def _load_assets():
    asset_dir = settings.CAPTION_MODERATION_ASSET_DIR
    metadata_path = asset_dir / 'caption_moderation_v1.json'
    model_path = asset_dir / 'caption_moderation_v1.joblib'
    if not metadata_path.exists() or not model_path.exists():
        raise ModerationUnavailable('Caption moderation assets are not installed on the server.')
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    if metadata.get('labels') != list(LABELS):
        raise ModerationUnavailable('Caption moderation labels do not match the server policy.')
    return joblib.load(model_path), metadata


def analyze_caption(caption):
    normalized = normalize_caption(caption)
    fingerprint = hashlib.sha256(normalized.casefold().encode('utf-8')).hexdigest()
    if not normalized:
        return CaptionModerationDecision('allow', {label: 0.0 for label in LABELS}, [], 'empty-v1', fingerprint)
    model, metadata = _load_assets()
    probabilities = model.predict_proba([normalized])[0]
    scores = {label: round(float(probabilities[index]), 6) for index, label in enumerate(LABELS)}
    thresholds = metadata['thresholds']
    reasons = [label for label in LABELS if scores[label] >= thresholds[label]['review']]
    has_identity_context = (
        scores['harassment_insult'] >= thresholds['harassment_insult']['review']
        or scores['threat_violence'] >= thresholds['threat_violence']['review']
        or scores['profanity_obscene'] >= thresholds['profanity_obscene']['review']
    )
    has_benign_sexual_context = bool(BENIGN_SEXUAL_CONTEXT_RE.search(normalized))
    if not has_identity_context and 'hate_identity_attack' in reasons:
        reasons.remove('hate_identity_attack')
    if has_benign_sexual_context and 'sexual_explicit' in reasons:
        reasons.remove('sexual_explicit')

    blocking = []
    if scores['threat_violence'] >= thresholds['threat_violence']['block']:
        blocking.append('threat_violence')
    if (
        scores['hate_identity_attack'] >= thresholds['hate_identity_attack']['block']
        and has_identity_context
    ):
        blocking.append('hate_identity_attack')
    if (
        scores['sexual_explicit'] >= thresholds['sexual_explicit']['block']
        and not has_benign_sexual_context
    ):
        blocking.append('sexual_explicit')

    if EXPLICIT_THREAT_RE.search(normalized):
        scores['threat_violence'] = max(scores['threat_violence'], 0.999)
        if 'threat_violence' not in reasons:
            reasons.append('threat_violence')
        blocking.append('threat_violence')

    if blocking:
        decision = 'block'
    elif any(label in SEVERE_LABELS for label in reasons):
        decision = 'review'
    elif reasons:
        decision = 'warn'
    else:
        decision = 'allow'
    return CaptionModerationDecision(
        decision,
        scores,
        sorted(set(reasons)),
        metadata['model_version'],
        fingerprint,
    )


def record_moderation_event(user, result, post=None):
    from .models import CaptionModerationEvent

    return CaptionModerationEvent.objects.create(
        user=user,
        post=post,
        caption_fingerprint=result.caption_fingerprint,
        model_version=result.model_version,
        decision=result.decision,
        scores=result.scores,
        reasons=result.reasons,
    )

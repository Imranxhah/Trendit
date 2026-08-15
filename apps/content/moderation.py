from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
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


def analyze_caption(caption):
    normalized = normalize_caption(caption)
    fingerprint = hashlib.sha256(normalized.casefold().encode('utf-8')).hexdigest()
    if not normalized:
        return CaptionModerationDecision('allow', {label: 0.0 for label in LABELS}, [], 'empty-v3', fingerprint)
    
    api_user = getattr(settings, 'SIGHTENGINE_TEXT_API_USER', '')
    api_secret = getattr(settings, 'SIGHTENGINE_TEXT_API_SECRET', '')
    
    if not api_user or not api_secret:
        raise ModerationUnavailable('Sightengine Text API credentials are missing.')
    
    import urllib.parse
    
    params = urllib.parse.urlencode({
        'text': normalized,
        'lang': 'en',
        'mode': 'standard,ml',
        'api_user': api_user,
        'api_secret': api_secret
    })
    url = f"https://api.sightengine.com/1.0/text/check.json?{params}"
    req = urllib.request.Request(url)
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode('utf-8'))
            if result.get('status') != 'success':
                raise ModerationUnavailable(f"Sightengine API error: {result.get('error', {}).get('message', 'Unknown error')}")
    except urllib.error.URLError as e:
        raise ModerationUnavailable(f"Sightengine request error: {e}")

    mod_classes = result.get('moderation_classes', {})
    
    scores = {label: 0.0 for label in LABELS}
    scores['sexual_explicit'] = mod_classes.get('sexual', 0.0)
    scores['harassment_insult'] = mod_classes.get('insulting', 0.0)
    scores['threat_violence'] = mod_classes.get('violent', 0.0)
    scores['hate_identity_attack'] = mod_classes.get('discriminatory', 0.0)
    
    profanity_matches = result.get('profanity', {}).get('matches', [])
    has_profanity = len(profanity_matches) > 0
    
    scores['profanity_obscene'] = max(mod_classes.get('toxic', 0.0), 0.9 if has_profanity else 0.0)

    reasons = []
    blocking = []

    # Use threshold logic (since Sightengine gives probabilities 0-1)
    if scores['sexual_explicit'] >= 0.9:
        reasons.append('sexual_explicit')
        blocking.append('sexual_explicit')
    elif scores['sexual_explicit'] >= 0.5:
        reasons.append('sexual_explicit')
        
    if scores['harassment_insult'] >= 0.9:
        reasons.append('harassment_insult')
        blocking.append('harassment_insult')
    elif scores['harassment_insult'] >= 0.5:
        reasons.append('harassment_insult')
        
    if scores['threat_violence'] >= 0.8:
        reasons.append('threat_violence')
        blocking.append('threat_violence')
    elif scores['threat_violence'] >= 0.5:
        reasons.append('threat_violence')
        
    if scores['hate_identity_attack'] >= 0.8:
        reasons.append('hate_identity_attack')
        blocking.append('hate_identity_attack')
    elif scores['hate_identity_attack'] >= 0.5:
        reasons.append('hate_identity_attack')
        
    if scores['profanity_obscene'] >= 0.9:
        reasons.append('profanity_obscene')
        # Obscene/profanity usually doesn't block entirely unless combined with others, but let's just warn/review

    has_benign_sexual_context = bool(BENIGN_SEXUAL_CONTEXT_RE.search(normalized))
    if has_benign_sexual_context and 'sexual_explicit' in reasons:
        reasons.remove('sexual_explicit')
        if 'sexual_explicit' in blocking:
            blocking.remove('sexual_explicit')

    if EXPLICIT_THREAT_RE.search(normalized):
        scores['threat_violence'] = max(scores['threat_violence'], 0.999)
        if 'threat_violence' not in reasons:
            reasons.append('threat_violence')
        if 'threat_violence' not in blocking:
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
        'sightengine-v1',
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

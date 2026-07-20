# Caption Moderation

Trendit enforces caption moderation twice:

1. Flutter runs the quantized multi-label model before upload for fast feedback.
2. DRF runs the server model during caption preflight and again when a post is created or edited.

The server decision is authoritative. Moderation events store a caption fingerprint,
model version, scores, and reason codes. They never store the raw caption.

## Labels

- `sexual_explicit`
- `profanity_obscene`
- `harassment_insult`
- `threat_violence`
- `hate_identity_attack`

Self-harm and spam are intentionally not present in this checkpoint because they need
separate reviewed datasets.

## PythonAnywhere deployment

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py check
```

The tracked model files must exist in `apps/content/moderation_assets/`. Set these
environment variables when a different asset location is required:

```text
CAPTION_MODERATION_ENABLED=True
CAPTION_MODERATION_ASSET_DIR=apps/content/moderation_assets
CAPTION_EXPORT_PSEUDONYM_KEY=<long-random-production-secret>
```

Reload the PythonAnywhere web app after installing requirements and migrating.
The authenticated preflight endpoint is `POST /api/content/moderate-caption/` with a
JSON body containing `caption`.

## Private caption export

Run this only after confirming that the privacy policy and user consent permit model
training:

```bash
python manage.py export_training_captions --acknowledge-consent
```

Exports stay under `private_training_exports/`, which is Git-ignored. Email addresses,
URLs, mentions, and phone numbers are masked. Account and content IDs are replaced with
keyed pseudonyms so records can be grouped without exposing database identifiers.

The local development database currently contains no posts, so the production export
must be run on PythonAnywhere. Do not commit, email, or upload the resulting JSONL file
to a public dataset service.

## Policy

High-confidence threats, contextual identity attacks, and non-educational explicit
sexual content are blocked. Uncertain severe predictions are retained for review.
Profanity or harassment alone produces a warning decision. A model-only block does not
automatically create an account strike; staff can inspect fingerprinted events in the
Django admin.

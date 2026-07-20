"""
Django settings for trendit_backend project.
Production-ready configuration for PythonAnywhere deployment.
"""

import os
from pathlib import Path
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

CAPTION_MODERATION_ENABLED = config('CAPTION_MODERATION_ENABLED', default=True, cast=bool)
_caption_moderation_asset_dir = Path(config(
    'CAPTION_MODERATION_ASSET_DIR',
    default=str(BASE_DIR / 'apps' / 'content' / 'moderation_assets'),
))
CAPTION_MODERATION_ASSET_DIR = (
    _caption_moderation_asset_dir
    if _caption_moderation_asset_dir.is_absolute()
    else BASE_DIR / _caption_moderation_asset_dir
)
CAPTION_EXPORT_PSEUDONYM_KEY = config('CAPTION_EXPORT_PSEUDONYM_KEY', default='')


# ─── Security ────────────────────────────────────────────────────────────────
SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')

# Secret token for the /api/core/cleanup-media/ cron endpoint
CLEANUP_SECRET_TOKEN = config('CLEANUP_SECRET_TOKEN', default='change-this-cleanup-token')

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*', cast=Csv())



# ─── Application definition ──────────────────────────────────────────────────
INSTALLED_APPS = [
    'unfold',
    'unfold.contrib.filters',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'phonenumber_field',
    'cloudinary_storage',
    'cloudinary',

    # Local apps
    'apps.users',
    'apps.content',
    'apps.social',
    'apps.core',
]

AUTH_USER_MODEL = 'users.User'

AUTHENTICATION_BACKENDS = [
    'apps.users.backends.DualLoginBackend',
    'django.contrib.auth.backends.ModelBackend',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
    'DEFAULT_RENDERER_CLASSES': (
        'apps.core.renderers.StandardizedJSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ),
}

# ─── SimpleJWT ───────────────────────────────────────────────────────────────
from datetime import timedelta

SIMPLE_JWT = {
    # Access token is short-lived — Flutter's Dio interceptor catches 401s and
    # silently swaps it using the refresh token, so 15 min is safe and tight.
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),

    # Refresh token lasts 30 days — covers typical app usage without forcing
    # users to re-login frequently.
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),

    # Each call to /token/refresh/ issues a brand-new refresh token and
    # immediately blacklists the old one — prevents replay attacks.
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,

    # Keeps the last_login field current without extra queries.
    'UPDATE_LAST_LOGIN': True,

    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'trendit_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'trendit_backend.wsgi.application'


# ─── Database ────────────────────────────────────────────────────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            'timeout': 20,
        }
    }
}


# ─── Cloudinary (Media Storage) ──────────────────────────────────────────────
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': config('CLOUDINARY_CLOUD_NAME', default=''),
    'API_KEY': config('CLOUDINARY_API_KEY', default=''),
    'API_SECRET': config('CLOUDINARY_API_SECRET', default=''),
}

# ─── PythonAnywhere Proxy (required for outbound connections on free tier) ────
# PythonAnywhere free accounts cannot make direct outbound TCP connections.
# All external requests (including Cloudinary uploads) must route through
# their HTTP proxy at proxy.server:3128.
# We detect PA by checking if HOME starts with /home/<username> on Linux.
_IS_PYTHONANYWHERE = os.path.exists('/etc/myconfig.fish') or \
    os.environ.get('PYTHONANYWHERE_SITE') or \
    os.environ.get('HOME', '').startswith('/home/')

if _IS_PYTHONANYWHERE:
    _PA_PROXY = 'http://proxy.server:3128'
    # Set for urllib3 / requests (used by cloudinary SDK internally)
    os.environ.setdefault('HTTP_PROXY', _PA_PROXY)
    os.environ.setdefault('HTTPS_PROXY', _PA_PROXY)
    # Set directly on cloudinary SDK config so it routes uploads via the proxy
    import cloudinary
    cloudinary.config(
        cloud_name=CLOUDINARY_STORAGE['CLOUD_NAME'],
        api_key=CLOUDINARY_STORAGE['API_KEY'],
        api_secret=CLOUDINARY_STORAGE['API_SECRET'],
        api_proxy=_PA_PROXY,
    )

STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


# ─── Password validation ─────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ─── Internationalization ────────────────────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# ─── Static & Media files ────────────────────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ─── CORS ────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000,http://127.0.0.1:3000',
    cast=Csv()
)
CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)


# ─── Default primary key field type ─────────────────────────────────────────
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ─── Phone number settings ───────────────────────────────────────────────────
PHONENUMBER_DB_FORMAT = 'E164'
PHONENUMBER_DEFAULT_FORMAT = 'E164'


# ─── Unfold Admin Theme ──────────────────────────────────────────────────────
UNFOLD = {
    "SITE_TITLE": "Trendit Admin",
    "SITE_HEADER": "Trendit Administration",
    "SITE_SYMBOL": "trending_up",
    "SHOW_HISTORY": True,
    "COLORS": {
        "primary": {
            "50": "250 245 255",
            "100": "243 232 255",
            "200": "233 213 255",
            "300": "216 180 254",
            "400": "192 132 252",
            "500": "168 85 247",
            "600": "147 51 234",
            "700": "126 34 206",
            "800": "107 33 168",
            "900": "88 28 135",
            "950": "59 7 100",
        },
    },
}

# ─── Google Auth ─────────────────────────────────────────────────────────────
GOOGLE_CLIENT_ID_WEB = config('GOOGLE_CLIENT_ID_WEB', default='')
GOOGLE_CLIENT_ID_IOS = config('GOOGLE_CLIENT_ID_IOS', default='')
GOOGLE_CLIENT_ID_ANDROID = config('GOOGLE_CLIENT_ID_ANDROID', default='')

# ─── Email Configuration ─────────────────────────────────────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)

# ─── Firebase Admin SDK ──────────────────────────────────────────────────────
import firebase_admin
from firebase_admin import credentials

FIREBASE_CREDENTIALS = config('FIREBASE_CREDENTIALS', default='')
if FIREBASE_CREDENTIALS and os.path.exists(FIREBASE_CREDENTIALS):
    if not firebase_admin._apps:
        try:
            cred = credentials.Certificate(FIREBASE_CREDENTIALS)
            firebase_admin.initialize_app(cred)
            print(f"Firebase Admin initialized with {FIREBASE_CREDENTIALS}")
        except Exception as e:
            print(f"Failed to initialize Firebase Admin: {e}")

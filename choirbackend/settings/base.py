from datetime import timedelta
from pathlib import Path

import dj_database_url
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',

    # Third Party Apps
    'rest_framework',
    'rest_framework_simplejwt',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # Local Apps
    'core',
    'authentication',
    'members',
    'subscriptions',
    'events',
    'attendance',
    'finance',
    'reports',
    'communication',

]

ASGI_APPLICATION = 'choirbackend.asgi.application'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'authentication.middleware.DisableCSRFForAPIMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware'
]

ROOT_URLCONF = 'choirbackend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'choirbackend.wsgi.application'

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=config('DATABASE_URL'),
        conn_max_age=config('CONN_MAX_AGE', default=0, cast=int),
        conn_health_checks=True,
    )
}

# Custom User Model
AUTH_USER_MODEL = 'authentication.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Accra'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SITE_ID = 1

# Allauth Settings
# Allauth Settings
# ACCOUNT_AUTHENTICATION_METHOD is deprecated
ACCOUNT_LOGIN_METHODS = {'email'}
ACCOUNT_ADAPTER = 'authentication.adapters.CustomAccountAdapter'
ACCOUNT_SIGNUP_FIELDS = ['email', 'first_name', 'last_name']

ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = 'username'

# Social Account Settings
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_VERIFICATION = 'none'
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_ADAPTER = 'authentication.adapters.CustomSocialAccountAdapter'

# Social Auth Providers
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': config('GOOGLE_CLIENT_ID', default=''),
            'secret': config('GOOGLE_CLIENT_SECRET', default=''),
            'key': ''
        },
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    }
}

# dj-rest-auth settings
REST_AUTH = {
    'USE_JWT': True,
    'JWT_AUTH_HTTPONLY': False,
    'JWT_AUTH_COOKIE': None,
    'TOKEN_MODEL': None,
    'USER_DETAILS_SERIALIZER': 'authentication.serializers.user_serializers.UserSerializer',
    'REGISTER_SERIALIZER': 'authentication.serializers.user_serializers.RegisterSerializer',
    'LOGIN_ON_REGISTER': False,
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=config('JWT_ACCESS_TOKEN_LIFETIME', default=60, cast=int)),
    'REFRESH_TOKEN_LIFETIME': timedelta(minutes=config('JWT_REFRESH_TOKEN_LIFETIME', default=1440, cast=int)),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': config('JWT_SECRET_KEY', default=SECRET_KEY),
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# CORS Settings
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:3000'
).split(',')
CORS_ALLOW_CREDENTIALS = True

# Spectacular Settings
SPECTACULAR_SETTINGS = {
    'TITLE': 'VocalEssence API',
    'DESCRIPTION': 'Chorale Management Platform API',
    'VERSION': '1.0.0',
    'SWAGGER_UI_SETTINGS': {
        'persistAuthorization': True,
    },
}

HUBTEL_CONFIG = {
    # API Credentials
    'API_ID': config('HUBTEL_API_ID', default=''),
    'API_KEY': config('HUBTEL_API_KEY', default=''),
    'MERCHANT_ACCOUNT_NUMBER': config('HUBTEL_MERCHANT_ACCOUNT_NUMBER', default=''),

    # API URLs
    'PAYMENT_API_URL': 'https://payproxyapi.hubtel.com/items/initiate',
    'STATUS_API_URL': 'https://api-txnstatus.hubtel.com/transactions',

    # Webhook URLs
    'CALLBACK_URL': config('HUBTEL_CALLBACK_URL', default=''),
    'RETURN_URL': config('HUBTEL_RETURN_URL', default=''),
    'CANCELLATION_URL': config('HUBTEL_CANCELLATION_URL', default=''),

    # IP Whitelist
    'WHITELISTED_IPS': [
        ip.strip() for ip in config('HUBTEL_WHITELISTED_IPS', default='').split(',') if ip.strip()
    ],

    # Payment settings
    'PAYMENT_EXPIRY_MINUTES': 5,
    'MAX_CLIENT_REFERENCE_LENGTH': 32,
    
    # SMS API Settings
    'SMS_CLIENT_ID': config('HUBTEL_SMS_CLIENT_ID', default='hopucxyx'),
    'SMS_CLIENT_SECRET': config('HUBTEL_SMS_CLIENT_SECRET', default='rzqepxui'),
    'SMS_SENDER_ID': config('HUBTEL_SMS_SENDER_ID', default='VECGhana'),
    'SMS_BASE_URL': config('HUBTEL_SMS_BASE_URL', default='https://sms.hubtel.com'),
    'SMS_SINGLE_PATH': '/v1/messages/send',
    'SMS_BATCH_PATH': '/v1/messages/batch/simple/send',
}

# Email Settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=EMAIL_HOST_USER)

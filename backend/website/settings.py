import os
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

BASE_DIR = Path(__file__).resolve().parent.parent
# socksio==1.0.0 add to req
# jebanie sie z static plikami
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = 'static/'

SECRET_KEY = os.environ['I_DRIVE_BACKEND_SECRET_KEY']
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTOCOL', 'https')

is_dev_env = os.getenv('IS_DEV_ENV', 'False') == 'True'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = is_dev_env

ALLOWED_HOSTS = ['*']  # todo

# USE_X_FORWARDED_HOST = True  # todo fix admin

# CSRF_COOKIE_SECURE = True # todo fix
# SESSION_COOKIE_SECURE = True

# Application definition
INSTALLED_APPS = [
    'simple_history',
    'django.contrib.admin',
    'website',
    'mptt',
    'corsheaders',
    'daphne',
    'django_celery_beat',
    'djoser',
    'rest_framework',
    'rest_framework.authtoken',
    'channels',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_user_agents',

]

DJOSER = {
    "LOGIN_FIELD": "username",
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django_user_agents.middleware.UserAgentMiddleware',
    'website.utilities.middlewares.RequestIdMiddleware',
    'website.utilities.middlewares.FailedRequestLoggerMiddleware',
    'website.utilities.middlewares.ApplyRateLimitHeadersMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

CORS_ALLOW_HEADERS = "*"
CORS_ALLOW_PRIVATE_NETWORK = True

CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^http:\/\/localhost:\d+$',
    r'^http:\/\/127.0.0.1:\d+$',
    r'^http:\/\/192.168.1.14:\d+$',
]

CORS_EXPOSE_HEADERS = (
    "retry-after",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset-After",
    "X-RateLimit-Bucket"
)

ROOT_URLCONF = 'website.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        "DIRS": [TEMPLATE_DIR],

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
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{os.environ['I_DRIVE_REDIS_ADDRESS']}",
    }
}
WSGI_APPLICATION = 'website.wsgi.application'

ASGI_APPLICATION = 'website.asgi.application'
# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(os.environ["I_DRIVE_BACKEND_STORAGE_DIR"], 'db.sqlite3'),
        'CONN_MAX_AGE': None

    }
}

# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [

]

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Europe/Warsaw'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

# STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Channels settings


CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(os.environ["I_DRIVE_REDIS_ADDRESS"], os.environ["I_DRIVE_REDIS_PORT"])],

        },
    },
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',

    ],
    'EXCEPTION_HANDLER': 'website.utilities.CustomExceptionHandler.custom_exception_handler',

    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/m',
        'user': '25/5s',
        'media': '1000/m',
        'folder_password': '20/m',
        'password_change': '10/m',
        'search': '60/m',
        'register': '20/h',
        'discord_settings': '2/1s',
        'proxy': '20/s',
        'login': '5/10s'

    },
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
}

# Celery settings
CELERY_BROKER_URL = f"redis://{os.environ['I_DRIVE_REDIS_ADDRESS']}"
CELERY_RESULT_BACKEND = f"redis://{os.environ['I_DRIVE_REDIS_ADDRESS']}"
# use json format for everything
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'


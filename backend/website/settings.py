import ipaddress
import os
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = BASE_DIR / "templates"


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_required(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise RuntimeError(f"{name} is required")

    return value.strip()


IS_DEV_ENV = env_bool("IS_DEV_ENV")
BEHIND_NGINX = env_bool("BEHIND_NGINX")

PROTOCOL = env_required("PROTOCOL")
DEPLOYMENT_HOST = env_required("DEPLOYMENT_HOST")
PUBLIC_ORIGIN = f"{PROTOCOL}://{DEPLOYMENT_HOST}"

SECRET_KEY = env_required("BACKEND_SECRET_KEY")
DEBUG = IS_DEV_ENV

# Static / reverse proxy
if BEHIND_NGINX:
    STATIC_URL = "/api/static/"
    STATIC_ROOT = "/var/www/idrive/backend-static"

    SESSION_COOKIE_PATH = "/api/"
    CSRF_COOKIE_PATH = "/api/"

    FORCE_SCRIPT_NAME = "/api"
    USE_X_FORWARDED_HOST = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
else:
    STATIC_URL = "/static/"
    STATIC_ROOT = BASE_DIR / "staticfiles"
    USE_X_FORWARDED_HOST = False


# Hosts

LAN_CIDR = os.getenv("LAN_CIDR", "192.168.1.0/24")
LAN_HOSTS = [str(ip) for ip in ipaddress.ip_network(LAN_CIDR, strict=False).hosts()]

if IS_DEV_ENV:
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = [
        "localhost",
        "127.0.0.1",
        "::1",
        DEPLOYMENT_HOST,
        *LAN_HOSTS,
    ]

# CORS

CORS_ALLOW_PRIVATE_NETWORK = True
CORS_ALLOWED_ORIGINS = [
    PUBLIC_ORIGIN
]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://localhost:\d+$",
    r"^http://127\.0\.0\.1:\d+$",
    r"^http://192\.168\.1\.\d{1,3}:\d+$",
]

CORS_EXPOSE_HEADERS = (
    "retry-after",
    "X-RateLimit-Remaining",
    "X-RateLimit-Reset-After",
    "X-RateLimit-Bucket",
    "Content-Range",
    "Accept-Ranges",
    "Content-Length"
)

DATA_UPLOAD_MAX_NUMBER_FIELDS = 102400000  # higher than the count of fields

# Application definition
INSTALLED_APPS = [
    'simple_history',
    'django.contrib.admin',
    'website',
    'mptt',
    'corsheaders',
    'daphne',
    'django_celery_beat',
    'rest_framework',
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
    'website.core.http.middlewares.ScriptNamePathMiddleware',
    'simple_history.middleware.HistoryRequestMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.gzip.GZipMiddleware',
    'django_user_agents.middleware.UserAgentMiddleware',
    'website.core.http.middlewares.FailedRequestLoggerMiddleware',
    'website.core.http.middlewares.ApplyRateLimitHeadersMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


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
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{os.environ['REDIS_ADDRESS']}",
        "OPTIONS": {
             "PASSWORD": os.environ['REDIS_PASSWORD'],
             "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}
WSGI_APPLICATION = 'website.wsgi.application'

ASGI_APPLICATION = 'website.asgi.application'
# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.sqlite3',
#         'NAME': os.path.join(os.environ["I_DRIVE_BACKEND_STORAGE_DIR"], 'db.sqlite3'),
#         'CONN_MAX_AGE': None
#
#     }
# }
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["POSTGRES_NAME"],
        "USER": os.environ["POSTGRES_USER"],
        "PASSWORD": os.environ["POSTGRES_PASSWORD"],
        "HOST": os.environ["POSTGRES_ADDRESS"],
        "PORT": os.environ["POSTGRES_PORT"],
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
            "hosts": [f"redis://:{os.environ['REDIS_PASSWORD']}@{os.environ['REDIS_ADDRESS']}:{os.environ['REDIS_PORT']}"],

        },
    },
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'website.auth.PerDeviceTokenAuthentication',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',

    ],
    'EXCEPTION_HANDLER': 'website.core.http.CustomExceptionHandler.custom_exception_handler',

    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/m',
        'user': '60/5s',
        'media': '1000/m',
        'uncached_media': '120/m',
        'media_anon': '500/m',
        'uncached_media_anon': '30/m',
        'folder_password': '20/m',
        'password_change': '10/m',
        'search': '60/m',
        'register': '20/h',
        'discord_settings': '30/m',
        'login': '5/10s'

    },
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
}

# Celery settings
CELERY_BROKER_URL = f"redis://:{os.environ['REDIS_PASSWORD']}@{os.environ['REDIS_ADDRESS']}:{os.environ['REDIS_PORT']}/0"
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
# use json format for everything
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_URL = 'static/'

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ['I_DRIVE_BACKEND_SECRET_KEY']

is_env = os.environ["IS_DEV_ENV"]

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = is_env
SILKY_PYTHON_PROFILER = is_env

#TODO
ALLOWED_HOSTS = ['*']

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'website',
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

]

DJOSER = {
    "LOGIN_FIELD": "username",
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    #'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'website.utilities.middlewares.RequestIdMiddleware',
    'website.utilities.middlewares.ApplyRateLimitHeadersMiddleware',
    #'silk.middleware.SilkyMiddleware',

    #"django.middleware.cache.UpdateCacheMiddleware",
    #"django.middleware.common.CommonMiddleware",
    #"django.middleware.cache.FetchFromCacheMiddleware",

]
CORS_ALLOW_HEADERS = "*"

CORS_ALLOW_PRIVATE_NETWORK = True

prefix = 'http://' if is_env else 'https://'
CORS_ALLOWED_ORIGINS = [
    f'{prefix}{os.environ["I_DRIVE_FRONTEND"]}',
    f'{prefix}{os.environ["I_DRIVE_BACKEND"]}',

    'http://localhost:8080',
    'http://localhost:5173',
]

CORS_EXPOSE_HEADERS = (
    "retry-after",
)

CSRF_TRUSTED_ORIGINS = [
    f'{prefix}{os.environ["I_DRIVE_FRONTEND"]}',
    f'{prefix}{os.environ["I_DRIVE_BACKEND"]}',

    'http://localhost:8080',
    'http://localhost:5173',
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
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{os.environ['I_DRIVE_REDIS']}",
    }
}
WSGI_APPLICATION = 'website.wsgi.application'

ASGI_APPLICATION = 'website.asgi.application'
# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'CONN_MAX_AGE':  None

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

#STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Channels settings
redis_addr = os.environ["I_DRIVE_REDIS"].split(':')[0]
redis_port = os.environ["I_DRIVE_REDIS"].split(':')[1]

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(redis_addr, redis_port)],  # set redis address

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
        'user': '100/5s',
        'media': '1000/m',
        'folder_password': '20/m',
        'password_change': '10/m',
        'search': '200/m'
    },
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
}

# Celery settings
CELERY_BROKER_URL = f"redis://{os.environ['I_DRIVE_REDIS']}"
CELERY_RESULT_BACKEND = f"redis://{os.environ['I_DRIVE_REDIS']}"
# use json format for everything
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'


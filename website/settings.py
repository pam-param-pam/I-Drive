import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-o5m-fk59yjgizf7k6d9mk#*23&_gcc^1nptept@qykzch7zho-'
os.environ[
    "DJANGO_ALLOW_ASYNC_UNSAFE"] = "True"  # is it dumb? Yes, does it work? Well until it breaks something, YES IT DOES!
# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
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
    'website.utilities.middlewares.ApplyRateLimitHeadersMiddleware'
    #'silk.middleware.SilkyMiddleware',

    #"django.middleware.cache.UpdateCacheMiddleware",
    #"django.middleware.common.CommonMiddleware",
    #"django.middleware.cache.FetchFromCacheMiddleware",

]
CORS_ALLOW_HEADERS = "*"

CORS_ALLOW_PRIVATE_NETWORK = True

CORS_ALLOWED_ORIGINS = [
    'http://127.0.0.1:8080',
    'http://127.0.0.1:5173',
    'http://172.24.240.1:5173',
    'http://172.23.16.1:5173',
    'http://192.168.56.1:5173',
    'http://192.168.1.14:5173',
    'http://localhost:8080',
    'http://localhost:5173',
    'https://pamparampam.dev',
    'https://api.pamparampam.dev',
    'https://idrive.pamparampam.dev',

]
CORS_EXPOSE_HEADERS = (
    "retry-after",
)
CSRF_TRUSTED_ORIGINS = [
    'http://127.0.0.1:8080',
    'http://127.0.0.1:5173',
    'http://localhost:8080',
    'http://localhost:5173',
    'https://pamparampam.dev',
    'https://api.pamparampam.dev',
    'https://idrive.pamparampam.dev',
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
        "LOCATION": "redis://127.0.0.1:6379",
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
"""
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',

        'USER': 'secret_user',
        'NAME': "postgres",
        'PASSWORD': 'secret_password',

        'HOST': '127.0.0.1',

        'PORT': '5432',
        'CONN_MAX_AGE': None

    }
}
"""
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

STATIC_URL = 'static/'
#STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Channels settings
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],  # set redis address

        },
    },
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.TokenAuthentication',
    ),
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'EXCEPTION_HANDLER': 'website.utilities.CustomExceptionHandler.custom_exception_handler',

    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/min',
        'user': '100/m',
        'media': '1000/min',
        'folder_password': '20/min',
        'password_change': '10/min',
        'search': '200/m'
    }
}

# Celery settings
CELERY_BROKER_URL = "redis://localhost:6379"
CELERY_RESULT_BACKEND = "redis://localhost:6379"
# use json format for everything
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

SILKY_PYTHON_PROFILER = True

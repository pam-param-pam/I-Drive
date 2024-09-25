import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ['I_DRIVE_STREAMER_SECRET_KEY']

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# jebanie sie z static plikami
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATIC_URL = 'static/'

is_env = os.getenv('IS_DEV_ENV', 'False') == 'True'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = is_env

ALLOWED_HOSTS = ['localhost', '127.0.0.1', os.environ['DEPLOYMENT_HOST'], 'api.pamparampam.dev'] #todo remove api.pamparampam.dev

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    #'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'streamer.urls'

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

WSGI_APPLICATION = 'streamer.wsgi.application'

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{os.environ['I_DRIVE_REDIS_ADDRESS']}",
    }
}

# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join( os.environ["I_DRIVE_STREAMER_STORAGE_DIR"], 'db.sqlite3'),
    }
}

REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],

    'DEFAULT_THROTTLE_RATES': {
        'user': '1000/min',

    }
}
# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [

]
CORS_ALLOW_HEADERS = "*"

CORS_ALLOW_PRIVATE_NETWORK = True

prefix = 'http://' if is_env else 'https://'

CORS_ALLOWED_ORIGINS = [
    f'{prefix}{os.environ["CORS_FRONTEND"]}:{os.environ["CORS_FRONTEND_PORT"]}',
    'http://127.0.0.1:5173', # frontend
]

CSRF_TRUSTED_ORIGINS = [
    f'{prefix}{os.environ["CORS_FRONTEND"]}:{os.environ["CORS_FRONTEND_PORT"]}',
    'http://127.0.0.1:5173',  # frontend
]

# CORS_EXPOSE_HEADERS = (
#     "retry-after",
# )

# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

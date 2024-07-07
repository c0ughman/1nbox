"""
Django settings for _1nbox_ai project.

Generated by 'django-admin startproject' using Django 5.0.1.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.0/ref/settings/
"""
import django-heroku
from pathlib import Path
import os

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

from dotenv import load_dotenv
import os

load_dotenv()

STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-9y#asx20a^uqj@r!k4v#1op2as7u+ssl#=w1wf3(gfp*f7%_h+'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['https://app-1nbox-ai-fb8295a32cce.herokuapp.com/', '127.0.0.1']


# Application definition

INSTALLED_APPS = [
    '_1nbox_ai',
    'rest_framework',
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = '_1nbox_ai.urls'

TEMPLATES = [
    {


        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'myapp/templates')],
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

WSGI_APPLICATION = '_1nbox_ai.wsgi.application'

CORS_ALLOWED_ORIGINS = [
    "https://www.1nbox-ai.com",
    "https://editor.weweb.io",
    # Add other allowed origins as needed
]

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CSRF_TRUSTED_ORIGINS = ['https://app-1nbox-ai-fb8295a32cce.herokuapp.com/',
                        'https://www.1nbox-ai.com',
                        'https://api.stripe.com/v1/webhook_endpoints',
                        'https://a.stripecdn.com',
                        'https://api.stripe.com',
                        'https://atlas.stripe.com',
                        'https://auth.stripe.com',
                        'https://b.stripecdn.com',
                        'https://billing.stripe.com',
                        'https://buy.stripe.com',
                        'https://c.stripecdn.com',
                        'https://checkout.stripe.com',
                        'https://climate.stripe.com',
                        'https://connect.stripe.com',
                        'https://dashboard.stripe.com',
                        'https://express.stripe.com',
                        'https://files.stripe.com',
                        'https://hooks.stripe.com',
                        'https://invoice.stripe.com',
                        'https://invoicedata.stripe.com',
                        'https://js.stripe.com',
                        'https://m.stripe.com',
                        'https://m.stripe.network',
                        'https://manage.stripe.com',
                        'https://pay.stripe.com',
                        'https://payments.stripe.com',
                        'https://q.stripe.com',
                        'https://qr.stripe.com',
                        'https://r.stripe.com',
                        'https://verify.stripe.com',
                        'https://stripe.com',
                        'https://terminal.stripe.com',
                        'https://uploads.stripe.com',
                        'https://editor.weweb.io'
                        ]
